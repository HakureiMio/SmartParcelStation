#!/usr/bin/env bash
# Usage: GATE_READER_TOKEN=... ./07_gate_card_access.sh [CARD_UID]
set -euo pipefail
GATEWAY_BASE_URL="${GATEWAY_BASE_URL:-http://127.0.0.1:19000}"
: "${GATE_READER_TOKEN:?Set GATE_READER_TOKEN}"
CARD_UID="${1:-CARD_UID_001}"
curl -fsS -i -X POST "${GATEWAY_BASE_URL}/local/gate/access-card" -H 'Content-Type: application/json' -H 'X-Gate-Reader-Id: GATE01' -H "X-Gate-Reader-Token: ${GATE_READER_TOKEN}" -d "{\"reader_id\":\"GATE01\",\"credential_type\":\"CARD_UID\",\"credential_value\":\"${CARD_UID}\"}"
