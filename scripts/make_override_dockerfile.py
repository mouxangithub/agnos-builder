#!/usr/bin/env python3
"""Generate an override Dockerfile.agnos that swaps the stable base stages
for a prebuilt image from the CNB artifact registry.

Dockerfile.agnos declares a cache boundary:

    FROM agnos AS agnos-system    <- everything above is baked into the
    FROM agnos-system AS agnos       prebuilt image (apt layers, uv deps,
                                     adbd/graphics builds)

The override replaces the second FROM with the prebuilt image. buildkit
then skips every stage not referenced anymore (agnos-compiler*,
agnos-base, agnos-system) and only the rootfs overlay and later layers
run locally.

IMPORTANT: the replacement stage must contain ONLY the FROM (+ ARG
re-declarations). Re-running the cached stages' instructions on top of
the prebuilt image would repeat the apt/uv work and break idempotent
scripts (e.g. build_adbd.sh re-patching an already-patched tree).

Usage: make_override_dockerfile.py <image-ref> [output]
  image-ref   e.g. docker.cnb.cool/<repo>/agnos-system-cache:<key>
  output      defaults to /tmp/Dockerfile.agnos.cached
"""
import sys

DEFAULT_OUTPUT = "/tmp/Dockerfile.agnos.cached"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    img = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT

    src = open("Dockerfile.agnos", encoding="utf-8").read()
    old = "FROM agnos-system AS agnos\n"
    if src.count(old) != 1:
        print(f"ERROR: anchor {old!r} found {src.count(old)} times (expected 1)", file=sys.stderr)
        return 1
    # USERNAME's ARG lives in the skipped agnos-base stage, so re-declare it
    # or the --check lint fails with UndefinedVar (check=error=true
    # promotes the warning to an error)
    new = f"FROM {img} AS agnos\nARG USERNAME=comma\n"
    src = src.replace(old, new, 1)

    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    print(f"override dockerfile written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
