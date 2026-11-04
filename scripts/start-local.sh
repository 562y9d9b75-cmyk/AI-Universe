#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/setup-local.sh
exec "$AIU_LOCAL_VENV/bin/python" scripts/run-local.py
