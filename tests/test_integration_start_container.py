# tests/test_integration_start_container.py
import sys
import time
import pathlib
import importlib.util
import os
import uuid
import pytest
import docker
from fastapi.testclient import TestClient

# Add the project root to Python path so we can import modules
project_root = pathlib.Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from container_manager import ContainerManager  # noqa: E402


IMAGE = "nginx:alpine"          # imageId used in the new API
MEM = "128m"                    # small mem limit for tests
CPU = "0.25"                    # quarter CPU


def _docker_or_skip():
    """Return a docker client or skip tests if Docker is unavailable."""
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception as e:
        pytest.skip(f"Docker not available: {e}")


def _load_app_module():
    """
    Load the API module dynamically without clashing with the 'fastapi' package.
    1) If ORCH_APP_FILE env var is set -> use that path.
    2) Otherwise, search common filenames/locations.
    """
    project_root = pathlib.Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # 1) env override (absolute or relative to project root)
    env_path = os.getenv("ORCH_APP_FILE")
    if env_path:
        target = (project_root / env_path).resolve() if not os.path.isabs(env_path) else pathlib.Path(env_path)
        if not target.exists():
            raise FileNotFoundError(f"ORCH_APP_FILE points to non-existing file: {target}")
    else:
        # 2) search common candidates
        candidates = [
            project_root / "fast_api.py",
            project_root / "api.py",
            project_root / "app.py",
            project_root / "main.py",
            project_root / "server.py",
            project_root / "src" / "fast_api.py",
            project_root / "src" / "api.py",
            project_root / "orchestrator" / "fast_api.py",
            project_root / "orchestrator" / "api.py",
        ]
        target = next((p for p in candidates if p.exists()), None)
        if target is None:
            looked = "\n  - ".join(str(p) for p in candidates)
            raise FileNotFoundError(
                "Could not find your API module.\n"
                "Set ORCH_APP_FILE to its path or place it at one of:\n  - " + looked
            )

    modname = f"orchestrator_api_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(modname, target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore

    # sanity: module should expose 'app' and 'manager'
    if not hasattr(module, "app"):
        raise AttributeError(f"{target} must define 'app = FastAPI(...)'")
    if not hasattr(module, "manager"):
        raise AttributeError(f"{target} must define 'manager = ContainerManager()'")

    return module


@pytest.fixture(scope="module")
def dclient():
    return _docker_or_skip()


@pytest.fixture(scope="module")
def app_module():
    return _load_app_module()


@pytest.fixture(autouse=True)
def cleanup_managed_containers(dclient, app_module):
    """
    Before & after each test, remove any containers we manage for IMAGE (by label).
    """
    label_key = app_module.manager.LABEL_KEY

    def _prune():
        for c in dclient.containers.list(all=True, filters={"label": f"{label_key}={IMAGE}"}):
            try:
                c.remove(force=True)
            except Exception:
                pass

    _prune()
    yield
    _prune()


def test_start_container_creates_and_runs(app_module, dclient):
    client = TestClient(app_module.app)

    # Start one container with resource hints (mapped by the server to docker args)
    payload = {
        "count": 1,
        "resources": {"cpu_limit": CPU, "memory_limit": MEM}
    }
    r = client.post(f"/containers/{IMAGE}/start", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "started" in data and isinstance(data["started"], list) and len(data["started"]) == 1
    cid = data["started"][0]

    # Verify with Docker that the container exists and is running
    c = dclient.containers.get(cid)
    c.reload()
    assert c.status == "running"


def test_instances_lists_created_instance(app_module, dclient):
    client = TestClient(app_module.app)

    # Create one
    r = client.post(f"/containers/{IMAGE}/start", json={"count": 1})
    assert r.status_code == 200
    cid = r.json()["started"][0]

    # List instances for this image
    r2 = client.get(f"/containers/{IMAGE}/instances")
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert "instances" in data and isinstance(data["instances"], list)
    # find the one we just created
    inst = next((i for i in data["instances"] if i.get("id") == cid), None)
    assert inst is not None
    # contract fields
    assert set(inst.keys()) >= {"id", "status", "endpoint"}  # resources is optional
    assert inst["status"] in ("running", "stopped")
    assert isinstance(inst["endpoint"], str)


def test_health_endpoint_returns_fields(app_module, dclient):
    client = TestClient(app_module.app)
    # Ensure one running instance
    r = client.post(f"/containers/{IMAGE}/start", json={"count": 1})
    cid = r.json()["started"][0]

    r2 = client.get(f"/containers/instances/{cid}/health")
    assert r2.status_code == 200, r2.text
    body = r2.json()

    # Contract shape
    assert set(body.keys()) >= {"cpu_usage", "memory_usage", "disk_usage", "status"}
    assert isinstance(body["cpu_usage"], (int, float))
    assert isinstance(body["memory_usage"], (int, float))
    assert isinstance(body["disk_usage"], (int, float))
    assert body["status"] in ("healthy", "warning", "critical", "stopped")
    # errors is optional; if present must be a list
    if "errors" in body:
        assert isinstance(body["errors"], list)


def test_stop_container_and_verify_docker_state(app_module, dclient):
    client = TestClient(app_module.app)

    r = client.post(f"/containers/{IMAGE}/start", json={"count": 1})
    cid = r.json()["started"][0]

    # Stop via new API
    r2 = client.post(f"/containers/{IMAGE}/stop", json={"instanceId": cid})
    assert r2.status_code == 200, r2.text
    assert r2.json().get("stopped") is True

    # Give Docker a moment to reflect the stopped state
    time.sleep(0.5)
    c = dclient.containers.get(cid)
    c.reload()
    # stopped containers report as 'exited' (or rarely 'created')
    assert c.status in ("exited", "created")


def test_delete_container_running(app_module, dclient):
    """
    Start a RUNNING container and delete it using the new DELETE body.
    Expect 200 and that the container is gone.
    """
    client = TestClient(app_module.app)

    # Start
    r = client.post(f"/containers/{IMAGE}/start", json={"count": 1})
    cid = r.json()["started"][0]

    # Delete via new API (body carries instanceId). Starlette's .delete() has no json kwarg.
    resp = client.request("DELETE", f"/containers/{IMAGE}", json={"instanceId": cid})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("deleted") is True

    with pytest.raises(docker.errors.NotFound):
        dclient.containers.get(cid)


def test_delete_container_not_found_returns_404(app_module):
    """
    Deleting a non-existent container should return 404 per the new API.
    """
    client = TestClient(app_module.app)
    resp = client.request("DELETE", f"/containers/{IMAGE}", json={"instanceId": "this-id-should-not-exist-xyz"})
    assert resp.status_code == 404
    assert "not found" in resp.json().get("detail", "").lower()
