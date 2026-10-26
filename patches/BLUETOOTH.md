# Carrot AGNOS Bluetooth trial

This experiment is scoped to ajouatom/openpilot `carrot-cinque_v3`. It preserves
the pinned Cinque v3 model and runtime. No rollout to `carrot-wip` is intended.

Base: as of the `20.2-carrot-bt1` release, Carrot builder merged with
commaai/agnos-builder `5932dc2` (AGNOS 20.2; earlier builds were based on
AGNOS 19.8 via `bdbf1bc`). The kernel remains bumped from
`eccd146599f2e2f159d951092642689bede91632` with the existing USB-PD v2/v3
patches on both boot images and the existing C3 PCIe/NVMe patch only on C3.
AGNOS 19.7/19.8 updated AMD GPU firmware and added Zstandard frame content
sizes needed by newer tinygrad and disabled unused ALSA state restoration;
20.1/20.2 additionally removed rsyslog/logrotate and the bundled GCC, and
reworked the userspace tree into `userspace/root/`. AGNOS 20.2 removed bluez
and rfkill from the base image, so both are re-added here for the Bluetooth
radio.
Carrot's Adreno library selection is retained. Tinygrad itself is not updated.

Bluetooth port attribution:

- Kernel Bluetooth changes from firestar5683/agnos-kernel-sdm845
  `4ee6b71b8ab9a461248985470726f5917943bc91`, excluding its PCIe/NVMe changes.
- Radio startup adapted from firestar5683/agnos-builder
  `75f04905701f905bf43e60cbf4cfb713039e3f0d`.

Includes native WCN3990 UART enablement, firmware download/baudrate support,
classic HID, BLE HID, RFCOMM, secure pairing crypto, BlueZ and persistent bonds.
Bluetooth firmware is read from the existing active-slot firmware partition;
this release does not flash either Bluetooth firmware partition.
GPS keeps ttyHS0; Bluetooth uses ttyHS1. No USB Bluetooth dongle is required.
USB Bluetooth adapters, audio routing, phone application protocols, and mapping
remote buttons to vehicle commands are outside this bring-up trial.

The radio is opt-in. With the vehicle offroad, on the test device only:

```sh
sudo install -d -m 700 /data/bluetooth
sudo touch /data/bluetooth/ENABLED
sudo systemctl start carrot-bluetooth-radio
bluetoothctl show
bluetoothctl --timeout 15 scan on
```

Pair only the accessory chosen by the user using interactive `bluetoothctl`:
`agent KeyboardDisplay`, `default-agent`, `pair <address>`, `trust <address>`,
`connect <address>`. Do not auto-accept arbitrary incoming pairing requests.
Verify HID input with `evtest`, BLE with `btmgmt info`, then test reboot and
restart persistence. A phone's Bluetooth menu pairing does not implement a
phone-control application protocol.

To opt out, remove only `/data/bluetooth/ENABLED` and stop
`carrot-bluetooth-radio.service`; existing bonds remain saved.
Build success on both image variants is not C3/C3X hardware validation.
C4 hardware results and rollback information are recorded in the openpilot
experiment document after testing.
