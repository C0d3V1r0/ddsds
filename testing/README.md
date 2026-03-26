# Nullius Testing Module

Этот модуль нужен для быстрой проверки, что MVP действительно работает end-to-end.

Состав:

- `smoke/mvp_smoke.py`
  Проверяет system/API/functionality:
  health, metrics, services, processes, logs, security API, block/unblock IP,
  появление временного процесса и тестовой лог-записи.
- `e2e/playwright.config.ts`
  Конфиг Playwright для проверки UI.
- `e2e/mvp.spec.ts`
  E2E smoke-набор для UI: dashboard, navigation, settings, security workflow.
- `run_mvp_suite.sh`
  Оркестратор полного прогона.

## Быстрый запуск на сервере

```bash
cd ~/ddsds
python3 testing/smoke/mvp_smoke.py
cd web && npx playwright test -c ../testing/e2e/playwright.config.ts
```

Или одной командой:

```bash
./testing/run_mvp_suite.sh
```

## Переменные окружения

- `NULLIUS_API_URL`
  По умолчанию: `http://127.0.0.1:8000`
- `NULLIUS_DASHBOARD_URL`
  По умолчанию: `https://127.0.0.1`
- `NULLIUS_DASHBOARD_USER`
  По умолчанию: `admin`
- `NULLIUS_DASHBOARD_PASSWORD`
  Если не задан, берётся из `/opt/nullius/config/.initial_password`
- `NULLIUS_SKIP_SYSTEMD`
  Если `1`, smoke-тест пропустит проверки `systemctl`

## Что считается достаточным для MVP

- smoke-скрипт проходит без ошибок
- e2e-набор проходит без ошибок
- после `reboot` сервисы поднимаются автоматически и smoke/e2e снова зелёные
