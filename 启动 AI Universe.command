#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")" || exit 1
/bin/bash scripts/start-docker.sh
status=$?
if [[ "$status" -ne 0 ]]; then
  printf '\n尚未完成启动。请保留上方信息，按回车退出。\n'
  read -r _
fi
exit "$status"
