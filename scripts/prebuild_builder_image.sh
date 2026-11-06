#!/usr/bin/env bash
# Optional: pre-build the kernel builder image and push it to the CNB docker
# registry, so the CI "warm prebuilt kernel builder image" stage can pull it
# instead of rebuilding (apt install) on every pipeline run.
#
# Run once on any arm64 machine with docker + a CNB token:
#   CNB_TOKEN=xxx ./scripts/prebuild_builder_image.sh
set -e

TAG="docker.cnb.cool/mouxancnb/agnos-builder/agnos-meta-builder:arm64"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null && pwd)"

: "${CNB_TOKEN:?set CNB_TOKEN first}"

echo "Building agnos-meta-builder (native $(uname -m))"
docker build -f "$DIR/Dockerfile.builder" -t agnos-meta-builder "$DIR" \
  --build-arg UNAME=builder \
  --build-arg UID=1000 \
  --build-arg GID=1000

docker tag agnos-meta-builder "$TAG"
echo "$CNB_TOKEN" | docker login docker.cnb.cool -u cnb --password-stdin
docker push "$TAG"
echo "pushed $TAG"
