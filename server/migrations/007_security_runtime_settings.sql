CREATE TABLE IF NOT EXISTS security_runtime_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    operation_mode TEXT NOT NULL DEFAULT 'auto_defend',
    updated_at INTEGER NOT NULL DEFAULT 0
);

INSERT OR IGNORE INTO security_runtime_settings (id, operation_mode, updated_at)
VALUES (1, 'auto_defend', 0);
