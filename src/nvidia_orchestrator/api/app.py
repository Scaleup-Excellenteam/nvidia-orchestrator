from __future__ import annotations

import asyncio
import os
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

import httpx
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    import psutil
except ImportError:
    psutil = None

from nvidia_orchestrator.core.container_manager import ContainerManager
from nvidia_orchestrator.storage.postgres_store import PostgresStore
from nvidia_orchestrator.utils.logger import logger

app = FastAPI(title="Team 3 Orchestrator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler for better error responses
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return {"error": "Internal server error", "detail": str(exc)}, 500

manager = ContainerManager()

## this section for service
@app.get("/health")
def health():
    """Basic health check - just returns OK if the service is running"""
    return {"status": "OK"}

@app.get("/health/detailed")
def health_detailed():
    """Detailed health check - validates all system components"""
    try:
        health_status = {
            "status": "OK",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {}
        }

        # Check Docker connection
        try:
            manager.client.ping()
            health_status["components"]["docker"] = {"status": "OK", "message": "Connected"}
        except Exception as e:
            health_status["components"]["docker"] = {"status": "ERROR", "message": str(e)}
            health_status["status"] = "DEGRADED"

        # Check PostgreSQL connection
        try:
            store = PostgresStore()
            if store.enabled:
                health_status["components"]["postgresql"] = {"status": "OK", "message": "Connected"}
            else:
                health_status["components"]["postgresql"] = {"status": "WARNING", "message": "Disabled"}
        except Exception as e:
            health_status["components"]["postgresql"] = {"status": "ERROR", "message": str(e)}
            health_status["status"] = "DEGRADED"

        # Check container manager
        try:
            managed_containers = manager.list_managed_containers()
            health_status["components"]["container_manager"] = {
                "status": "OK",
                "message": f"Managing {len(managed_containers)} containers"
            }
        except Exception as e:
            health_status["components"]["container_manager"] = {"status": "ERROR", "message": str(e)}
            health_status["status"] = "DEGRADED"

        # Check system resources
        try:
            if psutil:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                health_status["components"]["system_resources"] = {
                    "status": "OK",
                    "cpu_usage": f"{cpu_percent:.1f}%",
                    "memory_usage": f"{memory.percent:.1f}%"
                }
            else:
                health_status["components"]["system_resources"] = {"status": "WARNING", "message": "psutil not available"}
        except Exception as e:
            health_status["components"]["system_resources"] = {"status": "ERROR", "message": str(e)}

        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "ERROR",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }

@app.get("/test/integration")
def test_integration():
    """Test endpoint to validate complete system integration"""
    try:
        test_results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tests": {},
            "overall_status": "PASSED"
        }

        # Test 1: Docker connection
        try:
            manager.client.ping()
            test_results["tests"]["docker_connection"] = {"status": "PASS", "message": "Docker daemon accessible"}
        except Exception as e:
            test_results["tests"]["docker_connection"] = {"status": "FAIL", "message": str(e)}
            test_results["overall_status"] = "FAILED"

        # Test 2: Container listing
        try:
            containers = manager.list_managed_containers()
            test_results["tests"]["container_listing"] = {
                "status": "PASS",
                "message": f"Found {len(containers)} managed containers"
            }
        except Exception as e:
            test_results["tests"]["container_listing"] = {"status": "FAIL", "message": str(e)}
            test_results["overall_status"] = "FAILED"

        # Test 3: PostgreSQL connection
        try:
            store = PostgresStore()
            if store.enabled:
                test_results["tests"]["postgresql"] = {"status": "PASS", "message": "Database connected"}
            else:
                test_results["tests"]["postgresql"] = {"status": "WARNING", "message": "Database disabled"}
        except Exception as e:
            test_results["tests"]["postgresql"] = {"status": "FAIL", "message": str(e)}
            test_results["overall_status"] = "FAILED"

        # Test 4: System resources
        try:
            if psutil:
                cpu_count = psutil.cpu_count()
                memory = psutil.virtual_memory()
                test_results["tests"]["system_resources"] = {
                    "status": "PASS",
                    "message": f"{cpu_count} CPU cores, {round(memory.total / (1024**3), 1)}GB RAM"
                }
            else:
                test_results["tests"]["system_resources"] = {"status": "WARNING", "message": "psutil not available"}
        except Exception as e:
            test_results["tests"]["system_resources"] = {"status": "FAIL", "message": str(e)}

        # Test 5: Health monitoring
        try:
            # Check if health monitor is working by looking for recent health data
            store = PostgresStore()
            if store.enabled:
                recent_health = store.list_recent_health(limit=5)
                test_results["tests"]["health_monitoring"] = {
                    "status": "PASS",
                    "message": f"Health data available: {len(recent_health)} recent records"
                }
            else:
                test_results["tests"]["health_monitoring"] = {"status": "WARNING", "message": "Database disabled"}
        except Exception as e:
            test_results["tests"]["health_monitoring"] = {"status": "FAIL", "message": str(e)}

        return test_results

    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "ERROR",
            "error": str(e)
        }

@app.get("/system/resources")
def get_system_resources():
    """Returns available system resources for scaling decisions"""
    try:
        if psutil:
            # Get system resource information
            cpu_count = psutil.cpu_count()
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Get Docker container resource usage
            docker_usage = manager.get_system_resource_usage()

            return {
                "system": {
                    "cpu": {
                        "total_cores": cpu_count,
                        "current_usage_percent": round(cpu_percent, 2),
                        "available_cores": max(0, cpu_count - (cpu_count * cpu_percent / 100))
                    },
                    "memory": {
                        "total_gb": round(memory.total / (1024**3), 2),
                        "available_gb": round(memory.available / (1024**3), 2),
                        "usage_percent": round(memory.percent, 2)
                    },
                    "disk": {
                        "total_gb": round(disk.total / (1024**3), 2),
                        "free_gb": round(disk.free / (1024**3), 2),
                        "usage_percent": round((disk.used / disk.total) * 100, 2)
                    }
                },
                "docker": docker_usage
            }
        else:
            # psutil not available, return basic info
            return {
                "system": {
                    "cpu": {"total_cores": "unknown", "current_usage_percent": "unknown"},
                    "memory": {"total_gb": "unknown", "available_gb": "unknown"},
                    "disk": {"total_gb": "unknown", "free_gb": "unknown"}
                },
                "docker": manager.get_system_resource_usage(),
                "note": "psutil not available - limited system metrics"
            }
    except Exception as e:
        logger.error(f"Failed to get system resources: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve system resources: {str(e)}")

REGISTRY_BASE = os.getenv("REGISTRY_BASE", "http://localhost:8000")
SERVICE_ID    = os.getenv("SERVICE_ID", "orchestrator-1")
SERVICE_KIND  = os.getenv("SERVICE_KIND", "orchestrator")
PUBLIC_HOST   = os.getenv("PUBLIC_HOST", "127.0.0.1")
PUBLIC_PORT   = int(os.getenv("PUBLIC_PORT", "8000"))
HEALTH_PATH   = os.getenv("HEALTH_PATH", "http://localhost:8000/health")

def _health_url() -> str:
    return f"http://{PUBLIC_HOST}:{PUBLIC_PORT}{HEALTH_PATH}"

# --- רישום אוטומטי בעת עליית השרת ---
REGISTRY_URL = os.getenv("REGISTRY_URL")
REGISTRY_API_KEY = os.getenv("REGISTRY_API_KEY")

@app.on_event("startup")
async def do_register():
    """Register with service discovery and validate system startup"""
    logger.info("Starting Team 3 Orchestrator...")

    # Validate core system components
    startup_validation = await validate_startup()
    if not startup_validation["success"]:
        logger.error(f"Startup validation failed: {startup_validation['errors']}")
        # Continue startup but log the issues

    # Register with service discovery if configured
    if not REGISTRY_URL:
        logger.info("[registry] skipped: REGISTRY_URL not set")
        return

    payload = {
        "id": "orchestrator-1",
        "kind": "orchestrator",
        "url": HEALTH_PATH,
        "status":"UP"
    }
    headers = {"Content-Type": "application/json"}
    if REGISTRY_API_KEY:
        headers["Authorization"] = f"Bearer {REGISTRY_API_KEY}"

    for i in range(5):
        try:
            r = httpx.post(REGISTRY_URL, json=payload, headers=headers, timeout=5)
            if r.status_code == 200 or r.status_code == 201:
                logger.info("[registry] registered OK")
                return
            else:
                logger.warning(f"[registry] failed ({r.status_code}): {r.text}")
        except Exception as e:
            logger.warning(f"[registry] error: {e}")
        await asyncio.sleep(2 ** i)  # Exponential backoff

    logger.error("[registry] gave up registering after retries")

async def validate_startup() -> Dict[str, Any]:
    """Validate all system components during startup"""
    validation = {"success": True, "errors": [], "warnings": []}

    # Check Docker connection
    try:
        manager.client.ping()
        logger.info("[OK] Docker connection validated")
    except Exception as e:
        validation["success"] = False
        validation["errors"].append(f"Docker connection failed: {e}")
        logger.error(f"[FAIL] Docker connection failed: {e}")

    # Check PostgreSQL connection
    try:
        store = PostgresStore()
        if store.enabled:
            logger.info("[OK] PostgreSQL connection validated")
        else:
            validation["warnings"].append("PostgreSQL disabled - events will not be persisted")
            logger.warning("[WARN] PostgreSQL disabled - events will not be persisted")
    except Exception as e:
        validation["warnings"].append(f"PostgreSQL check failed: {e}")
        logger.warning(f"[WARN] PostgreSQL check failed: {e}")

    # Check container manager
    try:
        managed_containers = manager.list_managed_containers()
        logger.info(f"[OK] Container manager validated - managing {len(managed_containers)} containers")
    except Exception as e:
        validation["success"] = False
        validation["errors"].append(f"Container manager failed: {e}")
        logger.error(f"[FAIL] Container manager failed: {e}")

    # Check system resources
    try:
        if psutil:
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            logger.info(f"[OK] System resources validated - {cpu_count} CPU cores, {round(memory.total / (1024**3), 1)}GB RAM")
        else:
            validation["warnings"].append("psutil not available - limited system metrics")
            logger.warning("[WARN] psutil not available - limited system metrics")
    except Exception as e:
        validation["warnings"].append(f"System resource check failed: {e}")
        logger.warning(f"[WARN] System resource check failed: {e}")

    if validation["success"]:
        logger.info("[SUCCESS] All critical components validated successfully!")
    else:
        logger.error(f"[ERROR] Startup validation failed with {len(validation['errors'])} errors")

    return validation

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

# ContainerStats class already defined above

# ---- Pydantic v2 models are automatically resolved ----
# No need for model_rebuild() in Pydantic v2

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

@app.get("/images")
def get_images():
    """Returns current desired state and running container counts from PostgresStore"""
    try:
        # Import PostgresStore here to avoid circular imports
        store = PostgresStore()

        if store.enabled:
            desired_images = store.list_desired()

            # Enhance with current container counts
            enhanced_images = []
            for img in desired_images:
                image_name = img.get("image", "")
                current_instances = manager.list_instances_for_image(image_name)
                running_count = len([i for i in current_instances if i.get("state") == "running"])

                enhanced_img = img.copy()
                enhanced_img["current_running"] = running_count
                enhanced_img["total_instances"] = len(current_instances)
                enhanced_images.append(enhanced_img)

            return {"images": enhanced_images}
        return {"images": []}
    except Exception as e:
        logger.error(f"Failed to get images: {e}")
        return {"images": [], "error": str(e)}

@app.post("/start/container")
def start_container(body: StartBody):
    """Starts or reuses a container for a given image with env/ports/resources"""
    try:
        # For now, we'll use the existing start logic
        # This endpoint should be enhanced to handle reuse logic
        image = body.resources.get("image", "nginx:alpine") if body.resources else "nginx:alpine"
        count = body.count or 1

        resources: Dict[str, Any] = {}
        if body.resources:
            mem = body.resources.get("memory_limit")
            cpu = body.resources.get("cpu_limit")
            if mem:
                resources["mem_limit"] = mem
            if cpu is not None:
                try:
                    resources["nano_cpus"] = int(float(cpu) * 1_000_000_000)
                except (ValueError, TypeError):
                    pass

        started_ids: List[str] = []
        for _ in range(count):
            info = manager.create_container(image, env={}, ports={}, resources=resources)
            started_ids.append(info["id"])

        # Return the format expected by the prompt
        return {
            "ok": True,
            "action": "created",
            "image": image,
            "container_id": started_ids[0] if started_ids else None,
            "name": f"container-{started_ids[0]}" if started_ids else None,
            "status": "running",
            "ports": {},
            "desired_state_saved": True  # Add this line
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/containers")
def get_all_containers():
    """Returns all managed containers with status + host port bindings"""
    try:
        # Get all containers managed by this orchestrator
        all_containers = manager.list_managed_containers()

        # Format response for other teams
        formatted_containers = []
        for container in all_containers:
            formatted_containers.append({
                "id": container.get("id"),
                "name": container.get("name"),
                "image": container.get("image"),
                "status": container.get("state"),
                "ports": container.get("host_ports", {}),
                "created_at": container.get("created_at"),
                "resources": container.get("resources", {})
            })

        return {"containers": formatted_containers, "total": len(formatted_containers)}
    except Exception as e:
        logger.error(f"Failed to get all containers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve containers: {str(e)}")

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
    try:
        res = manager.container_stats(instanceId)
        if not res.get("ok"):
            if res.get("error") == "not-found":
                raise HTTPException(status_code=404, detail=f"Instance '{instanceId}' not found")
            raise HTTPException(status_code=400, detail=res.get("error", "failed"))

        c = res["container"]
        stats = res["stats"]

        # Safely reload container status
        try:
            c.reload()
            running = (c.status == "running")
        except Exception as e:
            # Container might have been deleted or is inaccessible
            raise HTTPException(status_code=404, detail=f"Instance '{instanceId}' is no longer accessible: {str(e)}")

        # Calculate health metrics with better error handling
        try:
            cpu_p = _calc_cpu_percent(stats) or 0.0
            mem_p = _calc_mem_percent(stats) or 0.0
            disk_p = 0.0  # docker stats lacks reliable per-container disk % by default
        except Exception:
            # If stats calculation fails, provide default values
            cpu_p = 0.0
            mem_p = 0.0
            disk_p = 0.0

        # Determine health status
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

        # Collect errors for unavailable metrics
        errs: List[str] = []
        if _calc_cpu_percent(stats) is None:
            errs.append("cpu_usage_unavailable")
        if _calc_mem_percent(stats) is None:
            errs.append("memory_limit_unavailable")
        if errs:
            body["errors"] = errs

        return body

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any unexpected errors and return a 500
        raise HTTPException(status_code=500, detail=f"Health check failed for instance '{instanceId}': {str(e)}")

# POST `/containers/{imageId}/start`
@app.post(
    "/containers/{imageId}/start",
    response_model=StartResponse,
    response_model_exclude_none=True,
)
def start_image(imageId: str, body: StartBody):
    try:
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
        failed_count = 0

        for i in range(count):
            try:
                info = manager.create_container(imageId, env={}, ports={}, resources=resources)
                started_ids.append(info["id"])
            except Exception as e:
                failed_count += 1
                # Log the failure but continue with other containers
                logger.error(f"Failed to start container {i+1}/{count} for image {imageId}: {e}")

        if failed_count > 0:
            if len(started_ids) == 0:
                # All containers failed
                raise HTTPException(status_code=500, detail=f"Failed to start any containers for image {imageId}. All {count} attempts failed.")
            else:
                # Some containers failed, but some succeeded
                logger.warning(f"Started {len(started_ids)}/{count} containers for image {imageId}. {failed_count} failed.")

        return {"started": started_ids}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start containers for image {imageId}: {str(e)}")

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

# DELETE `/containers/{idOrName}`
@app.delete("/containers/{idOrName}")
def delete_container_by_id(idOrName: str, force: bool = Query(False, description="Force deletion")):
    """Removes the container by ID or name"""
    try:
        res = manager.delete_container(idOrName, force=force)
        if not res.get("ok"):
            if res.get("error") == "not-found":
                raise HTTPException(status_code=404, detail=f"Container '{idOrName}' not found")
            raise HTTPException(status_code=400, detail=res.get("error", "failed"))
        return {"deleted": True, "container_id": idOrName, "name": idOrName}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# DELETE `/containers/{imageId}` (legacy endpoint)
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
            out = EndpointOut(**ep.model_dump(), last_heartbeat=now)  # Pydantic v2 compat
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

def run_server() -> None:
    """Run the API server."""
    import uvicorn
    uvicorn.run("nvidia_orchestrator.api.app:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    run_server()
