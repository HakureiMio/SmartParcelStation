#!/usr/bin/env bash
# Usage: SERVER_BASE_URL=http://127.0.0.1:18000/api/v1 ./01_server_health.sh
set -euo pipefail
SERVER_BASE_URL="${SERVER_BASE_URL:-http://127.0.0.1:18000/api/v1}"
curl -fsS -i "${SERVER_BASE_URL}/health"
