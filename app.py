from __future__ import annotations
import os
import socket
import shutil
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from container_manager import ContainerManager
from postgres_store import PostgresStore  # <- Postgres only

app = FastAPI(title="Team 3 Orchestrator API", version="1.0.0")
manager = ContainerManager()
_store = PostgresStore()


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
    except Exception:
        pass


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
    except Exception:
        pass


# ------------------ Routes expected by tests ------------------

@app.post("/containers/{image}/start")
def start_containers(image: str, body: StartRequest):
    started: List[str] = []
    for _ in range(body.count):
        summary = manager.create_container(
            image,
            env=body.env,
            ports=body.ports,
            resources=body.resources,
        )
        started.append(summary["id"])
        _record_event({
            "image": image,
            "container_id": summary["id"],
            "name": summary.get("name"),
            "host": socket.gethostname(),
            "ports": summary.get("ports", {}),
            "status": "running",
            "event": "create",
        })
    _persist_desired(image, body.count, body.resources)
    return {"started": started}


@app.get("/containers/{image}/instances")
def list_instances(image: str):
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
    return {"instances": instances}


@app.get("/containers/instances/{instanceId}/health")
def instance_health(instanceId: str):
    res = manager.container_stats(instanceId)
    if not res.get("ok"):
        if res.get("error") == "not-found":
            raise HTTPException(status_code=404, detail="instance not found")
        raise HTTPException(status_code=500, detail=str(res.get("error")))
    c = res["container"]
    stats = res["stats"] or {}
    server_alive = (getattr(c, "status", "") == "running")
    cpu = _cpu_percent_from_stats(stats) or 0.0
    mem = _mem_percent_from_stats(stats) or 0.0
    disk = _disk_usage_percent() or 0.0
    status = _status_from_metrics(server_alive, cpu, mem)
    return {"cpu_usage": cpu, "memory_usage": mem, "disk_usage": disk, "status": status}


@app.post("/containers/{image}/stop")
def stop_container(image: str, body: StopRequest):
    out = manager.stop_container(body.instanceId)
    if not out.get("ok"):
        if out.get("error") == "not-found":
            raise HTTPException(status_code=404, detail="instance not found")
        raise HTTPException(status_code=500, detail=str(out.get("error")))
    _record_event({
        "image": image,
        "container_id": body.instanceId,
        "host": socket.gethostname(),
        "status": "stopped",
        "event": "stop",
    })
    return {"stopped": True}


@app.delete("/containers/{image}")
def delete_container(image: str, body: DeleteRequest):
    out = manager.delete_container(body.instanceId, force=True)
    if not out.get("ok"):
        if out.get("error") == "not-found":
            raise HTTPException(status_code=404, detail="not found")
        raise HTTPException(status_code=500, detail=str(out.get("error")))
    _record_event({
        "image": image,
        "container_id": body.instanceId,
        "host": socket.gethostname(),
        "status": "removed",
        "event": "remove",
    })
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
