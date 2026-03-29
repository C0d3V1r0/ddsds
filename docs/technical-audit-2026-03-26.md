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
- убран небезопасный fallback `api token -> agent secret`
- UI WebSocket auth разведен с агентским секретом через отдельный `api.ws_token` / `NULLIUS_WS_TOKEN`
- включён реальный nginx rate limiting для `/api`, `/ws/live` и `/ws/agent`
- `/ws/agent` переведён в deny-by-default режим с отдельным nginx allowlist для доверенных сетей агента
- CORS origins вынесены из хардкода в `api.cors_origins`
- модель реакции на угрозы стала прозрачнее: `logged`, `review_required`, `auto_block`
- статус anomaly detector теперь отдаёт расширенное состояние и причину, а не только `ready`
- ML training loop теперь использует `ml.training_period` из конфига вместо хардкода
- подготовка baseline для anomaly detector вынесена в отдельный dataset builder с quality score, clean/discarded samples и фильтрацией шумных интервалов вокруг security events
- detection layer приведён к structured framework с явным registry правил вместо разрозненного роутинга по source
- `port_scan` больше не является “висячим” типом события: добавлен реальный detector по firewall/kernel логам и end-to-end enrich/policy path
- detection coverage усилен новыми сценариями: `command_injection` и `web_login_bruteforce`, чтобы продукт лучше видел реальные web-атаки и credential abuse beyond SSH
- проведён отдельный `functional-first` refactor pass: detection/baseline pipeline избавлен от лишних data-only классов, а `processes API` и frontend security hooks стали менее связанными и проще для тестирования
- добавлен `Response trail`: backend теперь хранит этапы `detected -> decision -> command_dispatched -> command_result`, а UI умеет показать эту цепочку для конкретного события или инцидента
- incident workflow вырос в полноценный detail API: инцидент теперь отдаёт progression, evidence summary, blocked context, operator notes и resolution summary, а frontend перестал собирать расследование из разрозненных запросов
- risk score теперь поддерживает историю снапшотов и тренд, а не только текущее мгновенное значение
- для single-server resilience добавлен встроенный backup-контур: `nullius-backup.timer` регулярно сохраняет БД и конфиг в `/opt/nullius/backups`
- backup-контур доведён до recovery-цикла: добавлены `nullius-verify-backup` и `nullius-restore`, так что resilience теперь покрывает не только создание архива, но и проверяемое восстановление
- добавлен первый честный шаг к warm standby: `deployment.role = primary|standby`, пассивный standby-режим без active response / mutating loops и отдельный `nullius-promote-standby` для безопасного ручного promote
- standby-контур усилен эксплуатационно: появился `primary lock` как anti-split-brain safeguard, non-destructive `nullius-failover-drill` и отдельный `failover-runbook.md`
- добавлен осторожный `failover orchestration` для standby: systemd timer следит за доступностью primary по health API, ждёт порог подряд неудачных проверок и не запускает promote, пока удерживается `primary lock`
- добавлен self-protection audit самой платформы: backend проверяет небезопасные режимы UI auth, overly broad CORS, транспорт агента и права доступа к `nullius.yaml` / `agent.key`, а `Система` показывает это отдельной карточкой

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
- системная сводка вынесена в отдельную страницу `Система`, а `Настройки` оставлены для реальных UI-предпочтений
- на графиках прорежены подписи осей, чтобы они не слипались
- логи получили фильтр по диапазону времени, а процессы — разделение `Завершить` / `Убить`
- `Logs Investigation` доведён до реального расследовательского workflow: из `Security` можно открыть связанные логи, а backend умеет фильтровать буфер по IP, поисковому запросу и типу события

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
- добавлен отдельный `security validation suite` для hostile/investigation regression-прохода на живом стенде
- e2e перенесён под `web/e2e`, чтобы зависимости резолвились штатно
- `build.sh` и `run_mvp_suite.sh` теперь принудительно тянут frontend dev-зависимости для e2e
- добавлены regression tests для install/runtime/config/security/live-logs

## Текущее состояние

Можно считать, что:

- Nullius оформился как self-hosted платформа защиты Linux-сервера, а не как набор разрозненных security-скриптов
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
