CREATE TABLE IF NOT EXISTS risk_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    score INTEGER NOT NULL,
    level TEXT NOT NULL,
    factors_json TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_risk_snapshots_timestamp
ON risk_snapshots(timestamp DESC);
