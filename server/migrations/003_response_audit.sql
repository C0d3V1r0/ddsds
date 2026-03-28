-- Трасса реакции: связывает детект, решение, отправку команды и итог выполнения.
ALTER TABLE security_events ADD COLUMN trace_id TEXT;
CREATE INDEX IF NOT EXISTS idx_security_trace_id ON security_events(trace_id);

ALTER TABLE agent_commands ADD COLUMN trace_id TEXT;
CREATE INDEX IF NOT EXISTS idx_agent_commands_trace_id ON agent_commands(trace_id);

CREATE TABLE IF NOT EXISTS response_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    trace_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    event_type TEXT,
    source_ip TEXT,
    action TEXT,
    command TEXT,
    details TEXT
);
CREATE INDEX IF NOT EXISTS idx_response_audit_trace_id ON response_audit(trace_id);
CREATE INDEX IF NOT EXISTS idx_response_audit_ts ON response_audit(timestamp);
