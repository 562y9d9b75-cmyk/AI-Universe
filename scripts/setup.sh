#!/usr/bin/env bash
set -euo pipefail
export NEXT_TELEMETRY_DISABLED=1
cd "$(dirname "$0")/.."
command -v python3 >/dev/null
command -v node >/dev/null
command -v docker >/dev/null
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
if command -v uv >/dev/null; then
  [[ -d .venv ]] || uv venv .venv
  uv pip sync --python .venv/bin/python backend/requirements.txt
else
  [[ -d .venv ]] || python3 -m venv .venv
  .venv/bin/python -m pip install -r backend/requirements.txt
fi
npm --prefix frontend ci --no-audit --no-fund
docker compose up -d --wait db redis
(cd backend && ../.venv/bin/python -m app.migrate)
npm --prefix frontend run build
printf '\n安装完成。运行 ./scripts/start.sh 启动个人工作空间。\n'
