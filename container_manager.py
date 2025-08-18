# container_manager.py
"""
ContainerManager: thin wrapper around docker-py tailored for Team 3 UI contract.

Key ideas:
- We tag each created container with LABEL_KEY = "managed-by" and set its value
  to the imageId (i.e., the image tag string). This allows grouping containers
  ("instances") by imageId using a simple label filter.
- Summaries include fields that are friendly for a UI: id, name, state, image,
  created_at, host_ports (flattened host port mapping), and optional "resources"
  (cpu_limit/memory_limit/disk_limit best-effort from inspect).
- Minimal and backward-compatible: no breaking changes to public method names.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
import time
import docker
from docker.models.containers import Container
from docker.errors import NotFound, APIError


def _to_nano_cpus(value) -> Optional[int]:
    """
    Convert fractional CPUs (e.g., 0.25 / "0.25") to nano_cpus int for Docker SDK.
    Returns None if value is missing or unparsable or <= 0.
    """
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
    """
    Normalize arbitrary resource hints into Docker SDK-supported kwargs for run().

    Accepts:
      - "mem_limit" / "memory" / "memory_limit"   -> mem_limit
      - "nano_cpus" (int)                          -> nano_cpus
      - "cpus" / "cpu" / "cpu_limit" (float/str)  -> nano_cpus (converted)

    Drops unknown keys and None values.
    """
    resources = resources or {}
    out: Dict[str, Any] = {}

    # memory
    mem = resources.get("mem_limit") or resources.get("memory") or resources.get("memory_limit")
    if mem:
        out["mem_limit"] = mem

    # cpu
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

    # cleanup
    return {k: v for k, v in out.items() if v is not None}


class ContainerManager:
    """
    Manage Docker containers in a UI-friendly way while keeping existing behavior.

    Labeling strategy
    -----------------
    - LABEL_KEY = "managed-by"
    - For each created container, we set labels = {LABEL_KEY: imageId}, where
      imageId is the requested image tag (e.g., "nginx:alpine").
    - This lets the UI query "instances" of a given image via a single label
      filter and keeps different images isolated from each other.

    Summary shape (returned by _summarize_container)
    ------------------------------------------------
    {
      "container_id": str,      # legacy
      "status": str,            # legacy (docker status)
      "ports": Dict,            # legacy (raw NetworkSettings->Ports)
      "id": str,
      "name": str,
      "state": str,             # docker status
      "image": str | None,      # best-effort tag
      "created_at": str,
      "host_ports": { "80/tcp": 52341, ... }  # flattened, int or None
      "resources": {            # optional, only if values exist
        "cpu_limit": str,       # e.g. "0.5"
        "memory_limit": str,    # e.g. "256m"
        "disk_limit": str       # None (not available via Docker inspect/stats)
      }
    }
    """

    LABEL_KEY = "managed-by"   # keep as before

    def __init__(self) -> None:
        """Initialize a Docker client from the environment."""
        self.client = docker.from_env()

    # ---------- helpers ----------

    @staticmethod
    def _normalize_ports(ports: Optional[Dict[str, Optional[int]]]) -> Optional[Dict[str, Optional[int]]]:
        """
        Normalize UI-provided ports mapping for docker-py.

        docker-py uses None to request a random host port. Many UIs prefer 0.
        This function converts 0 -> None and returns None if ports is falsy.

        Args:
            ports: Mapping like {"80/tcp": 0} or {"80/tcp": 8080}

        Returns:
            A mapping with 0 converted to None, or None if input is falsy.
        """
        if not ports:
            return None
        fixed: Dict[str, Optional[int]] = {}
        for cport, host_port in ports.items():
            fixed[cport] = None if host_port == 0 else host_port
        return fixed

    def _find_by_label_value(self, value: str) -> List[Container]:
        """
        Find all containers whose LABEL_KEY equals the given value.

        Args:
            value: Label value to match (we use the imageId/tag string)

        Returns:
            List of docker Container objects.
        """
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
        """
        Resolve a container by full/partial ID or by name.

        Strategy:
        1) Try docker's direct get (id or full name).
        2) If NotFound, scan all and match by exact name or id prefix.

        Raises:
            docker.errors.NotFound if no match is found.
        """
        try:
            return self.client.containers.get(name_or_id)
        except NotFound:
            for c in self.client.containers.list(all=True):
                if c.name == name_or_id or c.id.startswith(name_or_id):
                    return c
            raise

    def _detect_exposed_ports(self, image: str) -> Dict[str, Optional[int]]:
        """
        Best-effort detection of a Docker image's exposed ports.

        If no ports mapping was provided by the caller, we:
        - ensure the image exists locally (pull if missing),
        - read Config.ExposedPorts or ContainerConfig.ExposedPorts,
        - publish each exposed port to a random host port (None).

        Returns:
            Mapping like {"80/tcp": None}. Empty dict on failure.
        """
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
        """
        Convert a memory byte value (from HostConfig.Memory) to a human-ish string.

        Examples:
            268435456 -> "256m"
            1073741824 -> "1g"

        Returns:
            "Xm" / "Xg", or None if value is missing or <= 0.
        """
        if not val or val <= 0:
            return None
        g = 1024**3
        m = 1024**2
        if val % g == 0:
            return f"{val // g}g"
        return f"{val // m}m"

    @staticmethod
    def _cpu_limit_from_hostconfig(hc: Dict[str, Any]) -> Optional[str]:
        """
        Derive a CPU limit string from HostConfig.

        Priority:
            1) NanoCpus (int, Docker 1.13+): value / 1e9 -> "0.50"
            2) CpuQuota/CpuPeriod -> quota/period -> "0.50"

        Returns:
            CPU count as a compact string (e.g., "0.5"), or None if unknown.
        """
        nano = hc.get("NanoCpus") or 0
        if isinstance(nano, int) and nano > 0:
            return f"{nano / 1e9:.2f}".rstrip('0').rstrip('.')
        quota = hc.get("CpuQuota") or 0
        period = hc.get("CpuPeriod") or 100000
        if quota and period:
            return f"{quota / period:.2f}".rstrip('0').rstrip('.')
        return None

    @staticmethod
    def _status_running_or_stopped(status: str) -> str:
        """
        Map Docker status to Team 3's simplified "running"/"stopped".
        """
        return "running" if status == "running" else "stopped"

    @staticmethod
    def _summarize_container(c: Container) -> Dict[str, Any]:
        """
        Build a UI-friendly summary for a container.

        Includes legacy fields ("container_id", "status", "ports") for backward
        compatibility and adds flattened ports and resource hints.

        Args:
            c: docker Container

        Returns:
            Dict with the structure documented in the class docstring.
        """
        c.reload()
        attrs = c.attrs or {}
        net = attrs.get("NetworkSettings", {}) or {}
        ports_raw = net.get("Ports", {}) or {}

        # Flatten host ports (e.g., {"80/tcp":[{"HostPort":"52341"}]} -> {"80/tcp":52341})
        host_ports: Dict[str, Optional[int]] = {}
        for cport, bindings in ports_raw.items():
            if bindings and isinstance(bindings, list) and bindings[0].get("HostPort"):
                try:
                    host_ports[cport] = int(bindings[0]["HostPort"])
                except Exception:
                    host_ports[cport] = None
            else:
                host_ports[cport] = None

        # Best-effort image tag
        try:
            image_tag = c.image.tags[0] if getattr(c.image, "tags", None) else c.image.short_id
        except Exception:
            image_tag = None

        hc = attrs.get("HostConfig", {}) or {}
        res = {
            "cpu_limit": ContainerManager._cpu_limit_from_hostconfig(hc),
            "memory_limit": ContainerManager._fmt_mem_bytes(hc.get("Memory")),
            "disk_limit": None,  # not readily available from Docker APIs
        }

        return {
            "container_id": c.id,          # legacy
            "status": c.status,            # legacy
            "ports": ports_raw,            # legacy
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
        """
        Create and start a new managed container for the given image.

        Notes:
        - Applies label {LABEL_KEY: image} so the instance is grouped under its imageId.
        - If ports are not provided, attempts to auto-detect image ExposedPorts and
          publish them to random host ports.
        - Resources:
            * mem_limit: supports "256m", "1g", etc.
            * cpu_limit/cpus/cpu: converted to nano_cpus for Docker SDK.
        """
        port_map = self._normalize_ports(ports)
        if not port_map:
            # auto-detect exposed ports and publish to random host ports
            port_map = self._detect_exposed_ports(image)

        run_kwargs = _normalize_run_resources(resources)

        container = self.client.containers.run(
            image=image,
            detach=True,
            environment=env or None,
            ports=port_map or None,
            labels={self.LABEL_KEY: image},
            restart_policy={"Name": "unless-stopped"},
            **run_kwargs,  # only valid keys (e.g., mem_limit, nano_cpus)
        )
        # brief pause to let Docker populate NetworkSettings/Ports
        time.sleep(0.2)
        return self._summarize_container(container)

    # -------- public API (kept names) --------

    def ensure_singleton_for_image(
        self,
        image: str,
        *,
        env: Optional[Dict[str, str]] = None,
        ports: Optional[Dict[str, Optional[int]]] = None,
        resources: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ensure exactly one managed instance exists for a given imageId.

        If an instance with label (LABEL_KEY=image) exists:
            - Prefer a running container and return its summary.
        Else:
            - Create a new instance and return its summary.
        """
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
        """
        Always create a new managed instance for the given imageId (no singleton check).

        Returns:
            UI-friendly summary of the new instance.
        """
        return self._run_new_container(image, env=env, ports=ports, resources=resources)

    def list_managed_containers(self) -> List[Dict[str, Any]]:
        """
        List all containers managed by this orchestrator (i.e., having LABEL_KEY).
        """
        items = self.client.containers.list(all=True, filters={"label": [self.LABEL_KEY]})
        return [self._summarize_container(c) for c in items]

    def list_instances_for_image(self, image: str) -> List[Dict[str, Any]]:
        """
        List all managed instances that belong to a specific imageId.

        Args:
            image: imageId/tag used as LABEL_KEY value when the instance was created
        """
        return [self._summarize_container(c) for c in self._find_by_label_value(image)]

    def delete_container(self, name_or_id: str, *, force: bool = False) -> Dict[str, Any]:
        """
        Delete a container by name or ID.

        Returns:
            {"ok": True} on success,
            {"ok": False, "error": "not-found", "id": "..."} if missing,
            {"ok": False, "error": "..."} on other Docker API errors.
        """
        try:
            c = self._get_by_name_or_id(name_or_id)
            c.remove(force=force)
            return {"ok": True}
        except NotFound:
            return {"ok": False, "error": "not-found", "id": name_or_id}
        except APIError as e:
            return {"ok": False, "error": str(e)}

    def stop_container(self, name_or_id: str, timeout: int = 10) -> Dict[str, Any]:
        """
        Stop a running container by name or ID.

        Args:
            timeout: seconds to wait for a graceful stop before SIGKILL.

        Returns:
            {"ok": True} on success, otherwise same error structure as delete_container.
        """
        try:
            c = self._get_by_name_or_id(name_or_id)
            c.stop(timeout=timeout)
            return {"ok": True}
        except NotFound:
            return {"ok": False, "error": "not-found", "id": name_or_id}
        except APIError as e:
            return {"ok": False, "error": str(e)}

    def start_container(self, name_or_id: str) -> Dict[str, Any]:
        """
        Start a container by name or ID.

        Returns:
            {"ok": True} on success, otherwise same error structure as delete_container.
        """
        try:
            c = self._get_by_name_or_id(name_or_id)
            c.start()
            return {"ok": True}
        except NotFound:
            return {"ok": False, "error": "not-found", "id": name_or_id}
        except APIError as e:
            return {"ok": False, "error": str(e)}

    def container_stats(self, name_or_id: str) -> Dict[str, Any]:
        """
        Fetch one-shot docker stats for a container (no streaming).

        Returns:
            {"ok": True, "container": <Container>, "stats": <dict>} on success,
            {"ok": False, "error": "..."} otherwise.
        """
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
        """
        Update CPU and/or memory limits for all instances of a given imageId.

        Args:
            image:        imageId/tag that groups instances (LABEL_KEY value).
            cpu_limit:    e.g., "0.5" (sets NanoCpus). Float or string accepted.
            memory_limit: e.g., "256m".

        Returns:
            List of instance IDs that were successfully updated.
        """
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


### this data for the billing .

def _format_bytes(size: int) -> str:
    """Convert bytes to human-readable string (GB/MB/KB)."""
    if size is None:
        return "0B"
    # use 1024-based units
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"

def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """Return a one-shot 'docker stats' summary for billing, human-readable."""
        try:
            c = self.client.containers.get(container_id)
            s = c.stats(stream=False)

            # ---- CPU % (כפי ש-docker מחשב) ----
            cpu_total = s.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
            cpu_prev  = s.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
            sys_total = s.get("cpu_stats", {}).get("system_cpu_usage", 0) or 0
            sys_prev  = s.get("precpu_stats", {}).get("system_cpu_usage", 0) or 0
            cpu_delta = cpu_total - cpu_prev
            sys_delta = sys_total - sys_prev
            online = s.get("cpu_stats", {}).get("online_cpus")
            if not online:
                per_cpu = s.get("cpu_stats", {}).get("cpu_usage", {}).get("percpu_usage", []) or []
                online = max(1, len(per_cpu))
            cpu_percent = 0.0
            if cpu_delta > 0 and sys_delta > 0:
                cpu_percent = (cpu_delta / sys_delta) * online * 100.0

            # ---- Memory ----
            mem_usage_bytes = int(s.get("memory_stats", {}).get("usage", 0) or 0)
            mem_limit_bytes = int(s.get("memory_stats", {}).get("limit", 0) or 0)
            mem_usage_hr = _format_bytes(mem_usage_bytes)
            mem_limit_hr = _format_bytes(mem_limit_bytes)

            # ---- Network I/O (sum של כל הממשקים) ----
            networks = s.get("networks", {}) or {}
            rx_bytes = sum(int(v.get("rx_bytes", 0) or 0) for v in networks.values()) if isinstance(networks, dict) else 0
            tx_bytes = sum(int(v.get("tx_bytes", 0) or 0) for v in networks.values()) if isinstance(networks, dict) else 0
            net_io_hr = f"{_format_bytes(rx_bytes)} / {_format_bytes(tx_bytes)}"

            # ---- Block I/O ----
            blk = s.get("blkio_stats", {}) or {}
            io_rec = blk.get("io_service_bytes_recursive") or []
            read_bytes  = sum(int(x.get("value", 0) or 0) for x in io_rec if (x.get("op", "") or "").lower() == "read")
            write_bytes = sum(int(x.get("value", 0) or 0) for x in io_rec if (x.get("op", "") or "").lower() == "write")
            block_io_hr = f"{_format_bytes(read_bytes)} / {_format_bytes(write_bytes)}"

            # ---- PIDs ----
            pids = int(s.get("pids_stats", {}).get("current", 0) or 0)

            return {
                "id": c.id,
                "name": c.name,
                "cpu_percent": round(cpu_percent, 2),
                "mem_usage": mem_usage_hr,     
                "mem_limit": mem_limit_hr,    
                "net_io": net_io_hr,           
                "block_io": block_io_hr,       
                "pids": pids,
            }
        except NotFound:
            raise
        except APIError:
            raise