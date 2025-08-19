from __future__ import annotations
import os, time, socket, shutil, logging
from typing import Dict, Any, List, Optional
import httpx
from datetime import datetime, timezone

from container_manager import ContainerManager
from postgres_store import PostgresStore
from logger import logger

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

def _notify_discovery_service(container_info: dict, action: str):
    """Send update to Discovery Service"""
    try:
        discovery_url = os.getenv("DISCOVERY_SERVICE_URL", "http://localhost:7000")
        
        if action == "started":
            payload = {
                "id": container_info["id"],
                "image_id": container_info["image"],
                "host": socket.gethostname(),
                "port": _get_container_port(container_info),
                "caps": _get_container_caps(container_info)
            }
            httpx.post(f"{discovery_url}/registry/endpoints", json=payload, timeout=5)
            
        elif action == "stopped":
            httpx.put(f"{discovery_url}/registry/endpoints/{container_info['id']}/status?status=DOWN", timeout=5)
            
        elif action == "removed":
            httpx.delete(f"{discovery_url}/registry/endpoints/{container_info['id']}", timeout=5)
            
        logger.info(f"Discovery Service notified: {action} for {container_info['id']}")
        
    except Exception as e:
        logger.warning(f"Failed to notify Discovery Service: {e}")

def _notify_billing_service(container_info: dict, event_type: str):
    """Send event to Billing Service"""
    try:
        billing_url = os.getenv("BILLING_SERVICE_URL", "http://localhost:8001")
        
        payload = {
            "event": event_type,
            "container_id": container_info["id"],
            "image": container_info.get("image", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "host": socket.gethostname()
        }
        
        httpx.post(f"{billing_url}/events", json=payload, timeout=5)
        logger.info(f"Billing Service notified: {event_type} for {container_info['id']}")
        
    except Exception as e:
        logger.warning(f"Failed to notify Billing Service: {e}")

def sample_once(manager: ContainerManager, store: PostgresStore) -> None:
    if not store.enabled:
        logger.warning("PostgresStore disabled; skipping snapshot")
        return

    logger.debug("Starting health snapshot collection")
    
    # Get State Tracker
    state_tracker = get_state_tracker()
    
    # get all containers managed by this orchestrator (label = managed-by)
    instances: List[Dict[str, Any]] = manager.list_managed_containers()
    host = socket.gethostname()
    disk = _disk_percent() or 0.0
    
    # Clean up deleted containers
    current_container_ids = [s.get("id") for s in instances if s.get("id")]
    state_tracker.cleanup_removed_containers(current_container_ids)
    
    logger.info(f"Collecting health data for {len(instances)} containers on {host}")

    for s in instances:
        cid = s.get("id")
        name = s.get("name")
        image = s.get("image") or ""
        current_state = s.get("state")
        previous_state = state_tracker.get_previous_state(cid)
        
        # Check if state changed
        if current_state != previous_state:
            logger.info(f"Container {cid} state changed: {previous_state} -> {current_state}")
            
            # Send notifications to external services
            if current_state == "running":
                _notify_discovery_service(s, "started")
                _notify_billing_service(s, "started")
            elif current_state == "exited":
                _notify_discovery_service(s, "stopped")
                _notify_billing_service(s, "stopped")
            elif current_state == "removed":
                _notify_discovery_service(s, "removed")
                _notify_billing_service(s, "removed")
            
            # Update state
            state_tracker.update_state(cid, current_state)
        
        running = (current_state == "running")

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

        # write snapshot to Postgres
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
