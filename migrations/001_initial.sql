CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS library_roots (
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  last_completed_scan_at TEXT
);

CREATE TABLE IF NOT EXISTS photos (
  id INTEGER PRIMARY KEY,
  root_id INTEGER NOT NULL REFERENCES library_roots(id),
  path TEXT NOT NULL UNIQUE,
  device INTEGER,
  inode INTEGER,
  mime_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  mtime_ns INTEGER NOT NULL,
  last_seen_generation INTEGER,
  available INTEGER NOT NULL DEFAULT 1,
  hidden_at TEXT,
  last_shown_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS photos_root_available
  ON photos(root_id, available, hidden_at);
CREATE INDEX IF NOT EXISTS photos_last_shown
  ON photos(last_shown_at);
CREATE INDEX IF NOT EXISTS photos_identity
  ON photos(device, inode);

CREATE TABLE IF NOT EXISTS reflections (
  id INTEGER PRIMARY KEY,
  photo_id INTEGER NOT NULL UNIQUE REFERENCES photos(id),
  prompt_id TEXT NOT NULL,
  prompt_text TEXT NOT NULL,
  note TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
  photo_id INTEGER PRIMARY KEY REFERENCES photos(id),
  prompt_id TEXT NOT NULL,
  note TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  photo_id INTEGER NOT NULL REFERENCES photos(id),
  kind TEXT NOT NULL,
  occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS events_photo_kind_time
  ON events(photo_id, kind, occurred_at);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES (1, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));
