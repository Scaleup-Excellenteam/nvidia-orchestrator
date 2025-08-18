from __future__ import annotations
from typing import Dict, List, Optional, Any
import time, socket
import docker
from docker.models.containers import Container
from docker.errors import NotFound, APIError

from postgres_store import PostgresStore  # <- Postgres only



def _to_nano_cpus(value) -> Optional[int]:
    if value is None:
        return None
    try:
        f = float(value)
        if f > 0:
            return int(f * 1_000_000_000)
    except (TypeError, ValueError):
        pass
    return None


def _normalize_run_resources(resources: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    resources = resources or {}
    out: Dict[str, Any] = {}
    mem = resources.get("mem_limit") or resources.get("memory") or resources.get("memory_limit")
    if mem:
        out["mem_limit"] = mem
    if resources.get("nano_cpus") is not None:
        try:
            n = int(resources["nano_cpus"])
            if n > 0:
                out["nano_cpus"] = n
        except (TypeError, ValueError):
            pass
    else:
        cpu_any = resources.get("cpus") or resources.get("cpu") or resources.get("cpu_limit")
        n = _to_nano_cpus(cpu_any)
        if n:
            out["nano_cpus"] = n
    return {k: v for k, v in out.items() if v is not None}


class ContainerManager:
    LABEL_KEY = "managed-by"

    def __init__(self) -> None:
        self.client = docker.from_env()
        self._store = PostgresStore()  # enabled=False if not reachable

    # --- event helper ---
    def _record_event(self, payload: dict) -> None:
        try:
            if getattr(self, "_store", None) and getattr(self._store, "enabled", False):
                self._store.record_event(payload)
        except Exception:
            pass

    # ---------- helpers ----------
    @staticmethod
    def _normalize_ports(ports: Optional[Dict[str, Optional[int]]]) -> Optional[Dict[str, Optional[int]]]:
        if not ports:
            return None
        fixed: Dict[str, Optional[int]] = {}
        for cport, host_port in ports.items():
            fixed[cport] = None if host_port == 0 else host_port
        return fixed

    def _find_by_label_value(self, value: str) -> List[Container]:
        items = self.client.containers.list(all=True, filters={"label": [self.LABEL_KEY]})
        out: List[Container] = []
        for c in items:
            try:
                labels = c.labels or {}
                if labels.get(self.LABEL_KEY) == value:
                    out.append(c)
            except Exception:
                continue
        return out

    def _get_by_name_or_id(self, name_or_id: str) -> Container:
        try:
            return self.client.containers.get(name_or_id)
        except NotFound:
            for c in self.client.containers.list(all=True):
                if c.name == name_or_id or c.id.startswith(name_or_id):
                    return c
            raise

    def _detect_exposed_ports(self, image: str) -> Dict[str, Optional[int]]:
        try:
            img = self.client.images.get(image)
        except Exception:
            try:
                img = self.client.images.pull(image)
            except Exception:
                return {}
        try:
            cfg = (img.attrs.get("Config") or {}) or (img.attrs.get("ContainerConfig") or {})
            exposed = cfg.get("ExposedPorts") or {}
            if not isinstance(exposed, dict):
                return {}
            return {k: None for k in exposed.keys()}
        except Exception:
            return {}

    @staticmethod
    def _fmt_mem_bytes(val: Optional[int]) -> Optional[str]:
        if not val or val <= 0:
            return None
        g = 1024**3
        m = 1024**2
        if val % g == 0:
            return f"{val // g}g"
        return f"{val // m}m"

    @staticmethod
    def _cpu_limit_from_hostconfig(hc: Dict[str, Any]) -> Optional[str]:
        nano = hc.get("NanoCpus") or 0
        if isinstance(nano, int) and nano > 0:
            return f"{nano / 1e9:.2f}".rstrip('0').rstrip('.')
        quota = hc.get("CpuQuota") or 0
        period = hc.get("CpuPeriod") or 100000
        if quota and period:
            return f"{quota / period:.2f}".rstrip('0').rstrip('.')
        return None

    @staticmethod
    def _summarize_container(c: Container) -> Dict[str, Any]:
        c.reload()
        attrs = c.attrs or {}
        net = attrs.get("NetworkSettings", {}) or {}
        ports_raw = net.get("Ports", {}) or {}
        host_ports: Dict[str, Optional[int]] = {}
        for cport, bindings in ports_raw.items():
            if bindings and isinstance(bindings, list) and bindings[0].get("HostPort"):
                try:
                    host_ports[cport] = int(bindings[0]["HostPort"])
                except Exception:
                    host_ports[cport] = None
            else:
                host_ports[cport] = None
        try:
            image_tag = c.image.tags[0] if getattr(c.image, "tags", None) else c.image.short_id
        except Exception:
            image_tag = None
        hc = attrs.get("HostConfig", {}) or {}
        res = {
            "cpu_limit": ContainerManager._cpu_limit_from_hostconfig(hc),
            "memory_limit": ContainerManager._fmt_mem_bytes(hc.get("Memory")),
            "disk_limit": None,
        }
        return {
            "container_id": c.id,
            "status": c.status,
            "ports": ports_raw,
            "id": c.id,
            "name": c.name,
            "state": c.status,
            "image": image_tag,
            "created_at": attrs.get("Created", "") or "",
            "host_ports": host_ports,
            "resources": {k: v for k, v in res.items() if v is not None},
        }

    def _run_new_container(
        self,
        image: str,
        *,
        env: Optional[Dict[str, str]] = None,
        ports: Optional[Dict[str, Optional[int]]] = None,
        resources: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        port_map = self._normalize_ports(ports)
        if not port_map:
            port_map = self._detect_exposed_ports(image)
        run_kwargs = _normalize_run_resources(resources)
        container = self.client.containers.run(
            image=image,
            detach=True,
            environment=env or None,
            ports=port_map or None,
            labels={self.LABEL_KEY: image},
            restart_policy={"Name": "unless-stopped"},
            **run_kwargs,
        )
        time.sleep(0.2)
        summary = self._summarize_container(container)
        self._record_event({
            "image": image,
            "container_id": summary["id"],
            "name": summary.get("name"),
            "host": socket.gethostname(),
            "ports": summary.get("ports", {}),
            "status": "running",
            "event": "create",
        })
        return summary

    # -------- public API --------

    def ensure_singleton_for_image(
        self,
        image: str,
        *,
        env: Optional[Dict[str, str]] = None,
        ports: Optional[Dict[str, Optional[int]]] = None,
        resources: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        existing = self._find_by_label_value(image)
        if existing:
            pref = next((c for c in existing if c.status == "running"), existing[0])
            return self._summarize_container(pref)
        return self._run_new_container(image, env=env, ports=ports, resources=resources)

    def create_container(
        self,
        image: str,
        *,
        env: Optional[Dict[str, str]] = None,
        ports: Optional[Dict[str, Optional[int]]] = None,
        resources: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._run_new_container(image, env=env, ports=ports, resources=resources)

    def list_managed_containers(self) -> List[Dict[str, Any]]:
        items = self.client.containers.list(all=True, filters={"label": [self.LABEL_KEY]})
        return [self._summarize_container(c) for c in items]

    def list_instances_for_image(self, image: str) -> List[Dict[str, Any]]:
        return [self._summarize_container(c) for c in self._find_by_label_value(image)]

    def delete_container(self, name_or_id: str, *, force: bool = False) -> Dict[str, Any]:
        try:
            c = self._get_by_name_or_id(name_or_id)
            c.remove(force=force)
            self._record_event({
                "image": c.labels.get(self.LABEL_KEY, ""),
                "container_id": c.id,
                "name": c.name,
                "host": socket.gethostname(),
                "status": "removed",
                "event": "remove",
            })
            return {"ok": True}
        except NotFound:
            return {"ok": False, "error": "not-found", "id": name_or_id}
        except APIError as e:
            return {"ok": False, "error": str(e)}

    def stop_container(self, name_or_id: str, timeout: int = 10) -> Dict[str, Any]:
        try:
            c = self._get_by_name_or_id(name_or_id)
            c.stop(timeout=timeout)
            self._record_event({
                "image": c.labels.get(self.LABEL_KEY, ""),
                "container_id": c.id,
                "name": c.name,
                "host": socket.gethostname(),
                "status": "stopped",
                "event": "stop",
            })
            return {"ok": True}
        except NotFound:
            return {"ok": False, "error": "not-found", "id": name_or_id}
        except APIError as e:
            return {"ok": False, "error": str(e)}

    def start_container(self, name_or_id: str) -> Dict[str, Any]:
        try:
            c = self._get_by_name_or_id(name_or_id)
            c.start()
            self._record_event({
                "image": c.labels.get(self.LABEL_KEY, ""),
                "container_id": c.id,
                "name": c.name,
                "host": socket.gethostname(),
                "status": "running",
                "event": "start",
            })
            return {"ok": True}
        except NotFound:
            return {"ok": False, "error": "not-found", "id": name_or_id}
        except APIError as e:
            return {"ok": False, "error": str(e)}

    def container_stats(self, name_or_id: str) -> Dict[str, Any]:
        try:
            c = self._get_by_name_or_id(name_or_id)
            s = c.stats(stream=False)
            return {"ok": True, "container": c, "stats": s}
        except NotFound:
            return {"ok": False, "error": "not-found", "id": name_or_id}
        except APIError as e:
            return {"ok": False, "error": str(e)}

    def update_resources_for_image(
        self,
        image: str,
        *,
        cpu_limit: Optional[str] = None,
        memory_limit: Optional[str] = None
    ) -> List[str]:
        updated: List[str] = []
        for c in self._find_by_label_value(image):
            params: Dict[str, Any] = {}
            if memory_limit:
                params["mem_limit"] = memory_limit
            if cpu_limit is not None:
                n = _to_nano_cpus(cpu_limit)
                if n:
                    params["nano_cpus"] = n
            if params:
                try:
                    c.update(**params)
                    updated.append(c.id)
                except Exception:
                    continue
        return updated
