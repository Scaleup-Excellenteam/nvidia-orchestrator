# ContainerManager - מדריך מפורט לקוד

## 📋 **מבט כללי**

`ContainerManager` הוא הלב של המערכת - הוא מנהל את כל האינטראקציות עם Docker ומשמר את המצב הרצוי של containers.

---

## 🏗️ **מבנה המחלקה**

### **המחלקה הראשית:**
```python
class ContainerManager:
    LABEL_KEY = "orchestrator.image"  # תג לכל container מנוהל
```

### **מה המחלקה עושה:**
1. **מנהל containers** - יוצר, מפעיל, עוצר, מוחק
2. **שומר desired state** - מה אנחנו רוצים שיהיה
3. **מבצע reconciliation** - מוודא שהמצב בפועל תואם לרצוי
4. **מטפל ב-resources** - CPU, memory, ports
5. **שולח notifications** - service discovery callbacks

---

## 🔧 **Constructor ו-Initialization**

### **שורות 35-42:**
```python
def __init__(
    self,
    client: Optional[docker.DockerClient] = None,
    client_factory=None,
) -> None:
    # Do NOT talk to Docker during import; connect only when first needed.
    self._client: Optional[docker.DockerClient] = client
    self._client_factory = client_factory or docker.from_env

    # Super-simple desired-state store (swap to DB later if needed).
    self.desired_images: Dict[str, Dict[str, Any]] = {}  # image -> config dict
    # Optional bookkeeping (we mostly rely on labels for rediscovery).
    self._tracked: Dict[str, List[str]] = {}
```

### **מה זה עושה:**
1. **Lazy Docker Connection** - לא מתחבר ל-Docker עד שצריך
2. **Client Injection** - מאפשר להזריק Docker client חיצוני (לבדיקות)
3. **Desired State Store** - מילון פשוט בזיכרון (להחליף לדאטהבייס בהמשך)
4. **Container Tracking** - מעקב אחר containers (אופציונלי)

### **למה זה חשוב:**
- **לא block על import** - השרת עולה מהר
- **Testable** - אפשר להזריק mock Docker client
- **Flexible** - עובד עם Docker client חיצוני

---

## 🚀 **Internal Methods (שורות 44-75)**

### **1. `_cli()` - Docker Client Getter:**
```python
def _cli(self) -> docker.DockerClient:
    """Get (or lazily create) the Docker client."""
    if self._client is None:
        self._client = self._client_factory()
    return self._client
```

**מה זה עושה:**
- **Lazy Loading** - יוצר Docker client רק כשצריך
- **Singleton Pattern** - אותו client לכל החיים
- **Error Handling** - אם יש בעיה, זה קורה רק כשמנסים להשתמש

**למה זה טוב:**
- **Performance** - לא מתחבר ל-Docker אם לא צריך
- **Reliability** - אם Docker לא עובד, השרת עדיין עולה

### **2. `_discovery_callback_url()` - Service Discovery URL:**
```python
def _discovery_callback_url(self, image: str) -> Optional[str]:
    return (self.desired_images.get(image) or {}).get("env", {}).get("DISCOVERY_CALLBACK")
```

**מה זה עושה:**
- **מחפש URL** של service discovery callback
- **Chain of gets** - בטוח גם אם אין env או DISCOVERY_CALLBACK
- **Optional** - מחזיר None אם אין callback

**דוגמה:**
```python
# אם יש:
desired_images = {
    "nginx": {
        "env": {"DISCOVERY_CALLBACK": "http://localhost:9000/register"}
    }
}

# אז:
_discovery_callback_url("nginx")  # מחזיר "http://localhost:9000/register"
_discovery_callback_url("redis")   # מחזיר None
```

### **3. `_notify_discovery()` - Service Discovery Notification:**
```python
def _notify_discovery(self, *, image: str, c, status: str, event: str) -> None:
    """
    Optional best-effort callback for Service Discovery / LB demos.
    Payload: {image, container_id, name, host, ports, status, event}
    """
    url = self._discovery_callback_url(image)
    if not url:
        return
    try:
        host = socket.gethostname()
        payload = {
            "image": image,
            "container_id": c.id,
            "name": c.name,
            "host": host,
            "ports": (c.attrs.get("NetworkSettings", {}) or {}).get("Ports", {}),
            "status": status,
            "event": event,
        }
        requests.post(url, json=payload, timeout=2)
    except Exception:
        # demo-only, ignore failures
        pass
```

**מה זה עושה:**
1. **בודק אם יש callback URL** - אם לא, לא עושה כלום
2. **יוצר payload** - מידע על ה-container
3. **שולח HTTP POST** - לשרת service discovery
4. **Error Handling** - לא נכשל אם השרת לא זמין

**Payload שנשלח:**
```json
{
  "image": "nginx:alpine",
  "container_id": "abc123",
  "name": "nginx1",
  "host": "server-01",
  "ports": {"80/tcp": [{"HostPort": "8080"}]},
  "status": "running",
  "event": "create"
}
```

**למה זה חשוב:**
- **Service Discovery** - Load Balancer יודע על containers חדשים
- **Monitoring** - מעקב אחר שינויים
- **Demo Friendly** - קל להראות איך הכל עובד

---

## 📊 **Desired State Methods (שורות 77-95)**

### **`register_desired_state()` - שמירת מצב רצוי:**
```python
def register_desired_state(
    self,
    image: str,
    *,
    min_replicas: int,
    max_replicas: int,
    env: Dict[str, str],
    ports: Dict[str, int],
    resources: Dict[str, Any],
) -> None:
    """
    Save/refresh what's desired for a given image so other modules can query it
    or so you can implement /scale next.
    """
    self.desired_images[image] = {
        "image": image,
        "min_replicas": min_replicas,
        "max_replicas": max_replicas,
        "env": env or {},
        "ports": ports or {},
        "resources": resources or {},
    }
    self._tracked.setdefault(image, [])
```

**מה זה עושה:**
1. **שומר desired state** - מה אנחנו רוצים שיהיה
2. **מעדכן אם קיים** - או יוצר חדש
3. **מאתחל tracking** - רשימה ריקה של containers

**דוגמה:**
```python
manager.register_desired_state(
    image="nginx:alpine",
    min_replicas=1,
    max_replicas=3,
    env={"PORT": "80"},
    ports={"80/tcp": 0},
    resources={"cpu": "500m", "memory": "256m"}
)

# התוצאה:
# desired_images = {
#     "nginx:alpine": {
#         "image": "nginx:alpine",
#         "min_replicas": 1,
#         "max_replicas": 3,
#         "env": {"PORT": "80"},
#         "ports": {"80/tcp": 0},
#         "resources": {"cpu": "500m", "memory": "256m"}
#     }
# }
```

**למה זה חשוב:**
- **Configuration Management** - שומר הגדרות
- **Scaling** - יודע כמה containers צריך
- **Persistence** - המידע נשמר בין requests

---

## 🔍 **Query & Helper Methods (שורות 97-180)**

### **1. `_current_for_image()` - מציאת containers קיימים:**
```python
def _current_for_image(self, image: str, running_only: bool = False):
    """
    Find existing containers for this image by label.
    running_only=False -> include stopped/exited (all=True)
    running_only=True  -> only running
    """
    cli = self._cli()
    flt = {"label": f"{self.LABEL_KEY}={image}"}
    if running_only:
        return cli.containers.list(filters=flt)
    return cli.containers.list(all=True, filters=flt)
```

**מה זה עושה:**
1. **מחפש containers** לפי תג `orchestrator.image=<image>`
2. **Filtering** - רק containers עם התג הנכון
3. **Running vs All** - יכול להחזיר רק running או הכל

**דוגמה:**
```python
# אם יש containers:
# - nginx1 (running) עם label: orchestrator.image=nginx:alpine
# - nginx2 (stopped) עם label: orchestrator.image=nginx:alpine
# - redis1 (running) עם label: orchestrator.image=redis:alpine

_current_for_image("nginx:alpine", running_only=True)   # [nginx1]
_current_for_image("nginx:alpine", running_only=False)  # [nginx1, nginx2]
_current_for_image("redis:alpine", running_only=True)   # [redis1]
```

**למה זה חשוב:**
- **Rediscovery** - מוצא containers גם אחרי restart
- **State Management** - יודע מה יש בפועל
- **Scaling Decisions** - יכול להחליט אם צריך יותר containers

### **2. `_normalize_ports()` - נרמול פורטים:**
```python
@staticmethod
def _normalize_ports(ports: Dict[str, int]) -> Optional[Dict[str, Optional[int]]]:
    """
    Convert {"5678/tcp": 0} -> {"5678/tcp": None} so Docker allocates a free host port.
    Return None if ports is empty (no -p).
    """
    if not ports:
        return None
    out: Dict[str, Optional[int]] = {}
    for cport, hport in ports.items():
        out[cport] = None if (hport is None or hport == 0) else hport
    return out
```

**מה זה עושה:**
1. **ממיר פורטים** - `0` או `None` הופך ל-`None`
2. **Docker Port Allocation** - `None` = Docker בוחר פורט חופשי
3. **Empty Handling** - מחזיר `None` אם אין פורטים

**דוגמה:**
```python
_normalize_ports({"80/tcp": 0})      # {"80/tcp": None} - Docker בוחר פורט
_normalize_ports({"80/tcp": 8080})   # {"80/tcp": 8080} - פורט ספציפי
_normalize_ports({})                 # None - אין פורטים
```

**למה זה חשוב:**
- **Dynamic Ports** - לא צריך לדעת איזה פורט פנוי
- **Port Conflicts** - מונע התנגשויות
- **Docker Integration** - עובד עם Docker port mapping

### **3. `_summarize_container()` - סיכום container:**
```python
@staticmethod
def _summarize_container(c) -> Dict[str, Any]:
    """
    Produce a response-friendly dict about the container (id/name/status/port bindings).
    """
    c.reload()
    return {
        "container_id": c.id,
        "name": c.name,
        "status": c.status,
        # Host port bindings live under NetworkSettings->Ports
        "ports": (c.attrs.get("NetworkSettings", {}) or {}).get("Ports", {}),
    }
```

**מה זה עושה:**
1. **Container Info** - מחזיר מידע בסיסי על container
2. **Port Mapping** - איזה פורטים מחוברים
3. **Response Format** - פורמט מתאים ל-API

**דוגמה:**
```python
# התוצאה:
{
    "container_id": "abc123def456",
    "name": "nginx1",
    "status": "running",
    "ports": {
        "80/tcp": [
            {
                "HostIp": "0.0.0.0",
                "HostPort": "8080"
            }
        ]
    }
}
```

**למה זה חשוב:**
- **API Responses** - מידע ברור למשתמש
- **Port Discovery** - יודע איך להתחבר ל-container
- **Status Monitoring** - רואה מה המצב

### **4. `_cpu_to_nano_cpus()` - המרת CPU:**
```python
@staticmethod
def _cpu_to_nano_cpus(cpu_value: Any) -> Optional[int]:
    """
    Translate a user CPU value to Docker's nano_cpus (int).
    Accepts strings like "0.5", "1", "0", or Kubernetes-like "500m".
    """
    if cpu_value is None:
        return None
    try:
        s = str(cpu_value).strip().lower()
        if s.endswith("m"):              # e.g., "500m" => 0.5
            milli = float(s[:-1])
            v = milli / 1000.0
        else:
            v = float(s)
        return int(v * 1_000_000_000) if v > 0 else None
    except Exception:
        return None
```

**מה זה עושה:**
1. **CPU Conversion** - ממיר ערכים אנושיים ל-Docker nano_cpus
2. **Multiple Formats** - תומך ב-"0.5", "500m", "1"
3. **Error Handling** - מחזיר None אם יש בעיה

**דוגמה:**
```python
_cpu_to_nano_cpus("0.5")    # 500_000_000 (0.5 CPU)
_cpu_to_nano_cpus("500m")   # 500_000_000 (500 millicores)
_cpu_to_nano_cpus("1")      # 1_000_000_000 (1 CPU)
_cpu_to_nano_cpus("0")      # None (no limit)
```

**למה זה חשוב:**
- **Resource Limits** - מגביל CPU לכל container
- **User Friendly** - משתמשים יכולים לכתוב "500m"
- **Docker Integration** - עובד עם Docker CPU limits

### **5. `_ports_ready()` ו-`_wait_for_ports()` - בדיקת פורטים:**
```python
@staticmethod
def _ports_ready(c, expect_keys: Optional[List[str]] = None) -> bool:
    ports = (c.attrs.get("NetworkSettings", {}) or {}).get("Ports") or {}
    if not ports:
        return False
    if expect_keys:
        for k in expect_keys:
            v = ports.get(k)
            if not isinstance(v, list) or len(v) == 0:
                return False
        return True
    # no explicit expectation -> at least one non-empty binding
    return any(isinstance(v, list) and len(v) > 0 for v in ports.values())

def _wait_for_ports(self, c, expect_keys: Optional[List[str]], timeout: float = 5.0, interval: float = 0.1):
    """
    Reload until host-port bindings appear (needed on Desktop/macOS right after run/start).
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        c.reload()
        if self._ports_ready(c, expect_keys):
            return
        time.sleep(interval)
    # best effort; return regardless
```

**מה זה עושה:**
1. **Port Readiness Check** - בודק אם פורטים מוכנים
2. **Waiting Loop** - מחכה עד שפורטים מופיעים
3. **Timeout Protection** - לא מחכה לנצח

**למה זה חשוב:**
- **Port Binding** - Docker לפעמים לוקח זמן לחבר פורטים
- **Desktop Issues** - במיוחד על macOS/Windows
- **Reliability** - לא מחזיר ports לפני שהם מוכנים

---

## 🚀 **Core Action Methods (שורות 182-280)**

### **1. `_run_new_container()` - יצירת container חדש:**
```python
def _run_new_container(
    self,
    image: str,
    *,
    env: Dict[str, str],
    ports: Dict[str, int],
    resources: Dict[str, Any],
) -> Dict[str, Any]:
    """Always create a new managed container for `image`."""
    cli = self._cli()
    desired_status = (resources or {}).get("status", "running")
    expect_keys = list((ports or {}).keys()) or None

    try:
        cli.images.pull(image)
    except Exception:
        pass  # fine if already local/offline

    mem_limit = (resources or {}).get("memory")
    nano_cpus = self._cpu_to_nano_cpus((resources or {}).get("cpu"))
    port_map = self._normalize_ports(ports)

    try:
        c = cli.containers.run(
            image,
            detach=True,
            environment=env or None,
            ports=port_map,
            labels={self.LABEL_KEY: image},
            mem_limit=mem_limit,
            nano_cpus=nano_cpus,
            restart_policy={"Name": "unless-stopped"},
        )
        self._tracked.setdefault(image, []).append(c.id)

        if expect_keys:
            self._wait_for_ports(c, expect_keys)

        if desired_status == "stopped":
            c.stop()
            self._notify_discovery(image=image, c=c, status="stopped", event="create")
        else:
            self._notify_discovery(image=image, c=c, status="running", event="create")

        return {"ok": True, "action": "created", "image": image, **self._summarize_container(c)}
    except Exception as e:
        return {"ok": False, "error": f"Failed to run container: {e}"}
```

**מה זה עושה:**
1. **Image Pull** - מוריד image אם צריך
2. **Container Creation** - יוצר container עם כל ההגדרות
3. **Resource Limits** - מגדיר CPU/memory limits
4. **Port Mapping** - מחבר פורטים
5. **Labeling** - מסמן container כמנוהל
6. **Status Control** - מפעיל או עוצר לפי הגדרה
7. **Notification** - שולח callback
8. **Port Waiting** - מחכה שפורטים יהיו מוכנים

**פירוט השלבים:**
```python
# 1. הכנה
desired_status = resources.get("status", "running")  # ברירת מחדל: running
expect_keys = list(ports.keys()) or None            # איזה פורטים לצפות להם

# 2. Image Pull
cli.images.pull(image)  # מוריד אם צריך

# 3. Resource Preparation
mem_limit = resources.get("memory")           # מגבלת זיכרון
nano_cpus = self._cpu_to_nano_cpus(resources.get("cpu"))  # מגבלת CPU
port_map = self._normalize_ports(ports)      # מיפוי פורטים

# 4. Container Creation
c = cli.containers.run(
    image,
    detach=True,                              # רץ ברקע
    environment=env or None,                   # משתני סביבה
    ports=port_map,                           # מיפוי פורטים
    labels={self.LABEL_KEY: image},           # תג לזיהוי
    mem_limit=mem_limit,                      # מגבלת זיכרון
    nano_cpus=nano_cpus,                      # מגבלת CPU
    restart_policy={"Name": "unless-stopped"}, # מדיניות restart
)

# 5. Tracking
self._tracked.setdefault(image, []).append(c.id)

# 6. Port Waiting
if expect_keys:
    self._wait_for_ports(c, expect_keys)

# 7. Status Control
if desired_status == "stopped":
    c.stop()  # עוצר אם צריך

# 8. Notification
self._notify_discovery(image=image, c=c, status=desired_status, event="create")

# 9. Response
return {"ok": True, "action": "created", "image": image, **self._summarize_container(c)}
```

**למה זה חשוב:**
- **Container Lifecycle** - ניהול מלא של containers
- **Resource Management** - שליטה במשאבים
- **Error Handling** - מחזיר errors ברורים
- **Integration** - עובד עם Docker SDK

### **2. `ensure_singleton_for_image()` - וידוא שיש container:**
```python
def ensure_singleton_for_image(
    self,
    image: str,
    *,
    env: Dict[str, str],
    ports: Dict[str, int],
    resources: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Ensure there is at least one managed container for `image`.
    (Used by Stage 1 endpoint; reconciler uses _run_new_container for replicas.)
    """
    cli = self._cli()
    existing = self._current_for_image(image, running_only=False)
    desired_status = (resources or {}).get("status", "running")
    expect_keys = list((ports or {}).keys()) or None

    if existing:
        c = existing[0]
        if desired_status == "running" and c.status != "running":
            c.start()
            if expect_keys:
                self._wait_for_ports(c, expect_keys)
            self._notify_discovery(image=image, c=c, status="running", event="start")
        elif desired_status == "stopped" and c.status == "running":
            c.stop()
            self._notify_discovery(image=image, c=c, status="stopped", event="stop")
        return {
            "ok": True,
            "action": "kept-existing",
            "image": image,
            **self._summarize_container(c),
        }

    # No container exists yet -> create one
    return self._run_new_container(image, env=env, ports=ports, resources=resources)
```

**מה זה עושה:**
1. **Container Discovery** - מחפש containers קיימים
2. **Status Management** - מפעיל/עוצר לפי הגדרה
3. **Port Waiting** - מחכה שפורטים יהיו מוכנים
4. **Container Creation** - יוצר חדש אם צריך
5. **Notification** - שולח callbacks על שינויים

**הלוגיקה:**
```python
# 1. בדיקה אם יש containers
existing = self._current_for_image(image, running_only=False)

# 2. אם יש container קיים
if existing:
    c = existing[0]  # לוקח את הראשון
    
    # אם צריך running אבל הוא לא
    if desired_status == "running" and c.status != "running":
        c.start()  # מפעיל
        # מחכה לפורטים
        if expect_keys:
            self._wait_for_ports(c, expect_keys)
        # שולח notification
        self._notify_discovery(image=image, c=c, status="running", event="start")
    
    # אם צריך stopped אבל הוא רץ
    elif desired_status == "stopped" and c.status == "running":
        c.stop()  # עוצר
        # שולח notification
        self._notify_discovery(image=image, c=c, status="stopped", event="stop")
    
    # מחזיר container קיים
    return {"ok": True, "action": "kept-existing", ...}

# 3. אם אין container -> יוצר חדש
return self._run_new_container(image, env=env, ports=ports, resources=resources)
```

**למה זה חשוב:**
- **Idempotency** - אותו request = אותה תוצאה
- **Resource Efficiency** - לא יוצר duplicates
- **State Consistency** - מוודא שהמצב נכון
- **User Experience** - לא צריך לדעת אם יש container

---

## 🔧 **Utility Endpoints (שורות 282-350)**

### **1. `list_managed_containers()` - רשימת כל containers:**
```python
def list_managed_containers(self) -> List[Dict[str, Any]]:
    """Return a summary of all containers bearing the orchestrator label (any image)."""
    cli = self._cli()
    result: List[Dict[str, Any]] = []
    all_containers = cli.containers.list(all=True, filters={"label": self.LABEL_KEY})
    for c in all_containers:
        result.append(self._summarize_container(c))
    return result
```

**מה זה עושה:**
1. **Container Discovery** - מוצא כל containers עם התג הנכון
2. **Summary Creation** - יוצר סיכום לכל container
3. **Label Filtering** - רק containers שמנוהלים על ידי המערכת

**דוגמה:**
```python
# התוצאה:
[
    {
        "container_id": "abc123",
        "name": "nginx1",
        "status": "running",
        "ports": {"80/tcp": [{"HostPort": "8080"}]}
    },
    {
        "container_id": "def456",
        "name": "redis1",
        "status": "running",
        "ports": {"6379/tcp": [{"HostPort": "6379"}]}
    }
]
```

### **2. `get_containers_for_image()` - containers של image ספציפי:**
```python
def get_containers_for_image(self, image: str) -> List[Dict[str, Any]]:
    """Summaries of all managed containers for a specific image."""
    return [self._summarize_container(c) for c in self._current_for_image(image, running_only=False)]
```

**מה זה עושה:**
- **Image Filtering** - רק containers של image מסוים
- **Status Independent** - כולל running, stopped, exited
- **Summary Format** - אותו פורמט כמו `list_managed_containers`

### **3. `delete_container()` - מחיקת container:**
```python
def delete_container(self, name_or_id: str, *, force: bool = False) -> dict:
    """
    Remove a container by name or ID. Returns {"deleted": True/False, ...}.
    If the container is running and force=False, Docker will raise an error.
    """
    cli = self._cli()
    try:
        c = cli.containers.get(name_or_id)  # accepts name or id
    except Exception:
        return {"deleted": False, "error": "not-found"}

    try:
        if c.status == "running" and not force:
            c.stop(timeout=5)
            self._notify_discovery(image=c.labels.get(self.LABEL_KEY, ""), c=c, status="stopped", event="stop")
        c.remove(force=force)
        return {"deleted": True, "container_id": c.id, "name": c.name}
    except Exception as e:
        return {"deleted": False, "error": str(e)}
```

**מה זה עושה:**
1. **Container Lookup** - מוצא container לפי שם או ID
2. **Safe Deletion** - עוצר לפני מחיקה אם צריך
3. **Force Option** - יכול למחוק גם אם רץ
4. **Notification** - שולח callback על מחיקה
5. **Error Handling** - מחזיר errors ברורים

**הלוגיקה:**
```python
# 1. מציאת container
c = cli.containers.get(name_or_id)

# 2. אם רץ ולא force -> עוצר קודם
if c.status == "running" and not force:
    c.stop(timeout=5)
    # שולח notification
    self._notify_discovery(image=c.labels.get(self.LABEL_KEY, ""), c=c, status="stopped", event="stop")

# 3. מחיקה
c.remove(force=force)

# 4. תשובה
return {"deleted": True, "container_id": c.id, "name": c.name}
```

---

## 📈 **Reconcile & Scale Methods (שורות 352-420)**

### **1. `scale()` - שינוי מספר containers:**
```python
def scale(self, image: str, *, min_replicas: int, max_replicas: int) -> Dict[str, Any]:
    """
    Persist scale intent and immediately reconcile once.
    """
    cfg = self.desired_images.get(image, {"image": image, "env": {}, "ports": {}, "resources": {}})
    cfg.update({"min_replicas": min_replicas, "max_replicas": max_replicas})
    self.desired_images[image] = cfg
    return self.reconcile(image)
```

**מה זה עושה:**
1. **Configuration Update** - מעדכן min/max replicas
2. **Default Values** - יוצר config בסיסי אם לא קיים
3. **Immediate Reconciliation** - מוודא שהמצב תואם לרצוי

**דוגמה:**
```python
# לפני:
desired_images = {
    "nginx:alpine": {
        "min_replicas": 1,
        "max_replicas": 1
    }
}

# אחרי scale:
manager.scale("nginx:alpine", min_replicas=2, max_replicas=5)

# התוצאה:
desired_images = {
    "nginx:alpine": {
        "min_replicas": 2,  # עודכן
        "max_replicas": 5   # עודכן
    }
}
```

### **2. `reconcile()` - הבאת המצב לתואם לרצוי:**
```python
def reconcile(self, image: str) -> Dict[str, Any]:
    """
    Bring the number of RUNNING containers within [min, max] (naive).
    Start new containers up to min. If above max, stop/remove oldest first (FIFO).
    """
    cfg = self.desired_images.get(image)
    if not cfg:
        # default minimal config if not registered yet
        cfg = {"image": image, "min_replicas": 1, "max_replicas": 1, "env": {}, "ports": {}, "resources": {"status": "running"}}
        self.desired_images[image] = cfg

    env = cfg.get("env", {})
    ports = cfg.get("ports", {})
    resources = cfg.get("resources", {})
    min_r = int(cfg.get("min_replicas", 1))
    max_r = int(cfg.get("max_replicas", max(1, min_r)))

    running = self._current_for_image(image, running_only=True)
    n_running = len(running)
    actions: List[Dict[str, Any]] = []

    # Scale up to min
    if n_running < min_r:
        to_add = min_r - n_running
        for _ in range(to_add):
            res = self._run_new_container(image, env=env, ports=ports, resources=resources)
            actions.append({"action": "create", "ok": res.get("ok", False), "details": res})

    # Scale down to max
    if n_running > max_r:
        extra = n_running - max_r
        # Oldest first (FIFO): sort by creation time ascending, remove first `extra`
        running_sorted = sorted(running, key=lambda c: c.attrs.get("Created", ""))
        for c in running_sorted[:extra]:
            try:
                c.stop(timeout=5)
                self._notify_discovery(image=image, c=c, status="stopped", event="stop")
            except Exception:
                pass
            try:
                c.remove()
            except Exception:
                pass
            actions.append({"action": "remove", "container_id": c.id, "name": c.name})

    current = self.get_containers_for_image(image)
    return {"ok": True, "image": image, "desired": {"min_replicas": min_r, "max_replicas": max_r}, "actions": actions, "current": current}
```

**מה זה עושה:**
1. **Configuration Loading** - טוען הגדרות או יוצר ברירת מחדל
2. **Current State** - בודק כמה containers רץ
3. **Scale Up** - יוצר containers אם חסרים
4. **Scale Down** - מוחק containers אם יש יותר מדי
5. **FIFO Removal** - מוחק containers ישנים קודם
6. **Action Summary** - מחזיר סיכום של מה נעשה

**הלוגיקה:**
```python
# 1. טעינת הגדרות
cfg = self.desired_images.get(image)
min_r = cfg.get("min_replicas", 1)
max_r = cfg.get("max_replicas", max(1, min_r))

# 2. בדיקת המצב הנוכחי
running = self._current_for_image(image, running_only=True)
n_running = len(running)

# 3. Scale Up - אם חסרים containers
if n_running < min_r:
    to_add = min_r - n_running
    for _ in range(to_add):
        # יוצר container חדש
        res = self._run_new_container(image, env, ports, resources)
        actions.append({"action": "create", ...})

# 4. Scale Down - אם יש יותר מדי containers
if n_running > max_r:
    extra = n_running - max_r
    # ממיין לפי זמן יצירה (ישן קודם)
    running_sorted = sorted(running, key=lambda c: c.attrs.get("Created", ""))
    for c in running_sorted[:extra]:
        # עוצר ומוחק
        c.stop(timeout=5)
        c.remove()
        actions.append({"action": "remove", ...})

# 5. תשובה
return {
    "ok": True,
    "image": image,
    "desired": {"min_replicas": min_r, "max_replicas": max_r},
    "actions": actions,  # מה נעשה
    "current": current   # המצב הנוכחי
}
```

**למה זה חשוב:**
- **Auto-scaling** - מוודא שיש מספר נכון של containers
- **Resource Management** - לא מבזבז משאבים
- **Load Distribution** - מחלק עומס בין containers
- **State Consistency** - המצב בפועל תואם לרצוי

---

## 🏥 **Health & Stats Methods (שורות 422-460)**

### **1. `container_stats()` - סטטיסטיקות container:**
```python
def container_stats(self, name_or_id: str) -> Dict[str, Any]:
    """
    Best-effort docker stats for one container + host FS free bytes.
    Returns keys: status, server_alive, cpu_percent?, mem_usage?, mem_limit?, mem_percent?, fs_free_bytes?
    """
    cli = self._cli()
    try:
        c = cli.containers.get(name_or_id)
    except Exception:
        return {"ok": False, "error": "not-found"}

    status = c.status
    server_alive = status == "running"
    cpu_percent = None
    mem_usage = None
    mem_limit = None
    mem_percent = None

    try:
        st = c.stats(stream=False)
        # CPU%
        cpu = st.get("cpu_stats", {})
        precpu = st.get("precpu_stats", {})
        cpu_total = (cpu.get("cpu_usage", {}) or {}).get("total_usage", 0) - (precpu.get("cpu_usage", {}) or {}).get("total_usage", 0)
        sys_total = cpu.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
        num_cpus = len((cpu.get("cpu_usage", {}) or {}).get("percpu_usage") or []) or 1
        if sys_total > 0 and cpu_total >= 0:
            cpu_percent = (cpu_total / sys_total) * num_cpus * 100.0

        # Memory
        mem = st.get("memory_stats", {}) or {}
        mem_usage = mem.get("usage")
        mem_limit = mem.get("limit")
        if mem_usage is not None and mem_limit:
            mem_percent = (mem_usage / float(mem_limit)) * 100.0
    except Exception:
        # missing permissions or platform differences
        pass

    fs_free = None
    try:
        fs_free = shutil.disk_usage("/").free
    except Exception:
        pass

    return {
        "ok": True,
        "status": status,
        "server_alive": server_alive,
        "cpu_percent": cpu_percent,
        "mem_usage": mem_usage,
        "mem_limit": mem_limit,
        "mem_percent": mem_percent,
        "fs_free_bytes": fs_free,
    }
```

**מה זה עושה:**
1. **Container Lookup** - מוצא container לפי שם או ID
2. **Status Check** - בודק אם container חי
3. **CPU Stats** - מחשב אחוז CPU
4. **Memory Stats** - מחשב שימוש זיכרון
5. **Disk Space** - בודק מקום פנוי בדיסק
6. **Error Handling** - מחזיר None אם יש בעיה

**החישובים:**
```python
# CPU Percentage
cpu_total = current_cpu - previous_cpu
sys_total = current_system - previous_system
cpu_percent = (cpu_total / sys_total) * num_cpus * 100

# Memory Percentage
mem_percent = (mem_usage / mem_limit) * 100

# Disk Free
fs_free = shutil.disk_usage("/").free
```

**למה זה חשוב:**
- **Health Monitoring** - רואה אם containers בריאים
- **Resource Monitoring** - עוקב אחר שימוש במשאבים
- **Alerting** - יכול להתריע על בעיות
- **Scaling Decisions** - עוזר להחליט על scaling

### **2. `set_container_status()` - שינוי מצב container:**
```python
def set_container_status(self, name_or_id: str, *, status: str) -> Dict[str, Any]:
    """
    Start/stop a specific managed container. status in {"running","stopped"}.
    """
    cli = self._cli()
    try:
        c = cli.containers.get(name_or_id)
    except Exception:
        return {"ok": False, "error": "not-found"}

    image = c.labels.get(self.LABEL_KEY, "")
    expect_keys = list(((self.desired_images.get(image) or {}).get("ports") or {}).keys()) or None

    try:
        if status == "running":
            if c.status != "running":
                c.start()
                if expect_keys:
                    self._wait_for_ports(c, expect_keys)
                self._notify_discovery(image=image, c=c, status="running", event="start")
        elif status == "stopped":
            if c.status == "running":
                c.stop(timeout=5)
                self._notify_discovery(image=image, c=c, status="stopped", event="stop")
        else:
            return {"ok": False, "error": "invalid-status"}
        return {"ok": True, **self._summarize_container(c)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

**מה זה עושה:**
1. **Container Lookup** - מוצא container
2. **Status Validation** - בודק שהמצב תקין
3. **Start/Stop** - מפעיל או עוצר container
4. **Port Waiting** - מחכה שפורטים יהיו מוכנים
5. **Notification** - שולח callbacks
6. **Response** - מחזיר מידע מעודכן

**הלוגיקה:**
```python
# 1. מציאת container
c = cli.containers.get(name_or_id)

# 2. אם צריך running
if status == "running":
    if c.status != "running":
        c.start()  # מפעיל
        # מחכה לפורטים
        if expect_keys:
            self._wait_for_ports(c, expect_keys)
        # שולח notification
        self._notify_discovery(image=image, c=c, status="running", event="start")

# 3. אם צריך stopped
elif status == "stopped":
    if c.status == "running":
        c.stop(timeout=5)  # עוצר
        # שולח notification
        self._notify_discovery(image=image, c=c, status="stopped", event="stop")

# 4. תשובה
return {"ok": True, **self._summarize_container(c)}
```

**למה זה חשוב:**
- **Manual Control** - משתמשים יכולים לשלוט במצב
- **Maintenance** - עוצר containers לתחזוקה
- **Debugging** - מפעיל/עוצר לבדיקות
- **Integration** - עובד עם מערכות חיצוניות

---

## 🎯 **סיכום המחלקה**

### **מה יש לנו:**
✅ **Container Lifecycle** - יצירה, הפעלה, עצירה, מחיקה  
✅ **Resource Management** - CPU, memory, ports  
✅ **State Management** - desired state + reconciliation  
✅ **Auto-scaling** - מוודא מספר נכון של containers  
✅ **Health Monitoring** - סטטיסטיקות ובריאות  
✅ **Service Discovery** - callbacks למערכות חיצוניות  
✅ **Error Handling** - תשובות ברורות ו-robust  

### **מה חסר (להמשך):**
🔄 **Persistence** - שמירה לדאטהבייס  
🔄 **Async Support** - פעולות מקבילות  
🔄 **Advanced Scaling** - metrics-based scaling  
🔄 **Event System** - היסטוריה מלאה של שינויים  

### **הארכיטקטורה:**
```
FastAPI (HTTP Layer)
    ↓
ContainerManager (Business Logic)
    ↓
Docker SDK (Container Operations)
```

**המחלקה מושלמת ל-Stage 1** ומספקת בסיס מצוין להמשך פיתוח!

---

## 🤝 **תמיכה**

אם יש לך שאלות על הקוד או שאתה רוצה להוסיף features חדשים, תוכל לפנות אליי!
