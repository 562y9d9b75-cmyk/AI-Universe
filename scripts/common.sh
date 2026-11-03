#!/usr/bin/env bash
# Shared preflight; intentionally compatible with macOS /bin/bash 3.2.
aiu_check_environment() {
  local missing=0
  local tool
  printf '\n检查本机运行环境…\n'
  for tool in python3 node npm docker; do
    if command -v "$tool" >/dev/null 2>&1; then
      printf '  [已找到] %s\n' "$tool"
    else
      printf '  [缺少] %s\n' "$tool"
      missing=1
    fi
  done
  if command -v python3 >/dev/null 2>&1; then
    if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
      printf '  [需更新] Python 需要 3.11 或更高版本。\n'
      missing=1
    fi
  fi
  if command -v node >/dev/null 2>&1; then
    if ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 22 ? 0 : 1)'; then
      printf '  [需更新] Node.js 需要 22 或更高版本，建议安装 24 LTS。\n'
      missing=1
    fi
  fi
  if [[ "$missing" -ne 0 ]]; then
    cat <<'HELP'

缺少运行环境，尚未开始安装 AI Universe。这不是账号或模型授权错误。
请按上面标记安装缺少的项目；安装后重新打开终端：
  Python 3.11+：https://www.python.org/downloads/macos/
  Node.js 24 LTS（包含 npm）：https://nodejs.org/zh-cn/download
  Docker Desktop：https://www.docker.com/products/docker-desktop/
无需购买模型 API、数据库或服务器。安装 Docker 后需要打开 Docker Desktop。
HELP
    return 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    printf '\n[未就绪] 需要 Docker Compose v2。Mac 请安装/更新 Docker Desktop。\n'
    return 1
  fi
  if ! docker info >/dev/null 2>&1; then
    printf '\n[未就绪] 找到了 Docker，但 Docker 引擎尚未就绪。\nMac 请打开 Docker Desktop，等待显示引擎已运行，再执行本命令。\n'
    return 1
  fi
  printf '运行环境检查通过。\n\n'
}

aiu_report_error() {
  local line="$1" status="$2"
  printf '\n操作未完成（第 %s 行，退出码 %s）。请保留上方具体错误信息。\n不会删除你的配置或业务数据。\n' "$line" "$status" >&2
}

aiu_tail_logs() {
  # macOS BSD tail requires -n when following with multiple file names.
  local logfile
  for logfile in .run/api.log .run/worker.log .run/web.log; do
    if [[ -f "$logfile" ]]; then
      printf '\n--- %s ---\n' "$logfile"
      tail -n 30 "$logfile"
    fi
  done
}
