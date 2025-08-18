"""
ContainerManager: a thin orchestration wrapper around the Docker SDK.

- Keeps a minimal desired-state store per image (min/max/env/ports/resources).
- Ensures there is at least one managed container per image on demand.
- Uses Docker labels to rediscover containers even after process restarts.

New in this version:
- reconcile(image): naive scaler to meet desired min/max
- scale(image, min_replicas, max_replicas): persist + reconcile
- container_stats(name_or_id): best-effort CPU/mem/fs + liveness
- get_containers_for_image(image): summaries for one image
- set_container_status(name_or_id, "running"|"stopped"): start/stop + notify
- Optional service-discovery callback (env.DISCOVERY_CALLBACK)
"""
from typing import Dict, List, Optional, Any
import time
import shutil
import socket
import docker
import requests


class ContainerManager:
    """
    Encapsulates all Docker interactions so the FastAPI layer stays thin
    and focused on HTTP/Pydantic only.
    """

    LABEL_KEY = "orchestrator.image"  # every managed container gets this label

    def __init__(
        self,
        client: Optional[docker.DockerClient] = None,
        client_factory=None,
    ) -> None:
        # Do NOT talk to Docker during import; connect only when first needed.
        self._client: Optional[docker.DockerClient] = client
        self._client_factory = client_factory or docker.from_env

        # Super-simple desired-state store (swap to DB later if needed).
        self.desired_images: Dict[str, Dict[str, Any]] = {}  # image -> config dict
        # Optional bookkeeping (we mostly rely on labels for rediscovery).
        self._tracked: Dict[str, List[str]] = {}

    # ---------- internals ----------

    def _cli(self) -> docker.DockerClient:
        """Get (or lazily create) the Docker client."""
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _discovery_callback_url(self, image: str) -> Optional[str]:
        return (self.desired_images.get(image) or {}).get("env", {}).get("DISCOVERY_CALLBACK")

    def _notify_discovery(self, *, image: str, c, status: str, event: str) -> None:
        """
        Optional best-effort callback for Service Discovery / LB demos.
        Payload: {image, container_id, name, host, ports, status, event}
        """
        url = self._discovery_callback_url(image)
        if not url:
            return
        try:
            host = socket.gethostname()
            payload = {
                "image": image,
                "container_id": c.id,
                "name": c.name,
                "host": host,
                "ports": (c.attrs.get("NetworkSettings", {}) or {}).get("Ports", {}),
                "status": status,
                "event": event,
            }
            requests.post(url, json=payload, timeout=2)
        except Exception:
            # demo-only, ignore failures
            pass

    # ---------- desired state ----------

    def register_desired_state(
        self,
        image: str,
        *,
        min_replicas: int,
        max_replicas: int,
        env: Dict[str, str],
        ports: Dict[str, int],
        resources: Dict[str, Any],
    ) -> None:
        """
        Save/refresh what's desired for a given image so other modules can query it
        or so you can implement /scale next.
        """
        self.desired_images[image] = {
            "image": image,
            "min_replicas": min_replicas,
            "max_replicas": max_replicas,
            "env": env or {},
            "ports": ports or {},
            "resources": resources or {},  # {"cpu":"0.5","memory":"512m","status":"running"}
        }
        self._tracked.setdefault(image, [])

    # ---------- queries & helpers ----------

    def _current_for_image(self, image: str, running_only: bool = False):
        """
        Find existing containers for this image by label.
        running_only=False -> include stopped/exited (all=True)
        running_only=True  -> only running
        """
        cli = self._cli()
        flt = {"label": f"{self.LABEL_KEY}={image}"}
        if running_only:
            return cli.containers.list(filters=flt)
        return cli.containers.list(all=True, filters=flt)

    @staticmethod
    def _normalize_ports(ports: Dict[str, int]) -> Optional[Dict[str, Optional[int]]]:
        """
        Convert {"5678/tcp": 0} -> {"5678/tcp": None} so Docker allocates a free host port.
        Return None if ports is empty (no -p).
        """
        if not ports:
            return None
        out: Dict[str, Optional[int]] = {}
        for cport, hport in ports.items():
            out[cport] = None if (hport is None or hport == 0) else hport
        return out

    @staticmethod
    def _summarize_container(c) -> Dict[str, Any]:
        """
        Produce a response-friendly dict about the container (id/name/status/port bindings).
        """
        c.reload()
        return {
            "container_id": c.id,
            "name": c.name,
            "status": c.status,
            # Host port bindings live under NetworkSettings->Ports
            "ports": (c.attrs.get("NetworkSettings", {}) or {}).get("Ports", {}),
        }

    @staticmethod
    def _cpu_to_nano_cpus(cpu_value: Any) -> Optional[int]:
        """
        Translate a user CPU value to Docker's nano_cpus (int).
        Accepts strings like "0.5", "1", "0", or Kubernetes-like "500m".
        """
        if cpu_value is None:
            return None
        try:
            s = str(cpu_value).strip().lower()
            if s.endswith("m"):              # e.g., "500m" => 0.5
                milli = float(s[:-1])
                v = milli / 1000.0
            else:
                v = float(s)
            return int(v * 1_000_000_000) if v > 0 else None
        except Exception:
            return None

    @staticmethod
    def _ports_ready(c, expect_keys: Optional[List[str]] = None) -> bool:
        ports = (c.attrs.get("NetworkSettings", {}) or {}).get("Ports") or {}
        if not ports:
            return False
        if expect_keys:
            for k in expect_keys:
                v = ports.get(k)
                if not isinstance(v, list) or len(v) == 0:
                    return False
            return True
        # no explicit expectation -> at least one non-empty binding
        return any(isinstance(v, list) and len(v) > 0 for v in ports.values())

    def _wait_for_ports(self, c, expect_keys: Optional[List[str]], timeout: float = 5.0, interval: float = 0.1):
        """
        Reload until host-port bindings appear (needed on Desktop/macOS right after run/start).
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            c.reload()
            if self._ports_ready(c, expect_keys):
                return
            time.sleep(interval)
        # best effort; return regardless

    # ---------- core action ----------

    def _run_new_container(
        self,
        image: str,
        *,
        env: Dict[str, str],
        ports: Dict[str, int],
        resources: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Always create a new managed container for `image`."""
        cli = self._cli()
        desired_status = (resources or {}).get("status", "running")
        expect_keys = list((ports or {}).keys()) or None

        try:
            cli.images.pull(image)
        except Exception:
            pass  # fine if already local/offline

        mem_limit = (resources or {}).get("memory")
        nano_cpus = self._cpu_to_nano_cpus((resources or {}).get("cpu"))
        port_map = self._normalize_ports(ports)

        try:
            c = cli.containers.run(
                image,
                detach=True,
                environment=env or None,
                ports=port_map,
                labels={self.LABEL_KEY: image},
                mem_limit=mem_limit,
                nano_cpus=nano_cpus,
                restart_policy={"Name": "unless-stopped"},
            )
            self._tracked.setdefault(image, []).append(c.id)

            if expect_keys:
                self._wait_for_ports(c, expect_keys)

            if desired_status == "stopped":
                c.stop()
                self._notify_discovery(image=image, c=c, status="stopped", event="create")
            else:
                self._notify_discovery(image=image, c=c, status="running", event="create")

            return {"ok": True, "action": "created", "image": image, **self._summarize_container(c)}
        except Exception as e:
            return {"ok": False, "error": f"Failed to run container: {e}"}

    def ensure_singleton_for_image(
        self,
        image: str,
        *,
        env: Dict[str, str],
        ports: Dict[str, int],
        resources: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Ensure there is at least one managed container for `image`.
        (Used by Stage 1 endpoint; reconciler uses _run_new_container for replicas.)
        """
        cli = self._cli()
        existing = self._current_for_image(image, running_only=False)
        desired_status = (resources or {}).get("status", "running")
        expect_keys = list((ports or {}).keys()) or None

        if existing:
            c = existing[0]
            if desired_status == "running" and c.status != "running":
                c.start()
                if expect_keys:
                    self._wait_for_ports(c, expect_keys)
                self._notify_discovery(image=image, c=c, status="running", event="start")
            elif desired_status == "stopped" and c.status == "running":
                c.stop()
                self._notify_discovery(image=image, c=c, status="stopped", event="stop")
            return {
                "ok": True,
                "action": "kept-existing",
                "image": image,
                **self._summarize_container(c),
            }

        # No container exists yet -> create one
        return self._run_new_container(image, env=env, ports=ports, resources=resources)

    # ---------- utility endpoints ----------

    def list_managed_containers(self) -> List[Dict[str, Any]]:
        """Return a summary of all containers bearing the orchestrator label (any image)."""
        cli = self._cli()
        result: List[Dict[str, Any]] = []
        all_containers = cli.containers.list(all=True, filters={"label": self.LABEL_KEY})
        for c in all_containers:
            result.append(self._summarize_container(c))
        return result

    def get_containers_for_image(self, image: str) -> List[Dict[str, Any]]:
        """Summaries of all managed containers for a specific image."""
        return [self._summarize_container(c) for c in self._current_for_image(image, running_only=False)]

    def delete_container(self, name_or_id: str, *, force: bool = False) -> dict:
        """
        Remove a container by name or ID. Returns {"deleted": True/False, ...}.
        If the container is running and force=False, Docker will raise an error.
        """
        cli = self._cli()
        try:
            c = cli.containers.get(name_or_id)  # accepts name or id
        except Exception:
            return {"deleted": False, "error": "not-found"}

        try:
            if c.status == "running" and not force:
                c.stop(timeout=5)
                self._notify_discovery(image=c.labels.get(self.LABEL_KEY, ""), c=c, status="stopped", event="stop")
            c.remove(force=force)
            return {"deleted": True, "container_id": c.id, "name": c.name}
        except Exception as e:
            return {"deleted": False, "error": str(e)}

    # ---------- reconcile / scale ----------

    def scale(self, image: str, *, min_replicas: int, max_replicas: int) -> Dict[str, Any]:
        """
        Persist scale intent and immediately reconcile once.
        """
        cfg = self.desired_images.get(image, {"image": image, "env": {}, "ports": {}, "resources": {}})
        cfg.update({"min_replicas": min_replicas, "max_replicas": max_replicas})
        self.desired_images[image] = cfg
        return self.reconcile(image)

    def reconcile(self, image: str) -> Dict[str, Any]:
        """
        Bring the number of RUNNING containers within [min, max] (naive).
        Start new containers up to min. If above max, stop/remove oldest first (FIFO).
        """
        cfg = self.desired_images.get(image)
        if not cfg:
            # default minimal config if not registered yet
            cfg = {"image": image, "min_replicas": 1, "max_replicas": 1, "env": {}, "ports": {}, "resources": {"status": "running"}}
            self.desired_images[image] = cfg

        env = cfg.get("env", {})
        ports = cfg.get("ports", {})
        resources = cfg.get("resources", {})
        min_r = int(cfg.get("min_replicas", 1))
        max_r = int(cfg.get("max_replicas", max(1, min_r)))

        running = self._current_for_image(image, running_only=True)
        n_running = len(running)
        actions: List[Dict[str, Any]] = []

        # Scale up to min
        if n_running < min_r:
            to_add = min_r - n_running
            for _ in range(to_add):
                res = self._run_new_container(image, env=env, ports=ports, resources=resources)
                actions.append({"action": "create", "ok": res.get("ok", False), "details": res})

        # Scale down to max
        if n_running > max_r:
            extra = n_running - max_r
            # Oldest first (FIFO): sort by creation time ascending, remove first `extra`
            running_sorted = sorted(running, key=lambda c: c.attrs.get("Created", ""))
            for c in running_sorted[:extra]:
                try:
                    c.stop(timeout=5)
                    self._notify_discovery(image=image, c=c, status="stopped", event="stop")
                except Exception:
                    pass
                try:
                    c.remove()
                except Exception:
                    pass
                actions.append({"action": "remove", "container_id": c.id, "name": c.name})

        current = self.get_containers_for_image(image)
        return {"ok": True, "image": image, "desired": {"min_replicas": min_r, "max_replicas": max_r}, "actions": actions, "current": current}

    # ---------- health / stats ----------

    def container_stats(self, name_or_id: str) -> Dict[str, Any]:
        """
        Best-effort docker stats for one container + host FS free bytes.
        Returns keys: status, server_alive, cpu_percent?, mem_usage?, mem_limit?, mem_percent?, fs_free_bytes?
        """
        cli = self._cli()
        try:
            c = cli.containers.get(name_or_id)
        except Exception:
            return {"ok": False, "error": "not-found"}

        status = c.status
        server_alive = status == "running"
        cpu_percent = None
        mem_usage = None
        mem_limit = None
        mem_percent = None

        try:
            st = c.stats(stream=False)
            # CPU%
            cpu = st.get("cpu_stats", {})
            precpu = st.get("precpu_stats", {})
            cpu_total = (cpu.get("cpu_usage", {}) or {}).get("total_usage", 0) - (precpu.get("cpu_usage", {}) or {}).get("total_usage", 0)
            sys_total = cpu.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
            num_cpus = len((cpu.get("cpu_usage", {}) or {}).get("percpu_usage") or []) or 1
            if sys_total > 0 and cpu_total >= 0:
                cpu_percent = (cpu_total / sys_total) * num_cpus * 100.0

            # Memory
            mem = st.get("memory_stats", {}) or {}
            mem_usage = mem.get("usage")
            mem_limit = mem.get("limit")
            if mem_usage is not None and mem_limit:
                mem_percent = (mem_usage / float(mem_limit)) * 100.0
        except Exception:
            # missing permissions or platform differences
            pass

        fs_free = None
        try:
            fs_free = shutil.disk_usage("/").free
        except Exception:
            pass

        return {
            "ok": True,
            "status": status,
            "server_alive": server_alive,
            "cpu_percent": cpu_percent,
            "mem_usage": mem_usage,
            "mem_limit": mem_limit,
            "mem_percent": mem_percent,
            "fs_free_bytes": fs_free,
        }

    def set_container_status(self, name_or_id: str, *, status: str) -> Dict[str, Any]:
        """
        Start/stop a specific managed container. status in {"running","stopped"}.
        """
        cli = self._cli()
        try:
            c = cli.containers.get(name_or_id)
        except Exception:
            return {"ok": False, "error": "not-found"}

        image = c.labels.get(self.LABEL_KEY, "")
        expect_keys = list(((self.desired_images.get(image) or {}).get("ports") or {}).keys()) or None

        try:
            if status == "running":
                if c.status != "running":
                    c.start()
                    if expect_keys:
                        self._wait_for_ports(c, expect_keys)
                    self._notify_discovery(image=image, c=c, status="running", event="start")
            elif status == "stopped":
                if c.status == "running":
                    c.stop(timeout=5)
                    self._notify_discovery(image=image, c=c, status="stopped", event="stop")
            else:
                return {"ok": False, "error": "invalid-status"}
            return {"ok": True, **self._summarize_container(c)}
        except Exception as e:
            return {"ok": False, "error": str(e)}