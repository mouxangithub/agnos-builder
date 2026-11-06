#!/usr/bin/env python3
"""Check the QCA diagnostic backport against the target kernel API."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1] / 'agnos-kernel-sdm845'
qca = (root / 'drivers/bluetooth/hci_qca.c').read_text()
core = (root / 'net/bluetooth/hci_core.c').read_text()
header = (root / 'include/net/bluetooth/hci_core.h').read_text()
assert '#include <asm/unaligned.h>' in qca
assert re.search(r'H4_RECV_ACL,\s*\.recv = qca_recv_acl_data', qca)
assert re.search(r'get_unaligned_le16\(skb->data\) == 0x2edc\)\s*return hci_recv_diag\(hdev, skb\);\s*return hci_recv_frame\(hdev, skb\);', qca)
assert 'int hci_recv_diag(struct hci_dev *hdev, struct sk_buff *skb);' in header
assert 'EXPORT_SYMBOL(hci_recv_diag);' in core
assert 'hci_send_to_monitor(hdev, skb);' in core
print('QCA diagnostic routing, ordinary ACL fallback and target diagnostic API verified')
