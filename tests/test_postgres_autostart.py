import os, sys, time, uuid, pathlib, importlib.util, json
import pytest, docker, psycopg
from fastapi.testclient import TestClient

IMAGE = "nginx:alpine"
MEM = "128m"
CPU = "0.25"
PG_IMAGE = "postgres:16"
LABEL = "orch-test-pg"

def _docker_or_skip():
    try:
        client = docker.from_env(); client.ping(); return client
    except Exception as e:
        pytest.skip(f"Docker not available: {e}")

def _start_pg(dclient):
    # pull if needed
    try: dclient.images.get(PG_IMAGE)
    except Exception: dclient.images.pull(PG_IMAGE)

    name = f"{LABEL}-{uuid.uuid4().hex[:8]}"
    pw = "postgres"
    c = dclient.containers.run(
        PG_IMAGE, name=name, detach=True,
        environment={"POSTGRES_PASSWORD": pw, "POSTGRES_DB": "orchestrator", "POSTGRES_USER": "postgres"},
        ports={"5432/tcp": None}, labels={LABEL: "1"},
    )
    # discover host port
    host_port = None
    for _ in range(60):
        c.reload()
        ports = ((c.attrs.get("NetworkSettings") or {}).get("Ports") or {}).get("5432/tcp") or []
        if ports and ports[0].get("HostPort"):
            host_port = int(ports[0]["HostPort"]); break
        time.sleep(0.25)
    if not host_port:
        try: c.remove(force=True)
        finally: pytest.skip("Failed to map Postgres port")

    dsn = f"postgresql://postgres:{pw}@127.0.0.1:{host_port}/orchestrator"

    # wait until ready
    ok = False
    for _ in range(80):
        try:
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            ok = True; break
        except Exception:
            time.sleep(0.25)
    if not ok:
        try: c.remove(force=True)
        finally: pytest.skip("Postgres did not become ready in time")

    return c, dsn

def _load_app():
    project_root = pathlib.Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path: sys.path.insert(0, str(project_root))
    target = project_root / "app.py"
    if not target.exists(): pytest.skip("app.py not found")
    modname = f"orch_api_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(modname, target)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)  # type: ignore
    assert hasattr(module, "app") and hasattr(module, "manager")
    return module

@pytest.fixture(scope="session")
def dclient(): return _docker_or_skip()

@pytest.fixture(scope="session")
def pg(dclient):
    c, dsn = _start_pg(dclient)
    os.environ["POSTGRES_URL"] = dsn
    yield c, dsn
    try: c.remove(force=True)
    except Exception: pass

@pytest.fixture(scope="session")
def app_module(pg):  # import AFTER POSTGRES_URL is set
    return _load_app()

@pytest.fixture(autouse=True)
def cleanup_each_test(dclient, app_module, pg):
    label_key = app_module.manager.LABEL_KEY
    # db connect
    _, dsn = pg
    def _prune():
        # containers
        for c in dclient.containers.list(all=True, filters={"label": f"{label_key}={IMAGE}"}):
            try: c.remove(force=True)
            except Exception: pass
        # db rows
        with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE image=%s", (IMAGE,))
            cur.execute("DELETE FROM desired_images WHERE image=%s", (IMAGE,))
    _prune(); yield; _prune()

def _wait(assert_fn, timeout=12.0, interval=0.25, msg="condition not met"):
    start = time.time(); last=None
    while time.time() - start < timeout:
        try: assert_fn(); return
        except AssertionError as e: last=e
        time.sleep(interval)
    raise AssertionError(f"{msg}: {last}")

def test_pg_events_and_desired(app_module, pg):
    client = TestClient(app_module.app)
    _, dsn = pg

    # start 1
    r = client.post(f"/containers/{IMAGE}/start", json={"count":1, "resources":{"cpu_limit":CPU,"memory_limit":MEM}})
    assert r.status_code == 200, r.text
    cid = r.json()["started"][0]

    # check desired_images + events in DB
    def _assert_desired():
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT min_replicas,max_replicas,resources FROM desired_images WHERE image=%s", (IMAGE,))
            row = cur.fetchone(); assert row is not None
            assert row[0] == 1 and row[1] == 1
            res = row[2] or {}
            assert res.get("cpu_limit") == CPU and res.get("memory_limit") == MEM
    _wait(_assert_desired, msg="desired_images not upserted")

    def _has(kind):
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM events WHERE image=%s AND container_id=%s AND event=%s",
                        (IMAGE, cid, kind))
            return cur.fetchone()[0] >= 1

    _wait(lambda: (_has("create") or _has("start")), msg="missing create/start event")

    # stop -> event
    r2 = client.post(f"/containers/{IMAGE}/stop", json={"instanceId": cid})
    assert r2.status_code == 200
    _wait(lambda: _has("stop"), msg="missing stop event")

    # remove -> event
    r3 = client.request("DELETE", f"/containers/{IMAGE}", json={"instanceId": cid})
    assert r3.status_code == 200
    _wait(lambda: _has("remove"), msg="missing remove event")

    # /events endpoint reflects them
    r4 = client.get(f"/events?image={IMAGE}&limit=50")
    kinds = {e.get("event") for e in r4.json().get("events", [])}
    assert ("create" in kinds or "start" in kinds) and "stop" in kinds and "remove" in kinds
