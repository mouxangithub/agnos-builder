#!/usr/bin/env python3
"""Derive trial userspace from the immutable bt1 image, changing labels only.

Do not run apt against the target image: that would confound the kernel trial.
Requires host xz support (Python lzma), simg2img, img2simg and debugfs/e2fsck.
"""
import hashlib
import lzma
import os
from pathlib import Path
import re
import subprocess
import urllib.request
from datetime import datetime, timezone

BASE_ASSET = 'system-375c5d22335770ac08750660bb5b29a3331c550d6a9875b35f36b88af792ea44.img.xz'
BASE_URL = 'https://github.com/ajouatom/agnos-builder/releases/download/agnos-19.8-carrot-bt1/' + BASE_ASSET
COMPRESSED_HASH = '077d42186def98025ffad9723774c96f45da10c87cc6fedbc58d0cf4fa65ffd4'
SPARSE_HASH = 'a67410a888105ecce7bcc05e17cda77fd10572aa4380e9de242a7c92f3497114'
RAW_HASH = '375c5d22335770ac08750660bb5b29a3331c550d6a9875b35f36b88af792ea44'


def digest(path):
  h = hashlib.sha256()
  with path.open('rb') as f:
    for block in iter(lambda: f.read(1024 * 1024), b''):
      h.update(block)
  return h.hexdigest()


def copy_stream(src, dest):
  with dest.open('xb') as f:
    for block in iter(lambda: src.read(1024 * 1024), b''):
      f.write(block)


def main():
  root = Path(__file__).resolve().parents[1]
  work = root / 'build/bt2-frozen-userspace'
  work.mkdir(parents=True, exist_ok=False)
  output = root / 'output/system.img'
  assert not output.exists()
  version = os.environ['AGNOS_VERSION']
  commit = os.environ['GITHUB_SHA']
  assert version == '19.8-carrot-bt2' and re.fullmatch('[0-9a-f]{40}', commit)
  archive, sparse, raw = [work / n for n in ['base.img.xz', 'base.sparse.img', 'system.raw.img']]
  print('Downloading immutable bt1 userspace', flush=True)
  with urllib.request.urlopen(BASE_URL, timeout=120) as response:
    copy_stream(response, archive)
  assert digest(archive) == COMPRESSED_HASH
  with lzma.open(archive, 'rb') as f:
    copy_stream(f, sparse)
  assert digest(sparse) == SPARSE_HASH
  subprocess.run(['simg2img', str(sparse), str(raw)], check=True)
  assert raw.stat().st_size == 4718592000 and digest(raw) == RAW_HASH
  previous = subprocess.check_output(['debugfs', '-R', 'cat /VERSION', str(raw)], text=True)
  assert previous.strip() == '19.8-carrot-bt1'
  (work / 'VERSION').write_text(version)
  (work / 'BUILD').write_text(commit + '\n' + datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') + '\n')
  commands = work / 'debugfs.commands'
  commands.write_text('rm /VERSION\nwrite ' + str(work / 'VERSION') + ' /VERSION\n'
                      'rm /BUILD\nwrite ' + str(work / 'BUILD') + ' /BUILD\n')
  subprocess.run(['debugfs', '-w', '-f', str(commands), str(raw)], check=True)
  for name in ['VERSION', 'BUILD']:
    actual = subprocess.check_output(['debugfs', '-R', 'cat /' + name, str(raw)])
    assert actual == (work / name).read_bytes(), name
  subprocess.run(['e2fsck', '-fn', str(raw)], check=True)
  output.parent.mkdir(exist_ok=True)
  subprocess.run(['img2simg', str(raw), str(output)], check=True)
  print('Frozen bt1 userspace retained; only /VERSION and /BUILD labels changed', flush=True)


if __name__ == '__main__':
  main()
