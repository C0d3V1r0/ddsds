-- Начальная схема БД Nullius
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    cpu_total REAL,
    cpu_cores TEXT,
    ram_used INTEGER,
    ram_total INTEGER,
    disk TEXT,
    network_rx INTEGER,
    network_tx INTEGER,
    load_avg TEXT
);
CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(timestamp);

CREATE TABLE IF NOT EXISTS security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    source_ip TEXT,
    description TEXT,
    raw_log TEXT,
    action_taken TEXT,
    resolved INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_security_ts ON security_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_security_type ON security_events(type);

CREATE TABLE IF NOT EXISTS blocked_ips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL UNIQUE,
    reason TEXT,
    blocked_at INTEGER NOT NULL,
    expires_at INTEGER,
    auto INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS services (
    name TEXT PRIMARY KEY,
    status TEXT,
    pid INTEGER,
    uptime INTEGER,
    updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS ml_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    trained_at INTEGER,
    samples_count INTEGER,
    accuracy REAL,
    file_path TEXT,
    active INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS agent_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    command TEXT NOT NULL,
    params TEXT,
    result TEXT,
    error TEXT
);
