# Nullius v2 — Design Specification

## Overview

Nullius v2 — self-hosted «иммунная система» для Linux-серверов (Ubuntu/Debian). Устанавливается одной командой, работает полностью локально. Мониторит здоровье сервера, детектит угрозы (rule-based + ML), автоматически реагирует на атаки.

**Тип:** Self-hosted security platform
**Целевая ОС:** Ubuntu 20.04+ / Debian 11+
**Архитектура:** Микросервисы на одной машине

## MVP Scope

- **Мониторинг:** CPU, RAM, диск, сеть, сервисы, порты, логи
- **Security:** SSH brute-force, веб-атаки (SQLi, XSS, path traversal), блокировка IP (авто + ручная), мониторинг процессов
- **ML:** Детекция аномалий в метриках (Isolation Forest), классификация типа атаки (TF-IDF + LinearSVC)
- **Базовая аутентификация:** доступ к дашборду защищён паролем (задаётся при установке)

**Не входит в MVP:** Мультитенантность, уведомления (Telegram/Email), монетизация, RBAC.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│              Сервер клиента (Ubuntu/Debian)           │
│                                                       │
│  ┌─────────────┐    WebSocket     ┌──────────────┐   │
│  │  Go Agent   │ ──────────────→  │  FastAPI     │   │
│  │             │ ←──────────────  │  (API + ML)  │   │
│  │ • metrics   │  shared secret   │              │   │
│  │ • logs      │                  │ • REST API   │   │
│  │ • security  │                  │ • ML engine  │   │
│  │ • executor  │                  │ • WS server  │   │
│  └─────────────┘                  └──────┬───────┘   │
│                                          │           │
│                                     ┌────┴────┐     │
│                                     │ SQLite  │     │
│                                     └─────────┘     │
│                                          │           │
│  ┌─────────────┐                 ┌───────┴───────┐  │
│  │   Nginx     │ ←── proxies ──→ │  React SPA    │  │
│  │ (TLS/auth)  │                 │  (статика)    │  │
│  └─────────────┘                 └───────────────┘  │
└──────────────────────────────────────────────────────┘
```

**3 systemd-сервиса:**
1. `nullius-agent` — Go бинарник, root (доступ к логам, iptables, процессам)
2. `nullius-api` — FastAPI, непривилегированный пользователь `nullius`
3. `nginx` — TLS-терминация, basic auth, отдаёт React-статику, проксирует `/api` → FastAPI

**Потоки данных:**
- Agent собирает метрики каждые 5-10 секунд → шлёт по WebSocket в API
- API обрабатывает, пишет в SQLite, прогоняет через ML
- ML детектит аномалию → API шлёт команду агенту через WS (заблокировать IP, убить процесс)
- Фронтенд подключается к API по REST + отдельный WS для live-обновлений

**Порты:**
- `443` — Nginx (TLS, basic auth, фронтенд + проксирование API)
- `80` — Nginx (redirect → 443)
- `8000` — FastAPI (только 127.0.0.1, не доступен извне)
- Agent подключается к API по `ws://127.0.0.1:8000/ws/agent`

---

## Security Model

### Аутентификация дашборда

- Nginx basic auth — пароль задаётся при установке (`nullius-ctl set-password`)
- `/api/*` и `/ws/live` защищены через Nginx basic auth
- Пароль хранится в `/opt/nullius/config/.htpasswd` (bcrypt hash)
- При установке генерируется случайный пароль и выводится в консоль

### Аутентификация агента

- Shared secret в `/opt/nullius/config/agent.key` (генерируется при установке)
- Agent отправляет secret в первом WS-сообщении (handshake)
- API отклоняет соединения без валидного secret

### TLS

- При установке: самоподписанный сертификат (генерируется автоматически)
- `nullius-ctl tls --domain example.com` — Let's Encrypt через certbot
- HTTP → HTTPS redirect по умолчанию

### Защита от command injection

**Whitelist сервисов** (настраивается в nullius.yaml):
```yaml
security:
  allowed_services:
    - nginx
    - postgresql
    - redis
    - mysql
    - docker
```
Агент отклоняет `restart_service` для сервисов не из whitelist.

**Deny-list процессов** (захардкожен в агенте, не переопределяется):
- PID 1 (init/systemd)
- nullius-agent (свой PID)
- nullius-api
- sshd
- systemd-*

Агент отклоняет `kill_process` для этих процессов.

**Валидация параметров:**
- `ip` — валидация формата IPv4/IPv6
- `pid` — только числа, проверка deny-list
- `name` — только `[a-zA-Z0-9_-]`, проверка whitelist
- `duration` — только числа, макс 30 дней

---

## Tech Stack

| Компонент | Технология | Обоснование |
|-----------|------------|-------------|
| Агент | Go | Лёгкий бинарник, минимальный footprint, кросс-компиляция |
| API | FastAPI (Python) | Быстрая разработка, нативная интеграция с ML |
| БД | SQLite (WAL mode) | Zero-config, один файл, достаточно для self-hosted |
| Фронтенд | React 18 + TypeScript | Стандарт для дашбордов |
| Стилизация | Tailwind CSS | Dark + gradient accents (CrowdStrike-style), dark/light toggle |
| Графики | Recharts | Time-series визуализация |
| Стейт | Zustand | Лёгкий, простой |
| API-кэш | TanStack Query | Кэширование REST-запросов |
| Сборка | Vite | Быстрый dev-server и build |
| ML | scikit-learn (Isolation Forest, LinearSVC) | Проверенные алгоритмы, лёгкие модели |
| Связь Agent ↔ API | WebSocket | Реальное время, двусторонняя связь |

---

## Go Agent

**Ответственность:** сбор данных и выполнение команд. Ничего не решает сам — только собирает и делает то, что скажет API.

### Модули сбора

| Модуль | Что собирает | Источник | Интервал |
|--------|-------------|----------|----------|
| `metrics` | CPU, RAM, disk, network, load average | `/proc/stat`, `/proc/meminfo` | 5 сек |
| `services` | Статус systemd-юнитов, порты | `systemctl`, `ss` | 30 сек |
| `logs` | Новые строки из логов | `/var/log/auth.log`, nginx, journald | realtime (tail) |
| `processes` | Список процессов, CPU/RAM каждого | `/proc/[pid]/stat` | 10 сек |
| `network` | Активные соединения, открытые порты | `/proc/net/tcp`, `ss` | 10 сек |

### Формат сообщений (Agent → API)

```json
{
  "type": "metrics",
  "timestamp": 1774464000,
  "data": {
    "cpu": {"total": 23.5, "cores": [12.1, 35.0]},
    "ram": {"total": 8192, "used": 5500, "percent": 67.1},
    "disk": [{"mount": "/", "total": 50000, "used": 22500}],
    "network": {"rx_bytes_delta": 123456, "tx_bytes_delta": 78901}
  }
}
```

Поле `network` передаёт **дельты** (разница с предыдущим замером), не абсолютные значения. Агент хранит предыдущие значения счётчиков в памяти.

```json
{
  "type": "log_event",
  "timestamp": 1774464001,
  "data": {
    "source": "auth",
    "line": "Failed password for root from 192.168.1.100 port 22 ssh2",
    "file": "/var/log/auth.log"
  }
}
```

### Команды (API → Agent)

```json
{"id": "cmd_1234", "command": "block_ip", "params": {"ip": "192.168.1.100", "duration": 86400}}
```

### Ответы на команды (Agent → API)

```json
{"type": "command_result", "id": "cmd_1234", "status": "success"}
{"type": "command_result", "id": "cmd_5678", "status": "error", "error": "service not in whitelist"}
```

Каждая команда имеет уникальный `id`. Агент отвечает с тем же `id` и статусом. API ждёт ответ до 10 секунд, иначе — timeout.

### Executor

- `block_ip` → `iptables -A INPUT -s <ip> -j DROP` (валидация IP формата)
- `unblock_ip` → `iptables -D INPUT -s <ip> -j DROP`
- `kill_process` → `kill -15 <pid>`, через 5 сек `kill -9` если жив (проверка deny-list)
- `restart_service` → `systemctl restart <name>` (проверка whitelist)

### WebSocket Reconnect & Heartbeat

- Агент отправляет `{"type": "ping"}` каждые 15 секунд
- API отвечает `{"type": "pong"}`
- Если 3 пинга без ответа — агент переподключается с exponential backoff (1с, 2с, 4с, 8с, макс 60с)
- Во время разрыва агент буферизует метрики в ring buffer (макс 1000 сообщений), отправляет после reconnect
- API детектит отсутствие агента если нет сообщений >30 сек → выставляет статус "agent offline" на дашборде

### Graceful Shutdown

- SIGTERM → агент отправляет `{"type": "disconnect", "reason": "shutdown"}`, flush буфера, выход
- SIGINT → аналогично SIGTERM

### Безопасность агента

- Аутентификация через shared secret при handshake
- Команды принимает только от локального API (127.0.0.1)
- Whitelist разрешённых команд — нельзя выполнить произвольную команду
- Deny-list критических процессов — нельзя убить sshd, init, себя
- Whitelist сервисов — нельзя перезапустить произвольный сервис
- Валидация всех параметров (IP формат, числовой PID, имя сервиса)
- Лог всех выполненных команд

---

## FastAPI Backend

### Структура

```
server/
├── main.py                  # Точка входа, uvicorn
├── config.py                # Конфигурация из YAML
├── db.py                    # SQLite подключение, миграции
├── migrations/              # Пронумерованные SQL-скрипты (001_init.sql, 002_xxx.sql)
├── ws/
│   ├── agent.py             # WebSocket хендлер для агента
│   └── frontend.py          # WebSocket хендлер для фронтенда (live updates)
├── api/
│   ├── metrics.py           # GET /api/metrics, /api/metrics/history
│   ├── services.py          # GET /api/services
│   ├── security.py          # GET /api/security/events, POST /api/security/block
│   ├── processes.py         # GET /api/processes
│   ├── logs.py              # GET /api/logs
│   └── health.py            # GET /api/health
├── security/
│   ├── detector.py          # Правила детекции (SSH brute-force, SQLi, XSS)
│   ├── responder.py         # Логика автоответа
│   └── rules.py             # Конфигурируемые правила из YAML
├── tasks/
│   ├── retention.py         # Очистка старых данных по расписанию
│   └── expiry.py            # Разблокировка IP с истёкшим expires_at
└── ml/
    ├── anomaly.py            # Isolation Forest — train, predict, retrain
    ├── classifier.py         # TF-IDF + LinearSVC — train, predict
    ├── trainer.py            # Общий интерфейс обучения
    ├── features.py           # Извлечение фичей из сырых метрик и логов
    ├── datasets/
    │   └── base_attacks.csv  # Базовый датасет поставляемый с продуктом
    └── models/               # Сохранённые .joblib файлы
```

### API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/health` | Статус API, агента, БД, ML |
| GET | `/api/metrics` | Текущие метрики |
| GET | `/api/metrics/history?period=1h` | История метрик |
| GET | `/api/services` | Статус сервисов |
| GET | `/api/processes` | Список процессов |
| GET | `/api/security/events` | События безопасности |
| GET | `/api/security/blocked` | Заблокированные IP |
| POST | `/api/security/block` | Заблокировать IP вручную |
| POST | `/api/security/unblock` | Разблокировать IP |
| GET | `/api/logs?source=auth&limit=100` | Логи |
| GET | `/api/ml/status` | Статус ML-моделей |
| WS | `/ws/agent` | Канал агента (shared secret auth) |
| WS | `/ws/live` | Live-обновления для фронтенда |

### Поток обработки событий

```
Agent шлёт log_event
       ↓
detector.py — проверяет правила
  • SSH: 5+ неудачных попыток за 5 мин с одного IP
  • Web: regex-паттерны SQLi, XSS, path traversal
  • Process: подозрительные имена, высокое потребление
       ↓
responder.py — решает что делать
  • severity: low → логирует
  • severity: medium → логирует (уведомления — post-MVP)
  • severity: high → автоблок IP
  • severity: critical → блок + помечает для внимания на дашборде
       ↓
ml/anomaly.py — параллельно проверяет метрики
  • Isolation Forest на CPU/RAM/Network
  • Первые 24ч — режим обучения, используется только rule-based детекция
  • После обучения: если аномалия → событие в security
       ↓
SQLite ← сохраняет событие (async write через queue, retry при SQLITE_BUSY)
       ↓
WS /ws/live → пушит на фронтенд
```

### Background Tasks

**Retention cleanup** (запускается раз в час):
- Удаляет метрики старше 30 дней
- Удаляет security events старше 90 дней
- Удаляет agent commands старше 30 дней

**IP expiry check** (запускается каждые 60 секунд):
- Находит blocked_ips с `expires_at < now()`
- Отправляет команду `unblock_ip` агенту
- Удаляет запись из таблицы

**DB write queue:**
- Все записи в SQLite идут через asyncio.Queue
- Один writer-воркер, исключает contention
- При SQLITE_BUSY — retry с backoff (10ms, 20ms, 40ms, макс 3 попытки)

### Миграции БД

- Пронумерованные SQL-файлы: `001_init.sql`, `002_add_index.sql`, ...
- Таблица `schema_version` хранит текущую версию
- При старте API автоматически применяет непримёненные миграции
- `nullius-ctl update` запускает миграции перед рестартом

### Конфигурация (nullius.yaml)

```yaml
agent:
  metrics_interval: 5
  services_interval: 30
  log_sources:
    - /var/log/auth.log
    - /var/log/nginx/access.log
    - /var/log/nginx/error.log

security:
  ssh_brute_force:
    threshold: 5
    window: 300
    action: block
    block_duration: 86400
  web_attacks:
    enabled: true
    action: block
  auto_block: true
  allowed_services:
    - nginx
    - postgresql
    - redis
    - mysql
    - docker

ml:
  anomaly_detection: true
  training_period: 86400
  sensitivity: medium
```

---

## SQLite Schema

```sql
-- Версионирование схемы
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

-- Метрики
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    cpu_total REAL,
    cpu_cores TEXT,
    ram_used INTEGER,
    ram_total INTEGER,
    disk TEXT,
    network_rx INTEGER,
    network_tx INTEGER,
    load_avg TEXT
);
CREATE INDEX idx_metrics_ts ON metrics(timestamp);

-- Security события
CREATE TABLE security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    source_ip TEXT,
    description TEXT,
    raw_log TEXT,
    action_taken TEXT,
    resolved INTEGER DEFAULT 0
);
CREATE INDEX idx_security_ts ON security_events(timestamp);
CREATE INDEX idx_security_type ON security_events(type);

-- Заблокированные IP
CREATE TABLE blocked_ips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL UNIQUE,
    reason TEXT,
    blocked_at INTEGER NOT NULL,
    expires_at INTEGER,
    auto INTEGER DEFAULT 1
);

-- Статус сервисов (последний snapshot)
CREATE TABLE services (
    name TEXT PRIMARY KEY,
    status TEXT,
    pid INTEGER,
    uptime INTEGER,
    updated_at INTEGER
);

-- ML модели
CREATE TABLE ml_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    trained_at INTEGER,
    samples_count INTEGER,
    accuracy REAL,
    file_path TEXT,
    active INTEGER DEFAULT 0
);

-- Лог выполненных команд
CREATE TABLE agent_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    command TEXT NOT NULL,
    params TEXT,
    result TEXT,
    error TEXT
);
```

**Retention policy:**
- Метрики: 30 дней (~500K строк/месяц, ~50MB)
- Security events: 90 дней
- Agent commands: 30 дней
- SQLite WAL mode для конкурентного чтения/записи
- Единственный writer через asyncio.Queue — нет contention

---

## React Frontend

### Структура

```
src/
├── app/
│   ├── App.tsx
│   ├── main.tsx
│   └── router.tsx
├── pages/
│   ├── Dashboard.tsx
│   ├── Security.tsx
│   ├── Processes.tsx
│   ├── Logs.tsx
│   └── Settings.tsx
├── components/
│   ├── metrics/
│   │   ├── CpuCard.tsx
│   │   ├── RamCard.tsx
│   │   ├── DiskCard.tsx
│   │   ├── NetworkCard.tsx
│   │   └── MetricChart.tsx
│   ├── security/
│   │   ├── EventsList.tsx
│   │   ├── EventDetail.tsx
│   │   ├── BlockedIPs.tsx
│   │   └── ThreatBadge.tsx
│   ├── services/
│   │   └── ServiceStatus.tsx
│   └── ui/
│       ├── Sidebar.tsx
│       ├── Header.tsx
│       ├── Card.tsx
│       ├── Table.tsx
│       ├── Badge.tsx
│       ├── Chart.tsx
│       └── ThemeToggle.tsx
├── hooks/
│   ├── useMetrics.ts
│   ├── useSecurity.ts
│   ├── useWebSocket.ts
│   └── useLogs.ts
├── stores/
│   └── store.ts
├── lib/
│   ├── api.ts
│   └── ws.ts
└── styles/
    └── globals.css
```

### Страницы

- **Dashboard** — 4 карточки метрик с мини-графиками, CPU/RAM timeline, статус сервисов, последние 5 security-событий, ML-статус, индикатор agent online/offline
- **Security** — таблица событий с фильтрами, заблокированные IP, ручная блокировка, таймлайн атак 24ч
- **Processes** — таблица процессов (сортировка CPU/RAM), подсветка подозрительных, kill process
- **Logs** — live-стрим через WebSocket, фильтр по источнику, поиск, подсветка подозрительных строк
- **Settings** — просмотр текущего конфига nullius.yaml (read-only в MVP), статус ML-моделей, кнопка переобучения

### UI стиль

Dark + gradient accents (CrowdStrike-style):
- Тёмный фон (#0a0e1a), карточки с градиентами (#111827 → #1a1f35)
- Синие/фиолетовые акценты для метрик, красные для угроз, зелёные для нормы
- Dark/light theme toggle
- Tailwind CSS с кастомными CSS переменными для темизации

---

## ML Module

### 1. Anomaly Detector

- **Алгоритм:** Isolation Forest (sklearn)
- **Фичи:** CPU, RAM, disk I/O, network RX/TX, количество соединений, load average
- **Режим обучения (первые 24ч):** собирает baseline, ML-детекция неактивна, работает только rule-based
- **Инференс:** после обучения — каждые 5 секунд скорит новые метрики
- **Переобучение:** автоматически раз в 7 дней на последних данных
- **Выход:** score ниже порога → security event severity medium
- **Защита от poisoned baseline:** если во время обучения сработал rule-based детектор >10 раз, обучение сбрасывается и начинается заново (с предупреждением на дашборде)

### 2. Attack Classifier

- **Алгоритм:** TF-IDF + LinearSVC
- **Классы:** `ssh_brute_force`, `sqli`, `xss`, `path_traversal`, `port_scan`, `normal`
- **Датасет:** публичные WAF-датасеты (CSIC, HttpParams) + синтетика + парсинг auth.log
- **Роль:** второе мнение к rule-based detector
- **Базовая модель:** поставляется с установкой, дообучается на логах конкретного сервера

---

## Installation & Deployment

### Установка

```bash
curl -fsSL https://get.nullius.io/install.sh | sudo bash
```

**Шаги install.sh:**
1. Проверка ОС (Ubuntu 20.04+/Debian 11+) и архитектуры (amd64/arm64)
2. Создание пользователя `nullius`
3. Скачивание Go агента (предкомпилированный бинарник)
4. Установка Python 3.11+ venv + зависимости
5. Генерация дефолтного nullius.yaml
6. Генерация shared secret (`agent.key`) и пароля дашборда (`.htpasswd`)
7. Генерация самоподписанного TLS-сертификата
8. Размещение React билда в /opt/nullius/web/
9. Настройка Nginx конфига (TLS + basic auth + proxy)
10. Настройка logrotate для agent.log и api.log
11. Создание systemd-сервисов (с ресурсными лимитами)
12. Запуск всех компонентов
13. Вывод: пароль, URL `https://<server-ip>`

### Файловая структура на сервере

```
/opt/nullius/
├── bin/
│   └── nullius-agent
├── server/
│   ├── venv/
│   ├── main.py
│   ├── migrations/
│   └── ml/
│       ├── models/
│       └── datasets/
├── web/                     # React build (статика)
├── config/
│   ├── nullius.yaml
│   ├── agent.key            # Shared secret
│   └── .htpasswd            # Basic auth password
├── data/
│   └── nullius.db
└── logs/
    ├── agent.log
    └── api.log
```

### Systemd ресурсные лимиты

```ini
# nullius-agent.service
[Service]
MemoryMax=128M
CPUQuota=10%

# nullius-api.service
[Service]
MemoryMax=512M
CPUQuota=25%
```

Агент и API не съедят ресурсы сервера клиента даже при пиковой нагрузке.

### CLI-утилита nullius-ctl

```bash
nullius-ctl status          # статус всех компонентов (вызывает /api/health)
nullius-ctl logs [--follow] # просмотр логов (agent + api)
nullius-ctl config          # открыть nullius.yaml в $EDITOR
nullius-ctl set-password    # сменить пароль дашборда
nullius-ctl tls --domain X  # настроить Let's Encrypt
nullius-ctl update          # скачать новые бинарники, запустить миграции, рестарт
nullius-ctl reset-ml        # сбросить ML-модели и начать обучение заново
```

### Logrotate

```
/opt/nullius/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
```
