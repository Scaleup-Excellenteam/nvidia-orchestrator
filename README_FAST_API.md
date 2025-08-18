# FastAPI Orchestrator - מדריך מפורט לקוד

## 📋 **מבט כללי**

קובץ `fast_api.py` הוא השכבה החיצונית של המערכת - הוא חושף HTTP API שמאפשר לניהול containers דרך ContainerManager.

---

## 🏗️ **מבנה הקובץ**

### **1. Docstring ראשי (שורות 1-47)**
```python
"""
FastAPI layer that exposes container orchestration endpoints and delegates
all Docker logic to ContainerManager.
"""
```
**מה זה:** הסבר כללי על הקובץ + דוגמאות curl לכל ה-endpoints.

**מה יש שם:**
- הוראות הרצה
- דוגמאות curl מלאות
- הסבר על כל השלבים (Stage 1-3)

---

### **2. Imports (שורות 48-52)**
```python
from typing import Dict, Literal, Optional, List, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from container_manager import ContainerManager
```

**מה זה:** ייבוא כל החבילות הנדרשות.

**פירוט:**
- `typing` - טיפוסי נתונים מתקדמים
- `fastapi` - מסגרת ה-API
- `pydantic` - validation של נתונים
- `container_manager` - הלוגיקה העסקית שלנו

---

## 📊 **Pydantic Models (שורות 54-75)**

### **Resources Model (שורות 56-59)**
```python
class Resources(BaseModel):
    cpu: str                  # CPU quota, e.g., "0.5" or "500m"
    memory: str               # Docker memory string, e.g., "512m", "1g"
    status: Literal["running", "stopped"] = "running"
```

**מה זה:** מודל שמגדיר resources לכל container.

**פירוט השדות:**
- `cpu` - מכסה של CPU (למשל "0.5" או "500m")
- `memory` - מגבלת זיכרון (למשל "512m" או "1g")
- `status` - מצב Container (רק "running" או "stopped")

**דוגמאות:**
```json
{
  "cpu": "500m",
  "memory": "256m", 
  "status": "running"
}
```

### **StartContainerRequest Model (שורות 61-67)**
```python
class StartContainerRequest(BaseModel):
    image: str
    min_replicas: int = Field(ge=0, default=1)
    max_replicas: int = Field(ge=1, default=5)
    env: Dict[str, str] = Field(default_factory=dict)
    ports: Dict[str, int] = Field(default_factory=dict)
    resources: Resources
```

**מה זה:** מודל לבקשת יצירת container.

**פירוט השדות:**
- `image` - שם ה-Docker image (חובה)
- `min_replicas` - מספר מינימלי של containers (ברירת מחדל: 1)
- `max_replicas` - מספר מקסימלי של containers (ברירת מחדל: 5)
- `env` - משתני סביבה (ברירת מחדל: ריק)
- `ports` - מיפוי פורטים (ברירת מחדל: ריק)
- `resources` - משאבים (CPU, memory, status)

**Validation:**
- `min_replicas >= 0`
- `max_replicas >= 1`

### **ScaleRequest Model (שורות 69-71)**
```python
class ScaleRequest(BaseModel):
    min_replicas: int = Field(ge=0)
    max_replicas: int = Field(ge=1)
```

**מה זה:** מודל לבקשת שינוי מספר containers.

### **PatchContainerRequest Model (שורות 73-75)**
```python
class PatchContainerRequest(BaseModel):
    status: Literal["running", "stopped"]
```

**מה זה:** מודל לבקשת שינוי מצב container.

---

## 🚀 **FastAPI App & Routes (שורות 77-193)**

### **יצירת האפליקציה (שורות 77-78)**
```python
app = FastAPI(title="Orchestrator", version="0.2")
manager = ContainerManager()
```

**מה זה:** יצירת instance של FastAPI ו-ContainerManager.

**פירוט:**
- `app` - האפליקציה הראשית של FastAPI
- `manager` - instance של ContainerManager שמטפל בלוגיקה

---

### **Health Check (שורות 80-82)**
```python
@app.get("/health")
def health():
    return {"ok": True}
```

**מה זה:** בדיקת בריאות בסיסית של המערכת.

**Endpoint:** `GET /health`

**תשובה:** `{"ok": true}`

**שימוש:** לבדוק שהמערכת עובדת.

---

### **Start Container (שורות 84-102)**
```python
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
```

**מה זה:** יצירת container חדש או הפעלת קיים.

**Endpoint:** `POST /start/container`

**מה זה עושה:**
1. **שומר desired state** - שומר את המצב הרצוי
2. **מוודא שיש container** - יוצר או מפעיל container קיים
3. **מחזיר תוצאה** - פרטי ה-container שנוצר

**דוגמה:**
```bash
curl -X POST http://localhost:8000/start/container \
  -H "Content-Type: application/json" \
  -d '{
    "image": "nginx:alpine",
    "min_replicas": 1,
    "max_replicas": 3,
    "env": {},
    "ports": {"80/tcp": 0},
    "resources": {"cpu": "500m", "memory": "256m", "status": "running"}
  }'
```

---

### **Scale Image (שורות 104-109)**
```python
@app.post("/images/{image}/scale")
def scale_image(image: str, body: ScaleRequest):
    res = manager.scale(image, min_replicas=body.min_replicas, max_replicas=body.max_replicas)
    if not res.get("ok"):
        raise HTTPException(status_code=500, detail="scale-failed")
    return res
```

**מה זה:** שינוי מספר containers עבור image מסוים.

**Endpoint:** `POST /images/{image}/scale`

**פרמטרים:**
- `{image}` - שם ה-image
- `body` - min_replicas ו-max_replicas חדשים

**דוגמה:**
```bash
curl -X POST http://localhost:8000/images/nginx:alpine/scale \
  -H "Content-Type: application/json" \
  -d '{"min_replicas": 2, "max_replicas": 5}'
```

---

### **Reconcile Image (שורות 111-116)**
```python
@app.post("/images/{image}/reconcile")
def reconcile_image(image: str):
    res = manager.reconcile(image)
    if not res.get("ok"):
        raise HTTPException(status_code=500, detail="reconcile-failed")
    return res
```

**מה זה:** הפעלת reconciliation - מוודא שיש מספר נכון של containers.

**Endpoint:** `POST /images/{image}/reconcile`

**מה זה עושה:**
- בודק כמה containers יש
- יוצר containers אם חסרים
- מוחק containers אם יש יותר מדי

**דוגמה:**
```bash
curl -X POST http://localhost:8000/images/nginx:alpine/reconcile
```

---

### **List Image Containers (שורות 118-120)**
```python
@app.get("/images/{image}/containers")
def list_image_containers(image: str):
    return {"image": image, "containers": manager.get_containers_for_image(image)}
```

**מה זה:** רשימת כל containers של image מסוים.

**Endpoint:** `GET /images/{image}/containers`

**תשובה:**
```json
{
  "image": "nginx:alpine",
  "containers": [
    {
      "container_id": "abc123",
      "name": "nginx1",
      "status": "running",
      "ports": {"80/tcp": [{"HostPort": "8080"}]}
    }
  ]
}
```

---

### **List All Containers (שורות 122-125)**
```python
@app.get("/containers")
def list_containers():
    """List all containers managed by this orchestrator (by label)."""
    return {"containers": manager.list_managed_containers()}
```

**מה זה:** רשימת כל containers שמנוהלים על ידי המערכת.

**Endpoint:** `GET /containers`

**מה זה מחזיר:** רשימה של כל containers עם התג `orchestrator.image`.

---

### **Image Health (שורות 127-142)**
```python
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
```

**מה זה:** בדיקת בריאות מפורטת של containers של image מסוים.

**Endpoint:** `GET /images/{image}/health`

**מה זה מחזיר:**
- מצב כל container
- אחוז CPU
- אחוז זיכרון
- מקום פנוי בדיסק
- האם השרת חי

---

### **Patch Container Status (שורות 144-153)**
```python
@app.patch("/containers/{name_or_id}")
def patch_container(name_or_id: str, body: PatchContainerRequest):
    res = manager.set_container_status(name_or_id, status=body.status)
    if not res.get("ok"):
        if res.get("error") == "not-found":
            raise HTTPException(status_code=404, detail=f"Container '{name_or_id}' not found")
        raise HTTPException(status_code=400, detail=res.get("error", "failed"))
    return res
```

**מה זה:** שינוי מצב container (הפעלה/עצירה).

**Endpoint:** `PATCH /containers/{name_or_id}`

**מה זה עושה:**
- מפעיל container אם הוא עצור
- עוצר container אם הוא רץ

**דוגמה:**
```bash
curl -X PATCH http://localhost:8000/containers/nginx1 \
  -H "Content-Type: application/json" \
  -d '{"status": "stopped"}'
```

---

### **Delete Container (שורות 155-166)**
```python
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
```

**מה זה:** מחיקת container.

**Endpoint:** `DELETE /containers/{name_or_id}`

**פרמטרים:**
- `{name_or_id}` - שם או ID של container
- `force` - האם למחוק בכוח (query parameter)

**דוגמה:**
```bash
# מחיקה רגילה
curl -X DELETE "http://localhost:8000/containers/nginx1"

# מחיקה בכוח
curl -X DELETE "http://localhost:8000/containers/nginx1?force=true"
```

---

### **Desired State (שורות 168-173)**
```python
@app.get("/images")
def desired_state():
    """
    OPTIONAL: Expose in-memory desired-state entries to help the UI.
    Format mirrors ContainerManager.desired_images.
    """
    return {"images": list(manager.desired_images.values())}
```

**מה זה:** חשיפת המצב הרצוי של כל images.

**Endpoint:** `GET /images`

**מה זה מחזיר:** רשימה של כל images עם הגדרותיהם (min/max replicas, env, ports, resources).

---

### **Main Block (שורות 175-193)**
```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fast_api:app", host="0.0.0.0", port=8000, reload=True)
```

**מה זה:** הרצה ישירה של השרת.

**מה זה עושה:**
- יוצר שרת uvicorn
- רץ על כל הרשת (0.0.0.0)
- פורט 8000
- auto-reload כשהקוד משתנה

---

## 🎯 **סיכום Endpoints**

| Method | Endpoint | תיאור |
|--------|----------|-------|
| `GET` | `/health` | בדיקת בריאות |
| `POST` | `/start/container` | יצירת container |
| `POST` | `/images/{image}/scale` | שינוי מספר containers |
| `POST` | `/images/{image}/reconcile` | reconciliation |
| `GET` | `/images/{image}/containers` | containers של image |
| `GET` | `/containers` | כל containers |
| `GET` | `/images/{image}/health` | בריאות image |
| `PATCH` | `/containers/{name_or_id}` | שינוי מצב container |
| `DELETE` | `/containers/{name_or_id}` | מחיקת container |
| `GET` | `/images` | מצב רצוי של images |

---

## 🚀 **איך להריץ**

### **הרצה עם uvicorn:**
```bash
py -m uvicorn fast_api:app --reload --host 0.0.0.0 --port 8000
```

### **הרצה ישירה:**
```bash
py fast_api.py
```

---

## 📚 **קישורים שימושיים**

- **FastAPI Documentation:** https://fastapi.tiangolo.com/
- **Pydantic Documentation:** https://pydantic-docs.helpmanual.io/
- **Uvicorn Documentation:** https://www.uvicorn.org/

---

## 🤝 **תמיכה**

אם יש לך שאלות על הקוד או שאתה רוצה להוסיף features חדשים, תוכל לפנות אליי!
