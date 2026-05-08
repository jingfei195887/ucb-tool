from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, Protection
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.protection import SheetProtection

from ucb_tool import __version__ as TOOL_VERSION
from ucb_tool.core.ucb_bundle import UcbBundle, UcbInstance

_HEADERS = [
    "Field Path", "Offset (hex)", "Size", "Type", "Raw Bytes",
    "Value", "Decoded", "Enum Options", "Danger", "Help",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_meta(wb: Workbook, bundle: UcbBundle, source_hex: Path) -> None:
    ws = wb.create_sheet("_Meta", 0)
    rows = [
        ("tool_version", TOOL_VERSION),
        ("schema_version", "0.1"),
        ("chip", bundle.chip_id),
        ("family", bundle.family),
        ("source_hex", str(source_hex)),
        ("source_sha256", _sha256(source_hex)),
        ("exported_at", datetime.now(timezone.utc).isoformat()),
    ]
    for i, (k, v) in enumerate(rows, start=1):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=v)
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 80
    ws.protection = SheetProtection(sheet=True, formatCells=False)


def _write_summary(wb: Workbook, bundle: UcbBundle) -> None:
    ws = wb.create_sheet("Summary", 1)
    headers = ["UCB Name", "Address (ORIG)", "Size", "Confirmation", "CRC OK",
               "Danger Fields"]
    for c, h in enumerate(headers, start=1):
        ws.cell(row=1, column=c, value=h).font = Font(bold=True)
    r = 2
    for name, inst in bundle.instances.items():
        ws.cell(row=r, column=1, value=name)
        ws.cell(row=r, column=2, value=f"0x{inst.orig_addr:08X}")
        ws.cell(row=r, column=3, value=inst.schema.size)
        ws.cell(row=r, column=4, value="?")
        ws.cell(row=r, column=5, value="?")
        danger_fields = [
            f.path for f in inst.fields
            if f.schema.get("x-danger", "safe") != "safe"
        ]
        ws.cell(row=r, column=6, value=", ".join(danger_fields))
        r += 1
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 18
    ws.protection = SheetProtection(sheet=True, formatCells=False)


def _write_ucb_sheet(wb: Workbook, inst: UcbInstance) -> None:
    ws = wb.create_sheet(inst.schema.name)
    for c, h in enumerate(_HEADERS, start=1):
        ws.cell(row=1, column=c, value=h).font = Font(bold=True)
    r = 2
    for f in inst.fields:
        if f.schema.get("x-bitfield"):
            continue  # skip parent display row; child bits listed separately
        raw = bytes(inst.buf_orig[f.offset:f.offset + f.size])
        try:
            val: int | None = inst.get(f.path)
        except Exception:  # noqa: BLE001
            val = None
        ws.cell(row=r, column=1, value=f.path)
        ws.cell(row=r, column=2, value=f"0x{f.offset:04X}")
        ws.cell(row=r, column=3, value=f.size)
        ws.cell(row=r, column=4, value=f.schema.get("type", ""))
        ws.cell(row=r, column=5, value=raw.hex())
        render = f.schema.get("x-render")
        if val is not None and render == "hex":
            ws.cell(row=r, column=6, value=f"0x{val:X}")
        else:
            ws.cell(row=r, column=6, value=val)
        names = f.schema.get("x-enum-names") or {}
        if val is not None and names:
            ws.cell(row=r, column=7, value=names.get(str(val), ""))
        ws.cell(row=r, column=8, value=", ".join(f"{k}={v}" for k, v in names.items()))
        ws.cell(row=r, column=9, value=f.danger)
        ws.cell(row=r, column=10, value=f.schema.get("x-help", ""))
        r += 1
    for col in range(1, len(_HEADERS) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 18
    ws.protection = SheetProtection(sheet=True, formatCells=False)
    # Unlock the Value column so users can edit it in Excel.
    for row in ws.iter_rows(min_row=2, min_col=6, max_col=6):
        for cell in row:
            cell.protection = Protection(locked=False)


def export_to_xlsx(bundle: UcbBundle, out_path: str | Path, source_hex: Path) -> None:
    wb = Workbook()
    # Remove the default 'Sheet' that openpyxl creates.
    default_name = wb.active.title if wb.active else None
    if default_name and default_name in wb.sheetnames:
        del wb[default_name]
    _write_meta(wb, bundle, source_hex)
    _write_summary(wb, bundle)
    for inst in bundle.instances.values():
        _write_ucb_sheet(wb, inst)
    wb.save(str(out_path))
