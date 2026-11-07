#!/usr/bin/env python3
"""Generate an override Dockerfile.agnos that swaps the stable base stages
for prebuilt images from the CNB artifact registry.

The three stages replaced (all cached by the CI "warm system-image base
cache" stage) are the bulk of the system image build wall time and change
rarely:
  agnos-compiler-adbd    <- prebuilt image containing the compiled adbd
  agnos-compiler-graphics <- prebuilt image containing the graphics libs
  agnos-base             <- prebuilt image containing apt + uv dependency layers

buildkit skips every stage nothing references anymore (agnos-compiler,
agnos-base), so a cache hit turns the heavy front half of the build into an
image pull and only the rootfs overlay and later layers run locally.

Usage: make_override_dockerfile.py <image-ref-prefix> [output]
  image-ref-prefix  e.g. docker.cnb.cool/<repo>/agnos-system-cache:<key>
                    -adbd / -graphics suffixes are appended for the other two
  output            defaults to /tmp/Dockerfile.agnos.cached
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
    replacements = [
        ("FROM agnos-compiler AS agnos-compiler-adbd",
         f"FROM {img}-adbd AS agnos-compiler-adbd"),
        ("FROM agnos-compiler AS agnos-compiler-graphics",
         f"FROM {img}-graphics AS agnos-compiler-graphics"),
        ("FROM agnos-base AS agnos",
         f"FROM {img} AS agnos"),
    ]
    for old, new in replacements:
        if src.count(old) != 1:
            print(f"ERROR: anchor {old!r} found {src.count(old)} times (expected 1)", file=sys.stderr)
            return 1
        src = src.replace(old, new, 1)

    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    print(f"override dockerfile written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
