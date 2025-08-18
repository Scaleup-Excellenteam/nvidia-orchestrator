# app.py
from __future__ import annotations

from typing import Dict, Optional, Any, List, Literal
from docker.errors import NotFound, APIError
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from container_manager import ContainerManager
import requests
from enum import Enum
from datetime import datetime, timezone
import threading
import os
import asyncio
from datetime import datetime, timezone
import httpx

app = FastAPI(title="Team 3 Orchestrator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ContainerManager()

## this section for service 
@app.get("/health")
def health():
    return {"status": "OK"}

REGISTRY_BASE = os.getenv("REGISTRY_BASE", "http://localhost:7000")  
SERVICE_ID    = os.getenv("SERVICE_ID", "orchestrator-1")            
SERVICE_KIND  = os.getenv("SERVICE_KIND", "orchestrator")            
PUBLIC_HOST   = os.getenv("PUBLIC_HOST", "127.0.0.1")                
PUBLIC_PORT   = int(os.getenv("PUBLIC_PORT", "8000"))
HEALTH_PATH   = os.getenv("HEALTH_PATH", "/health")

def _health_url() -> str:
    return f"http://{PUBLIC_HOST}:{PUBLIC_PORT}{HEALTH_PATH}"

# --- רישום אוטומטי בעת עליית השרת ---
REGISTRY_URL = os.getenv("REGISTRY_URL")  
REGISTRY_API_KEY = os.getenv("REGISTRY_API_KEY")  

@app.on_event("startup")
async def do_register():
    if not REGISTRY_URL:
        print("[registry] skipped: REGISTRY_URL not set")
        return
    payload = {
        "id": "orchestrator-1",
        "image_id": "orchestrator",
        "host": "127.0.0.1",
        "port": 8801,
        "caps": {"CPU": "?", "MEM": "?"}
    }
    headers = {"Content-Type": "application/json"}
    if REGISTRY_API_KEY:
        headers["Authorization"] = f"Bearer {REGISTRY_API_KEY}"

    for i in range(5):
        try:
            r = httpx.post(REGISTRY_URL, json=payload, headers=headers, timeout=5)
            if r.status_code == 200 or r.status_code == 201:
                print("[registry] registered OK")
                return
            else:
                print(f"[registry] failed ({r.status_code}): {r.text}")
        except Exception as e:
            print(f"[registry] error: {e}")
    print("[registry] gave up registering after retries")







# -------------------------------------------------------------------
# Helper: fetch user from UI (/me) and map to {user_id, name, email}
# -------------------------------------------------------------------
def _fetch_ui_user() -> Dict[str, Optional[str]]:
    """
    Calls UI /me and returns {user_id, name, email}.
    - Configurable via UI_ME_URL (default: http://backend:8000/me)
    - Returns None values if UI is unavailable (won't break the request)
    """
    me_url = os.getenv("UI_ME_URL", "http://backend:8000/me")
    try:
        resp = requests.get(me_url, timeout=5)
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        return {
            "user_id": data.get("id") or data.get("user_id"),
            "name": data.get("first_name") or data.get("name"),
            "email": data.get("email"),
        }
    except Exception:
        return {"user_id": None, "name": None, "email": None}

# -------------------------------------------------------------------
# RESPONSE MODEL: include user fields + optional IO fields
# -------------------------------------------------------------------
class ContainerStats(BaseModel):
    # From UI (/me)
    user_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None

    # Container core stats
    id: str = Field(..., description="Docker container ID")
    cpu_percent: float
    mem_usage: str
    mem_limit: str

    # Optional fields (only included when requested)
    net_io: Optional[str] = None
    block_io: Optional[str] = None

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


class ContainerStats(BaseModel):
    id: str
    name: str
    cpu_percent: float
    mem_usage: str     
    mem_limit: str    
    net_io: str       
    block_io: str      
    pids: int

# ---- Pydantic forward-ref safety for dynamic import (pytest loads via spec_from_file_location) ----
for _m in (
    StartBody, StopBody, DeleteBody, PutResourcesBody,
    InstanceResources, InstanceView, InstancesResponse,
    HealthResponse, StartResponse, StopResponse, DeleteResponse, UpdateResourcesResponse,
):
    _m.model_rebuild()


# -------- Service Discovery / Registry Schemas --------

class StatusEnum(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    # If you later want it, just uncomment:
    # DEGRADED = "DEGRADED"

class Caps(BaseModel):
    cpu: Optional[str] = Field(default=None, description="e.g. '0.5' (cpus)")
    mem: Optional[str] = Field(default=None, description="e.g. '512m'")

class EndpointIn(BaseModel):
    id: str = Field(..., description="Unique endpoint id (usually container id or name)")
    image_id: str = Field(..., description="Image tag / id this endpoint runs")
    host: str = Field(..., description="Host/IP where service is reachable")
    port: int = Field(..., ge=1, le=65535, description="Service port on host")
    caps: Optional[Caps] = None

class EndpointOut(EndpointIn):
    status: StatusEnum = StatusEnum.UP
    last_heartbeat: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Updated on each register/update"
    )





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



'''
## for the billing section . 
# NEW billing route: /order/{user_id}/container
@app.get("/order/{user_id}/container", response_model=ContainerStats, response_model_exclude_none=True)
def get_billing_container_stats_for_user(
    user_id: str,
    container_id: str = Query(..., description="Docker container ID"),
    include_optional: bool = Query(False, description="Include net_io and block_io"),
):
    """
    Returns billing stats + user info from the UI (/me).
    - user_id in path is for routing/business; user data is fetched from /me as requested.
    - Optional fields are returned only when include_optional=true.
    """
    try:
        # If your ContainerManager.get_container_stats supports include_optional, prefer:
        # stats = manager.get_container_stats(container_id, include_optional=include_optional)
        stats = manager.get_container_stats(container_id)

        # Respect include_optional toggle if manager returns them unconditionally
        if include_optional and ("net_io" not in stats or "block_io" not in stats):
            stats.setdefault("net_io", None)
            stats.setdefault("block_io", None)
        else:
            stats.pop("net_io", None)
            stats.pop("block_io", None)

        ui_user = _fetch_ui_user()

        out: Dict[str, Any] = {
            "user_id": ui_user["user_id"],
            "name": ui_user["name"],
            "email": ui_user["email"],
            "id": stats["id"],
            "cpu_percent": stats["cpu_percent"],
            "mem_usage": stats["mem_usage"],
            "mem_limit": stats["mem_limit"],
            "created_at": stats["created_at"],
        }
        if include_optional:
            out["net_io"] = stats.get("net_io")
            out["block_io"] = stats.get("block_io")

        return out

    except NotFound:
        raise HTTPException(status_code=404, detail="Container not found")
    except APIError as e:
        raise HTTPException(status_code=502, detail=f"Docker API error: {getattr(e, 'explanation', str(e))}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
  '''  


# -------- In-memory registry (thread-safe) --------

class _Registry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: Dict[str, EndpointOut] = {}

    def upsert(self, ep: EndpointIn) -> EndpointOut:
        with self._lock:
            existing = self._data.get(ep.id)
            now = datetime.now(timezone.utc)
            if existing:
                # update mutable fields + heartbeat
                existing.image_id = ep.image_id
                existing.host = ep.host
                existing.port = ep.port
                existing.caps = ep.caps
                existing.last_heartbeat = now
                return existing
            out = EndpointOut(**ep.model_dict(), last_heartbeat=now)  # Pydantic v2 compat
            self._data[ep.id] = out
            return out

    def set_status(self, endpoint_id: str, status: StatusEnum) -> EndpointOut:
        with self._lock:
            if endpoint_id not in self._data:
                raise KeyError(endpoint_id)
            ep = self._data[endpoint_id]
            ep.status = status
            ep.last_heartbeat = datetime.now(timezone.utc)
            return ep

    def delete(self, endpoint_id: str) -> None:
        with self._lock:
            if endpoint_id not in self._data:
                raise KeyError(endpoint_id)
            del self._data[endpoint_id]

    def get(self, endpoint_id: str) -> Optional[EndpointOut]:
        with self._lock:
            return self._data.get(endpoint_id)

    def list_all(self) -> List[EndpointOut]:
        with self._lock:
            return list(self._data.values())

registry = _Registry()
    

# -------- Service Discovery / Registry Routes --------

@app.post("/registry/endpoints", response_model=EndpointOut, summary="Register or update an endpoint")
def register_or_update_endpoint(body: EndpointIn) -> EndpointOut:
    """
    Register a new endpoint or update an existing one.
    Returns the saved endpoint with refreshed last_heartbeat.
    """
    saved = registry.upsert(body)
    return saved


@app.delete("/registry/endpoints/{endpoint_id}", summary="Delete an endpoint")
def delete_endpoint(endpoint_id: str) -> Dict[str, bool]:
    """
    Remove an endpoint by id.
    Returns: { "ok": true } if deleted. 404 if it doesn't exist.
    """
    try:
        registry.delete(endpoint_id)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")


@app.put(
    "/registry/endpoints/{endpoint_id}/status",
    response_model=EndpointOut,
    summary="Set endpoint status (UP or DOWN)"
)
def set_endpoint_status(endpoint_id: str, status: StatusEnum):
    """
    Update status for an existing endpoint.
    Per your note, we limit to UP/DOWN. (DEGRADED is easy to enable later.)
    """
    # Enforce only UP/DOWN for now
    if status not in (StatusEnum.UP, StatusEnum.DOWN):
        raise HTTPException(status_code=400, detail="status must be UP or DOWN")

    try:
        updated = registry.set_status(endpoint_id, status)
        return updated
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")



## take the user id and the name from the ui . 
'''
resp = requests.get("http://backend:8000/me")  
data = resp.json()

user = {
    "user_id": data["id"],
    "name": data["first_name"],
    "email": data["email"],
}


@app.get("/current_user")
def current_user():
    resp = requests.get("http://backend:8000/me")
    data = resp.json()
    return {
        "user_id": data["id"],
        "name": data["first_name"],
        "email": data["email"],
    }

'''

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8805, reload=True)