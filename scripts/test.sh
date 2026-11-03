#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend run typecheck
.venv/bin/python scripts/test_e2e.py
