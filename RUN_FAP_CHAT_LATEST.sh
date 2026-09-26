#!/usr/bin/env bash
set -euo pipefail
LATEST_VERSION="1.0.01-unified-chat"
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "Starting FAP $LATEST_VERSION"
exec python3 "$ROOT/fap_v1_0_01_dynamic_sparse_routing_gateway.py"
