"""
mongodb.py - Optional MongoDB persistence for the Orchestrator.

- Uses pymongo (sync) so we don't need to change FastAPI routes to async.
- If MongoDB isn't reachable or pymongo isn't installed, it disables itself and
  the app continues to work with in-memory storage.

Collections:
  - desired_images: one doc per image (unique by "image")
  - events: lifecycle events (create/start/stop/remove) emitted by ContainerManager
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
import time

try:
    from pymongo import MongoClient, ASCENDING
except Exception:  # pragma: no cover
    MongoClient = None  # type: ignore


class MongoStore:
    def __init__(self, *, url: Optional[str] = None, db_name: str = "orchestrator"):
        self.enabled = False
        self._db = None

        if MongoClient is None:
            return  # pymongo missing -> stay disabled

        url = url or os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")
        try:
            client = MongoClient(url, serverSelectionTimeoutMS=1000)
            client.admin.command("ping")  # validate connectivity fast
            self._db = client[db_name]
            self.enabled = True
            self._ensure_indexes()
        except Exception:
            # No crash; just run without persistence
            self.enabled = False
            self._db = None

    # ---------- desired_images ----------
    def upsert_desired(self, image: str, doc: Dict[str, Any]) -> None:
        if not self.enabled: return
        self._db.desired_images.update_one({"image": image}, {"$set": doc}, upsert=True)

    def get_desired(self, image: str) -> Optional[Dict[str, Any]]:
        if not self.enabled: return None
        d = self._db.desired_images.find_one({"image": image}, {"_id": 0})
        return dict(d) if d else None

    def list_desired(self) -> List[Dict[str, Any]]:
        if not self.enabled: return []
        return [{k: v for k, v in d.items() if k != "_id"} for d in self._db.desired_images.find()]

    def update_scale(self, image: str, min_replicas: int, max_replicas: int) -> None:
        if not self.enabled: return
        self._db.desired_images.update_one(
            {"image": image},
            {"$set": {"min_replicas": min_replicas, "max_replicas": max_replicas}},
            upsert=True,
        )

    def delete_desired(self, image: str) -> None:
        if not self.enabled: return
        self._db.desired_images.delete_one({"image": image})

    # ---------- events ----------
    def record_event(self, payload: Dict[str, Any]) -> None:
        if not self.enabled: return
        payload = dict(payload)
        payload.setdefault("ts", time.time())
        self._db.events.insert_one(payload)

    def list_events(self, image: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.enabled: return []
        q: Dict[str, Any] = {}
        if image:
            q["image"] = image
        cur = self._db.events.find(q).sort("ts", -1).limit(limit)
        return [{k: v for k, v in d.items() if k != "_id"} for d in cur]

    # ---------- internals ----------
    def _ensure_indexes(self) -> None:
        self._db.desired_images.create_index([("image", ASCENDING)], unique=True)
        self._db.events.create_index([("image", ASCENDING), ("ts", ASCENDING)])
