# AGNOS 19.8 camera / Bluetooth diagnostic trial 2

This release is scoped to openpilot `carrot-camera-bt2`, created from current
`carrot-wip` on 2026-09-24 at the user's request. Do not select this OS in
`carrot-wip` until hardware results are reviewed.

Base: builder f5b3f77e59f1917f95e0752630ca08050463eede (19.8-carrot-bt1),
kernel eccd146599f2e2f159d951092642689bede91632. Existing BT, USB-PD,
C3 PCIe patches, GPU firmware, radio startup and scheduling are retained.

To avoid changes from unpinned apt repositories, the system image is derived
from the immutable bt1 release asset, verifying its compressed, sparse and raw
SHA256 values. Only /VERSION and /BUILD are replaced. Target libraries, services
and firmware stay byte-identical to that base. Host build utilities do not
become part of the target image. Filesystem metadata will also change as the
two version files are rewritten.

The extra patch routes raw Qualcomm ACL handle/flags 0x2edc through
`hci_recv_diag`, preserving monitor visibility, instead of treating it as an
ordinary connection handle 3804. All other ACL traffic follows the original
path. This follows `qca_recv_acl_data` in upstream Linux v6.12:
https://github.com/torvalds/linux/blob/v6.12/drivers/bluetooth/hci_qca.c

The target 4.9 kernel already exports this API. The original upstream GPL-2.0
driver license applies. This backport changes neither pairing nor HID input.

Live C4 capture before this change found 37 such packets in 12 seconds. This
establishes misclassification, not the cause of the occasional 96-102 ms
camera SOF-path gaps. Diagnostic packets still consume UART/workqueue time.
Compile success is not C3/C4 hardware or camera validation.

This trial also adds two disabled-by-default tracepoints under `camera`:
`cam_csid_sof_history` reads the previous SOF register and verifies the current
register did not change during the sample, and `cam_ife_irq_payload` exposes
the IRQ-captured timestamp/status at bottom-half entry. Additional MMIO reads
occur only while the history tracepoint is enabled. The existing SOF timestamp,
frame/request acceptance, error recovery and scheduling remain unchanged.

Validate previous-register semantics on normal frames first. Discard samples
whose current and verification timestamps differ; never interpret a torn
sample as a lost physical frame. A previous hardware timestamp between two
observed callbacks can establish an intervening hardware SOF. A missing
intermediate timestamp alone does not diagnose sensor, FSIN or CSI hardware.

Before a vehicle trial record build/boot slot, BT connection and model runtime;
afterwards verify diagnostic monitor classification, HID, reconnect, camera
SOF/receive timing, model gaps and pose validity. Preserve pairing state.
Retain the original OTA slot for rollback. Do not weaken validity thresholds.
