#!/usr/bin/env bash
# deploy.sh -- Called by CI after tests pass. Runs on the Hetzner server.
set -euo pipefail

APP_DIR="/opt/grantflow"
HEALTH_URL="https://grantflow.net/health"
HEALTH_TIMEOUT=30

echo "==> Deploying GrantFlow"

cd "$APP_DIR"

echo "==> Pulling latest code"
git pull origin main

echo "==> Installing dependencies"
uv sync

echo "==> Running pending migrations (if any)"
uv run alembic upgrade head 2>/dev/null || echo "    (no migration changes)"

echo "==> Restarting service"
systemctl restart grantflow

echo "==> Waiting for health check"
for i in $(seq 1 "$HEALTH_TIMEOUT"); do
    if /usr/bin/curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        echo "    Health check passed after ${i}s"
        exit 0
    fi
    sleep 1
done

echo "FATAL: Health check failed after ${HEALTH_TIMEOUT}s"
systemctl status grantflow --no-pager || true
journalctl -u grantflow --no-pager -n 20 || true
exit 1
