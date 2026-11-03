#!/usr/bin/env bash
# Contract tests for preflight errors and service supervision; compatible with Bash 3.2.
set -euo pipefail
cd "$(dirname "$0")/.."
BASH_BIN="${BASH:-/bin/bash}"
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
mkdir -p "$fixture/project/scripts" "$fixture/empty" "$fixture/bin"
cp scripts/common.sh scripts/setup.sh scripts/start.sh scripts/check-environment.sh "$fixture/project/scripts/"
ln -s "$(command -v dirname)" "$fixture/empty/dirname"
set +e
output="$(PATH="$fixture/empty" "$BASH_BIN" "$fixture/project/scripts/setup.sh" 2>&1)"
status=$?
set -e
[[ "$status" -ne 0 && "$output" == *'[缺少] python3'* && "$output" == *'[缺少] node'* && "$output" == *'[缺少] docker'* ]]
[[ ! -f "$fixture/project/.env" ]]
printf 'PASS: missing tools are named; no silent exit or config creation\n'
for tool in dirname mkdir rm sleep tail; do ln -s "$(command -v "$tool")" "$fixture/bin/$tool"; done
cat > "$fixture/bin/python3" <<'MOCK'
#!/bin/sh
if [ "$1" = '-c' ] && [ "${PYTHON_TOO_OLD:-0}" = 1 ]; then exit 1; fi
exit 0
MOCK
cat > "$fixture/bin/node" <<'MOCK'
#!/bin/sh
if [ "$1" = '-e' ]; then exit 0; fi
printf '%s\n' "$$" >> "$AIU_TEST_CHILD_PIDS"
exec /bin/sleep 30
MOCK
cat > "$fixture/bin/docker" <<'MOCK'
#!/bin/sh
if [ "$1" = info ] && [ "${DOCKER_DOWN:-0}" = 1 ]; then exit 1; fi
exit 0
MOCK
for tool in npm curl; do printf '#!/bin/sh\nexit 0\n' > "$fixture/bin/$tool"; done
chmod +x "$fixture/bin/python3" "$fixture/bin/node" "$fixture/bin/docker" "$fixture/bin/npm" "$fixture/bin/curl"
set +e
output="$(PATH="$fixture/bin" PYTHON_TOO_OLD=1 "$BASH_BIN" "$fixture/project/scripts/check-environment.sh" 2>&1)";status=$?
set -e
[[ "$status" -ne 0 && "$output" == *'Python 需要 3.11'* ]]
printf 'PASS: outdated Python is reported\n'
set +e
output="$(PATH="$fixture/bin" DOCKER_DOWN=1 "$BASH_BIN" "$fixture/project/scripts/check-environment.sh" 2>&1)";status=$?
set -e
[[ "$status" -ne 0 && "$output" == *'Docker 引擎尚未就绪'* ]]
printf 'PASS: installed-but-stopped Docker is explained\n'
PATH="$fixture/bin" "$BASH_BIN" "$fixture/project/scripts/check-environment.sh" > /dev/null
printf 'PASS: valid tools pass preflight\n'
mkdir -p "$fixture/project/.venv/bin" "$fixture/project/backend" "$fixture/project/frontend/.next"
printf 'POSTGRES_PASSWORD=test_fixture_only\nAIU_PORT=49100\nAIU_WEB_PORT=49101\n' > "$fixture/project/.env"
printf 'built\n' > "$fixture/project/frontend/.next/BUILD_ID"
cat > "$fixture/project/.venv/bin/python" <<'MOCK'
#!/bin/sh
if [ "${2:-}" = app.runtime ]; then /bin/sleep 1; exit 7; fi
exit 0
MOCK
cat > "$fixture/project/.venv/bin/uvicorn" <<'MOCK'
#!/bin/sh
printf '%s\n' "$$" >> "$AIU_TEST_CHILD_PIDS"
exec /bin/sleep 30
MOCK
chmod +x "$fixture/project/.venv/bin/"*
set +e
output="$(PATH="$fixture/bin" AIU_TEST_CHILD_PIDS="$fixture/children" "$BASH_BIN" "$fixture/project/scripts/start.sh" 2>&1)";status=$?
set -e
[[ "$status" -eq 7 && "$output" == *'AI Universe 已启动'* ]]
[[ ! -f "$fixture/project/.run/launcher.pid" && -f "$fixture/project/.env" ]]
while read -r pid; do if kill -0 "$pid" 2>/dev/null; then printf 'FAIL: started child %s survived cleanup\n' "$pid"; exit 1; fi; done < "$fixture/children"
printf 'PASS: service exit status preserved; sibling services stopped; owner config preserved\n'
cp scripts/start-docker.sh "$fixture/project/scripts/"
ln -s "$(command -v uname)" "$fixture/bin/uname"
# This PATH contains no Python, Node or npm; the Docker-only launcher must work.
mkdir -p "$fixture/docker-only"
for tool in dirname uname; do ln -s "$(command -v "$tool")" "$fixture/docker-only/$tool"; done
cp "$fixture/bin/docker" "$fixture/docker-only/docker"
output="$(PATH="$fixture/docker-only" "$BASH_BIN" "$fixture/project/scripts/start-docker.sh" 2>&1)"
[[ "$output" == *'AI Universe 已就绪'* ]]
printf 'PASS: Docker-only entrypoint needs no host Python, Node or npm\n'
set +e
output="$(PATH="$fixture/empty" "$BASH_BIN" "$fixture/project/scripts/start-docker.sh" 2>&1)";status=$?
set -e
[[ "$status" -ne 0 && "$output" == *'[缺少 Docker Desktop]'* ]]
printf 'PASS: Docker-only entrypoint explains missing Docker\n'
printf 'All 7 launcher checks passed on Bash %s\n' "$BASH_VERSION"
