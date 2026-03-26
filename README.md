# Nullius

Nullius — self-hosted security platform для одного Linux-хоста.

Состав:
- `web` — React/Vite dashboard
- `server` — FastAPI API + WebSocket backend
- `agent` — Go-агент для метрик, процессов, сервисов и логов
- `deploy` — сборка, установка, удаление, systemd/nginx
- `testing` — smoke и e2e проверки MVP

## Требования

- Ubuntu или Debian
- `root` для установки
- `go`, `node`, `npm`, `python3` для локальной сборки

## Локальная сборка релиза

```bash
./deploy/build.sh
```

После сборки готовый release лежит в `dist/`.

## Установка на сервер

Запускать нужно из `dist/`:

```bash
cd dist
./install.sh
```

Проверка состояния:

```bash
curl http://127.0.0.1:8000/api/health ; echo
nullius-ctl status
```

Ожидаемый результат:

```json
{"status":"ok","agent":"connected","db":"ok"}
```

## Удаление

Полное удаление:

```bash
cd dist
./uninstall.sh
```

Скрипт удаляет:
- `/opt/nullius`
- systemd units и drop-ins
- nginx config
- logrotate config
- локальный CLI
- системного пользователя `nullius`

## Тестирование MVP

Smoke:

```bash
python3 testing/smoke/mvp_smoke.py
```

Полный прогон:

```bash
./testing/run_mvp_suite.sh
```

Frontend e2e:

```bash
cd web
npm ci --include=dev
npx playwright install --with-deps chromium
npx playwright test -c e2e/playwright.config.ts
```

Server tests:

```bash
cd server
python3 -m venv venv
./venv/bin/pip install -r requirements-dev.txt
./venv/bin/pytest -q
```

Полный релизный чек-лист:

- [docs/release-checklist.md](docs/release-checklist.md)

Документация для новых разработчиков:

- [docs/developer-guide.md](docs/developer-guide.md)
- [docs/contributing.md](docs/contributing.md)

## Архитектурные заметки

- Dashboard защищён через nginx basic auth.
- Внутренний Bearer auth и WS token для UI по умолчанию отключены и могут быть включены через `api.require_bearer_auth` и `api.require_ws_token` в `nullius.yaml`.
- Если Bearer auth включён, используй отдельный `api.token` или env `NULLIUS_API_TOKEN`, а не агентский секрет.
- Разрешённые cross-origin источники задаются через `api.cors_origins`.
- Агент использует `agent.key`, лежащий рядом с `nullius.yaml`.
- Основной runtime health-check: `/api/health`.

## Основные команды

```bash
nullius-ctl status
nullius-ctl logs --follow
nullius-ctl smoke
nullius-ctl set-password
nullius-ctl uninstall
```
