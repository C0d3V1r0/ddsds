-- Дополнительные типы уведомлений для внешних интеграций.
ALTER TABLE telegram_settings ADD COLUMN notify_high_severity INTEGER DEFAULT 0;
ALTER TABLE slack_settings ADD COLUMN notify_high_severity INTEGER DEFAULT 0;
