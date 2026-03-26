-- - Добавляет колонку file_hash для верификации целостности ML-моделей
ALTER TABLE ml_models ADD COLUMN file_hash TEXT DEFAULT '';
