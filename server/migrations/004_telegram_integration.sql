-- Настройки Telegram-бота: токен, привязанный чат и прогресс polling-цикла.
CREATE TABLE IF NOT EXISTS telegram_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    bot_token TEXT DEFAULT '',
    bot_username TEXT DEFAULT '',
    bot_name TEXT DEFAULT '',
    chat_id TEXT DEFAULT '',
    chat_title TEXT DEFAULT '',
    last_update_id INTEGER DEFAULT 0,
    notify_auto_block INTEGER DEFAULT 1,
    last_error TEXT DEFAULT '',
    updated_at INTEGER NOT NULL
);

INSERT OR IGNORE INTO telegram_settings (
    id, bot_token, bot_username, bot_name, chat_id, chat_title, last_update_id, notify_auto_block, last_error, updated_at
) VALUES (
    1, '', '', '', '', '', 0, 1, '', strftime('%s', 'now')
);
