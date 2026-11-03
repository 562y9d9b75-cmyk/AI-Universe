#!/usr/bin/env bash
set -euo pipefail
export NEXT_TELEMETRY_DISABLED=1
cd "$(dirname "$0")/.."
source scripts/common.sh
trap 'aiu_report_error "$LINENO" "$?"' ERR
printf 'AI Universe · 安装准备\n'
aiu_check_environment
printf '[1/4] 准备本地配置（保留已有文件）\n'
if [[ ! -f .env ]]; then
  python3 - <<'PY'
import secrets,os
from pathlib import Path
p=secrets.token_hex(24)
fd=os.open('.env',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:f.write(f'POSTGRES_PASSWORD={p}\nAIU_DATABASE_URL=postgresql+psycopg://aiu:{p}@127.0.0.1:55432/aiu\nAIU_REDIS_URL=redis://127.0.0.1:56379/0\nAIU_ORIGIN=http://localhost:3000\n')
PY
fi
# This file is local owner-controlled configuration. Never commit it.
set -a; source .env; set +a
if [[ "${POSTGRES_PASSWORD:-}" == 'CHANGE_ME' ]]; then
  echo 'Replace CHANGE_ME in .env or remove only your unused template copy before setup.' >&2; exit 1
fi
printf '[2/4] 安装 Python 和前端依赖，首次安装可能需要几分钟…\n'
if command -v uv >/dev/null; then
  [[ -d .venv ]] || uv venv .venv
  uv pip sync --python .venv/bin/python backend/requirements.txt
else
  [[ -d .venv ]] || python3 -m venv .venv
  .venv/bin/python -m pip install -r backend/requirements.txt
fi
npm --prefix frontend ci --no-audit --no-fund
printf '[3/4] 启动数据库与任务通知服务…\n'
docker compose up -d --wait db redis
(cd backend && ../.venv/bin/python -m app.migrate)
printf '[4/4] 构建中文管理界面…\n'
npm --prefix frontend run build
printf '\n安装完成。运行 ./scripts/start.sh 启动个人工作空间。\n'
