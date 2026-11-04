#!/usr/bin/env bash
set -euo pipefail
export NEXT_TELEMETRY_DISABLED=1
cd "$(dirname "$0")/.."
source scripts/common.sh
source scripts/bootstrap-local.sh
trap 'aiu_report_error "$LINENO" "$?"' ERR
printf '\nAI Universe · 免 Docker 个人本地版\n正在准备验证过的便携运行时，不需要管理员权限。\n'
aiu_prepare_runtimes
export AIU_LOCAL_VENV="$AIU_LOCAL_HOME/venv"
if [[ ! -x "$AIU_LOCAL_VENV/bin/python" ]];then "$AIU_PYTHON_HOME/bin/python3" -m venv "$AIU_LOCAL_VENV";fi
requirements_hash="$(aiu_sha256 backend/requirements-local.txt)"
if [[ ! -f "$AIU_LOCAL_VENV/.requirements.sha256" ]] || [[ "$(cat "$AIU_LOCAL_VENV/.requirements.sha256")" != "$requirements_hash" ]];then
  printf '\n[1/3] 安装后台依赖（仅使用预编译包）…\n'
  if [[ -n "${SSL_CERT_FILE:-}" && -z "${PIP_CERT:-}" ]];then export PIP_CERT="$SSL_CERT_FILE";fi
  "$AIU_LOCAL_VENV/bin/python" -m pip install --only-binary=:all: -r backend/requirements-local.txt
  printf '%s\n' "$requirements_hash" > "$AIU_LOCAL_VENV/.requirements.sha256"
fi
lock_hash="$(aiu_sha256 frontend/package-lock.json)"
if [[ ! -f frontend/node_modules/.aiu-lock.sha256 ]] || [[ "$(cat frontend/node_modules/.aiu-lock.sha256)" != "$lock_hash" ]];then
  printf '\n[2/3] 安装界面依赖…\n'
  "$AIU_NODE_HOME/bin/node" "$AIU_NODE_HOME/lib/node_modules/npm/bin/npm-cli.js" --prefix frontend ci --no-audit --no-fund
  printf '%s\n' "$lock_hash" > frontend/node_modules/.aiu-lock.sha256
fi
{
  printf 'api-port=%s\n' "${AIU_PORT:-8000}"
  find frontend/app frontend/components frontend/public -type f -print | LC_ALL=C sort | while IFS= read -r file;do printf '%s %s\n' "$(aiu_sha256 "$file")" "$file";done
  for file in frontend/package.json frontend/package-lock.json frontend/next.config.ts frontend/tsconfig.json frontend/postcss.config.mjs;do printf '%s %s\n' "$(aiu_sha256 "$file")" "$file";done
} > "$AIU_LOCAL_HOME/run/build-inputs.txt"
build_hash="$(aiu_sha256 "$AIU_LOCAL_HOME/run/build-inputs.txt")"
if [[ ! -f frontend/.next/BUILD_ID || ! -f frontend/.next/.aiu-local-build.sha256 ]] || [[ "$(cat frontend/.next/.aiu-local-build.sha256 2>/dev/null || true)" != "$build_hash" ]];then
  printf '\n[3/3] 构建管理界面，首次需要几分钟…\n'
  AIU_API_ORIGIN="http://127.0.0.1:${AIU_PORT:-8000}" "$AIU_NODE_HOME/bin/node" "$AIU_NODE_HOME/lib/node_modules/npm/bin/npm-cli.js" --prefix frontend run build
  printf '%s\n' "$build_hash" > frontend/.next/.aiu-local-build.sha256
fi
printf '\n个人本地版已准备完成。数据保存在：\n%s/data\n' "$AIU_LOCAL_HOME"
