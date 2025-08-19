-- Simple database initialization - matches what postgres_store.py creates
CREATE TABLE IF NOT EXISTS desired_images (
  image        TEXT PRIMARY KEY,
  min_replicas INT  NOT NULL,
  max_replicas INT  NOT NULL,
  resources    JSONB,
  env          JSONB,
  ports        JSONB,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

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
);

CREATE TABLE IF NOT EXISTS health_snapshots (
    id BIGSERIAL PRIMARY KEY,
    image TEXT NOT NULL,
    container_id TEXT NOT NULL,
    name TEXT,
    host TEXT,
    cpu_usage DOUBLE PRECISION,
    memory_usage DOUBLE PRECISION,
    disk_usage DOUBLE PRECISION,
    status TEXT,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS health_image_ts_idx ON health_snapshots (image, ts DESC);
CREATE INDEX IF NOT EXISTS health_container_ts_idx ON health_snapshots (container_id, ts DESC);
CREATE INDEX IF NOT EXISTS events_image_ts_idx ON events (image, ts DESC);
