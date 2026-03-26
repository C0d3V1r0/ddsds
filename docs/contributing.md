# Contributing

Короткие правила для тех, кто вносит изменения в Nullius.

## Перед началом

- не коммить локальные артефакты
- не коммить секреты, `.env`, runtime DB, build output
- не возвращай в репозиторий `.superpowers`, `docs/superpowers`, `node_modules`, `dist`, `venv`

## Правило изменений

Если правишь часть системы, старайся понять соседние контуры:

- меняешь `agent` → проверь `server/ws/agent.py`
- меняешь API → проверь hooks/UI
- меняешь install/runtime → проверь smoke/release flow
- меняешь live updates → проверь polling + WS

## Минимальные проверки перед push

```bash
cd agent && go test ./...
cd ../server && ./venv/bin/pytest -q
cd ../web && npm run build
```

Если изменение затрагивает MVP flow:

```bash
./testing/run_mvp_suite.sh
```

## Что считается хорошим change set

- изменение решает конкретную проблему
- есть проверка или тест
- не тащит лишний мусор в diff
- не ломает install/uninstall/runtime
- не ухудшает читаемость проекта
