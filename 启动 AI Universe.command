#!/bin/bash
cd "$(dirname "$0")" || exit 1
/bin/bash scripts/start-local.sh
status=$?
if [[ "$status" -ne 0 ]];then printf '\n启动未完成。请保留上方信息，按回车退出。\n';read -r _;fi
exit "$status"
