from __future__ import annotations

import os
import shutil
import socket
import time
from typing import Any, Dict, List, Optional

from nvidia_orchestrator.core.container_manager import ContainerManager
from nvidia_orchestrator.storage.postgres_store import PostgresStore
from nvidia_orchestrator.utils.logger import logger

INTERVAL_SEC = int(os.getenv("HEALTH_INTERVAL_SECONDS", "60"))
RETENTION_DAYS = int(os.getenv("HEALTH_RETENTION_DAYS", "7"))

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

def sample_once(manager: ContainerManager, store: PostgresStore) -> None:
    if not store.enabled:
        logger.warning("PostgresStore disabled; skipping snapshot")
        return

    logger.debug("Starting health snapshot collection")

    # get all containers managed by this orchestrator (label = managed-by)
    instances: List[Dict[str, Any]] = manager.list_managed_containers()
    host = socket.gethostname()
    disk = _disk_percent() or 0.0

    logger.info(f"Collecting health data for {len(instances)} containers on {host}")

    for s in instances:
        cid = s.get("id")
        name = s.get("name")
        image = s.get("image") or ""
        running = (s.get("state") == "running")

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
