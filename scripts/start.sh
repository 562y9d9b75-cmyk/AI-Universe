#!/usr/bin/env bash
set -euo pipefail
export NEXT_TELEMETRY_DISABLED=1
cd "$(dirname "$0")/.."
source scripts/common.sh
trap 'aiu_report_error "$LINENO" "$?"' ERR
aiu_check_environment
[[ -f .env && -x .venv/bin/python && -f frontend/.next/BUILD_ID ]] || { echo '请先运行 ./scripts/setup.sh'; exit 1; }
set -a; source .env; set +a
export AIU_DATA_DIR="${AIU_DATA_DIR:-$PWD/.data}"
mkdir -p .run
# Avoid starting a competing scheduler or stopping somebody else's process.
if [[ -f .run/launcher.pid ]] && kill -0 "$(cat .run/launcher.pid)" 2>/dev/null; then echo 'AI Universe 已启动'; exit 1; fi
for port in "${AIU_PORT:-8000}" "${AIU_WEB_PORT:-3000}"; do
  python3 - "$port" <<'PY'
import socket,sys
s=socket.socket()
s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
try:s.bind(('127.0.0.1',int(sys.argv[1])))
except OSError:sys.exit('端口 '+sys.argv[1]+' 已被占用，请停止占用服务或修改本地端口配置')
finally:s.close()
PY
done
docker compose up -d --wait db redis
(cd backend && ../.venv/bin/python -m app.migrate)
echo $$ > .run/launcher.pid
children=()
cleanup(){ trap - EXIT INT TERM; for pid in "${children[@]}"; do kill "$pid" 2>/dev/null || true; done; wait || true; rm -f .run/launcher.pid; }
trap cleanup EXIT INT TERM
(cd backend && exec ../.venv/bin/uvicorn app.main:app --no-access-log --host 127.0.0.1 --port "${AIU_PORT:-8000}") >.run/api.log 2>&1 & children+=("$!")
(cd backend && exec ../.venv/bin/python -m app.runtime) >.run/worker.log 2>&1 & children+=("$!")
(cd frontend && exec node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port "${AIU_WEB_PORT:-3000}") >.run/web.log 2>&1 & children+=("$!")
for i in {1..60}; do
 if curl -fsS "http://127.0.0.1:${AIU_WEB_PORT:-3000}/api/health" >/dev/null 2>&1; then
   printf 'AI Universe 已启动。浏览器打开本机端口 %s；首次使用创建唯一的个人账户。\n按 Ctrl+C 停止，数据保留。日志位于 .run/。\n' "${AIU_WEB_PORT:-3000}"
   # macOS ships Bash 3.2, which does not implement wait -n.
   while true; do
     for pid in "${children[@]}"; do
       if ! kill -0 "$pid" 2>/dev/null; then
         if wait "$pid"; then status=0; else status=$?; fi
         printf '\n一个必要服务已退出（退出码 %s），正在停止本次启动的其余服务。\n' "$status"
         aiu_tail_logs
         [[ "$status" -ne 0 ]] || status=1
         exit "$status"
       fi
     done
     sleep 1
   done
 fi
 for pid in "${children[@]}"; do kill -0 "$pid" 2>/dev/null || { aiu_tail_logs; exit 1; }; done
 sleep 1
done
echo '启动未通过健康检查';aiu_tail_logs;exit 1
