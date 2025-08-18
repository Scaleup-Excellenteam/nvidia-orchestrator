# app.py
from __future__ import annotations

from typing import Dict, Optional, Any, List, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from container_manager import ContainerManager


app = FastAPI(title="Team 3 Orchestrator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ContainerManager()


# -------- Schemas per Team 3 contract --------

class ResourcesBody(BaseModel):
    cpu_limit: Optional[str] = None
    memory_limit: Optional[str] = None
    disk_limit: Optional[str] = None  # accepted by contract; may be no-op

class StartBody(BaseModel):
    count: Optional[int] = Field(default=1, ge=1)
    resources: Optional[Dict[str, Any]] = Field(
        default=None,
        description="{ cpu_limit?: string, memory_limit?: string, disk_limit?: string }",
    )

class StopBody(BaseModel):
    instanceId: str

class DeleteBody(BaseModel):
    instanceId: str

class PutResourcesBody(BaseModel):
    cpu_limit: Optional[str] = None
    memory_limit: Optional[str] = None
    disk_limit: Optional[str] = None  # accepted; may be ignored by backend


# -------- Response models (strictly match Team 3) --------

class InstanceResources(BaseModel):
    cpu_limit: Optional[str] = None
    memory_limit: Optional[str] = None
    disk_limit: Optional[str] = None

class InstanceView(BaseModel):
    id: str
    status: Literal["running", "stopped"]
    endpoint: str
    resources: Optional[InstanceResources] = None

class InstancesResponse(BaseModel):
    instances: List[InstanceView]

class HealthResponse(BaseModel):
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    status: Literal["healthy", "warning", "critical", "stopped"]
    errors: Optional[List[str]] = None

class StartResponse(BaseModel):
    started: List[str]

class StopResponse(BaseModel):
    stopped: bool

class DeleteResponse(BaseModel):
    deleted: bool

class UpdateResourcesResponse(BaseModel):
    updated: List[str]


# ---- Pydantic forward-ref safety for dynamic import (pytest loads via spec_from_file_location) ----
for _m in (
    StartBody, StopBody, DeleteBody, PutResourcesBody,
    InstanceResources, InstanceView, InstancesResponse,
    HealthResponse, StartResponse, StopResponse, DeleteResponse, UpdateResourcesResponse,
):
    _m.model_rebuild()


# -------- Utilities --------

def _first_endpoint_from_summary(s: Dict[str, Any]) -> str:
    host_ports = s.get("host_ports") or {}
    for _, hp in host_ports.items():
        if hp:
            return f"http://localhost:{hp}"
    return ""

def _instance_view(s: Dict[str, Any]) -> Dict[str, Any]:
    view: Dict[str, Any] = {
        "id": s.get("id"),
        "status": "running" if s.get("state") == "running" else "stopped",
        "endpoint": _first_endpoint_from_summary(s),
    }
    res = s.get("resources") or {}
    resources_out = {
        "cpu_limit": res.get("cpu_limit"),
        "memory_limit": res.get("memory_limit"),
        "disk_limit": res.get("disk_limit"),
    }
    # include resources only if at least one is present
    if any(v is not None for v in resources_out.values()):
        view["resources"] = {k: v for k, v in resources_out.items() if v is not None}
    return view

def _calc_cpu_percent(stats: Dict[str, Any]) -> Optional[float]:
    try:
        cpu = stats.get("cpu_stats", {})
        precpu = stats.get("precpu_stats", {})
        cpu_total = cpu.get("cpu_usage", {}).get("total_usage")
        precpu_total = precpu.get("cpu_usage", {}).get("total_usage")
        system = cpu.get("system_cpu_usage")
        presystem = precpu.get("system_cpu_usage")
        online_cpus = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage") or []) or 1
        if None in (cpu_total, precpu_total, system, presystem):
            return None
        cpu_delta = cpu_total - precpu_total
        sys_delta = system - presystem
        if cpu_delta > 0 and sys_delta > 0:
            return (cpu_delta / sys_delta) * online_cpus * 100.0
        return None
    except Exception:
        return None

def _calc_mem_percent(stats: Dict[str, Any]) -> Optional[float]:
    try:
        mem = stats.get("memory_stats", {})
        usage = mem.get("usage")
        limit = mem.get("limit")
        if usage and limit and limit > 0:
            return (usage / limit) * 100.0
        return None
    except Exception:
        return None


# -------- Routes --------

@app.get("/health")
def health():
    return {"ok": True}

# GET `/containers/{imageId}/instances`
@app.get(
    "/containers/{imageId}/instances",
    response_model=InstancesResponse,
    response_model_exclude_none=True,
)
def get_instances(imageId: str):
    items = manager.list_instances_for_image(imageId)
    return {"instances": [_instance_view(x) for x in items]}

# GET `/containers/instances/{instanceId}/health`
@app.get(
    "/containers/instances/{instanceId}/health",
    response_model=HealthResponse,
    response_model_exclude_none=True,
)
def instance_health(instanceId: str):
    res = manager.container_stats(instanceId)
    if not res.get("ok"):
        if res.get("error") == "not-found":
            raise HTTPException(status_code=404, detail=f"Instance '{instanceId}' not found")
        raise HTTPException(status_code=400, detail=res.get("error", "failed"))

    c = res["container"]
    stats = res["stats"]
    c.reload()
    running = (c.status == "running")

    cpu_p = _calc_cpu_percent(stats) or 0.0
    mem_p = _calc_mem_percent(stats) or 0.0
    disk_p = 0.0  # docker stats lacks reliable per-container disk % by default

    if not running:
        status: Literal["healthy","warning","critical","stopped"] = "stopped"
    elif cpu_p >= 90.0 or mem_p >= 90.0:
        status = "critical"
    elif cpu_p >= 75.0 or mem_p >= 75.0:
        status = "warning"
    else:
        status = "healthy"

    body: Dict[str, Any] = {
        "cpu_usage": round(cpu_p, 2),
        "memory_usage": round(mem_p, 2),
        "disk_usage": round(disk_p, 2),
        "status": status,
    }

    errs: List[str] = []
    if _calc_cpu_percent(stats) is None:
        errs.append("cpu_usage_unavailable")
    if _calc_mem_percent(stats) is None:
        errs.append("memory_limit_unavailable")
    if errs:
        body["errors"] = errs

    return body

# POST `/containers/{imageId}/start`
# POST `/containers/{imageId}/start`
@app.post(
    "/containers/{imageId}/start",
    response_model=StartResponse,
    response_model_exclude_none=True,
)
def start_image(imageId: str, body: StartBody):
    count = body.count or 1

    resources: Dict[str, Any] = {}
    if body.resources:
        # map contract -> docker kwargs used by ContainerManager
        mem = body.resources.get("memory_limit")
        cpu = body.resources.get("cpu_limit")
        if mem:
            resources["mem_limit"] = mem
        if cpu is not None:
            # convert fractional CPUs (e.g. "0.25") to nano_cpus (int)
            try:
                resources["nano_cpus"] = int(float(cpu) * 1_000_000_000)
            except (ValueError, TypeError):
                # ignore if unparsable; manager will run without CPU limit
                pass
        # disk_limit is accepted by contract but not enforced (no-op)

    started_ids: List[str] = []
    for _ in range(count):
        info = manager.create_container(imageId, env={}, ports={}, resources=resources)
        started_ids.append(info["id"])
    return {"started": started_ids}

# POST `/containers/{imageId}/stop`
@app.post(
    "/containers/{imageId}/stop",
    response_model=StopResponse,
    response_model_exclude_none=True,
)
def stop_image_instance(imageId: str, body: StopBody):
    res = manager.stop_container(body.instanceId)
    if not res.get("ok"):
        if res.get("error") == "not-found":
            raise HTTPException(status_code=404, detail=f"Instance '{body.instanceId}' not found")
        raise HTTPException(status_code=400, detail=res.get("error", "failed"))
    return {"stopped": True}

# DELETE `/containers/{imageId}`
@app.delete(
    "/containers/{imageId}",
    response_model=DeleteResponse,
    response_model_exclude_none=True,
)
def delete_image_instance(imageId: str, body: DeleteBody):
    res = manager.delete_container(body.instanceId, force=True)
    if not res.get("ok"):
        if res.get("error") == "not-found":
            raise HTTPException(status_code=404, detail=f"Instance '{body.instanceId}' not found")
        raise HTTPException(status_code=400, detail=res.get("error", "failed"))
    return {"deleted": True}

# PUT `/containers/{imageId}/resources`
@app.put(
    "/containers/{imageId}/resources",
    response_model=UpdateResourcesResponse,
    response_model_exclude_none=True,
)
def update_resources(imageId: str, body: PutResourcesBody):
    # Apply what the backend supports (cpu/memory); accept disk_limit as per contract.
    updated = manager.update_resources_for_image(
        imageId,
        cpu_limit=body.cpu_limit,
        memory_limit=body.memory_limit,
        # disk_limit currently not enforced by docker; intentionally ignored
    )
    # Contract requires array of instance IDs
    return {"updated": list(updated) if isinstance(updated, (list, tuple, set)) else (updated or [])}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8800, reload=True)
