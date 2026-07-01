#!/usr/bin/env bash
# Usage: run from repository root: ./scripts/demo/06_gateway_sync_pull.sh
set -euo pipefail
cd "$(dirname "$0")/../../smartparcel-gateway"
python -m gateway.main sync-pull
