#!/usr/bin/env bash
# Usage: GATE_READER_TOKEN=... ./10_gate_auth_result.sh
set -euo pipefail
GATEWAY_BASE_URL="${GATEWAY_BASE_URL:-http://127.0.0.1:19000}"
: "${GATE_READER_TOKEN:?Set GATE_READER_TOKEN}"
curl -fsS -i -H 'X-Gate-Reader-Id: GATE01' -H "X-Gate-Reader-Token: ${GATE_READER_TOKEN}" "${GATEWAY_BASE_URL}/local/gate/auth-result?reader_id=GATE01"
