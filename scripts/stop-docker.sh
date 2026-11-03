#!/usr/bin/env bash
set -euo pipefail
case "$OSTYPE" in darwin*) export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" ;; esac
cd "$(dirname "$0")/.."
docker compose -f compose.desktop.yaml stop
printf '\nAI Universe 已停止，数据库和成果文件保留。\n'
