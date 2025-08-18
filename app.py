from __future__ import annotations
import os
import socket
import shutil
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from container_manager import ContainerManager
from postgres_store import PostgresStore  # <- Postgres only
from logger import logger

app = FastAPI(title="Team 3 Orchestrator API", version="1.0.0")
manager = ContainerManager()
_store = PostgresStore()

logger.info("Orchestrator API starting up")

# ------------------ Models ------------------
class StartRequest(BaseModel):
    count: int = Field(1, ge=1)
    resources: Optional[Dict[str, Any]] = None
    env: Optional[Dict[str, str]] = None
    ports: Optional[Dict[str, Optional[int]]] = None


class StopRequest(BaseModel):
    instanceId: str


class DeleteRequest(BaseModel):
    instanceId: str


# ------------------ Helpers ------------------
def _first_host_port(host_ports: Dict[str, Optional[int]]) -> Optional[int]:
    for _, hp in host_ports.items():
        if isinstance(hp, int) and hp > 0:
            return hp
    return None


def _endpoint_from_summary(s: Dict[str, Any]) -> str:
    hp = _first_host_port(s.get("host_ports", {}) or {})
    return f"http://127.0.0.1:{hp}" if hp else ""


def _cpu_percent_from_stats(st: Dict[str, Any]) -> Optional[float]:
    try:
        cpu = st.get("cpu_stats", {}) or {}
        precpu = st.get("precpu_stats", {}) or {}
        cpu_total = (cpu.get("cpu_usage", {}) or {}).get("total_usage", 0) - \
                    (precpu.get("cpu_usage", {}) or {}).get("total_usage", 0)
        sys_total = cpu.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
        ncpu = len((cpu.get("cpu_usage", {}) or {}).get("percpu_usage") or []) or 1
        if sys_total > 0 and cpu_total >= 0:
            return (cpu_total / sys_total) * ncpu * 100.0
    except Exception:
        pass
    return None


def _mem_percent_from_stats(st: Dict[str, Any]) -> Optional[float]:
    try:
        mem = st.get("memory_stats", {}) or {}
        usage = float(mem.get("usage", 0.0))
        limit = float(mem.get("limit") or 0.0)
        if usage >= 0 and limit > 0:
            return (usage / limit) * 100.0
    except Exception:
        pass
    return None


def _disk_usage_percent() -> Optional[float]:
    try:
        du = shutil.disk_usage("/")
        used = du.total - du.free
        return (used / du.total) * 100.0 if du.total > 0 else None
    except Exception:
        return None


def _status_from_metrics(server_alive: bool, cpu: Optional[float], mem: Optional[float]) -> str:
    if not server_alive:
        return "stopped"
    if (cpu is not None and cpu >= 95.0) or (mem is not None and mem >= 95.0):
        return "critical"
    if (cpu is not None and cpu >= 85.0) or (mem is not None and mem >= 85.0):
        return "warning"
    return "healthy"


def _record_event(payload: Dict[str, Any]) -> None:
    try:
        if _store and getattr(_store, "enabled", False):
            _store.record_event(payload)
            logger.debug(f"Event recorded: {payload.get('event')} for {payload.get('container_id')}")
        else:
            logger.warning("Event store not available, skipping event recording")
    except Exception as e:
        logger.error(f"Failed to record event: {e}")


def _persist_desired(image: str, count: int, resources: Optional[Dict[str, Any]]) -> None:
    try:
        if _store and getattr(_store, "enabled", False):
            doc = {
                "image": image,
                "min_replicas": count,
                "max_replicas": count,
                "resources": resources or {},
            }
            _store.upsert_desired(image, doc)
            logger.debug(f"Desired state persisted for {image}: {count} replicas")
        else:
            logger.warning("Store not available, skipping desired state persistence")
    except Exception as e:
        logger.error(f"Failed to persist desired state for {image}: {e}")


# ------------------ Routes expected by tests ------------------

@app.post("/containers/{image}/start")
def start_containers(image: str, body: StartRequest):
    logger.info(f"Starting {body.count} container(s) for image: {image}")
    started: List[str] = []
    for i in range(body.count):
        try:
            summary = manager.create_container(
                image,
                env=body.env,
                ports=body.ports,
                resources=body.resources,
            )
            started.append(summary["id"])
            logger.info(f"Container {i+1}/{body.count} created: {summary['id']} ({summary.get('name', 'unnamed')})")
            _record_event({
                "image": image,
                "container_id": summary["id"],
                "name": summary.get("name"),
                "host": socket.gethostname(),
                "ports": summary.get("ports", {}),
                "status": "running",
                "event": "create",
            })
        except Exception as e:
            logger.error(f"Failed to create container {i+1}/{body.count} for {image}: {e}")
            raise HTTPException(status_code=500, detail=f"Container creation failed: {e}")
    
    _persist_desired(image, body.count, body.resources)
    logger.info(f"Successfully started {len(started)} container(s) for {image}")
    return {"started": started}


@app.get("/containers/{image}/instances")
def list_instances(image: str):
    logger.info(f"Listing instances for image: {image}")
    instances_raw = manager.list_instances_for_image(image)
    instances = []
    for s in instances_raw:
        status = "running" if s.get("state") == "running" else "stopped"
        instances.append({
            "id": s.get("id"),
            "status": status,
            "endpoint": _endpoint_from_summary(s),
            "resources": s.get("resources") or None,
        })
    logger.info(f"Found {len(instances)} instances for {image}")
    return {"instances": instances}


@app.get("/containers/instances/{instanceId}/health")
def instance_health(instanceId: str):
    logger.info(f"Checking health for instance: {instanceId}")
    res = manager.container_stats(instanceId)
    if not res.get("ok"):
        error_msg = res.get("error", "unknown error")
        logger.error(f"Health check failed for {instanceId}: {error_msg}")
        if res.get("error") == "not-found":
            raise HTTPException(status_code=404, detail="instance not found")
        raise HTTPException(status_code=500, detail=str(error_msg))
    
    c = res["container"]
    stats = res["stats"] or {}
    server_alive = (getattr(c, "status", "") == "running")
    cpu = _cpu_percent_from_stats(stats) or 0.0
    mem = _mem_percent_from_stats(stats) or 0.0
    disk = _disk_usage_percent() or 0.0
    status = _status_from_metrics(server_alive, cpu, mem)
    
    logger.info(f"Health check for {instanceId}: status={status}, cpu={cpu:.1f}%, mem={mem:.1f}%, disk={disk:.1f}%")
    return {"cpu_usage": cpu, "memory_usage": mem, "disk_usage": disk, "status": status}


@app.post("/containers/{image}/stop")
def stop_container(image: str, body: StopRequest):
    logger.info(f"Stopping container {body.instanceId} for image: {image}")
    out = manager.stop_container(body.instanceId)
    if not out.get("ok"):
        error_msg = out.get("error", "unknown error")
        logger.error(f"Failed to stop container {body.instanceId}: {error_msg}")
        if out.get("error") == "not-found":
            raise HTTPException(status_code=404, detail="instance not found")
        raise HTTPException(status_code=500, detail=str(error_msg))
    
    _record_event({
        "image": image,
        "container_id": body.instanceId,
        "host": socket.gethostname(),
        "status": "stopped",
        "event": "stop",
    })
    logger.info(f"Successfully stopped container {body.instanceId}")
    return {"stopped": True}


@app.delete("/containers/{image}")
def delete_container(image: str, body: DeleteRequest):
    logger.info(f"Deleting container {body.instanceId} for image: {image}")
    out = manager.delete_container(body.instanceId, force=True)
    if not out.get("ok"):
        error_msg = out.get("error", "unknown error")
        logger.error(f"Failed to delete container {body.instanceId}: {error_msg}")
        if out.get("error") == "not-found":
            raise HTTPException(status_code=404, detail="not found")
        raise HTTPException(status_code=500, detail=str(error_msg))
    
    _record_event({
        "image": image,
        "container_id": body.instanceId,
        "host": socket.gethostname(),
        "status": "removed",
        "event": "remove",
    })
    logger.info(f"Successfully deleted container {body.instanceId}")
    return {"deleted": True}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/events")
def list_events(image: Optional[str] = None, limit: int = 100):
    try:
        if _store and getattr(_store, "enabled", False):
            return {"ok": True, "events": _store.list_events(image=image, limit=limit)}
        return {"ok": True, "events": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
