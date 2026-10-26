#!/usr/bin/env bash
# Validates the checked-in Carrot release inputs before any Docker build runs.
#
# Two layers, mirroring the StarPilot validate_starpilot_inputs.sh idea:
#   1. sha256 pins for frozen binary inputs (amdgpu firmware blobs, the
#      bluetooth-radio script, the service unit). A mismatch means a merge or
#      hand edit clobbered the file - the build must not proceed silently.
#      If a change is intentional, update the pin below in the same commit.
#   2. grep assertions for behaviour-critical config lines, so a refactored
#      file cannot quietly drop the lines the trial depends on.
#
# Deliberately NOT version-pinned: the workflow reads VERSION dynamically.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null && pwd)"

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

expect_hash() {
  local path="$1"
  local expected="$2"
  local actual
  actual="$(sha256 "$DIR/$path")"
  if [[ "$actual" != "$expected" ]]; then
    echo "carrot input hash mismatch: $path" >&2
    echo "expected: $expected" >&2
    echo "actual:   $actual" >&2
    echo "if this change is intentional, update the pin in scripts/validate_carrot_inputs.sh in the same commit" >&2
    exit 1
  fi
}

expect_line() {
  local path="$1"
  local line="$2"
  if ! grep -Fxq "$line" "$DIR/$path"; then
    echo "carrot input missing required line in $path:" >&2
    echo "  $line" >&2
    exit 1
  fi
}

expect_hash userspace/root/usr/lib/firmware/amdgpu/gc_12_0_0_imu.bin.zst 9091ec887822b66b3e49b929a684a9c182057ff92340f2e7b84cba29156af3bf
expect_hash userspace/root/usr/lib/firmware/amdgpu/gc_12_0_0_me.bin.zst 0bf7d4b54ace8af59d5c99c289bbb1b8ce77d11114bb880df308be2c9d5e2638
expect_hash userspace/root/usr/lib/firmware/amdgpu/gc_12_0_0_mec.bin.zst b19544dc8138123d29d25b79116fc4354dd465640408f86c08a4c7ad6b1d32d4
expect_hash userspace/root/usr/lib/firmware/amdgpu/gc_12_0_0_pfp.bin.zst 06b2ba632fa1878a16b78d9734dc8211020d257c140202462f764a156e98daef
expect_hash userspace/root/usr/lib/firmware/amdgpu/gc_12_0_0_rlc.bin.zst c652022ab773a626da090fe448f4abd1775fdd92899bb68b6775c87f619a14b9
expect_hash userspace/root/usr/lib/firmware/amdgpu/psp_14_0_2_sos.bin.zst e81164f81e763d8de70539e7fdcc8ea58aa9b025cf9c95361a4c63bc791177f4
expect_hash userspace/root/usr/lib/firmware/amdgpu/sdma_7_0_0.bin.zst 68add1d0817164f4fde6fd971270e4652814558545cb2400a946004126986576
expect_hash userspace/root/usr/lib/firmware/amdgpu/smu_14_0_2.bin.zst b0a03edf1c7e5a171fafe0710165b6ce90540450d1cf00132d8f0033b6ad2099
expect_hash userspace/root/usr/comma/bluetooth-radio 9f3902324c5a9a3a7291aa4041fdb676aa0a47af3d193d9d97fc819d970483fe
expect_hash userspace/root/usr/lib/systemd/system/carrot-bluetooth-radio.service 33fb8e29c1ebe0e8185fa9b928e5125748bb0d984b31b2615c6372b221dd9e2d
# China-build setup zipapp: patched mici setup (gh-proxy downloads, zh-CHS
# default) - rebuild with scripts/build_carrot_setup.py, then update this pin.
expect_hash userspace/root/usr/comma/setup 77d056bf755f3295afb53f46b7c5112951aa760227f30f72dc5f24962e0cf419
expect_hash userspace/root/etc/gitconfig 1ae5d95cfa104917f33ab249b47b8091ee76b9d646c14380f58d454def42bd11

SERVICE=userspace/root/usr/lib/systemd/system/carrot-bluetooth-radio.service
expect_line "$SERVICE" "ExecCondition=/usr/bin/test -f /data/bluetooth/ENABLED"
expect_line "$SERVICE" "ExecStart=/usr/bin/btattach -B /dev/ttyHS1 -P qca -S 115200"
expect_line "$SERVICE" "ExecStop=/usr/comma/bluetooth-radio stop"
expect_line "$SERVICE" "ExecStopPost=/usr/comma/bluetooth-radio cleanup"
expect_line "$SERVICE" "Restart=on-failure"

RADIO=userspace/root/usr/comma/bluetooth-radio
expect_line "$RADIO" 'fd = os.open("/dev/btpower", os.O_RDWR)'
expect_line "$RADIO" '  fd = os.open("/dev/ttyHS1", os.O_RDWR | os.O_NOCTTY)'
expect_line "$RADIO" "    bluetoothctl power on >/dev/null 2>&1 && break"

expect_line userspace/services.sh "systemctl enable carrot-bluetooth-radio.service"

GITCONFIG=userspace/root/etc/gitconfig
expect_line "$GITCONFIG" '[url "https://gh-proxy.com/https://github.com/"]'
expect_line "$GITCONFIG" '	insteadOf = https://github.com/'

version="$(tr -d '[:space:]' < "$DIR/VERSION")"
case "$version" in
  ''|*[!A-Za-z0-9._-]*)
    echo "VERSION contains an unsafe or empty value: '$version'" >&2
    exit 1 ;;
esac

echo "Carrot AGNOS inputs validated ($version, Bluetooth trial inputs pinned)."
