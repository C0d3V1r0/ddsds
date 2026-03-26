# Developer Guide

Этот документ нужен новому разработчику, который впервые заходит в кодовую базу Nullius и хочет быстро понять:

- как устроен проект
- что за что отвечает
- как поднять локальное окружение
- какие проверки запускать перед коммитом

## 1. Что такое Nullius

Nullius — self-hosted host defense platform для одного Linux-хоста.

Система состоит из трёх основных частей:

- `agent` — Go-агент на хосте, собирает метрики, процессы, сервисы, логи и выполняет команды
- `server` — FastAPI backend, принимает данные от агента, хранит состояние, раздаёт API и WebSocket
- `web` — React/Vite dashboard для оператора

Вспомогательные части:

- `deploy` — сборка релиза, установка, удаление, systemd/nginx
- `testing` — smoke и e2e проверки MVP
- `docs` — архитектурные и релизные документы

## 2. Карта репозитория

### `agent/`

Основные точки входа:

- `main.go` — старт агента, wiring collectors и WS-клиента
- `config/config.go` — загрузка YAML-конфига агента
- `ws/client.go` — WebSocket-клиент и reconnect lifecycle

Ключевые подсистемы:

- `collector/metrics.go` — CPU, RAM, disk, load average
- `collector/processes.go` — снимок процессов
- `collector/services.go` — состояние systemd-сервисов
- `collector/logs.go` — tail логов
- `executor/` — выполнение команд с backend
- `buffer/ring.go` — буфер сообщений при недоступности API

### `server/`

Основные точки входа:

- `main.py` — создание FastAPI-приложения и runtime wiring
- `asgi.py` — ASGI entrypoint для `uvicorn`
- `config.py` — схема и загрузка конфига
- `db.py` — SQLite, migrations, write queue

API:

- `api/health.py`
- `api/metrics.py`
- `api/processes.py`
- `api/services.py`
- `api/logs.py`
- `api/security.py`
- `api/ml_status.py`

WebSocket:

- `ws/agent.py` — вход от агента
- `ws/frontend.py` — live updates для UI

Security / ML / background:

- `security/` — rule-based detection и response logic
- `ml/` — anomaly detector, classifier, training
- `tasks/` — retention и expiry задачи
- `migrations/` — SQL migration files

### `web/`

Основные точки входа:

- `src/main.tsx`
- `src/app/App.tsx`

Структура:

- `pages/` — основные экраны
- `components/metrics/` — карточки и графики overview
- `components/ui/` — общие UI-компоненты
- `hooks/` — API/polling/live-state hooks
- `lib/api.ts` — HTTP client
- `lib/ws.ts` — frontend WebSocket client
- `stores/store.ts` — zustand store
- `types/index.ts` — типы UI

E2E:

- `e2e/playwright.config.ts`
- `e2e/mvp.spec.ts`

## 3. Как данные проходят по системе

1. Агент собирает метрики, процессы, сервисы и логи на хосте.
2. Агент отправляет их в backend через `/ws/agent`.
3. Backend:
   - пишет данные в SQLite
   - обновляет in-memory snapshots
   - rule-based и частично ML-логика создают security events
   - рассылает live updates во frontend WS
4. UI читает:
   - API для текущего состояния
   - `/ws/live` для live-обновлений

## 4. Локальная разработка

### Agent

```bash
cd agent
go test ./...
```

### Server

```bash
cd server
python3 -m venv venv
./venv/bin/pip install -r requirements-dev.txt
./venv/bin/pytest -q
```

Если нужно поднять backend локально:

```bash
cd server
./venv/bin/python -m uvicorn asgi:app --host 127.0.0.1 --port 8000
```

### Web

```bash
cd web
npm ci --include=dev
npm run build
```

Для e2e:

```bash
cd web
npx playwright install --with-deps chromium
npx playwright test -c e2e/playwright.config.ts
```

## 5. Сборка релиза

```bash
./deploy/build.sh
```

После этого готовый пакет лежит в `dist/`.

## 6. Установка и удаление

Установка:

```bash
cd dist
./install.sh
```

Удаление:

```bash
cd dist
./uninstall.sh
```

После установки полезные проверки:

```bash
curl http://127.0.0.1:8000/api/health ; echo
nullius-ctl status
```

## 7. Что запускать перед коммитом

Минимальный набор:

```bash
cd agent && go test ./...
cd ../server && ./venv/bin/pytest -q
cd ../web && npm run build
```

Для изменений, влияющих на runtime/UI, желательно ещё:

```bash
./testing/run_mvp_suite.sh
```

## 8. Важные архитектурные правила

- Не смешивай агентский секрет и API Bearer token.
- Не клади runtime-артефакты в git.
- Не добавляй хрупкие install hotfix вручную, если их можно зашить в `deploy/`.
- Не добавляй глобальный агрессивный polling во frontend без причины.
- Любые live/update флоу проверяй и через API, и через WebSocket сценарии.

## 9. Если нужно быстро понять текущее состояние проекта

Сначала открой:

- `README.md`
- `docs/release-checklist.md`
- `docs/technical-audit-2026-03-26.md`
- `testing/README.md`

Этого достаточно, чтобы быстро войти в проект без чтения всего кода подряд.
