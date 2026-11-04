#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/bootstrap-local.sh
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
aiu_select_runtime Darwin:x86_64
[[ "$AIU_NODE_PLATFORM" == darwin-x64 && "$AIU_PYTHON_PLATFORM" == x86_64-apple-darwin ]]
printf 'PASS: Intel Mac selects pinned Intel archives\n'
aiu_select_runtime Darwin:arm64
[[ "$AIU_NODE_PLATFORM" == darwin-arm64 && "$AIU_PYTHON_PLATFORM" == aarch64-apple-darwin ]]
printf 'PASS: Apple Silicon selects separate ARM archives\n'
printf 'cached-payload' > "$fixture/archive"
checksum="$(aiu_sha256 "$fixture/archive")"
aiu_download_checked 'https://invalid.invalid/never-contact' "$fixture/archive" "$checksum"
printf 'PASS: verified cache reuses exact checksum without network\n'
if aiu_download_checked 'https://invalid.invalid/never-contact' "$fixture/archive" '0000000000000000000000000000000000000000000000000000000000000000' > "$fixture/error" 2>&1;then exit 1;fi
[[ "$(cat "$fixture/error")" == *'校验失败'* && "$(cat "$fixture/archive")" == cached-payload ]]
printf 'PASS: checksum mismatch stops and preserves existing file\n'
export AIU_LOCAL_HOME="$fixture/with spaces"
mkdir -p "$AIU_LOCAL_HOME/runtime" "$fixture/input/python/bin"
printf 'safe fixture' > "$fixture/input/python/bin/fixture"
(cd "$fixture/input" && tar -czf "$fixture/runtime.tar.gz" python)
checksum="$(aiu_sha256 "$fixture/runtime.tar.gz")"
aiu_unpack_runtime "$fixture/runtime.tar.gz" "$AIU_LOCAL_HOME/runtime/pinned" "$checksum"
[[ "$(cat "$AIU_LOCAL_HOME/runtime/pinned/bin/fixture")" == 'safe fixture' ]]
aiu_unpack_runtime "$fixture/runtime.tar.gz" "$AIU_LOCAL_HOME/runtime/pinned" "$checksum"
printf 'PASS: atomic extraction and repeated preparation work with spaces\n'
printf 'All 5 local bootstrap checks passed on Bash %s\n' "$BASH_VERSION"
