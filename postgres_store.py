# postgres_store.py
from __future__ import annotations
import os, json
from typing import Any, Dict, List, Optional
import psycopg
from psycopg.rows import tuple_row

class PostgresStore:
    """
    Drop-in replacement for MongoStore, same method names:
      - upsert_desired(image, doc)
      - list_desired()
      - record_event(payload)
      - list_events(image=None, limit=100)
    On first connect it creates the tables if they don't exist.
    """
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or os.getenv(
            "POSTGRES_URL",
            # local default, change if you like
            "postgresql://postgres:postgres@127.0.0.1:5432/orchestrator"
        )
        self.enabled = False
        try:
            with psycopg.connect(self.dsn, autocommit=True) as conn:
                with conn.cursor(row_factory=tuple_row) as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS desired_images (
                          image        TEXT PRIMARY KEY,
                          min_replicas INT  NOT NULL,
                          max_replicas INT  NOT NULL,
                          resources    JSONB,
                          env          JSONB,
                          ports        JSONB,
                          updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS events (
                          id           BIGSERIAL PRIMARY KEY,
                          image        TEXT        NOT NULL,
                          container_id TEXT,
                          name         TEXT,
                          host         TEXT,
                          ports        JSONB,
                          status       TEXT,
                          event        TEXT        NOT NULL CHECK (event IN ('create','start','stop','remove')),
                          ts           TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS events_image_ts_idx ON events (image, ts DESC)")
            self.enabled = True
        except Exception:
            self.enabled = False

    # -------- desired_images --------
    def upsert_desired(self, image: str, doc: Dict[str, Any]) -> None:
        if not self.enabled: return
        with psycopg.connect(self.dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO desired_images(image,min_replicas,max_replicas,resources,env,ports)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (image) DO UPDATE
                SET min_replicas=EXCLUDED.min_replicas,
                    max_replicas=EXCLUDED.max_replicas,
                    resources=EXCLUDED.resources,
                    env=EXCLUDED.env,
                    ports=EXCLUDED.ports,
                    updated_at=now()
            """, (
                image,
                int(doc.get("min_replicas", 1)),
                int(doc.get("max_replicas", 1)),
                json.dumps(doc.get("resources") or {}),
                json.dumps(doc.get("env") or {}),
                json.dumps(doc.get("ports") or {}),
            ))

    def list_desired(self) -> List[Dict[str, Any]]:
        if not self.enabled: return []
        with psycopg.connect(self.dsn) as conn, conn.cursor(row_factory=tuple_row) as cur:
            cur.execute("SELECT image,min_replicas,max_replicas,resources,env,ports FROM desired_images")
            rows = cur.fetchall()
        return [
            {"image": r[0], "min_replicas": r[1], "max_replicas": r[2],
             "resources": r[3], "env": r[4], "ports": r[5]}
            for r in rows
        ]

    # -------- events --------
    def record_event(self, payload: Dict[str, Any]) -> None:
        if not self.enabled: return
        with psycopg.connect(self.dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO events(image,container_id,name,host,ports,status,event,ts)
                VALUES (%s,%s,%s,%s,%s,%s,%s,now())
            """, (
                payload.get("image"),
                payload.get("container_id"),
                payload.get("name"),
                payload.get("host"),
                json.dumps(payload.get("ports") or {}),
                payload.get("status"),
                payload.get("event"),
            ))

    def list_events(self, image: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.enabled: return []
        with psycopg.connect(self.dsn) as conn, conn.cursor(row_factory=tuple_row) as cur:
            if image:
                cur.execute("""
                    SELECT image,container_id,name,host,ports,status,event,ts
                    FROM events WHERE image=%s ORDER BY ts DESC LIMIT %s
                """, (image, limit))
            else:
                cur.execute("""
                    SELECT image,container_id,name,host,ports,status,event,ts
                    FROM events ORDER BY ts DESC LIMIT %s
                """, (limit,))
            rows = cur.fetchall()
        return [
            {"image": r[0], "container_id": r[1], "name": r[2], "host": r[3],
             "ports": r[4], "status": r[5], "event": r[6], "ts": r[7].timestamp()}
            for r in rows
        ]
