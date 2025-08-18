"""
FastAPI layer that exposes container orchestration endpoints and delegates
all Docker interactions to `ContainerManager`.

Run locally:
    uvicorn fast_api:app --reload --host 0.0.0.0 --port 8000

Quick demo:
  Start & register:
    curl -X POST http://localhost:8000/start/container \
      -H "Content-Type: application/json" -d '{
        "image":"nginx:alpine",
        "min_replicas":1,
        "max_replicas":3,
        "env":{"DISCOVERY_CALLBACK":"http://localhost:9000/register"},
        "ports":{"80/tcp":0},
        "resources":{"cpu":"500m","memory":"256m","status":"running"}
      }'

  Scale:
    curl -X POST http://localhost:8000/images/nginx:alpine/scale \
      -H "Content-Type: application/json" -d '{"min_replicas":2,"max_replicas":3}'

  Reconcile once:
    curl -X POST http://localhost:8000/images/nginx:alpine/reconcile

  List all managed:
    curl http://localhost:8000/containers

  Per-image containers:
    curl http://localhost:8000/images/nginx:alpine/containers

  Health per image:
    curl http://localhost:8000/images/nginx:alpine/health

  Stop one:
    curl -X PATCH http://localhost:8000/containers/<id> \
      -H "Content-Type: application/json" -d '{"status":"stopped"}'

  Delete one:
    curl -X DELETE "http://localhost:8000/containers/<id>?force=true"
"""

from typing import Dict, Literal, Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from container_manager import ContainerManager


# ------------------ Pydantic schemas ------------------
class Resources(BaseModel):
    """Compute/Memory and desired lifecycle for a single managed container.

    Attributes
    ----------
    cpu:
        CPU quota for the container. Accepts a float as string (e.g., "0.5")
        or milli-CPU (e.g., "500m"). Converted to Docker's `nano_cpus`.
    memory:
        Memory limit for the container in Docker notation (e.g., "256m", "1g").
    status:
        Desired lifecycle state for the singleton. If "running", the manager
        will start (or keep) one container alive. If "stopped", it will stop
        the container after creation/rediscovery.
    """

    cpu: str
    memory: str
    status: Literal["running", "stopped"] = "running"


class StartContainerRequest(BaseModel):
    """Request body for creating/ensuring a singleton container for an image.

    Attributes
    ----------
    image:
        Image reference to run (e.g., "nginx:alpine" or "repo/app:1.2.3").
        This value is also used as the label value `orchestrator.image=<image>`
        so the instance can be rediscovered after restarts.
    min_replicas / max_replicas:
        Stored for future scaling stages. In Step‑1 only the singleton is used.
    env:
        Environment variables to inject into the container process.
    ports:
        Mapping of container ports to host ports using Docker SDK format.
        Example: {"80/tcp": 0} publishes container port 80 to a random host port.
    resources:
        CPU/memory limits and desired status (see :class:`Resources`).
    """

    image: str
    min_replicas: int = Field(ge=0, default=1)
    max_replicas: int = Field(ge=1, default=5)
    env: Dict[str, str] = Field(default_factory=dict)
    ports: Dict[str, int] = Field(default_factory=dict)
    resources: Resources

class Caps(BaseModel):
    cpu: str
    mem: str
    weight: int = 1

class ServiceView(BaseModel):
    id: str                      # your “website name” (see mapping below)
    image_id: str                # the image reference, e.g. "nginx:alpine"
    host: str                    # "127.0.0.1"
    port: Optional[int]          # published host port (if any)
    status: Literal["up","down","degraded"]
    caps: Caps

# Optional: let caller supply a friendly service id and weight
class StartContainerRequest(BaseModel):
    image: str
    min_replicas: int = Field(ge=0, default=1)
    max_replicas: int = Field(ge=1, default=5)
    env: Dict[str, str] = Field(default_factory=dict)
    ports: Dict[str, int] = Field(default_factory=dict)
    resources: Resources
    service_id: Optional[str] = None         # NEW (website name)
    weight: int = 1                          # NEW (routing weight)
class ScaleRequest(BaseModel):
    """Target scale boundaries to persist for an image (future stages)."""

    min_replicas: int = Field(ge=0)
    max_replicas: int = Field(ge=1)


class PatchContainerRequest(BaseModel):
    """Patch one container's desired runtime status (running/stopped)."""

    status: Literal["running", "stopped"]


# ------------------ FastAPI app & routes ------------------
app = FastAPI(title="Orchestrator", version="0.2")
manager = ContainerManager()
def _first_host_port(ports: dict) -> Optional[int]:
    for bindings in (ports or {}).values():
        if isinstance(bindings, list) and bindings:
            try:
                return int(bindings[0].get("HostPort"))
            except Exception:
                pass
    return None

def _probe_health(port: Optional[int]) -> Optional[bool]:
    if not port:
        return None
    try:
        import httpx
        r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.5)
        return r.status_code == 200
    except Exception:
        return False

def _status_from(docker_status: str, app_healthy: Optional[bool]) -> Literal["up","down","degraded"]:
    if docker_status != "running":
        return "down"
    if app_healthy is True:
        return "up"
    return "degraded"

def _first_host_port(ports: dict) -> Optional[int]:
    for bindings in (ports or {}).values():
        if isinstance(bindings, list) and bindings:
            try:
                return int(bindings[0].get("HostPort"))
            except Exception:
                pass
    return None

def _status_from(summary_status: str, app_healthy: Optional[bool]) -> Literal["up","down","degraded"]:
    if summary_status != "running":
        return "down"
    if app_healthy is True:
        return "up"
    # running but app health probe failed/unknown
    return "degraded"
@app.get("/health")
def health() -> dict:
    """Liveness endpoint for probes and simple diagnostics.

    Returns
    -------
    dict
        `{ "ok": True }` if the API process is up.
    """

    return {"ok": True}


@app.post("/start/container", response_model=ServiceView)
def start_container(body: StartContainerRequest) -> ServiceView:
    # register desired state
    manager.register_desired_state(
        body.image,
        min_replicas=body.min_replicas,
        max_replicas=body.max_replicas,
        env=body.env,
        ports=body.ports,
        resources=body.resources.model_dump(),
    )

    # launch
    result = manager.ensure_singleton_for_image(
        body.image, env=body.env, ports=body.ports, resources=body.resources.model_dump()
    )
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

    # extract port + status
    host_port = _first_host_port(result.get("ports") or {})
    app_healthy = _probe_health(host_port)

    service_name = body.service_id or body.image.split(":")[0]
    return ServiceView(
        id=service_name,
        image_id=body.image,
        host="127.0.0.1",
        port=host_port,
        status=_status_from(result.get("status",""), app_healthy),
        caps=Caps(cpu=body.resources.cpu, mem=body.resources.memory, weight=body.weight),
    )

@app.post("/images/{image}/scale")
def scale_image(image: str, body: ScaleRequest) -> dict:
    """Persist scale boundaries for an image (min/max replicas).

    Notes
    -----
    In Step‑1 this doesn't create multiple instances; it simply stores the
    desired range for later stages. If your `ContainerManager.scale` already
    implements spawning/tearing down replicas, this endpoint will call it.

    Raises
    ------
    HTTPException(500)
        If the manager returns a failed result.
    """

    res = manager.scale(image, min_replicas=body.min_replicas, max_replicas=body.max_replicas)
    if not res.get("ok"):
        raise HTTPException(status_code=500, detail="scale-failed")
    return res


@app.post("/images/{image}/reconcile")
def reconcile_image(image: str) -> dict:
    """Bring current containers for an image in line with desired state.

    Typically ensures the count/status match what was set via `/start/container`
    and `/images/{image}/scale`.
    """

    res = manager.reconcile(image)
    if not res.get("ok"):
        raise HTTPException(status_code=500, detail="reconcile-failed")
    return res


@app.get("/images/{image}/containers")
def list_image_containers(image: str) -> dict:
    """List Docker summaries for all containers labeled for this image."""

    return {"image": image, "containers": manager.get_containers_for_image(image)}


@app.get("/containers", response_model=List[ServiceView])
def list_containers() -> List[ServiceView]:
    summaries = manager.list_managed_containers()
    views: List[ServiceView] = []

    for summary in summaries:
        image = summary["image"]
        desired = manager.desired_images.get(image, {})
        cpu = desired.get("resources", {}).get("cpu", "0.5")
        mem = desired.get("resources", {}).get("memory", "256m")
        weight = desired.get("resources", {}).get("weight", 1)
        service_name = desired.get("service_id") or image.split(":")[0]

        host_port = _first_host_port(summary.get("ports") or {})
        app_healthy = _probe_health(host_port)

        views.append(ServiceView(
            id=service_name,
            image_id=image,
            host="127.0.0.1",
            port=host_port,
            status=_status_from(summary.get("status",""), app_healthy),
            caps=Caps(cpu=cpu, mem=mem, weight=weight),
        ))

    return views



@app.get("/images/{image}/health")
def image_health(image: str) -> dict:
    """Return per-container health/metrics for the given image.

    For each container, the manager tries to report:
      * `server_alive` – process/container liveness
      * `cpu_percent`, `mem_percent` – instantaneous usage from Docker stats
      * `fs_free_bytes` – free space where available
    """

    items = []
    for summary in manager.get_containers_for_image(image):
        stats = manager.container_stats(summary["container_id"])
        items.append({
            "container_id": summary["container_id"],
            "name": summary["name"],
            "status": summary["status"],
            "ports": summary["ports"],
            "server_alive": stats.get("server_alive") if stats.get("ok") else None,
            "cpu_percent": stats.get("cpu_percent") if stats.get("ok") else None,
            "mem_percent": stats.get("mem_percent") if stats.get("ok") else None,
            "fs_free_bytes": stats.get("fs_free_bytes") if stats.get("ok") else None,
        })
    return {"image": image, "health": items}


@app.patch("/containers/{name_or_id}")
def patch_container(name_or_id: str, body: PatchContainerRequest) -> dict:
    """Set one container's runtime status.

    Parameters
    ----------
    name_or_id:
        Docker name or ID of the target container (visible in `/containers`).

    Raises
    ------
    HTTPException(404)
        If the container cannot be found.
    HTTPException(400)
        If Docker returns an error while changing status.
    """

    res = manager.set_container_status(name_or_id, status=body.status)
    if not res.get("ok"):
        if res.get("error") == "not-found":
            raise HTTPException(status_code=404, detail=f"Container '{name_or_id}' not found")
        raise HTTPException(status_code=400, detail=res.get("error", "failed"))
    return res


@app.delete("/containers/{name_or_id}")
def delete_container(name_or_id: str, force: bool = False) -> dict:
    """Delete a container by name or ID.

    Parameters
    ----------
    name_or_id:
        Docker name or container ID.
    force:
        If True, forcibly remove even if running (maps to `docker rm -f`).

    Raises
    ------
    HTTPException(404)
        If the container is not found.
    HTTPException(400)
        For other Docker/manager errors.
    """

    result = manager.delete_container(name_or_id, force=force)
    if not result.get("deleted"):
        if result.get("error") == "not-found":
            raise HTTPException(status_code=404, detail=f"Container '{name_or_id}' not found")
        raise HTTPException(status_code=400, detail=result.get("error", "failed"))
    return result


@app.get("/images")
def desired_state() -> dict:
    """Expose the in-memory desired-state map to help the UI/debugging.

    Returns
    -------
    dict
        List of desired-state entries (image, min/max, env, ports, resources).
    """

    return {"images": list(manager.desired_images.values())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
