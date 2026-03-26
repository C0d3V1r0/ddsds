# Nullius Technical Audit

Дата: 2026-03-26

## Что проверено

- архитектура install/runtime/update
- backend auth, WebSocket flows, input validation
- frontend data flow, polling, bundle size
- UX состояния loading/error/empty
- repo hygiene и runtime/dev separation
- smoke/e2e контур MVP

## Что исправлено

### Runtime / Deploy

- backend теперь читает `agent.key` рядом с `nullius.yaml`
- чистая установка больше не требует ручного `systemd override`
- `install.sh` стал детерминированнее при повторной раскатке
- `uninstall.sh` удаляет систему почти под ноль
- `.htpasswd` получает корректные права для nginx

### Backend / Security

- ручная блокировка IP получила жёсткую pydantic-валидацию
- `duration` для ручного блока ограничен и валидируется
- live-логи действительно рассылаются во frontend WS
- исправлен runtime-баг в `ws.frontend.broadcast`
- auth-модель для MVP упрощена и приведена к рабочей схеме
- Bearer auth API разведен с агентским секретом через отдельный `api.token` / `NULLIUS_API_TOKEN`
- CORS origins вынесены из хардкода в `api.cors_origins`

### Frontend / Performance

- включён route-based lazy loading
- основной frontend bundle уменьшен примерно с `~624 kB` до `~240 kB`
- глобальный `refetchInterval` по умолчанию убран из QueryClient
- polling остался только на реально обновляемых данных
- тяжёлый код графиков вынесен в отдельный lazy chunk `MetricChart`

### UX / UI

- overview получил системный summary
- loading/error/empty состояния стали единообразнее
- `Security`, `Processes`, `Settings`, `Logs` стали понятнее в first-run сценарии
- ручные действия на `Security` стали яснее и безопаснее

### Repo Hygiene

- runtime и dev Python dependencies разделены
- удалены лишние зависимости `pydantic-settings`, `websockets`
- из git убраны runtime артефакты:
  - `agent/nullius-agent`
  - `server/data/*.db-shm`
  - `server/data/*.db-wal`
- усилен `.gitignore`

### QA / Testing

- добавлен smoke-модуль MVP
- добавлен e2e smoke на Playwright
- e2e перенесён под `web/e2e`, чтобы зависимости резолвились штатно
- `build.sh` и `run_mvp_suite.sh` теперь принудительно тянут frontend dev-зависимости для e2e
- добавлены regression tests для install/runtime/config/security/live-logs

## Текущее состояние

Можно считать, что:

- MVP функционально рабочий
- чистая установка воспроизводима
- uninstall воспроизводим
- smoke/test контур покрывает базовые рабочие сценарии

## Remaining Technical Debt

### P1

- bundle всё ещё можно уменьшить дальше, прежде всего за счёт heavy dashboard chunk
- стоит сделать отдельные reusable page-level components для intro/actions/status sections
- часть polling всё ещё дублирует live-поток и может быть уменьшена
- отсутствует формальный reboot-test в автоматическом CI контуре

### P2

- нужен более строгий accessibility pass по кнопкам, таблицам и focus states
- нужен отдельный release/ops документ с upgrade flow
- можно дополнительно нормализовать naming/comments по всему репозиторию

## Release Criteria

Сборку можно считать готовой к MVP-использованию, если выполняются:

1. `./deploy/build.sh`
2. чистая установка через `dist/install.sh`
3. `curl http://127.0.0.1:8000/api/health`
4. `python3 testing/smoke/mvp_smoke.py`
5. `cd web && npx playwright test -c e2e/playwright.config.ts`

Ожидаемый runtime результат:

```json
{"status":"ok","agent":"connected","db":"ok"}
```
