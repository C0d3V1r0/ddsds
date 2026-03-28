# Nullius

Nullius — self-hosted платформа защиты Linux-сервера, которая собирает системную телеметрию, анализирует логи и метрики, выявляет угрозы и аномалии, отображает состояние хоста в реальном времени и позволяет применять защитные действия с полным локальным контролем над данными и инфраструктурой.

В основе Nullius лежит хост-агент, который работает непосредственно на сервере, собирает метрики, читает системные и веб-логи, отслеживает процессы и сервисы, а также выполняет команды реакции. Эти данные передаются в backend Nullius, где они сохраняются, обрабатываются, визуализируются и анализируются. Платформа использует rule-based detection и локально работающие ML-модули для классификации атак и поиска аномалий, не отправляя чувствительную телеметрию, логи и security events во внешние AI или LLM сервисы.

Nullius предоставляет единый live-dashboard, где можно видеть CPU, RAM, диск, сеть, процессы, сервисы, логи, события безопасности, состояние ML-модуля и состояние самой платформы. Система умеет обнаруживать подозрительную активность, фиксировать security events, автоматически или вручную блокировать IP-адреса, завершать процессы, перезапускать разрешённые сервисы и помогать оператору принимать решения по защите хоста.

Иными словами, Nullius — это не просто мониторинг, не просто IDS и не просто панель логов, а единая локальная платформа наблюдения, анализа и реакции для защиты Linux-сервера.

## Что входит в платформу

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

Runtime-проверка детекции сканирования портов:

```bash
NULLIUS_SCAN_TARGET_HOST=<ip_сервера> python3 testing/smoke/port_scan_smoke.py
```

Полный прогон:

```bash
./testing/run_mvp_suite.sh
```

Полный destructive acceptance на живом сервере:

```bash
sudo ./testing/run_release_acceptance.sh --destructive
```

Примечание:
- smoke-набор рассчитан в первую очередь на установленный Nullius на Linux-хосте
- на macOS и других non-systemd окружениях проверки `systemctl` будут автоматически пропущены с предупреждением
- финальный verdict по MVP лучше получать на целевом сервере, где действительно подняты `nullius-api`, `nullius-agent` и `nginx`

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
- [docs/product-roadmap.md](docs/product-roadmap.md)
- [docs/paradigms.md](docs/paradigms.md)

## Архитектурные заметки

- Dashboard защищён через nginx basic auth.
- Внутренний Bearer auth и WS token для UI по умолчанию отключены и могут быть включены через `api.require_bearer_auth` и `api.require_ws_token` в `nullius.yaml`.
- Если Bearer auth включён, обязательно задай отдельный `api.token` или env `NULLIUS_API_TOKEN`.
- Если включён WS token для UI, задай отдельный `api.ws_token` / `NULLIUS_WS_TOKEN` или осознанно переиспользуй UI API token.
- API token больше не fallback'ится к `agent.key`/`NULLIUS_AGENT_SECRET`.
- UI WebSocket token тоже больше не fallback'ится к `agent.key`/`NULLIUS_AGENT_SECRET`.
- Разрешённые cross-origin источники задаются через `api.cors_origins`.
- Агент использует `agent.key`, лежащий рядом с `nullius.yaml`.
- `/ws/agent` теперь закрыт deny-by-default allowlist'ом на уровне nginx; для внешнего агента нужно явно разрешить доверенную подсеть в `snippets/nullius-agent-allowlist.conf`.
- Основной runtime health-check: `/api/health`.
- Интервал фонового обучения anomaly detector теперь управляется через `ml.training_period`, а первый запуск не откладывается дольше чем на 15 минут.
- При шумном окне anomaly detector теперь старается обучаться не на всём окне целиком, а на очищенном baseline: участки метрик рядом с security events автоматически исключаются из обучения.
- Подготовка baseline вынесена в отдельный ML-этап: для обучающего датасета теперь считаются clean/discarded samples и quality score, чтобы UI и backend видели качество обучения, а не только факт запуска.
- Nginx-конфиг теперь включает реальный rate limiting для `/api` и WebSocket-точек, а не только документирует его.
- Detection layer оформлен как лёгкий внутренний framework с явным реестром правил, чтобы новые типы событий появлялись в системе только вместе с реальным detector-ом.
- `port_scan` теперь действительно детектится по firewall/kernel логам через число уникальных destination ports в коротком окне, а не существует только как UI-тип события.
- Агент по умолчанию пытается читать не только `auth` и `nginx`, но и optional firewall-источники (`/var/log/ufw.log`, `/var/log/kern.log`); отсутствие этих файлов больше не создаёт постоянный log-spam.
- `install.sh` теперь сама включает лёгкий iptables logging hook для новых TCP SYN-попыток, чтобы детекция `port_scan` работала из коробки без ручного включения UFW.

## Модель реакции на угрозы

- `logged` — событие зафиксировано, но активная реакция не применялась.
- `review_required` — событие требует внимания оператора, но система не делает autoblock.
- `auto_block` — IP был автоматически заблокирован.

Текущее поведение по умолчанию:

- rule-based `ssh_brute_force` и `sqli` могут уйти в `auto_block`, если у события есть IP и включён `security.auto_block`
- `medium` severity и ML-события идут в `review_required`
- слабые/informational события остаются `logged`

## Что есть в UI

- `Обзор` показывает метрики именно Linux-хоста: CPU, RAM, диск, сеть, сервисы и свежие security events.
- `Система` показывает состояние самой платформы Nullius: API, агент, БД, ML-модуль и сведения о развёртывании.
- В `Система` риск сервера теперь показывает не только текущий score, но и краткий тренд по накопленной истории risk snapshots.
- `Процессы` поддерживают два уровня действия:
  - `Завершить` — мягкое завершение через `SIGTERM`
  - `Убить` — принудительный `SIGKILL` для обычных user-space процессов
- `Логи` поддерживают серверную фильтрацию по источнику, диапазону `from/to`, IP, типу события и поисковому запросу.
- Из `Безопасность` можно сразу перейти к связанным логам инцидента или отдельного события с уже собранным расследовательским контекстом.
- В `Безопасность` появился `Response trail`: для события или инцидента можно открыть цепочку `signal -> decision -> command -> result` и понять, что именно сделала система и чем это закончилось.
- `ML-модуль` для anomaly detector показывает не только `ready`, но и понятную причину текущего состояния: ожидание, обучение, недостаточно данных, недостаточно чистых данных, отложено, ошибка.
- Для anomaly detector в `Система` теперь также показывается качество baseline: сколько метрик реально вошло в clean dataset и сколько было отброшено как шум.
- В разделе `Интеграции` можно подключить Telegram-бота по токену, привязать чат через `/start`, получать уведомления об автоблокировках и событиях высокого уровня, а также запрашивать `/status`, `/risk`, `/incidents`.
- В разделе `Интеграции` можно подключить Slack через `Incoming Webhook`, выбрать типы уведомлений и отправить тестовое сообщение прямо из UI.

## Отказоустойчивость single-server развёртывания

- API и agent работают под `systemd` с автоперезапуском.
- SQLite использует `WAL`, а запись идёт через последовательную очередь.
- Nullius теперь автоматически снимает резервные копии БД и конфига через `nullius-backup.timer`.
- Бэкапы складываются в `/opt/nullius/backups` и автоматически чистятся по retention.

## Основные команды

```bash
nullius-ctl status
nullius-ctl logs --follow
nullius-ctl smoke
nullius-ctl set-password
nullius-ctl uninstall
```
