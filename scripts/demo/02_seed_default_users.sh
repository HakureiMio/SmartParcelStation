#!/usr/bin/env bash
# Usage: ADMIN_BOOTSTRAP_TOKEN=... ./02_seed_default_users.sh
set -euo pipefail
SERVER_BASE_URL="${SERVER_BASE_URL:-http://127.0.0.1:18000/api/v1}"
: "${ADMIN_BOOTSTRAP_TOKEN:?Set ADMIN_BOOTSTRAP_TOKEN}"
curl -fsS -i -X POST "${SERVER_BASE_URL}/dev/default-users" -H "X-Admin-Bootstrap-Token: ${ADMIN_BOOTSTRAP_TOKEN}"
