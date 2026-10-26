#!/usr/bin/env python3
"""Validate build inputs and resolved kernel options for the native radio trial."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ('BT', 'BT_BREDR', 'BT_LE', 'BT_RFCOMM', 'BT_HIDP', 'BT_HCIUART',
            'BT_HCIUART_H4', 'BT_HCIUART_QCA', 'MSM_BT_POWER', 'BTFM_SLIM',
            'BTFM_SLIM_WCN3990', 'UHID', 'HIDRAW', 'CRYPTO_ECDH', 'CRYPTO_CCM')


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--kernel-config', type=Path)
  args = parser.parse_args()
  source = ROOT / 'agnos-kernel-sdm845'
  config_path = args.kernel_config or source / 'arch/arm64/configs/tici_defconfig'
  config = config_path.read_text().splitlines()
  missing = [name for name in REQUIRED if f'CONFIG_{name}=y' not in config]
  assert not missing, f'Missing kernel features: {missing}'
  dts = (source / 'arch/arm64/boot/dts/qcom/sdm845.dtsi').read_text()
  assert 'hsuart0 = &qupv3_gps_uart;' in dts, 'GPS UART must retain ttyHS0'
  assert 'hsuart1 = &qupv3_se6_4uart;' in dts
  common = (source / 'arch/arm64/boot/dts/qcom/comma_common.dtsi').read_text()
  assert re.search(r'&qupv3_se6_4uart\s*\{\s*status = "ok";', common)
  for path in (ROOT / 'userspace/root/usr/lib/firmware/amdgpu').glob('*.zst'):
    data = path.read_bytes()
    assert data[:4] == b'\x28\xb5\x2f\xfd', path
    assert data[4] & 0xE0, f'Zstd frame content size absent: {path}'
  helper = (ROOT / 'userspace/root/usr/comma/bluetooth-radio').read_text()
  assert 'BLUETOOTH_STATE=/data/bluetooth' in helper
  assert '/dev/ttyHS1' in helper
  assert 'mount -o ro,nosuid,nodev,noexec' in helper
  service = (ROOT / 'userspace/root/usr/lib/systemd/system/carrot-bluetooth-radio.service').read_text()
  assert 'ExecCondition=/usr/bin/test -f /data/bluetooth/ENABLED' in service
  assert 'RequiresMountsFor=/data' in service
  print('Bluetooth kernel options, GPS UART, persistent state and AGNOS 19.8 firmware headers verified')


if __name__ == '__main__':
  main()
