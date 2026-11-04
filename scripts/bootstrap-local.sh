#!/usr/bin/env bash
# Source from the repository root. Compatible with macOS Bash3.2.
source scripts/runtime-versions.sh
aiu_sha256() {
  local result
  if command -v shasum >/dev/null 2>&1; then result="$(shasum -a 256 "$1")";printf '%s\n' "${result%% *}"
  elif command -v sha256sum >/dev/null 2>&1; then result="$(sha256sum "$1")";printf '%s\n' "${result%% *}"
  elif command -v openssl >/dev/null 2>&1; then result="$(openssl dgst -sha256 "$1")";printf '%s\n' "${result##* }"
  else printf '缺少 SHA-256 校验工具，已停止，不执行未验证下载。\n' >&2;return 1;fi
}
aiu_download_checked() {
  local url="$1" archive="$2" checksum="$3" actual
  if [[ -f "$archive" ]]; then
    actual="$(aiu_sha256 "$archive")" || return 1
    if [[ "$actual" == "$checksum" ]]; then return 0;fi
    printf '缓存文件校验失败，已停止并保留：%s\n' "$archive" >&2;return 1
  fi
  printf '正在下载并校验：%s\n' "${archive##*/}"
  curl --fail --location --retry 2 --connect-timeout 20 --max-time 600 --output "$archive.part" "$url" || return 1
  actual="$(aiu_sha256 "$archive.part")" || return 1
  if [[ "$actual" != "$checksum" ]]; then printf 'SHA-256 不匹配，已停止，未解压或执行下载。\n' >&2;return 1;fi
  mv "$archive.part" "$archive"
}
aiu_unpack_runtime() (
  set -e
  local archive="$1" destination="$2" checksum="$3" stage
  if [[ -f "$destination/.verified-sha256" ]] && [[ "$(cat "$destination/.verified-sha256")" == "$checksum" ]]; then return 0;fi
  if [[ -e "$destination" ]]; then printf '运行时目录不完整，已保留：%s\n' "$destination" >&2;return 1;fi
  stage="$(mktemp -d "$AIU_LOCAL_HOME/runtime/.install.XXXXXX")"
  trap 'rm -rf "$stage"' EXIT
  tar -xzf "$archive" --strip-components=1 -C "$stage"
  printf '%s\n' "$checksum" > "$stage/.verified-sha256"
  mv "$stage" "$destination"
)
aiu_local_paths() {
  case "$(uname -s)" in
    Darwin) AIU_LOCAL_HOME="${AIU_LOCAL_HOME:-$HOME/Library/Application Support/AI Universe/local}" ;;
    *) AIU_LOCAL_HOME="${AIU_LOCAL_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/ai-universe/local}" ;;
  esac
  export AIU_LOCAL_HOME
}
aiu_prepare_runtimes() {
  local system version major minor rest tool
  system="$(uname -s)"
  if [[ "$system" == Darwin ]]; then
    version="$(sw_vers -productVersion)";major="${version%%.*}";rest="${version#*.}";minor="${rest%%.*}"
    if [[ "$major" -lt 13 || ( "$major" -eq 13 && "$minor" -lt 5 ) ]]; then printf '便携运行时要求 macOS13.5 或以上；当前 %s。已停止，未安装。\n' "$version" >&2;return 1;fi
  fi
  aiu_select_runtime "$system:$(uname -m)" || return 1
  for tool in curl tar;do if ! command -v "$tool" >/dev/null 2>&1;then printf '缺少系统命令：%s\n' "$tool" >&2;return 1;fi;done
  aiu_local_paths
  umask 077
  mkdir -p "$AIU_LOCAL_HOME/runtime" "$AIU_LOCAL_HOME/archives" "$AIU_LOCAL_HOME/data" "$AIU_LOCAL_HOME/run"
  AIU_PYTHON_HOME="$AIU_LOCAL_HOME/runtime/python-${AIU_PYTHON_VERSION}-${AIU_PYTHON_PLATFORM}"
  AIU_NODE_HOME="$AIU_LOCAL_HOME/runtime/node-${AIU_NODE_VERSION}-${AIU_NODE_PLATFORM}"
  if [[ -f "$AIU_PYTHON_HOME/.verified-sha256" ]] && [[ "$(cat "$AIU_PYTHON_HOME/.verified-sha256")" != "$AIU_PYTHON_SHA" ]];then printf 'Python 校验标记不匹配，已停止。\n' >&2;return 1;fi
  if [[ -f "$AIU_NODE_HOME/.verified-sha256" ]] && [[ "$(cat "$AIU_NODE_HOME/.verified-sha256")" != "$AIU_NODE_SHA" ]];then printf 'Node 校验标记不匹配，已停止。\n' >&2;return 1;fi
  if [[ ! -f "$AIU_PYTHON_HOME/.verified-sha256" ]]; then
    aiu_download_checked "$AIU_PYTHON_URL" "$AIU_LOCAL_HOME/archives/$AIU_PYTHON_ARCHIVE" "$AIU_PYTHON_SHA" || return 1
    aiu_unpack_runtime "$AIU_LOCAL_HOME/archives/$AIU_PYTHON_ARCHIVE" "$AIU_PYTHON_HOME" "$AIU_PYTHON_SHA" || return 1
  fi
  if [[ ! -f "$AIU_NODE_HOME/.verified-sha256" ]]; then
    aiu_download_checked "$AIU_NODE_URL" "$AIU_LOCAL_HOME/archives/$AIU_NODE_ARCHIVE" "$AIU_NODE_SHA" || return 1
    aiu_unpack_runtime "$AIU_LOCAL_HOME/archives/$AIU_NODE_ARCHIVE" "$AIU_NODE_HOME" "$AIU_NODE_SHA" || return 1
  fi
  export AIU_PYTHON_HOME AIU_NODE_HOME PATH="$AIU_NODE_HOME/bin:$AIU_PYTHON_HOME/bin:$PATH"
  [[ "$("$AIU_PYTHON_HOME/bin/python3" --version)" == "Python $AIU_PYTHON_VERSION" ]] || return 1
  [[ "$("$AIU_NODE_HOME/bin/node" --version)" == "v$AIU_NODE_VERSION" ]] || return 1
  printf '便携 Python %s / Node.js %s 已就绪。\n' "$AIU_PYTHON_VERSION" "$AIU_NODE_VERSION"
}
