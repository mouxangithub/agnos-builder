#!/usr/bin/env python3
"""Rebuild the checked-in Carrot setup zipapp with the China patches.

Inputs (all paths relative to the sunnypilot checkout, override with SP_OPENPILOT):
  - system/ui/mici_setup.py source tree is NOT used directly; the patched app
    is scripts/carrot_mici_setup.py (based on the upstream source).
  - selfdrive/ui/translations/app_zh-CHS.po  (Simplified Chinese strings)
  - selfdrive/ui/translations/languages.json (contains zh-CHS)
  - selfdrive/assets/fonts/NotoSansCJKsc-Regular.otf (CJK fallback font)

The zipapp is rewritten in place: every entry is preserved byte-for-byte
except the four above. Run from the agnos-builder repo root:

  python3 scripts/build_carrot_setup.py
"""
import os
import re
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SETUP_PATH = REPO_ROOT / "userspace" / "root" / "usr" / "comma" / "setup"
PATCHED_SETUP = REPO_ROOT / "scripts" / "carrot_mici_setup.py"
SP_OPENPILOT = Path(os.environ.get("SP_OPENPILOT", "E:/sp/openpilot"))

TRANSLATIONS_ZIP = "openpilot/selfdrive/ui/translations"
LANG_ENTRY = f"{TRANSLATIONS_ZIP}/app_zh-CHS.po"
LANGS_JSON_ENTRY = f"{TRANSLATIONS_ZIP}/languages.json"
FONT_ENTRY = "openpilot/selfdrive/assets/fonts/NotoSansCJKsc-Regular.otf"
MIICI_ENTRY = "openpilot/system/ui/mici_setup.py"

# Carrot-specific strings not present in the sunnypilot po file.
EXTRA_TRANSLATIONS: dict[str, str] = {
  "• It has not been tested by comma.": "• 未经 comma 官方测试。",
  "• It may not comply with safety standards.": "• 可能不符合安全标准。",
  "• It may damage your device and/or vehicle.": "• 可能损坏您的设备或车辆。",
}

TR_RE = re.compile(r'\btr\(\s*"((?:[^"\\]|\\.)*)"\s*\)')


def po_translations(po_text: str) -> dict[str, str]:
  """Minimal po parser matching openpilot's own loader (msgid -> msgstr)."""
  out: dict[str, str] = {}
  msgid: list[str] = []
  msgstr: list[str] = []
  field = None

  def flush():
    nonlocal msgid, msgstr, field
    if msgid and msgstr:
      out["".join(msgid)] = "".join(msgstr)
    msgid, msgstr, field = [], [], None

  for raw in po_text.splitlines():
    line = raw.strip()
    if not line:
      flush()
      continue
    if line.startswith("#"):
      continue
    if line.startswith("msgid "):
      flush()
      field = "id"
      msgid = [po_str(line[6:])]
    elif line.startswith("msgstr "):
      field = "str"
      msgstr = [po_str(line[7:])]
    elif line.startswith('"'):
      (msgid if field == "id" else msgstr).append(po_str(line))
  flush()
  return out


def po_str(s: str) -> str:
  s = s.strip()
  assert s.startswith('"') and s.endswith('"'), s
  return s[1:-1].replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")


def unescape_for_po(s: str) -> str:
  return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def main() -> int:
  if not SP_OPENPILOT.exists():
    print(f"sunnypilot checkout not found: {SP_OPENPILOT} (set SP_OPENPILOT)", file=sys.stderr)
    return 1

  patched_src = PATCHED_SETUP.read_text(encoding="utf-8")
  sp_po = (SP_OPENPILOT / "selfdrive/ui/translations/app_zh-CHS.po").read_text(encoding="utf-8")
  langs_json = (SP_OPENPILOT / "selfdrive/ui/translations/languages.json").read_text(encoding="utf-8")
  font_path = SP_OPENPILOT / "selfdrive/assets/fonts/NotoSansCJKsc-Regular.otf"
  if not font_path.exists():
    print(f"CJK font not found: {font_path}", file=sys.stderr)
    return 1

  translations = po_translations(sp_po)
  translations.update(EXTRA_TRANSLATIONS)

  # Coverage check: every tr() literal in the patched app must translate.
  # Manual unescape (unicode_escape would mangle non-ASCII like "•").
  def unescape(s: str) -> str:
    return s.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')

  missing = sorted({m for m in TR_RE.findall(patched_src) if unescape(m) not in translations})
  if missing:
    print("untranslated tr() strings:", file=sys.stderr)
    for m in missing:
      print(f'  "{m}"', file=sys.stderr)
    return 1

  with zipfile.ZipFile(SETUP_PATH) as zin:
    entries = {info.filename: zin.read(info.filename) for info in zin.infolist()}
    order = [info.filename for info in zin.infolist()]

  entries[MIICI_ENTRY] = patched_src.encode("utf-8")
  entries[LANG_ENTRY] = sp_po.encode("utf-8")
  entries[LANGS_JSON_ENTRY] = langs_json.encode("utf-8")
  entries[FONT_ENTRY] = font_path.read_bytes()
  if FONT_ENTRY not in order:
    order.append(FONT_ENTRY)

  tmp = SETUP_PATH.with_suffix(".tmp")
  with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for name in order:
      zout.writestr(name, entries[name])
  os.replace(tmp, SETUP_PATH)

  print(f"setup zipapp rebuilt: {SETUP_PATH}")
  print(f"  entries: {len(order)} (was {len(order) - 1}), tr() coverage: OK")
  return 0


if __name__ == "__main__":
  sys.exit(main())
