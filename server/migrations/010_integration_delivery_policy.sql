-- Политика доставки уведомлений: тихие часы и минимальный уровень серьёзности.
ALTER TABLE telegram_settings ADD COLUMN notify_min_severity TEXT DEFAULT 'high';
ALTER TABLE telegram_settings ADD COLUMN quiet_hours_start TEXT DEFAULT '';
ALTER TABLE telegram_settings ADD COLUMN quiet_hours_end TEXT DEFAULT '';

ALTER TABLE slack_settings ADD COLUMN notify_min_severity TEXT DEFAULT 'high';
ALTER TABLE slack_settings ADD COLUMN quiet_hours_start TEXT DEFAULT '';
ALTER TABLE slack_settings ADD COLUMN quiet_hours_end TEXT DEFAULT '';
