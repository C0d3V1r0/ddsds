-- Workflow-слой инцидентов: операторский статус и короткие заметки расследования.
CREATE TABLE IF NOT EXISTS incident_state (
    incident_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS incident_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    incident_type TEXT NOT NULL,
    source_ip TEXT,
    note TEXT NOT NULL,
    status_at_time TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_incident_notes_incident_id ON incident_notes(incident_id, created_at DESC);
