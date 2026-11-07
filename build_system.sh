#!/usr/bin/env bash
set -eo pipefail

# Make sure we're in the correct spot
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"
cd $DIR

# Fail fast on clobbered checked-in inputs before any Docker work starts.
./scripts/validate_carrot_inputs.sh

# Download (or reuse) and verify the Ubuntu Base tarball; shared with the
# CNB warm-cache stage which runs before this script.
./scripts/prepare_ubuntu_base.sh
UBUNTU_FILE="ubuntu-base-24.04.3-base-arm64.tar.gz"

BUILD_DIR="$DIR/build"
OUTPUT_DIR="$DIR/output"

OUT_IMAGE="$OUTPUT_DIR/system.img"

# Create temp dir if non-existent
mkdir -p $BUILD_DIR $OUTPUT_DIR

# Setup qemu multiarch, not needed for remote arm64 builds
if [ "$(uname -m)" = "x86_64" ] && [ -z "$NS" ]; then
  echo "Registering emulator"
  docker run --rm --privileged tonistiigi/binfmt --install all
fi

# Check agnos-builder Dockerfile
export DOCKER_BUILDKIT=1
# CNB pipeline can point this at an override Dockerfile whose stable base
# stages (apt + uv dependency layers) are replaced by a prebuilt image from
# the CNB artifact registry (see the "warm system-image base cache" stage in
# .cnb.yml); everything else stays identical.
AGNOS_DOCKERFILE=${AGNOS_DOCKERFILE:-Dockerfile.agnos}
docker buildx build -f $AGNOS_DOCKERFILE --check $DIR

GIT_HASH=${GIT_HASH:-$(git --git-dir=$DIR/.git rev-parse HEAD)}
BUILD_DATETIME="$(date '+%Y-%m-%dT%H:%M:%S')"

if [ ! -z "$NS" ]; then
  # Netless (comma nsc) remote builder: single-pass flow, zstd on by default
  if ! command -v zstd &> /dev/null; then
    echo "zstd missing, please install it"
    exit 1
  fi
  echo "Building system image (nsc)"
  rm -rf $BUILD_DIR/image
  nsc build --region ${NS_REGION:-us} --output-local $BUILD_DIR/image --build-arg ZSTD=1 \
    -f Dockerfile.agnos $DIR --platform=linux/arm64 \
    --build-arg UBUNTU_BASE_IMAGE=$UBUNTU_FILE \
    --build-arg GIT_HASH=$GIT_HASH \
    --build-arg BUILD_DATETIME=$BUILD_DATETIME
  if [ -f $BUILD_DIR/image/system.img.zst ]; then
    zstd -q -d -f $BUILD_DIR/image/system.img.zst -o $OUT_IMAGE
  else
    mv $BUILD_DIR/image/system.img $OUT_IMAGE
  fi
  rm -rf $BUILD_DIR/image
elif [ -n "$SPLIT_IMAGE_BUILD" ]; then
  # Lightweight CI runners (e.g. CNB) give each docker daemon a small storage
  # quota; the mkfs.ext4 + img2simg peak (raw 2G + sparse ~2G inside one RUN)
  # overflows it and img2simg dies with "Failed to write sparse file". Build
  # only the rootfs stage in docker, then assemble the image on the host.
  [ "$(id -u)" = "0" ] || { echo "SPLIT_IMAGE_BUILD requires root"; exit 1; }
  for tool in mkfs.ext4 img2simg setcap; do
    command -v $tool >/dev/null 2>&1 || {
      echo "missing tool: $tool (apt-get install e2fsprogs android-sdk-libsparse-utils libcap2-bin)"
      exit 1
    }
  done
  if [ -n "$ZSTD" ] && ! command -v zstd >/dev/null 2>&1; then
    echo "zstd missing, please install it"
    exit 1
  fi
  echo "Building system image (split: rootfs in docker, assembly on host)"
  rm -rf $BUILD_DIR/image && mkdir -p $BUILD_DIR/image
  docker buildx build -f $AGNOS_DOCKERFILE $DIR --platform=linux/arm64 \
    --target agnos -t agnos-rootfs:local \
    --build-arg UBUNTU_BASE_IMAGE=$UBUNTU_FILE \
    --build-arg GIT_HASH=$GIT_HASH \
    --build-arg BUILD_DATETIME=$BUILD_DATETIME
  docker rm -f agnos-rootfs-tmp >/dev/null 2>&1 || true
  docker create --name agnos-rootfs-tmp agnos-rootfs:local /bin/sh >/dev/null
  rm -rf $BUILD_DIR/rootfs && mkdir -p $BUILD_DIR/rootfs
  # docker export streams the flattened rootfs (uid/gid preserved) through the
  # client, so the heavy files never land in the daemon's storage again
  docker export agnos-rootfs-tmp | tar -x -C $BUILD_DIR/rootfs
  docker rm -f agnos-rootfs-tmp >/dev/null
  cd $BUILD_DIR/rootfs
  # These files are bind mounted in containers, so they can only be set here.
  ln -sf /proc/sys/kernel/hostname etc/hostname
  printf "127.0.0.1    localhost.localdomain localhost\n127.0.0.1    comma\n" > etc/hosts
  ln -sf /run/systemd/resolve/stub-resolv.conf etc/resolv.conf
  setcap cap_net_raw+ep bin/ping
  printf "%s\n%s\n" "$GIT_HASH" "$BUILD_DATETIME" > BUILD
  ROOTFS_IMAGE_SIZE=${ROOTFS_IMAGE_SIZE:-2048M}
  mkfs.ext4 -q -d . $BUILD_DIR/image/system.img "$ROOTFS_IMAGE_SIZE"
  img2simg $BUILD_DIR/image/system.img $OUT_IMAGE
  rm -f $BUILD_DIR/image/system.img
  cd $DIR
  rm -rf $BUILD_DIR/rootfs
  if [ -n "$ZSTD" ]; then
    zstd -q -T0 -9 --rm $OUT_IMAGE
  fi
else
  # Default: build the image inside docker, only the sparse image is exported
  echo "Building system image"
  BUILD="docker buildx build --output type=local,dest=$BUILD_DIR/image"
  rm -rf $BUILD_DIR/image
  $BUILD -f Dockerfile.agnos $DIR --platform=linux/arm64 \
    --build-arg UBUNTU_BASE_IMAGE=$UBUNTU_FILE \
    --build-arg GIT_HASH=$GIT_HASH \
    --build-arg BUILD_DATETIME=$BUILD_DATETIME
  if [ -f $BUILD_DIR/image/system.img.zst ]; then
    zstd -q -d -f $BUILD_DIR/image/system.img.zst -o $OUT_IMAGE
  else
    mv $BUILD_DIR/image/system.img $OUT_IMAGE
  fi
  rm -rf $BUILD_DIR/image
fi

echo "Done!"
