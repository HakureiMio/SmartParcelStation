#!/usr/bin/env bash
# Usage: STAFF_TOKEN=... GATE_READER_TOKEN=... ./11_replace_card_demo.sh
set -euo pipefail
SERVER_BASE_URL="${SERVER_BASE_URL:-http://127.0.0.1:18000/api/v1}"
: "${STAFF_TOKEN:?Set STAFF_TOKEN}"
curl -fsS -i -X POST "${SERVER_BASE_URL}/staff/users/2/cards/bind" -H 'Content-Type: application/json' -H "Authorization: Bearer ${STAFF_TOKEN}" -d '{"station_id":1,"credential_type":"CARD_UID","credential_value":"CARD_UID_002","reason":"REPLACEMENT_DEMO"}'
printf '\nRun 06_gateway_sync_pull.sh, then test CARD_UID_001 and CARD_UID_002 with 07_gate_card_access.sh.\n'
