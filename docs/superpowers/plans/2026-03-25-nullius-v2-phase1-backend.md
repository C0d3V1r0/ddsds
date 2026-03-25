# Nullius v2 — Phase 1: FastAPI Backend + SQLite

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend with SQLite storage, WebSocket handlers for agent and frontend, security detection engine, and REST API — the core brain of Nullius.

**Architecture:** FastAPI app with async SQLite (aiosqlite), WebSocket server for Go agent ingestion and frontend live updates, rule-based security detector + responder, background tasks for retention cleanup and IP expiry. All writes go through a single asyncio.Queue writer to avoid SQLite contention.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, aiosqlite, pydantic, pyyaml, pytest, pytest-asyncio, httpx (test client)

**Spec:** `docs/superpowers/specs/2026-03-25-nullius-v2-design.md`

**Plan order:**
- Phase 1 (this plan): FastAPI Backend + SQLite
- Phase 2: Go Agent
- Phase 3: React Frontend
- Phase 4: ML Module
- Phase 5: Installation & Deployment

---

## File Structure

```
server/
├── main.py                    # FastAPI app, startup/shutdown, mount routers
├── config.py                  # Load nullius.yaml, pydantic Settings model
├── db.py                      # SQLite connection, migration runner, write queue
├── migrations/
│   └── 001_init.sql           # Initial schema
├── ws/
│   ├── agent.py               # WS /ws/agent — auth, message routing, command responses
│   └── frontend.py            # WS /ws/live — broadcast events to dashboard
├── api/
│   ├── health.py              # GET /api/health
│   ├── metrics.py             # GET /api/metrics, /api/metrics/history
│   ├── services.py            # GET /api/services
│   ├── security.py            # GET /api/security/events, /blocked, POST block/unblock
│   ├── processes.py           # GET /api/processes
│   └── logs.py                # GET /api/logs
├── security/
│   ├── detector.py            # Rule-based detection (SSH, web attacks)
│   ├── responder.py           # Decide action based on severity
│   └── rules.py               # Parse rules from config
├── tasks/
│   ├── retention.py           # Cleanup old metrics/events/commands
│   └── expiry.py              # Unblock expired IPs
├── requirements.txt           # Python dependencies
├── nullius.yaml               # Default config (dev)
└── tests/
    ├── conftest.py            # Fixtures: test db, test client, test config
    ├── test_db.py             # DB connection, migrations, write queue
    ├── test_config.py         # Config loading
    ├── test_health.py         # Health endpoint
    ├── test_metrics.py        # Metrics endpoints
    ├── test_services.py       # Services endpoint
    ├── test_security_api.py   # Security REST endpoints
    ├── test_processes.py      # Processes endpoint
    ├── test_logs.py           # Logs endpoint
    ├── test_ws_agent.py       # Agent WebSocket
    ├── test_ws_frontend.py    # Frontend WebSocket
    ├── test_detector.py       # Security detection rules
    ├── test_responder.py      # Response logic
    ├── test_retention.py      # Data retention cleanup
    └── test_expiry.py         # IP expiry
```

---

### Task 1: Project Scaffold & Config

**Files:**
- Create: `server/requirements.txt`
- Create: `server/config.py`
- Create: `server/nullius.yaml`
- Create: `server/tests/conftest.py`
- Create: `server/tests/test_config.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
aiosqlite==0.20.0
pydantic==2.9.0
pydantic-settings==2.5.0
pyyaml==6.0.2
websockets==13.0
pytest==8.3.0
pytest-asyncio==0.24.0
httpx==0.27.0
```

- [ ] **Step 2: Create Python venv and install deps**

Run:
```bash
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 3: Write failing test for config loading**

```python
# server/tests/test_config.py
import pytest
from config import load_config, NulliusConfig

def test_load_config_from_yaml(tmp_path):
    yaml_content = """
agent:
  metrics_interval: 5
  services_interval: 30
  log_sources:
    - /var/log/auth.log

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

ml:
  anomaly_detection: true
  training_period: 86400
  sensitivity: medium
"""
    config_file = tmp_path / "nullius.yaml"
    config_file.write_text(yaml_content)
    config = load_config(str(config_file))
    assert config.agent.metrics_interval == 5
    assert config.security.ssh_brute_force.threshold == 5
    assert config.security.allowed_services == ["nginx", "postgresql"]
    assert config.ml.sensitivity == "medium"

def test_load_config_defaults(tmp_path):
    yaml_content = "agent:\n  metrics_interval: 10\n"
    config_file = tmp_path / "nullius.yaml"
    config_file.write_text(yaml_content)
    config = load_config(str(config_file))
    assert config.agent.metrics_interval == 10
    assert config.agent.services_interval == 30  # default
    assert config.security.auto_block is True  # default
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 5: Implement config.py**

```python
# server/config.py
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel

class AgentConfig(BaseModel):
    metrics_interval: int = 5
    services_interval: int = 30
    log_sources: list[str] = ["/var/log/auth.log"]

class SSHBruteForceConfig(BaseModel):
    threshold: int = 5
    window: int = 300
    action: str = "block"
    block_duration: int = 86400

class WebAttacksConfig(BaseModel):
    enabled: bool = True
    action: str = "block"

class SecurityConfig(BaseModel):
    ssh_brute_force: SSHBruteForceConfig = SSHBruteForceConfig()
    web_attacks: WebAttacksConfig = WebAttacksConfig()
    auto_block: bool = True
    allowed_services: list[str] = ["nginx", "postgresql", "redis", "mysql", "docker"]

class MLConfig(BaseModel):
    anomaly_detection: bool = True
    training_period: int = 86400
    sensitivity: str = "medium"

class NulliusConfig(BaseModel):
    agent: AgentConfig = AgentConfig()
    security: SecurityConfig = SecurityConfig()
    ml: MLConfig = MLConfig()

def load_config(path: str) -> NulliusConfig:
    config_path = Path(path)
    if not config_path.exists():
        return NulliusConfig()
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    return NulliusConfig(**data)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 7: Create default nullius.yaml**

```yaml
# server/nullius.yaml
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

- [ ] **Step 8: Create conftest.py with shared fixtures**

```python
# server/tests/conftest.py
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from pathlib import Path

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_config_path(tmp_path):
    config = """
agent:
  metrics_interval: 5
  services_interval: 30
  log_sources: []
security:
  ssh_brute_force:
    threshold: 3
    window: 60
    action: block
    block_duration: 3600
  web_attacks:
    enabled: true
    action: block
  auto_block: true
  allowed_services:
    - nginx
    - test-service
ml:
  anomaly_detection: false
  training_period: 86400
  sensitivity: medium
"""
    p = tmp_path / "nullius.yaml"
    p.write_text(config)
    return str(p)
```

- [ ] **Step 9: Commit**

```bash
git add server/requirements.txt server/config.py server/nullius.yaml server/tests/conftest.py server/tests/test_config.py
git commit -m "feat(server): add project scaffold and config loading"
```

---

### Task 2: SQLite Database & Migrations

**Files:**
- Create: `server/db.py`
- Create: `server/migrations/001_init.sql`
- Create: `server/tests/test_db.py`

- [ ] **Step 1: Write failing test for DB init and migrations**

```python
# server/tests/test_db.py
import pytest
import pytest_asyncio
import aiosqlite
from db import init_db, get_db, enqueue_write, start_writer, stop_writer

@pytest_asyncio.fixture
async def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    await init_db(path)
    return path

@pytest.mark.asyncio
async def test_init_db_creates_tables(db_path):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
    assert "metrics" in tables
    assert "security_events" in tables
    assert "blocked_ips" in tables
    assert "services" in tables
    assert "ml_models" in tables
    assert "agent_commands" in tables
    assert "schema_version" in tables

@pytest.mark.asyncio
async def test_init_db_wal_mode(db_path):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("PRAGMA journal_mode")
        mode = (await cursor.fetchone())[0]
    assert mode == "wal"

@pytest.mark.asyncio
async def test_schema_version_recorded(db_path):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("SELECT version FROM schema_version")
        versions = [row[0] for row in await cursor.fetchall()]
    assert 1 in versions

@pytest.mark.asyncio
async def test_write_queue(db_path):
    writer_task = await start_writer(db_path)
    await enqueue_write(
        "INSERT INTO metrics (timestamp, cpu_total) VALUES (?, ?)",
        (1000, 23.5)
    )
    await stop_writer(writer_task)
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("SELECT cpu_total FROM metrics WHERE timestamp = 1000")
        row = await cursor.fetchone()
    assert row[0] == 23.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Create migration SQL**

```sql
-- server/migrations/001_init.sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
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
CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(timestamp);

CREATE TABLE IF NOT EXISTS security_events (
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
CREATE INDEX IF NOT EXISTS idx_security_ts ON security_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_security_type ON security_events(type);

CREATE TABLE IF NOT EXISTS blocked_ips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL UNIQUE,
    reason TEXT,
    blocked_at INTEGER NOT NULL,
    expires_at INTEGER,
    auto INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS services (
    name TEXT PRIMARY KEY,
    status TEXT,
    pid INTEGER,
    uptime INTEGER,
    updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS ml_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    trained_at INTEGER,
    samples_count INTEGER,
    accuracy REAL,
    file_path TEXT,
    active INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS agent_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    command TEXT NOT NULL,
    params TEXT,
    result TEXT,
    error TEXT
);
```

- [ ] **Step 4: Implement db.py**

```python
# server/db.py
import asyncio
import time
from pathlib import Path
from typing import Optional
import aiosqlite

_write_queue: asyncio.Queue = asyncio.Queue()
_db_path: Optional[str] = None

async def init_db(db_path: str) -> None:
    global _db_path
    _db_path = db_path
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        await _run_migrations(conn)
        await conn.commit()

async def _run_migrations(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version "
        "(version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL)"
    )
    cursor = await conn.execute("SELECT version FROM schema_version")
    applied = {row[0] for row in await cursor.fetchall()}

    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        return

    for sql_file in sorted(migrations_dir.glob("*.sql")):
        version = int(sql_file.stem.split("_")[0])
        if version in applied:
            continue
        sql = sql_file.read_text()
        await conn.executescript(sql)
        await conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, int(time.time()))
        )

async def get_db() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(_db_path)
    conn.row_factory = aiosqlite.Row
    return conn

async def enqueue_write(sql: str, params: tuple = ()) -> None:
    await _write_queue.put((sql, params))

async def _writer_loop(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        while True:
            sql, params = await _write_queue.get()
            if sql is None:
                break
            for attempt in range(3):
                try:
                    await conn.execute(sql, params)
                    await conn.commit()
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(0.01 * (2 ** attempt))

async def start_writer(db_path: str) -> asyncio.Task:
    return asyncio.create_task(_writer_loop(db_path))

async def stop_writer(writer_task: asyncio.Task) -> None:
    await _write_queue.put((None, ()))
    await writer_task
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/db.py server/migrations/001_init.sql server/tests/test_db.py
git commit -m "feat(server): add SQLite database layer with migrations and write queue"
```

---

### Task 3: FastAPI App & Health Endpoint

**Files:**
- Create: `server/main.py`
- Create: `server/api/health.py`
- Create: `server/tests/test_health.py`
- Update: `server/tests/conftest.py`

- [ ] **Step 1: Write failing test for health endpoint**

```python
# server/tests/test_health.py
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_health_returns_status(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "agent" in data
    assert "db" in data
```

- [ ] **Step 2: Update conftest.py with test_app fixture**

Add to `server/tests/conftest.py`:

```python
@pytest_asyncio.fixture
async def test_app(tmp_path, test_config_path):
    # Import here to avoid circular imports
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from main import create_app
    app = await create_app(
        config_path=test_config_path,
        db_path=str(tmp_path / "test.db")
    )
    yield app
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 4: Implement health endpoint**

```python
# server/api/health.py
from fastapi import APIRouter

router = APIRouter()

# Will be set by main.py on startup
_agent_connected = False
_db_ok = False

def set_agent_status(connected: bool) -> None:
    global _agent_connected
    _agent_connected = connected

def set_db_status(ok: bool) -> None:
    global _db_ok
    _db_ok = ok

@router.get("/api/health")
async def health():
    return {
        "status": "ok",
        "agent": "connected" if _agent_connected else "disconnected",
        "db": "ok" if _db_ok else "error",
    }
```

- [ ] **Step 5: Implement main.py**

```python
# server/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from config import load_config, NulliusConfig
from db import init_db, start_writer, stop_writer
from api import health

_writer_task = None

async def create_app(
    config_path: str = "nullius.yaml",
    db_path: str = "data/nullius.db",
) -> FastAPI:
    config = load_config(config_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _writer_task
        await init_db(db_path)
        health.set_db_status(True)
        _writer_task = await start_writer(db_path)
        yield
        if _writer_task:
            await stop_writer(_writer_task)

    app = FastAPI(title="Nullius API", lifespan=lifespan)
    app.state.config = config
    app.state.db_path = db_path
    app.include_router(health.router)
    return app

if __name__ == "__main__":
    import uvicorn
    import asyncio

    async def run():
        app = await create_app()
        config = uvicorn.Config(app, host="127.0.0.1", port=8000)
        server = uvicorn.Server(config)
        await server.serve()

    asyncio.run(run())
```

- [ ] **Step 6: Create api/__init__.py**

```python
# server/api/__init__.py
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add server/main.py server/api/__init__.py server/api/health.py server/tests/test_health.py server/tests/conftest.py
git commit -m "feat(server): add FastAPI app with health endpoint"
```

---

### Task 4: Metrics API

**Files:**
- Create: `server/api/metrics.py`
- Create: `server/tests/test_metrics.py`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/test_metrics.py
import pytest
import time
from httpx import AsyncClient, ASGITransport
from db import get_db, enqueue_write

@pytest.mark.asyncio
async def test_get_current_metrics_empty(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/metrics")
    assert resp.status_code == 200
    assert resp.json() is None

@pytest.mark.asyncio
async def test_get_current_metrics(test_app):
    now = int(time.time())
    conn = await get_db()
    await conn.execute(
        "INSERT INTO metrics (timestamp, cpu_total, ram_used, ram_total) VALUES (?, ?, ?, ?)",
        (now, 45.2, 4096, 8192)
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/metrics")
    data = resp.json()
    assert data["cpu_total"] == 45.2
    assert data["ram_used"] == 4096

@pytest.mark.asyncio
async def test_get_metrics_history(test_app):
    now = int(time.time())
    conn = await get_db()
    for i in range(5):
        await conn.execute(
            "INSERT INTO metrics (timestamp, cpu_total) VALUES (?, ?)",
            (now - i * 60, 20.0 + i)
        )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/metrics/history?period=1h")
    data = resp.json()
    assert len(data) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_metrics.py -v`
Expected: FAIL

- [ ] **Step 3: Implement metrics.py**

```python
# server/api/metrics.py
import time
from fastapi import APIRouter
from db import get_db

router = APIRouter()

PERIOD_SECONDS = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "24h": 86400,
    "7d": 604800,
}

@router.get("/api/metrics")
async def get_current_metrics():
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT * FROM metrics ORDER BY timestamp DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        await conn.close()

@router.get("/api/metrics/history")
async def get_metrics_history(period: str = "1h"):
    seconds = PERIOD_SECONDS.get(period, 3600)
    since = int(time.time()) - seconds
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT * FROM metrics WHERE timestamp >= ? ORDER BY timestamp ASC",
            (since,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()
```

- [ ] **Step 4: Register router in main.py**

Add to `create_app()` in `main.py`:
```python
from api import metrics
app.include_router(metrics.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_metrics.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/api/metrics.py server/tests/test_metrics.py server/main.py
git commit -m "feat(server): add metrics REST endpoints"
```

---

### Task 5: Services, Processes, Logs API

**Files:**
- Create: `server/api/services.py`
- Create: `server/api/processes.py`
- Create: `server/api/logs.py`
- Create: `server/tests/test_services.py`
- Create: `server/tests/test_processes.py`
- Create: `server/tests/test_logs.py`

- [ ] **Step 1: Write failing test for services**

```python
# server/tests/test_services.py
import pytest
import time
from httpx import AsyncClient, ASGITransport
from db import get_db

@pytest.mark.asyncio
async def test_get_services_empty(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/services")
    assert resp.status_code == 200
    assert resp.json() == []

@pytest.mark.asyncio
async def test_get_services(test_app):
    conn = await get_db()
    await conn.execute(
        "INSERT INTO services (name, status, pid, uptime, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("nginx", "running", 1234, 86400, int(time.time()))
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/services")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "nginx"
    assert data[0]["status"] == "running"
```

- [ ] **Step 2: Write failing test for processes**

```python
# server/tests/test_processes.py
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_get_processes_returns_list(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/processes")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 3: Write failing test for logs**

```python
# server/tests/test_logs.py
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_get_logs_returns_list(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/logs?source=auth&limit=10")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_services.py tests/test_processes.py tests/test_logs.py -v`
Expected: FAIL

- [ ] **Step 5: Implement services.py**

```python
# server/api/services.py
from fastapi import APIRouter
from db import get_db

router = APIRouter()

@router.get("/api/services")
async def get_services():
    conn = await get_db()
    try:
        cursor = await conn.execute("SELECT * FROM services ORDER BY name")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()
```

- [ ] **Step 6: Implement processes.py**

Processes are stored in memory (pushed by agent via WS), not in SQLite. The endpoint returns the latest snapshot.

```python
# server/api/processes.py
from fastapi import APIRouter

router = APIRouter()

_latest_processes: list[dict] = []

def update_processes(processes: list[dict]) -> None:
    global _latest_processes
    _latest_processes = processes

@router.get("/api/processes")
async def get_processes():
    return _latest_processes
```

- [ ] **Step 7: Implement logs.py**

Logs are also in-memory ring buffer, pushed by agent.

```python
# server/api/logs.py
from collections import deque
from fastapi import APIRouter

router = APIRouter()

_log_buffer: deque[dict] = deque(maxlen=5000)

def append_log(entry: dict) -> None:
    _log_buffer.append(entry)

@router.get("/api/logs")
async def get_logs(source: str = "", limit: int = 100):
    logs = list(_log_buffer)
    if source:
        logs = [l for l in logs if l.get("source") == source]
    return logs[-limit:]
```

- [ ] **Step 8: Register routers in main.py**

Add to `create_app()`:
```python
from api import services, processes, logs
app.include_router(services.router)
app.include_router(processes.router)
app.include_router(logs.router)
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd server && python -m pytest tests/test_services.py tests/test_processes.py tests/test_logs.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add server/api/services.py server/api/processes.py server/api/logs.py server/tests/test_services.py server/tests/test_processes.py server/tests/test_logs.py server/main.py
git commit -m "feat(server): add services, processes, and logs endpoints"
```

---

### Task 6: Security API (Events + Block/Unblock)

**Files:**
- Create: `server/api/security.py`
- Create: `server/tests/test_security_api.py`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/test_security_api.py
import pytest
import time
from httpx import AsyncClient, ASGITransport
from db import get_db

@pytest.mark.asyncio
async def test_get_security_events_empty(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/events")
    assert resp.status_code == 200
    assert resp.json() == []

@pytest.mark.asyncio
async def test_get_security_events_with_filter(test_app):
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (now, "ssh_brute_force", "high", "10.0.0.1", "5 failed attempts")
    )
    await conn.execute(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (now, "sqli", "medium", "10.0.0.2", "SQL injection attempt")
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/events?type=ssh_brute_force")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["type"] == "ssh_brute_force"

@pytest.mark.asyncio
async def test_get_blocked_ips(test_app):
    conn = await get_db()
    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, auto) VALUES (?, ?, ?, ?)",
        ("192.168.1.100", "brute force", int(time.time()), 1)
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/security/blocked")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ip"] == "192.168.1.100"

@pytest.mark.asyncio
async def test_block_ip_valid(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/security/block", json={
            "ip": "10.0.0.5",
            "reason": "manual block",
            "duration": 3600
        })
    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"

@pytest.mark.asyncio
async def test_block_ip_invalid_format(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/security/block", json={
            "ip": "not-an-ip",
            "reason": "test"
        })
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_unblock_ip(test_app):
    conn = await get_db()
    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, auto) VALUES (?, ?, ?, ?)",
        ("10.0.0.6", "test", int(time.time()), 0)
    )
    await conn.commit()
    await conn.close()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/security/unblock", json={"ip": "10.0.0.6"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "unblocked"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_security_api.py -v`
Expected: FAIL

- [ ] **Step 3: Implement security.py**

```python
# server/api/security.py
import ipaddress
import time
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db import get_db

router = APIRouter()

class BlockRequest(BaseModel):
    ip: str
    reason: str = ""
    duration: Optional[int] = None  # seconds, None = permanent

class UnblockRequest(BaseModel):
    ip: str

def _validate_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

@router.get("/api/security/events")
async def get_security_events(
    type: str = "",
    severity: str = "",
    limit: int = 100
):
    conn = await get_db()
    try:
        query = "SELECT * FROM security_events WHERE 1=1"
        params: list = []
        if type:
            query += " AND type = ?"
            params.append(type)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()

@router.get("/api/security/blocked")
async def get_blocked_ips():
    conn = await get_db()
    try:
        cursor = await conn.execute("SELECT * FROM blocked_ips ORDER BY blocked_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()

@router.post("/api/security/block")
async def block_ip(req: BlockRequest):
    if not _validate_ip(req.ip):
        raise HTTPException(status_code=400, detail="Invalid IP address format")
    now = int(time.time())
    expires = now + req.duration if req.duration else None
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT OR REPLACE INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) "
            "VALUES (?, ?, ?, ?, 0)",
            (req.ip, req.reason, now, expires)
        )
        await conn.commit()
    finally:
        await conn.close()
    # TODO: send block_ip command to agent via WS
    return {"status": "blocked", "ip": req.ip}

@router.post("/api/security/unblock")
async def unblock_ip(req: UnblockRequest):
    if not _validate_ip(req.ip):
        raise HTTPException(status_code=400, detail="Invalid IP address format")
    conn = await get_db()
    try:
        await conn.execute("DELETE FROM blocked_ips WHERE ip = ?", (req.ip,))
        await conn.commit()
    finally:
        await conn.close()
    # TODO: send unblock_ip command to agent via WS
    return {"status": "unblocked", "ip": req.ip}
```

- [ ] **Step 4: Register router in main.py**

Add to `create_app()`:
```python
from api import security
app.include_router(security.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && python -m pytest tests/test_security_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/api/security.py server/tests/test_security_api.py server/main.py
git commit -m "feat(server): add security events and IP blocking endpoints"
```

---

### Task 7: Security Detector (Rule-Based)

**Files:**
- Create: `server/security/__init__.py`
- Create: `server/security/detector.py`
- Create: `server/security/rules.py`
- Create: `server/tests/test_detector.py`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/test_detector.py
import pytest
from security.detector import Detector
from config import load_config

@pytest.fixture
def detector(test_config_path):
    config = load_config(test_config_path)
    return Detector(config.security)

def test_ssh_brute_force_below_threshold(detector):
    results = []
    for i in range(2):
        result = detector.check_log({
            "source": "auth",
            "line": f"Failed password for root from 10.0.0.1 port 22 ssh2",
            "file": "/var/log/auth.log"
        })
        if result:
            results.append(result)
    assert len(results) == 0

def test_ssh_brute_force_above_threshold(detector):
    results = []
    for i in range(3):  # threshold is 3 in test config
        result = detector.check_log({
            "source": "auth",
            "line": "Failed password for root from 10.0.0.1 port 22 ssh2",
            "file": "/var/log/auth.log"
        })
        if result:
            results.append(result)
    assert len(results) == 1
    assert results[0]["type"] == "ssh_brute_force"
    assert results[0]["severity"] == "high"
    assert results[0]["source_ip"] == "10.0.0.1"

def test_ssh_different_ips_no_trigger(detector):
    results = []
    for i in range(5):
        result = detector.check_log({
            "source": "auth",
            "line": f"Failed password for root from 10.0.0.{i} port 22 ssh2",
            "file": "/var/log/auth.log"
        })
        if result:
            results.append(result)
    assert len(results) == 0

def test_sqli_detection(detector):
    result = detector.check_log({
        "source": "nginx",
        "line": '10.0.0.5 - - "GET /page?id=1 OR 1=1-- HTTP/1.1" 200',
        "file": "/var/log/nginx/access.log"
    })
    assert result is not None
    assert result["type"] == "sqli"

def test_xss_detection(detector):
    result = detector.check_log({
        "source": "nginx",
        "line": '10.0.0.5 - - "GET /search?q=<script>alert(1)</script> HTTP/1.1" 200',
        "file": "/var/log/nginx/access.log"
    })
    assert result is not None
    assert result["type"] == "xss"

def test_path_traversal_detection(detector):
    result = detector.check_log({
        "source": "nginx",
        "line": '10.0.0.5 - - "GET /../../etc/passwd HTTP/1.1" 200',
        "file": "/var/log/nginx/access.log"
    })
    assert result is not None
    assert result["type"] == "path_traversal"

def test_normal_log_no_detection(detector):
    result = detector.check_log({
        "source": "auth",
        "line": "Accepted publickey for user from 10.0.0.1 port 22 ssh2",
        "file": "/var/log/auth.log"
    })
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_detector.py -v`
Expected: FAIL

- [ ] **Step 3: Implement rules.py**

```python
# server/security/rules.py
import re

SSH_FAILED_PATTERN = re.compile(
    r"Failed password.*from\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
)

WEB_ATTACK_PATTERNS = {
    "sqli": re.compile(
        r"(?i)(\b(union\s+select|or\s+1\s*=\s*1|and\s+1\s*=\s*1|"
        r"select\s+.*\s+from|insert\s+into|drop\s+table|"
        r";\s*delete\s+from|'\s*or\s*'|1\s*or\s*1))",
    ),
    "xss": re.compile(
        r"(?i)(<script|javascript:|on(load|error|click|mouseover)\s*=|"
        r"<img\s+[^>]*onerror|<svg\s+[^>]*onload)",
    ),
    "path_traversal": re.compile(
        r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e/|\.\.%2f){2,}",
    ),
}

NGINX_LOG_IP_PATTERN = re.compile(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
```

- [ ] **Step 4: Implement detector.py**

```python
# server/security/detector.py
import time
from collections import defaultdict
from config import SecurityConfig
from security.rules import SSH_FAILED_PATTERN, WEB_ATTACK_PATTERNS, NGINX_LOG_IP_PATTERN

class Detector:
    def __init__(self, config: SecurityConfig):
        self.config = config
        # {ip: [timestamp, timestamp, ...]}
        self._ssh_attempts: dict[str, list[int]] = defaultdict(list)

    def check_log(self, log_entry: dict) -> dict | None:
        source = log_entry.get("source", "")
        line = log_entry.get("line", "")

        if source == "auth":
            return self._check_ssh(line)
        if source in ("nginx", "apache"):
            return self._check_web(line)
        return None

    def _check_ssh(self, line: str) -> dict | None:
        match = SSH_FAILED_PATTERN.search(line)
        if not match:
            return None

        ip = match.group(1)
        now = int(time.time())
        window = self.config.ssh_brute_force.window
        threshold = self.config.ssh_brute_force.threshold

        self._ssh_attempts[ip].append(now)
        # Remove old attempts outside the window
        self._ssh_attempts[ip] = [
            t for t in self._ssh_attempts[ip] if now - t <= window
        ]

        if len(self._ssh_attempts[ip]) >= threshold:
            self._ssh_attempts[ip] = []  # Reset after trigger
            return {
                "type": "ssh_brute_force",
                "severity": "high",
                "source_ip": ip,
                "description": f"{threshold}+ failed SSH attempts in {window}s",
                "raw_log": line,
            }
        return None

    def _check_web(self, line: str) -> dict | None:
        if not self.config.web_attacks.enabled:
            return None

        ip_match = NGINX_LOG_IP_PATTERN.search(line)
        source_ip = ip_match.group(1) if ip_match else ""

        for attack_type, pattern in WEB_ATTACK_PATTERNS.items():
            if pattern.search(line):
                severity = "high" if attack_type == "sqli" else "medium"
                return {
                    "type": attack_type,
                    "severity": severity,
                    "source_ip": source_ip,
                    "description": f"{attack_type} pattern detected",
                    "raw_log": line,
                }
        return None
```

```python
# server/security/__init__.py
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && python -m pytest tests/test_detector.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/security/__init__.py server/security/detector.py server/security/rules.py server/tests/test_detector.py
git commit -m "feat(server): add rule-based security detector"
```

---

### Task 8: Security Responder

**Files:**
- Create: `server/security/responder.py`
- Create: `server/tests/test_responder.py`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/test_responder.py
import pytest
from security.responder import Responder

@pytest.fixture
def responder():
    return Responder(auto_block=True)

def test_low_severity_logs_only(responder):
    action = responder.decide({"severity": "low", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "log"

def test_medium_severity_logs(responder):
    action = responder.decide({"severity": "medium", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "log"

def test_high_severity_blocks(responder):
    action = responder.decide({"severity": "high", "source_ip": "10.0.0.1", "type": "ssh_brute_force"})
    assert action["action"] == "block"
    assert action["ip"] == "10.0.0.1"

def test_critical_severity_blocks(responder):
    action = responder.decide({"severity": "critical", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "block"
    assert action["highlight"] is True

def test_high_severity_no_block_when_disabled(responder):
    r = Responder(auto_block=False)
    action = r.decide({"severity": "high", "source_ip": "10.0.0.1", "type": "test"})
    assert action["action"] == "log"

def test_no_block_without_ip(responder):
    action = responder.decide({"severity": "high", "source_ip": "", "type": "test"})
    assert action["action"] == "log"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_responder.py -v`
Expected: FAIL

- [ ] **Step 3: Implement responder.py**

```python
# server/security/responder.py

class Responder:
    def __init__(self, auto_block: bool = True):
        self.auto_block = auto_block

    def decide(self, event: dict) -> dict:
        severity = event.get("severity", "low")
        source_ip = event.get("source_ip", "")

        if severity in ("high", "critical") and self.auto_block and source_ip:
            return {
                "action": "block",
                "ip": source_ip,
                "highlight": severity == "critical",
            }

        return {"action": "log"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && python -m pytest tests/test_responder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/security/responder.py server/tests/test_responder.py
git commit -m "feat(server): add security responder with auto-block logic"
```

---

### Task 9: Agent WebSocket Handler

**Files:**
- Create: `server/ws/__init__.py`
- Create: `server/ws/agent.py`
- Create: `server/tests/test_ws_agent.py`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/test_ws_agent.py
import pytest
import json
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

@pytest.mark.asyncio
async def test_agent_ws_rejects_without_auth(test_app):
    from starlette.testclient import TestClient
    client = TestClient(test_app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"type": "metrics", "data": {}})

@pytest.mark.asyncio
async def test_agent_ws_accepts_with_auth(test_app):
    client = TestClient(test_app)
    with client.websocket_connect("/ws/agent") as ws:
        ws.send_json({"type": "auth", "secret": "test-secret"})
        resp = ws.receive_json()
        assert resp["type"] == "auth_ok"

@pytest.mark.asyncio
async def test_agent_ws_handles_metrics(test_app):
    client = TestClient(test_app)
    with client.websocket_connect("/ws/agent") as ws:
        ws.send_json({"type": "auth", "secret": "test-secret"})
        ws.receive_json()  # auth_ok
        ws.send_json({
            "type": "metrics",
            "timestamp": 1000,
            "data": {
                "cpu": {"total": 25.0, "cores": [25.0]},
                "ram": {"total": 8192, "used": 4096, "percent": 50.0},
                "disk": [],
                "network": {"rx_bytes_delta": 100, "tx_bytes_delta": 200}
            }
        })
        ws.send_json({"type": "ping"})
        resp = ws.receive_json()
        assert resp["type"] == "pong"

@pytest.mark.asyncio
async def test_agent_ws_handles_ping(test_app):
    client = TestClient(test_app)
    with client.websocket_connect("/ws/agent") as ws:
        ws.send_json({"type": "auth", "secret": "test-secret"})
        ws.receive_json()  # auth_ok
        ws.send_json({"type": "ping"})
        resp = ws.receive_json()
        assert resp["type"] == "pong"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_ws_agent.py -v`
Expected: FAIL

- [ ] **Step 3: Implement agent WS handler**

```python
# server/ws/__init__.py
```

```python
# server/ws/agent.py
import json
import time
from fastapi import WebSocket, WebSocketDisconnect
from db import enqueue_write
from api.logs import append_log
from api.processes import update_processes
from api import health

_agent_ws: WebSocket | None = None

def get_agent_ws() -> WebSocket | None:
    return _agent_ws

async def agent_ws_handler(ws: WebSocket, secret: str):
    global _agent_ws
    await ws.accept()

    # Wait for auth message
    try:
        msg = await ws.receive_json()
        if msg.get("type") != "auth" or msg.get("secret") != secret:
            await ws.send_json({"type": "auth_error", "error": "invalid secret"})
            await ws.close(code=4001)
            return
        await ws.send_json({"type": "auth_ok"})
    except Exception:
        await ws.close(code=4001)
        return

    _agent_ws = ws
    health.set_agent_status(True)

    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")

            if msg_type == "ping":
                await ws.send_json({"type": "pong"})

            elif msg_type == "metrics":
                await _handle_metrics(msg)

            elif msg_type == "log_event":
                await _handle_log(msg)

            elif msg_type == "services":
                await _handle_services(msg)

            elif msg_type == "processes":
                update_processes(msg.get("data", []))

            elif msg_type == "command_result":
                pass  # TODO: resolve pending command futures

            elif msg_type == "disconnect":
                break

    except WebSocketDisconnect:
        pass
    finally:
        _agent_ws = None
        health.set_agent_status(False)

async def _handle_metrics(msg: dict):
    data = msg.get("data", {})
    ts = msg.get("timestamp", int(time.time()))
    cpu = data.get("cpu", {})
    ram = data.get("ram", {})
    net = data.get("network", {})
    await enqueue_write(
        "INSERT INTO metrics (timestamp, cpu_total, cpu_cores, ram_used, ram_total, "
        "network_rx, network_tx, load_avg, disk) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ts,
            cpu.get("total"),
            json.dumps(cpu.get("cores", [])),
            ram.get("used"),
            ram.get("total"),
            net.get("rx_bytes_delta"),
            net.get("tx_bytes_delta"),
            json.dumps(data.get("load_avg", [])),
            json.dumps(data.get("disk", [])),
        )
    )

async def _handle_log(msg: dict):
    data = msg.get("data", {})
    append_log({
        "timestamp": msg.get("timestamp", int(time.time())),
        "source": data.get("source", ""),
        "line": data.get("line", ""),
        "file": data.get("file", ""),
    })

async def _handle_services(msg: dict):
    services = msg.get("data", [])
    now = int(time.time())
    for svc in services:
        await enqueue_write(
            "INSERT OR REPLACE INTO services (name, status, pid, uptime, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (svc.get("name"), svc.get("status"), svc.get("pid"), svc.get("uptime"), now)
        )

async def send_command(command: str, params: dict) -> None:
    ws = get_agent_ws()
    if ws:
        cmd_id = f"cmd_{int(time.time() * 1000)}"
        await ws.send_json({
            "id": cmd_id,
            "command": command,
            "params": params,
        })
```

- [ ] **Step 4: Mount WS in main.py**

Add to `create_app()`:
```python
from ws.agent import agent_ws_handler

agent_secret = "test-secret"  # TODO: load from config/agent.key

@app.websocket("/ws/agent")
async def ws_agent(ws: WebSocket):
    await agent_ws_handler(ws, agent_secret)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && python -m pytest tests/test_ws_agent.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/ws/__init__.py server/ws/agent.py server/tests/test_ws_agent.py server/main.py
git commit -m "feat(server): add agent WebSocket handler with auth and message routing"
```

---

### Task 10: Frontend WebSocket (Live Updates)

**Files:**
- Create: `server/ws/frontend.py`
- Create: `server/tests/test_ws_frontend.py`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/test_ws_frontend.py
import pytest
from starlette.testclient import TestClient
from ws.frontend import broadcast

@pytest.mark.asyncio
async def test_frontend_ws_connects(test_app):
    client = TestClient(test_app)
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json({"type": "ping"})
        resp = ws.receive_json()
        assert resp["type"] == "pong"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_ws_frontend.py -v`
Expected: FAIL

- [ ] **Step 3: Implement frontend.py**

```python
# server/ws/frontend.py
from fastapi import WebSocket, WebSocketDisconnect

_clients: list[WebSocket] = []

async def frontend_ws_handler(ws: WebSocket):
    await ws.accept()
    _clients.append(ws)
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        _clients.remove(ws)

async def broadcast(event: dict) -> None:
    disconnected = []
    for ws in _clients:
        try:
            await ws.send_json(event)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _clients.remove(ws)
```

- [ ] **Step 4: Mount WS in main.py**

Add to `create_app()`:
```python
from ws.frontend import frontend_ws_handler

@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await frontend_ws_handler(ws)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_ws_frontend.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/ws/frontend.py server/tests/test_ws_frontend.py server/main.py
git commit -m "feat(server): add frontend WebSocket for live updates"
```

---

### Task 11: Background Tasks (Retention + IP Expiry)

**Files:**
- Create: `server/tasks/__init__.py`
- Create: `server/tasks/retention.py`
- Create: `server/tasks/expiry.py`
- Create: `server/tests/test_retention.py`
- Create: `server/tests/test_expiry.py`

- [ ] **Step 1: Write failing test for retention**

```python
# server/tests/test_retention.py
import pytest
import time
from db import init_db, get_db
from tasks.retention import cleanup_old_data

@pytest.mark.asyncio
async def test_cleanup_removes_old_metrics(tmp_path):
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    conn = await get_db()
    now = int(time.time())
    old = now - 31 * 86400  # 31 days ago
    await conn.execute(
        "INSERT INTO metrics (timestamp, cpu_total) VALUES (?, ?)", (old, 10.0)
    )
    await conn.execute(
        "INSERT INTO metrics (timestamp, cpu_total) VALUES (?, ?)", (now, 20.0)
    )
    await conn.commit()
    await conn.close()

    deleted = await cleanup_old_data(db_path)
    assert deleted["metrics"] == 1

    conn = await get_db()
    cursor = await conn.execute("SELECT COUNT(*) FROM metrics")
    count = (await cursor.fetchone())[0]
    await conn.close()
    assert count == 1
```

- [ ] **Step 2: Write failing test for IP expiry**

```python
# server/tests/test_expiry.py
import pytest
import time
from db import init_db, get_db
from tasks.expiry import expire_blocked_ips

@pytest.mark.asyncio
async def test_expire_removes_expired_ips(tmp_path):
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    conn = await get_db()
    now = int(time.time())
    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) "
        "VALUES (?, ?, ?, ?, ?)",
        ("10.0.0.1", "test", now - 7200, now - 3600, 1)  # expired 1h ago
    )
    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) "
        "VALUES (?, ?, ?, ?, ?)",
        ("10.0.0.2", "test", now, now + 3600, 1)  # expires in 1h
    )
    await conn.execute(
        "INSERT INTO blocked_ips (ip, reason, blocked_at, auto) "
        "VALUES (?, ?, ?, ?)",
        ("10.0.0.3", "permanent", now, 0)  # permanent
    )
    await conn.commit()
    await conn.close()

    expired = await expire_blocked_ips(db_path)
    assert expired == ["10.0.0.1"]

    conn = await get_db()
    cursor = await conn.execute("SELECT ip FROM blocked_ips ORDER BY ip")
    remaining = [row[0] for row in await cursor.fetchall()]
    await conn.close()
    assert "10.0.0.1" not in remaining
    assert "10.0.0.2" in remaining
    assert "10.0.0.3" in remaining
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_retention.py tests/test_expiry.py -v`
Expected: FAIL

- [ ] **Step 4: Implement retention.py**

```python
# server/tasks/__init__.py
```

```python
# server/tasks/retention.py
import time
import aiosqlite

RETENTION = {
    "metrics": 30 * 86400,
    "security_events": 90 * 86400,
    "agent_commands": 30 * 86400,
}

async def cleanup_old_data(db_path: str) -> dict[str, int]:
    now = int(time.time())
    deleted = {}
    async with aiosqlite.connect(db_path) as conn:
        for table, max_age in RETENTION.items():
            cutoff = now - max_age
            cursor = await conn.execute(
                f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,)
            )
            deleted[table] = cursor.rowcount
        await conn.commit()
    return deleted
```

- [ ] **Step 5: Implement expiry.py**

```python
# server/tasks/expiry.py
import time
import aiosqlite

async def expire_blocked_ips(db_path: str) -> list[str]:
    now = int(time.time())
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT ip FROM blocked_ips WHERE expires_at IS NOT NULL "
            "AND expires_at > 0 AND expires_at < ?",
            (now,)
        )
        expired = [row[0] for row in await cursor.fetchall()]
        if expired:
            placeholders = ",".join("?" * len(expired))
            await conn.execute(
                f"DELETE FROM blocked_ips WHERE ip IN ({placeholders})",
                expired
            )
            await conn.commit()
    return expired
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd server && python -m pytest tests/test_retention.py tests/test_expiry.py -v`
Expected: PASS

- [ ] **Step 7: Wire background tasks into main.py**

Add to `lifespan` in `create_app()`:
```python
import asyncio
from tasks.retention import cleanup_old_data
from tasks.expiry import expire_blocked_ips

async def _background_tasks(db_path: str):
    while True:
        try:
            await expire_blocked_ips(db_path)
        except Exception:
            pass
        await asyncio.sleep(60)

async def _retention_task(db_path: str):
    while True:
        await asyncio.sleep(3600)
        try:
            await cleanup_old_data(db_path)
        except Exception:
            pass
```

Start them in lifespan `yield` block and cancel on shutdown.

- [ ] **Step 8: Commit**

```bash
git add server/tasks/__init__.py server/tasks/retention.py server/tasks/expiry.py server/tests/test_retention.py server/tests/test_expiry.py server/main.py
git commit -m "feat(server): add background tasks for data retention and IP expiry"
```

---

### Task 12: Integration — Wire Detector + Responder into Agent WS

**Files:**
- Modify: `server/ws/agent.py`
- Modify: `server/main.py`

- [ ] **Step 1: Update agent.py to run log events through detector + responder**

In `_handle_log()`, after appending to log buffer:

```python
# At module level
_detector = None
_responder = None

def init_security(detector, responder):
    global _detector, _responder
    _detector = detector
    _responder = responder

async def _handle_log(msg: dict):
    data = msg.get("data", {})
    log_entry = {
        "timestamp": msg.get("timestamp", int(time.time())),
        "source": data.get("source", ""),
        "line": data.get("line", ""),
        "file": data.get("file", ""),
    }
    append_log(log_entry)

    if _detector is None:
        return

    event = _detector.check_log(data)
    if event is None:
        return

    # Save security event
    ts = msg.get("timestamp", int(time.time()))
    await enqueue_write(
        "INSERT INTO security_events (timestamp, type, severity, source_ip, description, raw_log, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, event["type"], event["severity"], event.get("source_ip", ""),
         event["description"], event.get("raw_log", ""), "")
    )

    # Decide response
    action = _responder.decide(event)
    if action["action"] == "block":
        await send_command("block_ip", {"ip": action["ip"], "duration": 86400})
        await enqueue_write(
            "INSERT OR REPLACE INTO blocked_ips (ip, reason, blocked_at, expires_at, auto) "
            "VALUES (?, ?, ?, ?, 1)",
            (action["ip"], event["description"], ts, ts + 86400)
        )

    # Broadcast to frontend
    from ws.frontend import broadcast
    await broadcast({"type": "security_event", "data": event})
```

- [ ] **Step 2: Initialize detector and responder in main.py**

In `create_app()`:
```python
from security.detector import Detector
from security.responder import Responder
from ws.agent import init_security

detector = Detector(config.security)
responder = Responder(auto_block=config.security.auto_block)
init_security(detector, responder)
```

- [ ] **Step 3: Run all tests**

Run: `cd server && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add server/ws/agent.py server/main.py
git commit -m "feat(server): wire security detector and responder into agent WS pipeline"
```

---

### Task 13: Full Integration Test

**Files:**
- Create: `server/tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# server/tests/test_integration.py
import pytest
import time
from starlette.testclient import TestClient
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_full_flow_metrics_to_api(test_app):
    """Agent sends metrics via WS, verify they appear in REST API."""
    client = TestClient(test_app)

    # Agent connects and sends metrics
    with client.websocket_connect("/ws/agent") as ws:
        ws.send_json({"type": "auth", "secret": "test-secret"})
        ws.receive_json()  # auth_ok

        ws.send_json({
            "type": "metrics",
            "timestamp": int(time.time()),
            "data": {
                "cpu": {"total": 42.0, "cores": [42.0]},
                "ram": {"total": 8192, "used": 4000, "percent": 48.8},
                "disk": [{"mount": "/", "total": 50000, "used": 25000}],
                "network": {"rx_bytes_delta": 1000, "tx_bytes_delta": 500}
            }
        })

        # Give write queue time to process
        ws.send_json({"type": "ping"})
        ws.receive_json()

    # Verify via REST
    import asyncio
    await asyncio.sleep(0.5)  # Let write queue flush

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        resp = await http.get("/api/metrics")
    data = resp.json()
    assert data is not None
    assert data["cpu_total"] == 42.0

@pytest.mark.asyncio
async def test_full_flow_ssh_attack_detection(test_app):
    """Agent sends SSH failed log events, verify security event created."""
    client = TestClient(test_app)

    with client.websocket_connect("/ws/agent") as ws:
        ws.send_json({"type": "auth", "secret": "test-secret"})
        ws.receive_json()

        # Send 3 failed SSH attempts (threshold is 3 in test config)
        for i in range(3):
            ws.send_json({
                "type": "log_event",
                "timestamp": int(time.time()),
                "data": {
                    "source": "auth",
                    "line": "Failed password for root from 10.0.0.99 port 22 ssh2",
                    "file": "/var/log/auth.log"
                }
            })

        ws.send_json({"type": "ping"})
        ws.receive_json()

    import asyncio
    await asyncio.sleep(0.5)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        resp = await http.get("/api/security/events?type=ssh_brute_force")
    events = resp.json()
    assert len(events) >= 1
    assert events[0]["source_ip"] == "10.0.0.99"
```

- [ ] **Step 2: Run integration test**

Run: `cd server && python -m pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `cd server && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add server/tests/test_integration.py
git commit -m "test(server): add full integration tests for metrics and security flow"
```

---

## Summary

After completing all 13 tasks, the backend will have:
- Config loading from YAML
- SQLite with migrations and async write queue
- REST API for metrics, services, processes, logs, security events, IP blocking
- Health endpoint
- Agent WebSocket with auth, ping/pong, message routing
- Frontend WebSocket for live updates
- Rule-based security detector (SSH brute-force, SQLi, XSS, path traversal)
- Responder with auto-block logic
- Background tasks for data retention and IP expiry
- Full integration tests

**Next phases:**
- Phase 2: Go Agent
- Phase 3: React Frontend
- Phase 4: ML Module
- Phase 5: Installation & Deployment
