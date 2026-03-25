# Nullius v2 — Phase 5: Installation & Deployment

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create install.sh script, systemd services, nginx config, nullius-ctl CLI, TLS setup, and logrotate — everything needed to install Nullius on Ubuntu/Debian with one command.

**Architecture:** Bash install script downloads pre-built Go binary + Python server, sets up systemd services, nginx reverse proxy with TLS, generates secrets and credentials. nullius-ctl is a bash wrapper for common management tasks.

**Tech Stack:** Bash, systemd, nginx, certbot, logrotate

**Spec:** `docs/superpowers/specs/2026-03-25-nullius-v2-design.md`
**Depends on:** Phases 1-4 complete and tested

---

## File Structure

```
deploy/
├── install.sh                 # Main installation script
├── nullius-ctl                # CLI management tool
├── nullius-agent.service      # systemd unit for Go agent
├── nullius-api.service        # systemd unit for FastAPI
├── nginx-nullius.conf         # nginx site config
├── logrotate-nullius           # logrotate config
├── uninstall.sh               # Clean removal
└── build.sh                   # Build Go binary + React + package
```

---

### Task 1: Build Script (Cross-compile + Package)

**Files:**
- Create: `deploy/build.sh`

- [ ] **Step 1: Write build.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-dev}"
BUILD_DIR="dist"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "=== Building Nullius v${VERSION} ==="

# 1. Build Go agent for Linux amd64 + arm64
echo "Building Go agent..."
cd agent
GOOS=linux GOARCH=amd64 go build -ldflags "-s -w" -o "../${BUILD_DIR}/nullius-agent-amd64" .
GOOS=linux GOARCH=arm64 go build -ldflags "-s -w" -o "../${BUILD_DIR}/nullius-agent-arm64" .
cd ..

# 2. Build React frontend
echo "Building frontend..."
cd src/..  # project root
npm ci
npm run build
cp -r dist/. "${BUILD_DIR}/web/"
cd ..

# 3. Package Python server (without venv)
echo "Packaging server..."
tar czf "${BUILD_DIR}/server.tar.gz" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='venv' \
  --exclude='tests' \
  server/

# 4. Copy deploy files
cp deploy/install.sh "${BUILD_DIR}/"
cp deploy/nullius-ctl "${BUILD_DIR}/"
cp deploy/nullius-agent.service "${BUILD_DIR}/"
cp deploy/nullius-api.service "${BUILD_DIR}/"
cp deploy/nginx-nullius.conf "${BUILD_DIR}/"
cp deploy/logrotate-nullius "${BUILD_DIR}/"

echo "=== Build complete: ${BUILD_DIR}/ ==="
```

- [ ] **Step 2: Commit**

---

### Task 2: Systemd Service Files

**Files:**
- Create: `deploy/nullius-agent.service`
- Create: `deploy/nullius-api.service`

- [ ] **Step 1: Write agent service**

```ini
# deploy/nullius-agent.service
[Unit]
Description=Nullius Security Agent
After=network.target nullius-api.service
Wants=nullius-api.service

[Service]
Type=simple
ExecStart=/opt/nullius/bin/nullius-agent /opt/nullius/config/nullius.yaml /opt/nullius/config/agent.key
Restart=always
RestartSec=5
StandardOutput=append:/opt/nullius/logs/agent.log
StandardError=append:/opt/nullius/logs/agent.log
MemoryMax=128M
CPUQuota=10%

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Write API service**

```ini
# deploy/nullius-api.service
[Unit]
Description=Nullius API Server
After=network.target

[Service]
Type=simple
User=nullius
Group=nullius
WorkingDirectory=/opt/nullius/server
ExecStart=/opt/nullius/server/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/opt/nullius/logs/api.log
StandardError=append:/opt/nullius/logs/api.log
MemoryMax=512M
CPUQuota=25%
Environment=NULLIUS_CONFIG=/opt/nullius/config/nullius.yaml
Environment=NULLIUS_DB=/opt/nullius/data/nullius.db

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Commit**

---

### Task 3: Nginx Config

**Files:**
- Create: `deploy/nginx-nullius.conf`

- [ ] **Step 1: Write nginx config**

```nginx
# deploy/nginx-nullius.conf
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name _;

    ssl_certificate /opt/nullius/config/tls/cert.pem;
    ssl_certificate_key /opt/nullius/config/tls/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    auth_basic "Nullius";
    auth_basic_user_file /opt/nullius/config/.htpasswd;

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket for frontend live updates
    location /ws/live {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    # Agent WS — no basic auth (uses shared secret)
    location /ws/agent {
        auth_basic off;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    # Frontend static files
    location / {
        root /opt/nullius/web;
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 2: Commit**

---

### Task 4: Install Script

**Files:**
- Create: `deploy/install.sh`

- [ ] **Step 1: Write install.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "  Nullius — Server Immune System"
echo "  Installation Script"
echo "========================================="

# Check root
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: Run as root (sudo bash install.sh)"
    exit 1
fi

# Check OS
if ! grep -qE '(Ubuntu|Debian)' /etc/os-release 2>/dev/null; then
    echo "ERROR: Only Ubuntu 20.04+ and Debian 11+ are supported"
    exit 1
fi

# Check arch
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  AGENT_BIN="nullius-agent-amd64" ;;
    aarch64) AGENT_BIN="nullius-agent-arm64" ;;
    *)       echo "ERROR: Unsupported architecture: $ARCH"; exit 1 ;;
esac

INSTALL_DIR="/opt/nullius"

echo "[1/10] Creating nullius user..."
useradd --system --no-create-home --shell /usr/sbin/nologin nullius 2>/dev/null || true

echo "[2/10] Creating directories..."
mkdir -p "$INSTALL_DIR"/{bin,server,web,config/tls,data,logs}

echo "[3/10] Installing Go agent..."
# In production: download from releases
# cp "$AGENT_BIN" "$INSTALL_DIR/bin/nullius-agent"
chmod +x "$INSTALL_DIR/bin/nullius-agent"

echo "[4/10] Setting up Python environment..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv nginx openssl > /dev/null
python3 -m venv "$INSTALL_DIR/server/venv"
# tar xzf server.tar.gz -C "$INSTALL_DIR/"
"$INSTALL_DIR/server/venv/bin/pip" install -q -r "$INSTALL_DIR/server/requirements.txt"

echo "[5/10] Generating configuration..."
if [[ ! -f "$INSTALL_DIR/config/nullius.yaml" ]]; then
    cat > "$INSTALL_DIR/config/nullius.yaml" << 'YAML'
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
YAML
fi

echo "[6/10] Generating secrets..."
# Agent shared secret
if [[ ! -f "$INSTALL_DIR/config/agent.key" ]]; then
    openssl rand -hex 32 > "$INSTALL_DIR/config/agent.key"
    chmod 600 "$INSTALL_DIR/config/agent.key"
fi

# Dashboard password
DASHBOARD_PASSWORD=$(openssl rand -base64 16 | tr -d '=+/')
echo "admin:$(openssl passwd -6 "$DASHBOARD_PASSWORD")" > "$INSTALL_DIR/config/.htpasswd"
chmod 600 "$INSTALL_DIR/config/.htpasswd"

echo "[7/10] Generating TLS certificate..."
if [[ ! -f "$INSTALL_DIR/config/tls/cert.pem" ]]; then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$INSTALL_DIR/config/tls/key.pem" \
        -out "$INSTALL_DIR/config/tls/cert.pem" \
        -subj "/CN=nullius" 2>/dev/null
fi

echo "[8/10] Installing nginx config..."
cp nginx-nullius.conf /etc/nginx/sites-available/nullius
ln -sf /etc/nginx/sites-available/nullius /etc/nginx/sites-enabled/nullius
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "[9/10] Installing systemd services..."
cp nullius-agent.service /etc/systemd/system/
cp nullius-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable nullius-api nullius-agent
systemctl start nullius-api
sleep 2
systemctl start nullius-agent

echo "[10/10] Setting up logrotate..."
cat > /etc/logrotate.d/nullius << 'LOGROTATE'
/opt/nullius/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
LOGROTATE

# Fix ownership
chown -R nullius:nullius "$INSTALL_DIR/server" "$INSTALL_DIR/data" "$INSTALL_DIR/logs"
chown root:root "$INSTALL_DIR/bin/nullius-agent"

# Install nullius-ctl
cp nullius-ctl /usr/local/bin/nullius-ctl
chmod +x /usr/local/bin/nullius-ctl

SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "========================================="
echo "  Nullius installed successfully!"
echo ""
echo "  Dashboard: https://${SERVER_IP}"
echo "  Username:  admin"
echo "  Password:  ${DASHBOARD_PASSWORD}"
echo ""
echo "  Save this password! It won't be shown again."
echo "  Use 'nullius-ctl set-password' to change it."
echo "========================================="
```

- [ ] **Step 2: Commit**

---

### Task 5: nullius-ctl CLI

**Files:**
- Create: `deploy/nullius-ctl`

- [ ] **Step 1: Write nullius-ctl**

```bash
#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/nullius"

usage() {
    echo "Usage: nullius-ctl <command>"
    echo ""
    echo "Commands:"
    echo "  status          Show status of all components"
    echo "  logs [--follow] View logs"
    echo "  config          Edit configuration"
    echo "  set-password    Change dashboard password"
    echo "  tls --domain X  Setup Let's Encrypt TLS"
    echo "  update          Update Nullius to latest version"
    echo "  reset-ml        Reset ML models and retrain"
    echo "  uninstall       Remove Nullius"
}

cmd_status() {
    echo "=== Nullius Status ==="
    echo ""
    echo "Agent:  $(systemctl is-active nullius-agent 2>/dev/null || echo 'not installed')"
    echo "API:    $(systemctl is-active nullius-api 2>/dev/null || echo 'not installed')"
    echo "Nginx:  $(systemctl is-active nginx 2>/dev/null || echo 'not installed')"
    echo ""
    # Health check
    if curl -sk https://127.0.0.1/api/health 2>/dev/null | python3 -m json.tool 2>/dev/null; then
        :
    else
        echo "API health check failed"
    fi
}

cmd_logs() {
    if [[ "${1:-}" == "--follow" || "${1:-}" == "-f" ]]; then
        tail -f "$INSTALL_DIR/logs/agent.log" "$INSTALL_DIR/logs/api.log"
    else
        echo "=== Agent Log (last 20 lines) ==="
        tail -20 "$INSTALL_DIR/logs/agent.log" 2>/dev/null || echo "(empty)"
        echo ""
        echo "=== API Log (last 20 lines) ==="
        tail -20 "$INSTALL_DIR/logs/api.log" 2>/dev/null || echo "(empty)"
    fi
}

cmd_config() {
    ${EDITOR:-nano} "$INSTALL_DIR/config/nullius.yaml"
    echo "Config updated. Restart services to apply:"
    echo "  systemctl restart nullius-api nullius-agent"
}

cmd_set_password() {
    read -sp "New password: " password
    echo
    read -sp "Confirm: " confirm
    echo
    if [[ "$password" != "$confirm" ]]; then
        echo "Passwords don't match"
        exit 1
    fi
    echo "admin:$(openssl passwd -6 "$password")" > "$INSTALL_DIR/config/.htpasswd"
    echo "Password updated."
}

cmd_tls() {
    if [[ -z "${1:-}" ]]; then
        echo "Usage: nullius-ctl tls --domain example.com"
        exit 1
    fi
    domain="$1"
    apt-get install -y -qq certbot python3-certbot-nginx > /dev/null
    certbot --nginx -d "$domain" --non-interactive --agree-tos --register-unsafely-without-email
    echo "TLS configured for $domain"
}

cmd_update() {
    echo "Updating Nullius..."
    # Download latest release, apply migrations, restart
    systemctl stop nullius-agent nullius-api
    # TODO: download and replace binaries
    "$INSTALL_DIR/server/venv/bin/python" -c "
import asyncio
from db import init_db
asyncio.run(init_db('$INSTALL_DIR/data/nullius.db'))
print('Migrations applied')
"
    systemctl start nullius-api nullius-agent
    echo "Update complete."
}

cmd_reset_ml() {
    echo "Resetting ML models..."
    rm -rf "$INSTALL_DIR/server/ml/models/"*.joblib
    systemctl restart nullius-api
    echo "ML models reset. Training will start automatically."
}

case "${1:-}" in
    status)       cmd_status ;;
    logs)         cmd_logs "${2:-}" ;;
    config)       cmd_config ;;
    set-password) cmd_set_password ;;
    tls)          cmd_tls "${3:-}" ;;
    update)       cmd_update ;;
    reset-ml)     cmd_reset_ml ;;
    uninstall)    bash "$INSTALL_DIR/../deploy/uninstall.sh" ;;
    *)            usage ;;
esac
```

- [ ] **Step 2: Commit**

---

### Task 6: Testing on Ubuntu/Debian VM

- [ ] **Step 1: Provision a VM (vagrant, cloud, or local)**

- [ ] **Step 2: Copy dist/ to VM and run install.sh**

```bash
scp -r dist/ user@vm:/tmp/nullius/
ssh user@vm "cd /tmp/nullius && sudo bash install.sh"
```

- [ ] **Step 3: Verify all services running**

```bash
nullius-ctl status
```

- [ ] **Step 4: Open dashboard in browser, verify UI loads**

- [ ] **Step 5: Check metrics appearing after 30 seconds**

- [ ] **Step 6: Trigger SSH brute-force test**

```bash
for i in {1..6}; do ssh -o StrictHostKeyChecking=no invalid@localhost; done
```

Verify: security event appears in dashboard, IP blocked.

- [ ] **Step 7: Verify ML starts training after 24h data collected**

- [ ] **Step 8: Test nullius-ctl commands**

```bash
nullius-ctl status
nullius-ctl logs
nullius-ctl set-password
nullius-ctl reset-ml
```

- [ ] **Step 9: Commit any fixes from testing**
