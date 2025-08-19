from __future__ import annotations

import os
import shutil
import socket
import time
from typing import Any, Dict, List, Optional

import httpx

from nvidia_orchestrator.core.container_manager import ContainerManager
from nvidia_orchestrator.storage.postgres_store import PostgresStore
from nvidia_orchestrator.utils.logger import logger

INTERVAL_SEC = int(os.getenv("HEALTH_INTERVAL_SECONDS", "60"))
RETENTION_DAYS = int(os.getenv("HEALTH_RETENTION_DAYS", "7"))

class ContainerStateTracker:
    """Real-time tracking of container states in memory"""

    def __init__(self):
        self._states_in_memory = {}  # {container_id: state}

    def get_previous_state(self, container_id: str) -> Optional[str]:
        """Get the previous state of a container"""
        return self._states_in_memory.get(container_id)

    def update_state(self, container_id: str, new_state: str):
        """Update the state of a container"""
        old_state = self._states_in_memory.get(container_id)
        self._states_in_memory[container_id] = new_state
        return old_state

    def cleanup_removed_containers(self, current_container_ids: List[str]):
        """Clean up deleted containers from memory"""
        current_ids = set(current_container_ids)
        stored_ids = set(self._states_in_memory.keys())
        removed_ids = stored_ids - current_ids

        for removed_id in removed_ids:
            del self._states_in_memory[removed_id]
            logger.debug(f"Removed state tracking for deleted container: {removed_id}")

# Global state tracker instance
_state_tracker = None

def get_state_tracker() -> ContainerStateTracker:
    """Create State Tracker (singleton pattern)"""
    global _state_tracker
    if _state_tracker is None:
        _state_tracker = ContainerStateTracker()
    return _state_tracker

def _get_container_port(container_info: dict) -> int:
    """Extract container port"""
    host_ports = container_info.get("host_ports", {})
    for _, port_info in host_ports.items():
        if port_info and isinstance(port_info, list) and len(port_info) > 0:
            return int(port_info[0].get("HostPort", 8000))
    return 8000  # default fallback

def _get_container_caps(container_info: dict) -> dict:
    """Extract container capabilities"""
    resources = container_info.get("resources", {})
    return {
        "cpu": str(resources.get("cpu_limit", "0.5")),
        "mem": str(resources.get("memory_limit", "256m"))
    }

def _cpu_percent(stats: Dict[str, Any]) -> Optional[float]:
    try:
        cpu = stats.get("cpu_stats", {}) or {}
        precpu = stats.get("precpu_stats", {}) or {}
        cpu_total = (cpu.get("cpu_usage", {}) or {}).get("total_usage", 0) - \
                    (precpu.get("cpu_usage", {}) or {}).get("total_usage", 0)
        sys_total = (cpu.get("system_cpu_usage", 0) or 0) - (precpu.get("system_cpu_usage", 0) or 0)
        ncpu = len((cpu.get("cpu_usage", {}) or {}).get("percpu_usage") or []) or 1
        if sys_total > 0 and cpu_total >= 0:
            return (cpu_total / sys_total) * ncpu * 100.0
    except Exception:
        pass
    return None

def _mem_percent(stats: Dict[str, Any]) -> Optional[float]:
    try:
        mem = stats.get("memory_stats", {}) or {}
        usage = float(mem.get("usage", 0.0))
        limit = float(mem.get("limit") or 0.0)
        if limit > 0:
            return (usage / limit) * 100.0
    except Exception:
        pass
    return None

def _disk_percent() -> Optional[float]:
    try:
        du = shutil.disk_usage("/")
        used = du.total - du.free
        return (used / du.total) * 100.0 if du.total > 0 else None
    except Exception:
        return None

def _status(server_running: bool, cpu: Optional[float], mem: Optional[float]) -> str:
    if not server_running:
        return "stopped"
    if (cpu is not None and cpu >= 95.0) or (mem is not None and mem >= 95.0):
        return "critical"
    if (cpu is not None and cpu >= 85.0) or (mem is not None and mem >= 85.0):
        return "warning"
    return "healthy"

async def register_container_to_discovery(container_info: dict, registry_url: str, api_key: Optional[str] = None) -> bool:
    """Register container with service discovery system"""
    if not registry_url:
        return False

    try:
        container_id = container_info.get("id")
        container_name = container_info.get("name")
        image = container_info.get("image", "")
        host = socket.gethostname()
        port = _get_container_port(container_info)
        caps = _get_container_caps(container_info)

        payload = {
            "id": container_id,
            "image_id": image,
            "host": host,
            "port": port,
            "caps": caps
        }

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Use the correct endpoint: /registry/endpoints
        registry_endpoint = f"{registry_url.rstrip('/')}/registry/endpoints"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(registry_endpoint, json=payload, headers=headers, timeout=5.0)
            if response.status_code in (200, 201):
                logger.info(f"Registered container {container_name} ({container_id}) to service discovery")
                return True
            else:
                logger.warning(f"Failed to register container {container_name}: {response.status_code}")
                return False
    except Exception as e:
        logger.error(f"Error registering container to service discovery: {e}")
        return False

def sample_once(manager: ContainerManager, store: PostgresStore) -> None:
    if not store.enabled:
        logger.warning("PostgresStore disabled; skipping snapshot")
        return

    logger.debug("Starting health snapshot collection")

    # Get state tracker
    state_tracker = get_state_tracker()

    # Get all containers managed by this orchestrator (label = managed-by)
    instances: List[Dict[str, Any]] = manager.list_managed_containers()
    host = socket.gethostname()
    disk = _disk_percent() or 0.0

    logger.info(f"Collecting health data for {len(instances)} containers on {host}")

    current_container_ids = []
    for s in instances:
        cid = s.get("id")
        current_container_ids.append(cid)
        name = s.get("name")
        image = s.get("image") or ""
        running = (s.get("state") == "running")

        # Track state changes
        previous_state = state_tracker.get_previous_state(cid)
        current_state = "running" if running else "stopped"
        if previous_state != current_state:
            state_tracker.update_state(cid, current_state)
            logger.info(f"Container {name} ({cid}) state changed: {previous_state} -> {current_state}")

            # Record a compatible lifecycle event (schema allows: create/start/stop/remove)
            try:
                mapped_event = "start" if current_state == "running" else "stop"
                store.record_event({
                    "image": image,
                    "container_id": cid,
                    "name": name,
                    "host": socket.gethostname(),
                    "ports": {},
                    "status": current_state,
                    "event": mapped_event,
                })
            except Exception as e:
                logger.error(f"Failed to record lifecycle event on state change: {e}")

        logger.debug(f"Checking health for container {cid} ({name}) - running: {running}")

        cpu = 0.0
        mem = 0.0
        if running:
            try:
                res = manager.container_stats(cid)
                if res.get("ok"):
                    stats = res["stats"] or {}
                    cpu = _cpu_percent(stats) or 0.0
                    mem = _mem_percent(stats) or 0.0
                    logger.debug(f"Container {cid}: CPU={cpu:.1f}%, MEM={mem:.1f}%")
                else:
                    logger.warning(f"Failed to get stats for {cid}: {res.get('error')}")
            except Exception as e:
                logger.error(f"Error getting stats for {cid}: {e}")
        else:
            logger.debug(f"Container {cid} not running, skipping stats collection")

        status = _status(running, cpu, mem)
        logger.debug(f"Container {cid} health status: {status}")

        # Write snapshot to Postgres
        try:
            store.record_health_snapshot({
                "image": image,
                "container_id": cid,
                "name": name,
                "host": host,
                "cpu_usage": cpu,
                "memory_usage": mem,
                "disk_usage": disk,
                "status": status,
            })
        except Exception as e:
            logger.error(f"Failed to record health snapshot for {cid}: {e}")

    # Clean up removed containers from state tracker
    state_tracker.cleanup_removed_containers(current_container_ids)

    logger.info(f"Health snapshot collection completed for {len(instances)} containers")

def run_forever() -> None:
    # Remove the basicConfig since we're using our custom logger
    manager = ContainerManager()
    store = PostgresStore()

    logger.info("Health monitor starting: interval=%ss, retention_days=%s, store.enabled=%s",
                 INTERVAL_SEC, RETENTION_DAYS, store.enabled)

    while True:
        t0 = time.time()
        try:
            sample_once(manager, store)
            # simple retention (optional)
            if RETENTION_DAYS > 0:
                try:
                    pruned = store.prune_old_health(RETENTION_DAYS)
                    if pruned > 0:
                        logger.info(f"Pruned {pruned} old health records")
                except Exception as e:
                    logger.error(f"Failed to prune old health records: {e}")
        except Exception as e:
            logger.exception("Health monitor loop error: %s", e)

        # sleep the remaining time in the minute
        elapsed = time.time() - t0
        to_sleep = max(1.0, INTERVAL_SEC - elapsed)
        logger.debug(f"Health monitor loop completed in {elapsed:.2f}s, sleeping for {to_sleep:.2f}s")
        time.sleep(to_sleep)

if __name__ == "__main__":
    run_forever()
