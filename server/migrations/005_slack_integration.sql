-- Настройки Slack Incoming Webhook для уведомлений Nullius.
CREATE TABLE IF NOT EXISTS slack_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    webhook_url TEXT DEFAULT '',
    notify_auto_block INTEGER DEFAULT 1,
    last_error TEXT DEFAULT '',
    updated_at INTEGER NOT NULL
);

INSERT OR IGNORE INTO slack_settings (
    id, webhook_url, notify_auto_block, last_error, updated_at
) VALUES (
    1, '', 1, '', strftime('%s', 'now')
);
