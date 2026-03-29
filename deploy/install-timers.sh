#!/usr/bin/env bash
# install-timers.sh -- Idempotent systemd timer installation.
# Safe to re-run on every deploy.
# Note: GrantFlow uses APScheduler for job scheduling (runs in-app),
# so this is a placeholder for future systemd timer needs.
set -euo pipefail

echo "==> Timer management (APScheduler handles scheduling in-app)"
echo "==> Jobs registered: daily_ingestion, weekly_state_ingestion, daily_enrichment"
