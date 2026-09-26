#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python3 fap_v87_12_semantic_adaptive_gateway.py
