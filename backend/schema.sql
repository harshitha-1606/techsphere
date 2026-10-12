CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  event_date TEXT NOT NULL,
  college TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS participants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER NOT NULL REFERENCES events(id),
  email TEXT NOT NULL,                 -- normalised (trimmed, lower-case); unique per event
  name TEXT NOT NULL,
  department TEXT NOT NULL,
  team TEXT, roll_no TEXT, mobile TEXT, topic TEXT,
  data_hash TEXT NOT NULL,             -- hash of name+department; certificate is stale if it differs
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (event_id, email)
);
CREATE TABLE IF NOT EXISTS certificates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  participant_id INTEGER NOT NULL UNIQUE REFERENCES participants(id) ON DELETE CASCADE,
  certificate_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','generated','failed')),
  data_hash TEXT,
  file_name TEXT,
  error TEXT,
  generated_at TEXT
);
CREATE TABLE IF NOT EXISTS staged_imports (
  token TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS import_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT, total INTEGER, valid INTEGER, invalid INTEGER,
  inserted INTEGER, updated INTEGER, unchanged INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
