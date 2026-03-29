# Nullius Testing Module

Этот модуль нужен для быстрой проверки, что MVP действительно работает end-to-end.

Состав:

- `smoke/mvp_smoke.py`
  Проверяет system/API/functionality:
  health, metrics, services, processes, logs, security API, block/unblock IP,
  появление временного процесса и тестовой лог-записи.
- `smoke/port_scan_smoke.py`
  Проверяет runtime-детекцию сканирования портов как поведения, а не конкретного инструмента.
- `smoke/incident_investigation_smoke.py`
  Проверяет, что detail API инцидента на живом стенде отдаёт progression, evidence, resolution summary и связанный response context.
- `../web/e2e/playwright.config.ts`
  Конфиг Playwright для проверки UI.
- `../web/e2e/mvp.spec.ts`
  E2E smoke-набор для UI: dashboard, navigation, settings, security workflow.
- `run_mvp_suite.sh`
  Оркестратор полного прогона.
- `run_security_validation_suite.sh`
  Security-ориентированный прогон: MVP smoke + incident investigation + optional runtime port scan smoke.

## Быстрый запуск на сервере

```bash
python3 testing/smoke/mvp_smoke.py
NULLIUS_SCAN_TARGET_HOST=<ip_сервера> python3 testing/smoke/port_scan_smoke.py
cd web && npm ci --include=dev && npx playwright test -c e2e/playwright.config.ts
```

Если запускаешь server unit/integration тесты локально, ставь dev-зависимости Python отдельно:

```bash
cd server
python3 -m venv venv
./venv/bin/pip install -r requirements-dev.txt
./venv/bin/python -m pip_audit
./venv/bin/ruff check .
```

Или одной командой:

```bash
./testing/run_mvp_suite.sh
```

Для security-oriented прогона на живом стенде:

```bash
NULLIUS_SCAN_TARGET_HOST=<ip_сервера> ./testing/run_security_validation_suite.sh
```

Для полного acceptance на живом сервере после чистой переустановки:

```bash
sudo ./testing/run_release_acceptance.sh --destructive
```

Сценарий специально вынесен в отдельный скрипт, потому что он разрушительно переустанавливает текущий стенд.

Особенности smoke:
- `testing/smoke/mvp_smoke.py` ориентирован на установленный Nullius на Linux-хосте
- после переустановки через актуальный `install.sh` Nullius сама включает лёгкий logging hook для TCP SYN, поэтому `testing/smoke/port_scan_smoke.py` должен работать без ручного включения UFW
- на установленном стенде теперь также работает `nullius-backup.timer`, который создаёт резервные копии БД и конфига в `/opt/nullius/backups`
- recovery path теперь тоже считается частью MVP-проверки:
  - `nullius-backup`
  - `nullius-verify-backup`
  - при отдельном окне обслуживания можно прогнать `nullius-restore <archive>`
- для standby-пары полезно регулярно прогонять `nullius-failover-drill`
- если включён `failover.enabled`, полезно держать под наблюдением `nullius-failover-orchestrator.timer`
- `testing/smoke/incident_investigation_smoke.py` полезен после changes в incidents, response trail и operator workflow
- `run_security_validation_suite.sh` удобен как отдельный hostile-pass перед релизом detection/policy/investigation изменений
- новый сценарий расследования логов лучше проверять руками через UI: `Security -> Related logs`, чтобы убедиться, что переход собирает корректные фильтры по IP, времени и типу события
- для runtime port scan smoke задавай `NULLIUS_SCAN_TARGET_HOST` как адрес сервера, который реально попадёт в firewall/kernel лог
- если запуск идёт не на Linux или `systemctl` недоступен, systemd-проверки будут пропущены с `WARN`
- для финального MVP-вердикта лучше прогонять suite на целевом сервере, а не только на локальной машине разработки

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
