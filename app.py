"""
FastAPI layer that exposes container orchestration endpoints and delegates
all Docker logic to ContainerManager.

Run:
    uvicorn fast_api:app --reload

Quick demo (Stage 1..3):
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
from typing import Dict, Literal, Optional, List, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from container_manager import ContainerManager


# ------------------ Pydantic schemas ------------------

class Resources(BaseModel):
    cpu: str                  # CPU quota, e.g., "0.5" or "500m"
    memory: str               # Docker memory string, e.g., "512m", "1g"
    status: Literal["running", "stopped"] = "running"


class StartContainerRequest(BaseModel):
    image: str
    min_replicas: int = Field(ge=0, default=1)
    max_replicas: int = Field(ge=1, default=5)
    env: Dict[str, str] = Field(default_factory=dict)
    ports: Dict[str, int] = Field(default_factory=dict)   # containerPort/proto -> hostPort (0 for random)
    resources: Resources


class ScaleRequest(BaseModel):
    min_replicas: int = Field(ge=0)
    max_replicas: int = Field(ge=1)


class PatchContainerRequest(BaseModel):
    status: Literal["running", "stopped"]


# ------------------ FastAPI app & routes ------------------

app = FastAPI(title="Orchestrator", version="0.2")
manager = ContainerManager()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/start/container")
def start_container(body: StartContainerRequest):
    """
    Ensure at least one managed container exists for the given image and
    persist desired state (min/max/env/ports/resources).
    """
    manager.register_desired_state(
        body.image,
        min_replicas=body.min_replicas,
        max_replicas=body.max_replicas,
        env=body.env,
        ports=body.ports,
        resources=body.resources.model_dump()
    )

    result = manager.ensure_singleton_for_image(
        body.image,
        env=body.env,
        ports=body.ports,
        resources=body.resources.model_dump()
    )

    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result


@app.post("/images/{image}/scale")
def scale_image(image: str, body: ScaleRequest):
    res = manager.scale(image, min_replicas=body.min_replicas, max_replicas=body.max_replicas)
    if not res.get("ok"):
        raise HTTPException(status_code=500, detail="scale-failed")
    return res


@app.post("/images/{image}/reconcile")
def reconcile_image(image: str):
    res = manager.reconcile(image)
    if not res.get("ok"):
        raise HTTPException(status_code=500, detail="reconcile-failed")
    return res


@app.get("/images/{image}/containers")
def list_image_containers(image: str):
    return {"image": image, "containers": manager.get_containers_for_image(image)}


@app.get("/containers")
def list_containers():
    """List all containers managed by this orchestrator (by label)."""
    return {"containers": manager.list_managed_containers()}


@app.get("/images/{image}/health")
def image_health(image: str):
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
def patch_container(name_or_id: str, body: PatchContainerRequest):
    res = manager.set_container_status(name_or_id, status=body.status)
    if not res.get("ok"):
        if res.get("error") == "not-found":
            raise HTTPException(status_code=404, detail=f"Container '{name_or_id}' not found")
        raise HTTPException(status_code=400, detail=res.get("error", "failed"))
    return res


@app.delete("/containers/{name_or_id}")
def delete_container(name_or_id: str, force: bool = False):
    """
    Delete a container by name or ID.
    """
    result = manager.delete_container(name_or_id, force=force)
    if not result.get("deleted"):
        if result.get("error") == "not-found":
            raise HTTPException(status_code=404, detail=f"Container '{name_or_id}' not found")
        raise HTTPException(status_code=400, detail=result.get("error", "failed"))
    return result


@app.get("/images")
def desired_state():
    """
    OPTIONAL: Expose in-memory desired-state entries to help the UI.
    Format mirrors ContainerManager.desired_images.
    """
    return {"images": list(manager.desired_images.values())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fast_api:app", host="0.0.0.0", port=8000, reload=True)