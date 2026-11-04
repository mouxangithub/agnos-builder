#!/usr/bin/env python3
"""Package one system image and two device-specific boot images for carrot AGNOS."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess


SECTOR_SIZE = 4096
RELEASE_ASSET_LIMIT = 2 * 1024 * 1024 * 1024
EXPECTED_PARTITIONS = ("xbl", "xbl_config", "abl", "aop", "devcfg", "boot", "system")


def checksum(path: Path) -> str:
  digest = hashlib.sha256()
  with path.open("rb") as source:
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
      digest.update(chunk)
  return digest.hexdigest()


def sparse_hashes(path: Path) -> tuple[str, str, int]:
  raw_hash = hashlib.sha256()
  ondevice_hash = hashlib.sha256()
  total_size = 0

  with path.open("rb") as source:
    header = struct.unpack("<I4H4I", source.read(28))
    magic, major, minor, file_header_size, chunk_header_size, block_size, _, total_chunks, _ = header
    assert magic == 0xED26FF3A
    assert (major, minor) == (1, 0)
    assert file_header_size == 28 and chunk_header_size == 12
    assert block_size == SECTOR_SIZE

    for _ in range(total_chunks):
      chunk_type, _, chunk_blocks, _ = struct.unpack("<2H2I", source.read(12))
      chunk_size = chunk_blocks * SECTOR_SIZE
      if chunk_type == 0xCAC1:
        data = source.read(chunk_size)
        assert len(data) == chunk_size
        raw_hash.update(data)
        ondevice_hash.update(data)
      elif chunk_type == 0xCAC2:
        fill = source.read(4)
        data = fill * (chunk_size // 4)
        raw_hash.update(data)
        if fill != b"\x00\x00\x00\x00":
          ondevice_hash.update(data)
      elif chunk_type == 0xCAC3:
        raise ValueError("DONT_CARE sparse chunks are not supported by the AGNOS OTA updater")
      else:
        raise ValueError(f"unsupported sparse chunk type: {chunk_type:#x}")
      total_size += chunk_size

  return raw_hash.hexdigest(), ondevice_hash.hexdigest(), total_size


def compress(source: Path, destination: Path) -> None:
  with destination.open("wb") as output:
    subprocess.run(["xz", "-0", "-T0", "-c", str(source)], stdout=output, check=True)
  if destination.stat().st_size >= RELEASE_ASSET_LIMIT:
    raise ValueError(f"{destination.name} exceeds GitHub's 2 GiB release asset limit")


def package_boot(path: Path, output_dir: Path, device_group: str, base_url: str) -> dict:
  raw_size = path.stat().st_size
  raw_hash = checksum(path)
  padding = (SECTOR_SIZE - raw_size % SECTOR_SIZE) % SECTOR_SIZE
  ondevice = hashlib.sha256()
  with path.open("rb") as source:
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
      ondevice.update(chunk)
  ondevice.update(b"\x00" * padding)

  asset = f"boot-{device_group}-{raw_hash}.img.xz"
  compressed_path = output_dir / asset
  compress(path, compressed_path)
  return {
    "name": "boot",
    "url": f"{base_url}/{asset}",
    "compressed_hash": checksum(compressed_path),
    "compressed_size": compressed_path.stat().st_size,
    "hash": raw_hash,
    "hash_raw": raw_hash,
    "size": raw_size,
    "sparse": False,
    "full_check": True,
    "has_ab": True,
    "ondevice_hash": ondevice.hexdigest(),
  }


def package_system(path: Path, output_dir: Path, base_url: str) -> dict:
  sparse_hash, ondevice_hash, raw_size = sparse_hashes(path)
  asset = f"system-{sparse_hash}.img.xz"
  compressed_path = output_dir / asset
  compress(path, compressed_path)
  return {
    "name": "system",
    "url": f"{base_url}/{asset}",
    "compressed_hash": checksum(compressed_path),
    "compressed_size": compressed_path.stat().st_size,
    "hash": checksum(path),
    "hash_raw": sparse_hash,
    "size": raw_size,
    "sparse": True,
    "full_check": False,
    "has_ab": True,
    "ondevice_hash": ondevice_hash,
  }


def compose_manifest(base_path: Path, boot: dict, system: dict) -> list[dict]:
  manifest = json.loads(base_path.read_text())
  names = tuple(partition["name"] for partition in manifest)
  if names != EXPECTED_PARTITIONS:
    raise ValueError(f"unexpected base manifest layout in {base_path}: {names}")
  return [boot if p["name"] == "boot" else system if p["name"] == "system" else p for p in manifest]


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--version", required=True)
  parser.add_argument("--release-base-url", required=True)
  parser.add_argument("--system", type=Path, required=True)
  parser.add_argument("--c3-boot", type=Path, required=True)
  parser.add_argument("--c4-boot", type=Path, required=True)
  parser.add_argument("--c3-base-manifest", type=Path, required=True)
  parser.add_argument("--c4-base-manifest", type=Path, required=True)
  parser.add_argument("--output-dir", type=Path, required=True)
  args = parser.parse_args()

  args.output_dir.mkdir(parents=True, exist_ok=True)
  system = package_system(args.system, args.output_dir, args.release_base_url)
  c3_boot = package_boot(args.c3_boot, args.output_dir, "c3-c3clone", args.release_base_url)
  c4_boot = package_boot(args.c4_boot, args.output_dir, "c3x-c4", args.release_base_url)

  manifests = {
    "agnos-c3-c3clone.json": compose_manifest(args.c3_base_manifest, c3_boot, system),
    "agnos-c3x-c4.json": compose_manifest(args.c4_base_manifest, c4_boot, system),
  }
  for name, manifest in manifests.items():
    (args.output_dir / name).write_text(json.dumps(manifest, indent=2) + "\n")
  (args.output_dir / "VERSION").write_text(args.version + "\n")

  checksums = []
  for path in sorted(args.output_dir.iterdir()):
    if path.is_file() and path.name != "SHA256SUMS":
      checksums.append(f"{checksum(path)}  {path.name}")
  (args.output_dir / "SHA256SUMS").write_text("\n".join(checksums) + "\n")


if __name__ == "__main__":
  main()
