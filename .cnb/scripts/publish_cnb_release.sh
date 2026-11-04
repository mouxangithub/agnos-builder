#!/usr/bin/env bash
# Publish the packaged OTA release to the CNB release of ${CNB_REPO}.
#
# Runs inside the CNB pipeline where CNB_TOKEN is provided by the platform
# (repo-scoped). Idempotent: an existing release for the tag is reused and
# assets are overwritten, so reruns after partial failures are safe.
#
# Env:
#   CNB_TOKEN   - CNB access token (auto-injected by the CNB pipeline)
#   CNB_REPO    - repo slug, e.g. mouxancnb/agnos-builder
set -euo pipefail

if [ -z "${CNB_TOKEN:-}" ]; then
  echo "ERROR: CNB_TOKEN is not set (expected to be provided by the CNB pipeline)" >&2
  exit 1
fi
: "${CNB_REPO:?CNB_REPO must be set}"

AGNOS_VERSION="$(tr -d '[:space:]' < VERSION)"
case "$AGNOS_VERSION" in
  ''|*[!A-Za-z0-9._-]*)
    echo "VERSION contains an unsafe or empty value: '$AGNOS_VERSION'" >&2
    exit 1 ;;
esac
RELEASE_TAG="agnos-$AGNOS_VERSION"

ASSET_DIR="output/carrot-ota"
[ -d "$ASSET_DIR" ] || { echo "ERROR: $ASSET_DIR missing, run the package stage first" >&2; exit 1; }

api="https://api.cnb.cool/${CNB_REPO}"
auth=(-H "Authorization: Bearer $CNB_TOKEN" -H "Accept: application/vnd.cnb.api+json")

# Create-or-get the release for this tag (idempotent on reruns).
release="$(curl -sf "${auth[@]}" "$api/-/releases/tags/$RELEASE_TAG" || true)"
if [ -z "$release" ]; then
  release="$(curl -sf -X POST "${auth[@]}" -H 'Content-Type: application/json' \
    -d "$(jq -n --arg tag "$RELEASE_TAG" --arg ver "$AGNOS_VERSION" \
      '{tag_name: $tag, name: ("Carrot AGNOS " + $ver),
        body: ("Carrot AGNOS " + $ver + " with Carrot USB-PD v3 kernels and native WCN3990 Bluetooth. OTA manifests for C3/C3 clone and C3X/C4."),
        is_draft: false, is_prerelease: true, make_latest: "false", target_commitish: "master"}' \
    )" "$api/-/releases")"
fi
release_id="$(echo "$release" | jq -r '.id')"
if [ -z "$release_id" ] || [ "$release_id" = "null" ]; then
  echo "ERROR: could not resolve CNB release id for $RELEASE_TAG" >&2
  echo "$release" >&2
  exit 1
fi
echo "CNB release id: $release_id"

for f in "$ASSET_DIR"/*; do
  name="$(basename "$f")"
  size="$(stat -c%s "$f")"
  up="$(curl -sf -X POST "${auth[@]}" -H 'Content-Type: application/json' \
    -d "$(jq -n --arg n "$name" --argjson s "$size" \
      '{asset_name: $n, size: $s, overwrite: true}')" \
    "$api/-/releases/$release_id/asset-upload-url")"
  upload_url="$(echo "$up" | jq -r '.upload_url')"
  verify_url="$(echo "$up" | jq -r '.verify_url')"
  [ -n "$upload_url" ] && [ "$upload_url" != "null" ] || { echo "ERROR: no upload_url for $name" >&2; exit 1; }

  # Presigned PUT: no auth header, stream from disk.
  code="$(curl -sS -o /dev/null -w '%{http_code}' -X PUT \
    -H 'Content-Type: application/octet-stream' \
    --data-binary "@$f" "$upload_url")"
  [[ "$code" =~ ^2 ]] || { echo "ERROR: asset PUT failed for $name (http $code)" >&2; exit 1; }

  # Confirm the upload; verify_url carries %2F path segments, so it
  # must go through curl (no URL re-encoding) as POST with auth.
  code="$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
    -H "Authorization: Bearer $CNB_TOKEN" -H 'Accept: application/json' \
    "$verify_url")"
  [[ "$code" =~ ^2 ]] || { echo "ERROR: upload verification failed for $name (http $code)" >&2; exit 1; }
  echo "uploaded $name ($size bytes) to CNB release $RELEASE_TAG"
done

echo "CNB release published: https://cnb.cool/${CNB_REPO}/-/releases/tag/$RELEASE_TAG"
