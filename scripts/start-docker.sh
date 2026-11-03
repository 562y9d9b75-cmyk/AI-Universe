#!/usr/bin/env bash
# Docker-only path, compatible with macOS Bash 3.2. No host Python/Node required.
set -euo pipefail
case "$OSTYPE" in darwin*) export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" ;; esac
cd "$(dirname "$0")/.."
printf '\nAI Universe · 本机容器启动\n'
if ! command -v docker >/dev/null 2>&1; then
  printf '\n[缺少 Docker Desktop] 请安装并打开：\nhttps://www.docker.com/products/docker-desktop/\n安装后重新打开本启动文件。Python 和 Node.js 已由容器提供。\n'
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  printf '\n需要更新 Docker Desktop，以提供 Docker Compose v2。\n'
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  printf '\nDocker 引擎尚未就绪。请打开 Docker Desktop，等待它显示引擎已运行，再启动。\n'
  exit 1
fi
if [[ ! -f .env ]]; then
  if ! command -v openssl >/dev/null 2>&1; then
    printf '\n缺少系统 openssl，无法安全生成本地数据库密码。请保留此信息。\n'
    exit 1
  fi
  password="$(openssl rand -hex 24)"
  # noclobber prevents overwriting a concurrent/existing owner config.
  (umask 077; set -o noclobber; printf 'POSTGRES_PASSWORD=%s\nAIU_WEB_PORT=3000\n' "$password" > .env)
  unset password
fi
# Existing .env belongs to the owner; never overwrite or print it.
set -a; source .env; set +a
if [[ -z "${POSTGRES_PASSWORD:-}" || "${POSTGRES_PASSWORD:-}" == 'CHANGE_ME' ]]; then
  printf '\n本地配置缺少有效数据库密码。已有 .env 已保留，不会覆盖。\n'
  exit 1
fi
printf '\n正在准备全部服务。首次需下载开源组件并构建，可能需要几分钟。\n'
if ! docker compose -f compose.desktop.yaml up -d --build --wait --wait-timeout 180; then
  printf '\n未能启动全部服务，请保留上方错误。已有配置和数据不会被删除。\n'
  docker compose -f compose.desktop.yaml logs --tail 30 api worker web || true
  exit 1
fi
printf '\nAI Universe 已就绪：http://localhost:%s\n首次使用请创建唯一的个人账户。\n关闭此终端不会删除数据。停止请运行：bash scripts/stop-docker.sh\n' "${AIU_WEB_PORT:-3000}"
if [[ "$(uname -s)" == Darwin ]] && command -v open >/dev/null 2>&1; then
  open "http://localhost:${AIU_WEB_PORT:-3000}" || true
fi
