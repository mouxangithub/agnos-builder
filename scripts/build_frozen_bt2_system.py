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

BASE_ASSET = 'system-943840f0b1ccb53dd705174dbaf2cfa03b88ca07cad2ab94585d65b2bdf6453b.img.xz'
BASE_URL = 'https://github.com/mouxangithub/agnos-builder/releases/download/agnos-20.2-carrot-bt1/' + BASE_ASSET
COMPRESSED_HASH = '22b7923752bbf30c595eb386284e1d1d80c54ac684d11430cd6c282d32a8d4b5'
SPARSE_HASH = '15cf165732ec30238611aaf4ac02be17252219d43df789e8e80d9e85302bbc8b'
RAW_HASH = '943840f0b1ccb53dd705174dbaf2cfa03b88ca07cad2ab94585d65b2bdf6453b'


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
  assert version == '20.2-carrot-bt2' and re.fullmatch('[0-9a-f]{40}', commit)
  archive, sparse, raw = [work / n for n in ['base.img.xz', 'base.sparse.img', 'system.raw.img']]
  print('Downloading immutable bt1 userspace', flush=True)
  with urllib.request.urlopen(BASE_URL, timeout=120) as response:
    copy_stream(response, archive)
  assert digest(archive) == COMPRESSED_HASH
  with lzma.open(archive, 'rb') as f:
    copy_stream(f, sparse)
  assert digest(sparse) == SPARSE_HASH
  subprocess.run(['simg2img', str(sparse), str(raw)], check=True)
  assert raw.stat().st_size == 2147483648 and digest(raw) == RAW_HASH
  previous = subprocess.check_output(['debugfs', '-R', 'cat /VERSION', str(raw)], text=True)
  assert previous.strip() == '20.2-carrot-bt1'
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
