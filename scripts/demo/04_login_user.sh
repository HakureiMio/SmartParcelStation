#!/usr/bin/env bash
# Usage: ./04_login_user.sh  (copy token from response into USER_TOKEN)
set -euo pipefail
SERVER_BASE_URL="${SERVER_BASE_URL:-http://127.0.0.1:18000/api/v1}"
curl -fsS -i -X POST "${SERVER_BASE_URL}/auth/login" -H 'Content-Type: application/json' -d '{"role":"client","username":"demo_user001","password":"123456"}'
