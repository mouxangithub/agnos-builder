#!/usr/bin/env bash
# Download and verify the Ubuntu Base tarball used by Dockerfile.agnos.
# Shared by build_system.sh and the CNB "warm system-image base cache"
# stage (the warm stage runs before build_system.sh, so the tarball must
# exist in the workspace before its docker buildx build).
set -eo pipefail

UBUNTU_BASE_URL="https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/"
UBUNTU_FILE="ubuntu-base-24.04.3-base-arm64.tar.gz"
UBUNTU_FILE_CHECKSUM="7b2dced6dd56ad5e4a813fa25c8de307b655fdabc6ea9213175a92c48dabb048"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null && pwd)"
cd "$DIR"

# Prefer the CNB-local mirrors first (the runner is in mainland China and
# cdimage.ubuntu.com is slow there); fall back to the official source.
if [ ! -f "$UBUNTU_FILE" ]; then
  for url in \
    "$UBUNTU_BASE_URL/$UBUNTU_FILE" \
    "https://mirrors.tuna.tsinghua.edu.cn/ubuntu-cdimage/ubuntu-base/releases/24.04/release/$UBUNTU_FILE"; do
    echo "Downloading Ubuntu Base: $url"
    if curl --connect-timeout 10 -C - -o "$UBUNTU_FILE" "$url" --silent --remote-time --fail; then
      break
    fi
    rm -f "$UBUNTU_FILE"
  done
fi
if [ ! -f "$UBUNTU_FILE" ]; then
  echo "Download failed, please check Ubuntu releases: $UBUNTU_BASE_URL"
  exit 1
fi

if [ "$(sha256sum "$UBUNTU_FILE" | awk '{print $1}')" != "$UBUNTU_FILE_CHECKSUM" ]; then
  echo "Checksum mismatch, please check Ubuntu releases: $UBUNTU_BASE_URL"
  exit 1
fi
echo "Ubuntu Base ready: $UBUNTU_FILE"
