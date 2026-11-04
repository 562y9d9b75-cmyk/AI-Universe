#!/usr/bin/env bash
# Upstream SHA256 manifests checked 2026-11-03; no remote scripts are executed.
AIU_NODE_VERSION=24.22.2
AIU_PYTHON_VERSION=3.12.16
AIU_PYTHON_RELEASE=20261026
aiu_select_runtime() {
  case "$1" in
    Darwin:x86_64)
      AIU_NODE_PLATFORM=darwin-x64
      AIU_NODE_SHA=d5e336d588c45be0c37dbd52cc29895593009ca4997a77a1fd02815131ed0e52
      AIU_PYTHON_PLATFORM=x86_64-apple-darwin
      AIU_PYTHON_SHA=37c38fda76fec1fbf310adcbafb7f0d96af13b5511bf8ea954c3aa8eec185734 ;;
    Darwin:arm64)
      AIU_NODE_PLATFORM=darwin-arm64
      AIU_NODE_SHA=aa9549349e47dffaa42dcf95d6e06ade8c4bdafc980979883b88767670df385a
      AIU_PYTHON_PLATFORM=aarch64-apple-darwin
      AIU_PYTHON_SHA=353d5f1b4fd2715e7053f12f068435d5bbad16b91e057006b5d01e0925709a7e ;;
    Linux:x86_64)
      AIU_NODE_PLATFORM=linux-x64
      AIU_NODE_SHA=361718c444e49af2ca5a110c83ba6a8901143f23ab285ebbef0341f391f482a9
      AIU_PYTHON_PLATFORM=x86_64-unknown-linux-gnu
      AIU_PYTHON_SHA=ce4f6d0a6cfdb3bed6e44c2f9affd85943c76a42e25ad3a259002f31d6fb8a20 ;;
    *) printf '暂不支持自动准备此平台：%s\n' "$1" >&2;return 1 ;;
  esac
  AIU_NODE_ARCHIVE="node-v${AIU_NODE_VERSION}-${AIU_NODE_PLATFORM}.tar.gz"
  AIU_PYTHON_ARCHIVE="cpython-${AIU_PYTHON_VERSION}+${AIU_PYTHON_RELEASE}-${AIU_PYTHON_PLATFORM}-install_only_stripped.tar.gz"
  AIU_NODE_URL="https://nodejs.org/dist/v${AIU_NODE_VERSION}/${AIU_NODE_ARCHIVE}"
  AIU_PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${AIU_PYTHON_RELEASE}/${AIU_PYTHON_ARCHIVE}"
}
