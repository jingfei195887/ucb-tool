#!/usr/bin/env python3
"""Generate UCB JSON Schema files from extracted Infineon AURIX UM text.

Input: /tmp/ucb-extract/{tc4dx,tc48x,tc4zx}/UCB{0,1}_{NN}.txt — one text
blob per UCB slot, captured from the 49.4.x / 44.4.x "Firmware" chapter of
the TC4Dx / TC48x / TC4Zx user manuals.

Output: src/ucb_tool/schemas/{tc4dx,tc48x,tc4zx}/<NAME>.json — one JSON
Schema per UCB slot, keyed by the UCB's logical name (BMHD0, USERCFG,
SWAP, HSM, PFLASH_OTP1_ORIG, …) with fallback to UCBx_NN when the long
name doesn't map to a canonical identifier.

Usage:
    python tools/gen_ucb_schemas.py            # regen everything
    python tools/gen_ucb_schemas.py --chip tc4dx

The parser is deliberately best-effort: the PDF extract is noisy (wrapped
names, stray page headers, table-continuation markers) and we flag anything
uncertain with ``x-help: "TBD: verify..."`` and record TBD notes in
``x-ucb-meta.tbd`` rather than skip.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- Constants ---------------------------------------------------------------

UCB0_BASE = 0xAE400000
UCB1_BASE = 0xAEC00000

STRIDE = {"tc4dx": 0x800, "tc48x": 0x100, "tc4zx": 0x100}
FAMILY = {"tc4dx": "TC4Dx", "tc48x": "TC48x", "tc4zx": "TC4Zx"}

EXTRACT_ROOT = Path("/tmp/ucb-extract")
SCHEMAS_ROOT = (
    Path(__file__).resolve().parent.parent / "src" / "ucb_tool" / "schemas"
)

CHAPTER = {"tc4dx": "49", "tc48x": "44", "tc4zx": "44"}
UM_VERSION = {"tc4dx": "v1.1 (2025-04-22)",
              "tc48x": "v0.9 (2025-03-25)",
              "tc4zx": "v0.9 (2025-03-25)"}


# --- Data classes ------------------------------------------------------------

@dataclass
class RawRegister:
    """One row from the UCB register-overview table."""
    short_name: str
    long_name: str
    abs_offset: int
    rel_offset: int
    array_count: int | None = None
    array_stride: int | None = None
    field_rows: list[FieldRow] = field(default_factory=list)
    is_simple_32: bool = True
    enum_names: dict[int, str] = field(default_factory=dict)


@dataclass
class FieldRow:
    """A field row from the per-register 'Field Bits Type Description' table."""
    name: str
    hi: int
    lo: int
    access: str
    desc: str


@dataclass
class SlotSpec:
    chip: str
    region: str
    slot: int
    slot_base_abs: int
    stride: int
    regs: list[RawRegister] = field(default_factory=list)
    tbd_notes: list[str] = field(default_factory=list)


# --- Text preprocessing ------------------------------------------------------

_SLOT_RE = re.compile(r"UCB(\d)_(\d{2})", re.I)
_PAGE_RE = re.compile(r"^----- PDF page \d+ -----\s*$")
_FOOTER_RES = (
    re.compile(r"^restricted - NDA required!$"),
    re.compile(r"^AURIX™ +TC4[A-Za-z0-9]+ user manual$"),
    re.compile(r"^[0-9]+\s+Firmware$"),
    re.compile(r"^Reference manual \d+ v[\d.]+$"),
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    re.compile(r"^D R A F T$"),
)


def _strip_chrome(text: str) -> str:
    """Drop page-break lines and boilerplate footer lines."""
    out: list[str] = []
    for ln in text.splitlines():
        if _PAGE_RE.match(ln):
            continue
        s = ln.strip()
        if any(r.match(s) for r in _FOOTER_RES):
            continue
        out.append(ln.rstrip())
    return "\n".join(out)


# --- Register-overview parsing ----------------------------------------------

def _extract_overview_block(text: str, region: str, slot: int) -> str:
    """Return text from 'Register overview - UCBx_NN' until the next section.

    The overview ends at the first numbered heading that introduces a
    per-register detail section, e.g. "44.4.3.5.1 SWAP_ORIG_SAL x", or at
    the next "Register overview - UCBx_NN" for a different slot.
    """

    needle = f"Register overview - UCB{region[-1]}_{slot:02d}"
    idx = text.find(needle)
    if idx == -1:
        return ""
    tail = text[idx:]
    end = len(tail)
    # Any line that starts with digits.dots.digits + space is a heading.
    # In Infineon UM, "NN.N.N.N.N <title>" introduces the first detail
    # subsection (depth ≥ 4 dots).
    m = re.search(
        r"\n\d+\.\d+\.\d+\.\d+(?:\.\d+)?\s+[A-Za-z]",
        tail[len(needle):],
    )
    if m:
        end = m.start() + len(needle) + 1
    # Also clip at the NEXT "Register overview -" heading.
    m2 = re.search(r"\n[0-9.]+\s+Register overview - UCB",
                   tail[len(needle):])
    if m2 and (m2.start() + len(needle) + 1) < end:
        end = m2.start() + len(needle) + 1
    return tail[:end]


def _parse_overview_rows(block: str, region: str, slot: int,
                         stride: int) -> list[RawRegister]:
    """Parse the table rows into RawRegister records.

    Handles wrapped short names ("UCB0_09_BMI_BMHD\\nID") and wrapped long
    names. The end-of-row anchor is the hex offset token, optionally
    followed by a page number.
    """

    lines = block.splitlines()
    # Drop lines we don't want to consume: table title, header row, etc.
    rows: list[RawRegister] = []
    buf: list[str] = []

    def flush(buf_lines: list[str]) -> None:
        if not buf_lines:
            return
        joined = " ".join(s.strip() for s in buf_lines if s.strip())
        # The offset is the LAST hex token on the row, optionally with
        # "+<idx>*YYH?" array-stride suffix where idx is "x" or "n", then
        # optional page number.
        m = None
        for mm in re.finditer(
            r"([0-9A-Fa-f]{1,6})H(?:\+[xn]\*([0-9A-Fa-f]+)H?)?",
            joined,
        ):
            tail = joined[mm.end():].strip()
            if not tail or re.match(r"^\d+$", tail):
                m = mm  # keep the latest candidate that is at end-of-line
        if m is None:
            return
        offset_token = m.group(0)
        array_stride_token = m.group(2)
        # Everything before the offset is (short + long).
        prefix = joined[:m.start()].strip()
        short, long_name = _split_short_long(prefix)
        if short is None:
            return
        # Parse offset.
        if array_stride_token is not None:
            abs_off = int(m.group(1), 16)
            array_stride = int(array_stride_token, 16)
            cnt_m = re.search(r"\([xn]=0[-–]([0-9]+)\)", joined)
            array_count = int(cnt_m.group(1)) + 1 if cnt_m else None
        else:
            abs_off = int(offset_token.rstrip("H"), 16)
            array_stride = None
            array_count = None
        rel_off = abs_off - slot * stride
        rows.append(RawRegister(
            short_name=short,
            long_name=long_name,
            abs_offset=abs_off,
            rel_offset=rel_off,
            array_count=array_count,
            array_stride=array_stride,
        ))

    # A line that is ONLY a hex-offset (optionally with page number) is a
    # definite row terminator. A line that merely ends in "...XXXXH" might
    # contain the token inside prose ("= B359H" etc.).
    LINE_IS_OFFSET_ONLY = re.compile(
        r"^[0-9A-Fa-f]{1,6}H(?:\+[xn]\*[0-9A-Fa-f]+H?)?\s*(?:\d+)?\s*$"
    )
    # A normal row ends on its last field with "... XXXXH [page#]?" and a
    # register short name earlier on the same line.
    LINE_ENDS_WITH_OFFSET = re.compile(
        r"\s[0-9A-Fa-f]{1,6}H(?:\+[xn]\*[0-9A-Fa-f]+H?)?\s*(?:\d+)?\s*$"
    )
    # First line of a row starts with a short-name identifier. We accept
    # either "SHORT<space>..." or just "SHORT$" (wrapped short name).
    SHORT_NAME_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\s|$)")
    EQUALS_HEX_ONLY = re.compile(r"=\s*[0-9A-Fa-f]+H\s*$")

    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if re.match(r"^\d+(?:\.\d+)+\s+", s):  # section heading
            continue
        if s.startswith("Table ") or s.startswith("(table continues"):
            continue
        if s.startswith("Register overview"):
            continue
        if s.startswith("Short name"):
            continue
        if s in ("address", "Offset", "See", "Offset address", "Long name"):
            continue
        buf.append(s)
        # Definite terminators:
        if LINE_IS_OFFSET_ONLY.match(s):
            flush(buf)
            buf = []
            continue
        # Normal row: line contains a short name early AND ends with offset.
        if (SHORT_NAME_TOKEN.match(buf[0] if buf else "") and
                LINE_ENDS_WITH_OFFSET.search(s) and
                not EQUALS_HEX_ONLY.search(s)):
            flush(buf)
            buf = []
    flush(buf)
    return rows


def _split_short_long(prefix: str) -> tuple[str | None, str]:
    """Split "short long-text" — stitching wrapped short-name fragments."""

    toks = prefix.split()
    if not toks:
        return None, ""
    short = toks[0]
    i = 1
    # Stitch wrapped suffixes.
    while i < len(toks) and _looks_like_suffix(short, toks[i]):
        short = short + toks[i]
        i += 1
    long_name = " ".join(toks[i:]).strip()
    if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", short):
        return None, long_name
    return short, long_name


def _looks_like_suffix(head: str, nxt: str) -> bool:
    """Best-effort: is `nxt` a continuation of an all-caps short name?

    Accepts short lowercase-'x'/-'n' subscript tokens like 'x', 'n', 'Rx',
    'Bn' which frequently appear when PDF extraction breaks an identifier
    just before an indexing subscript.
    """
    if len(nxt) > 10:
        return False
    if not re.match(r"^[A-Za-z0-9_]+$", nxt):
        return False
    if not re.match(r"^[A-Z0-9_]+$", head):
        return False
    # Subscript-only continuations: "x", "n", "Rx", "Bn"
    if nxt in ("x", "n") or re.fullmatch(r"[A-Z][xn]", nxt):
        return True
    known_wraps = {"ID", "TION", "TION_COPY", "SEx", "DATA", "CODE",
                   "ORDx", "WORDx"}
    if nxt in known_wraps:
        return True
    stubs = ("CONFIRMA", "BMHD", "PRPROC", "CRCSE", "MARKE",
             "STATU", "KEYID", "LENGTH", "TYPE", "DATA1_W",
             "DATA0_W", "RTC_DA", "DRPROC", "PFPROC")
    if any(head.endswith(s) for s in stubs):
        return True
    combined = head + nxt
    return combined.count("_") > head.count("_")


# --- Per-register detail parsing ---------------------------------------------

def _extract_detail_block(text: str, short_full_candidates: list[str]) -> str:
    """Extract the detail section for a register.

    Tries each candidate short-name (e.g. "SAL", "UCB0_09_SAL") and returns
    the text from "SHORT Offset address: XXXXH" through the start of the
    next register detail section.
    """

    for short in short_full_candidates:
        # Find "SHORT [(...)]  Offset address:" with optional newline between.
        pattern = re.compile(
            rf"(?:^|\n){re.escape(short)}(?:\s*\([^)\n]*\))?\s*(?:\n\s*)?Offset\s+address:"
        )
        m = pattern.search(text)
        if not m:
            continue
        start = m.start()
        # end at next detail section (any short name followed by "Offset address:")
        rest = text[m.end():]
        m2 = re.search(
            r"\n[A-Z][A-Z0-9_]*(?:\s*\([^)\n]*\))?\s*(?:\n\s*)?Offset\s+address:",
            rest,
        )
        end = m.end() + m2.start() if m2 else len(text)
        # Also stop at "Register overview -" heading for next slot.
        m3 = re.search(r"\n[0-9.]+\s+Register overview - UCB", rest)
        if m3 and (m.end() + m3.start()) < end:
            end = m.end() + m3.start()
        return text[start:end]
    return ""


_FIELD_ROW = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+"
    r"(?P<hi>\d+):(?P<lo>\d+)\s+"
    r"(?P<access>[rwh]+)"
    r"(?:\s+(?P<desc>.*))?$"
)


def _parse_field_rows(block: str) -> tuple[list[FieldRow], dict[int, str]]:
    """Parse 'Field Bits Type Description' table. Return (rows, enum_map).

    Enum map keys are integer values; values are short labels.
    """

    lines = block.splitlines()
    # Find the table header
    start = -1
    for i, ln in enumerate(lines):
        if ln.strip().startswith("Field Bits Type Description"):
            start = i
            break
    if start == -1:
        return [], {}

    field_rows: list[FieldRow] = []
    enum_names: dict[int, str] = {}
    cur: FieldRow | None = None
    wrapped_name: str | None = None

    def commit() -> None:
        nonlocal cur
        if cur is not None:
            cur.desc = cur.desc.strip()
            field_rows.append(cur)
            cur = None

    for ln in lines[start + 1:]:
        raw = ln.strip()
        if not raw:
            continue
        # Second "Field Bits Type Description" = a second table within this
        # block — stop here, we only want the first register's table.
        if raw.startswith("Field Bits Type Description"):
            break
        if "Offset address:" in raw and raw.split()[0] != cur.name if cur else False:
            break
        if re.match(r"^\d+(?:\.\d+){2,}\s+[A-Z]", raw):
            break
        if raw.startswith("Register overview"):
            break
        # Stop if we hit another register detail section "(continued)" marker.
        if raw.startswith("("):
            continue

        m = _FIELD_ROW.match(raw)
        if m:
            commit()
            name = m.group("name")
            if wrapped_name is not None:
                name = wrapped_name + name
                wrapped_name = None
            cur = FieldRow(
                name=name,
                hi=int(m.group("hi")),
                lo=int(m.group("lo")),
                access=m.group("access"),
                desc=m.group("desc") or "",
            )
            continue

        em = _parse_enum_value_line(raw)
        if em is not None:
            val, label = em
            enum_names[val] = label
            if cur is not None:
                cur.desc += f" {raw}"
            continue

        if cur is None:
            # Wrapped field name
            if re.match(r"^[A-Z][A-Z0-9_]+$", raw) and len(raw) <= 20:
                wrapped_name = (wrapped_name or "") + raw
            continue

        # Continuation of current.desc
        cur.desc += " " + raw

    commit()
    return field_rows, enum_names


_ENUM_VALUE = re.compile(
    r"""^(?:
           (?P<hex>0x[0-9A-Fa-f]+)
         | (?P<bin>0b[01]+)
         | (?P<aurixhex>[0-9A-F]+H)
         | (?P<aurixbin>[01]+B)
         | (?P<dec>\d+)
        )\s*
        (?:=\s*["']?(?P<label>[A-Za-z_][A-Za-z0-9_]*)["']?\s*[-–]?\s*|[-–]\s*)
        (?P<desc>.+)$""",
    re.VERBOSE,
)


def _parse_enum_value_line(s: str) -> tuple[int, str] | None:
    m = _ENUM_VALUE.match(s)
    if m:
        if m.group("hex"):
            val = int(m.group("hex"), 16)
        elif m.group("bin"):
            val = int(m.group("bin"), 2)
        elif m.group("aurixhex"):
            val = int(m.group("aurixhex").rstrip("H"), 16)
        elif m.group("aurixbin"):
            val = int(m.group("aurixbin").rstrip("B"), 2)
        else:
            val = int(m.group("dec"))
        label = (m.group("label") or "").strip()
        if not label:
            # fallback: first word of desc
            label = m.group("desc").split()[0].strip("\"'")
        return val, label[:40]
    # Shape "B359H BMHDID: ..."
    m2 = re.match(r"^([0-9A-F]+)H\s+([A-Z][A-Z0-9_]*)[:\s].*$", s)
    if m2:
        return int(m2.group(1), 16), m2.group(2)
    return None


# --- SlotSpec construction ---------------------------------------------------

def _strip_slot_prefix(short: str, region: str, slot: int) -> str:
    pfx = f"UCB{region[-1]}_{slot:02d}_"
    if short.startswith(pfx):
        return short[len(pfx):]
    return short


def parse_slot_file(path: Path, chip: str) -> SlotSpec:
    m = _SLOT_RE.search(path.stem)
    if not m:
        raise ValueError(f"cannot identify slot from filename: {path}")
    region = f"UCB{m.group(1)}"
    slot = int(m.group(2))
    stride = STRIDE[chip]
    slot_base = (UCB0_BASE if region == "UCB0" else UCB1_BASE) + slot * stride

    text = _strip_chrome(path.read_text(encoding="utf-8", errors="replace"))
    spec = SlotSpec(chip=chip, region=region, slot=slot,
                    slot_base_abs=slot_base, stride=stride)

    overview = _extract_overview_block(text, region, slot)
    if not overview:
        spec.tbd_notes.append(f"no register overview for {region}_{slot:02d}")
        return spec

    rows = _parse_overview_rows(overview, region, slot, stride)
    # Deduplicate by (short_name, abs_offset) — extraction can repeat rows.
    seen: set[tuple[str, int]] = set()
    unique: list[RawRegister] = []
    for r in rows:
        key = (r.short_name, r.abs_offset)
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    rows = unique

    # Validate rel_offsets fit inside the slot.
    valid: list[RawRegister] = []
    for r in rows:
        r.short_name = _strip_slot_prefix(r.short_name, region, slot)
        if r.rel_offset < 0 or r.rel_offset >= stride:
            # Offset belongs to another slot's table — likely overview
            # bled into the next section.
            spec.tbd_notes.append(
                f"{r.short_name} offset {r.abs_offset:#x} outside slot "
                f"[{slot * stride:#x}..{(slot + 1) * stride:#x}); skipped"
            )
            continue
        valid.append(r)
    rows = valid

    # Per-register detail blocks.
    for r in rows:
        cands = [r.short_name, f"UCB{region[-1]}_{slot:02d}_{r.short_name}"]
        db = _extract_detail_block(text, cands)
        if not db:
            r.is_simple_32 = True
            continue
        # If the overview row said "+x*N" but we didn't infer a count, try
        # the detail header: "(x=0-N)" or "(n=0-N)".
        if r.array_stride and not r.array_count:
            mc = re.search(r"\([xn]=0[-–]([0-9]+)\)", db)
            if mc:
                r.array_count = int(mc.group(1)) + 1
        frs, enums = _parse_field_rows(db)
        r.field_rows = frs
        r.enum_names = enums
        if len(frs) == 1 and frs[0].hi == 31 and frs[0].lo == 0:
            r.is_simple_32 = True
        elif len(frs) >= 2:
            r.is_simple_32 = False
        else:
            r.is_simple_32 = True

    spec.regs = rows
    return spec


# --- Danger / computed classification ---------------------------------------

def _danger_for(short: str, long_name: str) -> str:
    s = f"{short} {long_name}".upper()
    if "ROLLBACK" in s:
        return "irreversible"
    if any(tok in s for tok in ("PASSWORD", "PW0", "PW1", "PW2", "PW3",
                                 "PW4", "PW5", "PW6", "PW7", " PW ",
                                 "PROCON", "OTP", "CONFIRM", "KEY", "HSM")):
        return "lock"
    if any(tok in s for tok in ("STAD", "BMI", "HWCFG", "BOOT",
                                 "DBG", " LOCK", "HSM_EN", "RESET", "LBIST")):
        return "brick"
    return "safe"


def _computed_for(short: str, long_name: str,
                  size: int) -> tuple[str | None, bool]:
    up = short.upper()
    if "CRC" in up:
        return "crc32-aurix", True
    if up in ("CONFIRMATION", "CONFIRMATION_COPY") and size == 8:
        return "confirmation", False
    return None, False


# --- Canonical UCB naming ----------------------------------------------------

def _canonical_ucb_name(regs: list[RawRegister], region: str,
                        slot: int) -> str:
    """Derive a stable UCB name from the long-name prefixes.

    We use the first 1-2 registers' long_name to figure out the family of
    the slot (BMHD0/1/2/3, SWAP, USERCFG, HSM, …). When ambiguous we fall
    back to the positional UCBx_NN name.
    """

    if not regs:
        return f"UCB{region[-1]}_{slot:02d}"

    longs_upper = " ".join(r.long_name.upper() for r in regs)
    shorts_upper = " ".join(r.short_name.upper() for r in regs)
    hay = f"{longs_upper} {shorts_upper}"

    # BMHD — use the number from "BMHD0", "BMHD1", etc.
    mbm = re.search(r"BMHD([0-3])", hay)
    if mbm and ("BMHD" in shorts_upper or "BMHD" in longs_upper):
        n = mbm.group(1)
        if region == "UCB1":
            return f"BMHD{n}_CS"
        return f"BMHD{n}"

    # SWAP
    if "SWAP" in hay:
        tag = "CS" if region == "UCB1" else "RTC"
        if "COPY" in hay and "ORIG" not in hay:
            return f"SWAP_COPY_{tag}"
        if "ORIG" in hay and "COPY" not in hay:
            return f"SWAP_ORIG_{tag}"
        # Default: name by slot position.
        return f"SWAP_{tag}_SLOT{slot:02d}"

    # USERCFG / user-cfg / user config
    if any(tok in hay for tok in ("USERCFG", "USER CFG",
                                   "USER CONFIG", "USER SELECTION",
                                   "LOCKSTEP", "HOSTRAMAIN", "PMS_PAD")):
        tag = "CS" if region == "UCB1" else "RTC"
        if "COPY" in hay and "ORIG" not in hay:
            return f"USERCFG_COPY_{tag}"
        # A second USERCFG slot is typically the COPY; use slot parity as hint.
        return f"USERCFG_ORIG_{tag}" \
            if slot in (17, 2) or "ORIG" in hay else f"USERCFG_{tag}_SLOT{slot:02d}"

    # HSM firmware / keys
    if "HSM" in hay:
        if "FIRMWARE" in hay or "FW" in shorts_upper:
            return "HSM_FW"
        if "KEY" in hay:
            return "HSM_KEYS"
        return f"HSM_{region}_{slot:02d}"

    # PFLASH OTP
    mp = re.search(r"PFLASH_OTP(\d)(?:_(ORIG|COPY))?", hay)
    if mp:
        base = f"PFLASH_OTP{mp.group(1)}"
        if mp.group(2):
            return f"{base}_{mp.group(2)}"
        return base

    # DFLASH OTP
    md = re.search(r"DFLASH_OTP(\d)(?:_(ORIG|COPY))?", hay)
    if md:
        base = f"DFLASH_OTP{md.group(1)}"
        if md.group(2):
            return f"{base}_{md.group(2)}"
        return base

    # PROCON
    if "PROCON" in hay:
        if "COPY" in hay and "ORIG" not in hay:
            return f"PROCON_COPY_{region}_{slot:02d}"
        if "ORIG" in hay and "COPY" not in hay:
            return f"PROCON_ORIG_{region}_{slot:02d}"
        return f"PROCON_{region}_{slot:02d}"

    # Debug / DBG
    if "DBG" in hay or "DEBUG IF" in hay:
        if "COPY" in hay:
            return "DBG_COPY"
        if "ORIG" in hay:
            return "DBG_ORIG"

    # CHIPID / product info
    if "CHIPID" in hay or "PRODUCT_NAME" in hay:
        return f"CHIPINFO_{region}_{slot:02d}"

    # Fallback: positional
    return f"UCB{region[-1]}_{slot:02d}"


def _is_reserved_long(long_name: str) -> bool:
    s = long_name.strip().lower()
    return s.startswith("reserved") or s == ""


# --- Emission ----------------------------------------------------------------

def _unique_name(name: str, used: set[str]) -> str:
    cand = name
    i = 1
    while cand in used:
        i += 1
        cand = f"{name}_{i}"
    used.add(cand)
    return cand


def _field_help_text(r: RawRegister) -> str:
    parts = r.long_name.split(" - ", 1)
    return parts[1].strip() if len(parts) == 2 else r.long_name.strip()


def _register_size(r: RawRegister) -> int:
    """Pick a byte size for a register from its field rows (default 4)."""
    if not r.field_rows:
        # CONFIRMATION magic is 8 bytes, everything else default 4
        if r.short_name.upper() in ("CONFIRMATION", "CONFIRMATION_COPY"):
            return 8
        return 4
    max_hi = max(fr.hi for fr in r.field_rows)
    if max_hi >= 32:
        return 8
    if max_hi >= 16:
        return 4
    if max_hi >= 8:
        return 2
    return 1


def _emit_properties(spec: SlotSpec, tbd_notes: list[str]) -> dict[str, dict[str, Any]]:
    props: dict[str, dict[str, Any]] = {}
    used: set[str] = set()
    used_offsets: set[int] = set()
    ucb_size = spec.stride

    for r in spec.regs:
        if _is_reserved_long(r.long_name):
            continue
        for name, prop in _emit_single(r, used, tbd_notes, ucb_size):
            if prop["x-offset"] in used_offsets:
                # silently drop exact duplicates
                continue
            used_offsets.add(int(prop["x-offset"]))
            props[name] = prop
    return props


def _emit_single(r: RawRegister, used_names: set[str], tbd: list[str],
                 ucb_size: int) -> list[tuple[str, dict[str, Any]]]:
    """Emit one or more properties for one RawRegister."""

    help_text = _field_help_text(r)
    danger = _danger_for(r.short_name, r.long_name)

    # Array expansion
    if r.array_count and r.array_stride:
        item_size = 4  # all AURIX UCB array items are 32-bit words
        # Interleaved-struct case (SWAP entries: SAL/STATUS/MARKER/CRCSE
        # stride 16B, each field 4B). Emit individual fields one per slot
        # so offsets stay accurate and xlsx round-trip works.
        if r.array_stride > item_size:
            out: list[tuple[str, dict[str, Any]]] = []
            base = re.sub(r"x$", "", r.short_name)
            for i in range(r.array_count):
                off = r.rel_offset + i * r.array_stride
                if off + item_size > ucb_size:
                    tbd.append(
                        f"{r.short_name}[{i}] @ {off:#x} overflows UCB; "
                        "truncated"
                    )
                    break
                nm = _unique_name(f"{base}_{i}", used_names)
                sub = {
                    "type": "integer",
                    "minimum": 0, "maximum": 4294967295,
                    "x-offset": off, "x-size": item_size,
                    "x-endian": "little",
                    "x-render": "password" if danger == "lock" else "hex",
                    "x-help": f"{help_text} (entry {i})",
                }
                if danger != "safe":
                    sub["x-danger"] = danger
                out.append((nm, sub))
            return out

        # Contiguous array: item_size == array_stride.
        total = r.array_count * item_size
        if r.rel_offset + total > ucb_size:
            tbd.append(
                f"{r.short_name}[{r.array_count}] overflows UCB "
                f"({r.rel_offset:#x}+{total:#x}>{ucb_size:#x})"
            )
            r.array_count = max(0, (ucb_size - r.rel_offset) // item_size)
            total = r.array_count * item_size
            if total == 0:
                return []
        name = _unique_name(re.sub(r"x$", "", r.short_name), used_names)
        prop: dict[str, Any] = {
            "type": "array",
            "items": {"type": "integer", "minimum": 0, "maximum": 4294967295},
            "minItems": r.array_count, "maxItems": r.array_count,
            "x-offset": r.rel_offset, "x-size": total, "x-endian": "little",
            "x-render": "password" if danger == "lock" else "hex",
            "x-help": help_text,
        }
        if danger != "safe":
            prop["x-danger"] = danger
        return [(name, prop)]

    size = _register_size(r)
    if r.rel_offset + size > ucb_size:
        tbd.append(
            f"{r.short_name} rel_offset {r.rel_offset:#x}+{size} > "
            f"{ucb_size:#x}; clamping"
        )
        size = max(1, ucb_size - r.rel_offset)

    name = _unique_name(r.short_name, used_names)
    x_comp, ro = _computed_for(r.short_name, r.long_name, size)

    # Bitfield form?
    if not r.is_simple_32 and r.field_rows:
        total_bits = size * 8
        sub_props: dict[str, dict[str, Any]] = {}
        used_child: set[str] = set()
        for fr in r.field_rows:
            if fr.lo > fr.hi or fr.hi >= total_bits:
                tbd.append(
                    f"{r.short_name}.{fr.name}: bits {fr.hi}:{fr.lo} out of "
                    f"{total_bits}-bit reg; dropped"
                )
                continue
            c_name = _unique_name(fr.name, used_child)
            width = fr.hi - fr.lo + 1
            sub: dict[str, Any] = {
                "type": "boolean" if width == 1 else "integer",
                "x-bits": [fr.lo, fr.hi],
                "title": fr.desc.split("  ")[0].strip() or fr.name,
            }
            # Attach enum labels (for UI) but NOT a hard enum constraint.
            if r.enum_names:
                fit = {v: lbl for v, lbl in r.enum_names.items()
                       if 0 <= v < (1 << width)}
                if fit and len(fit) <= 16 and width <= 8:
                    vals = sorted(fit.keys())
                    sub["x-enum-names"] = {str(v): fit[v] for v in vals}
            sub_dan = _danger_for(fr.name, fr.desc)
            if sub_dan != "safe":
                sub["x-danger"] = sub_dan
            sub_props[c_name] = sub

        if sub_props:
            prop_obj: dict[str, Any] = {
                "type": "object",
                "x-offset": r.rel_offset, "x-size": size, "x-endian": "little",
                "x-bitfield": True,
                "title": help_text,
                "properties": sub_props,
            }
            return [(name, prop_obj)]
        # fall through to simple

    # Simple integer.
    prop_simple: dict[str, Any] = {
        "type": "integer",
        "minimum": 0, "maximum": (1 << (size * 8)) - 1,
        "x-offset": r.rel_offset, "x-size": size, "x-endian": "little",
        "x-render": "password" if danger == "lock" else "hex",
        "x-help": help_text,
    }
    if danger != "safe":
        prop_simple["x-danger"] = danger
    if x_comp:
        prop_simple["x-computed"] = x_comp
        prop_simple.pop("x-render", None)
        if ro:
            prop_simple["readOnly"] = True
    elif r.enum_names and size <= 4:
        # Record enum labels for UI rendering but do NOT add a hard
        # JSON-Schema ``enum`` constraint — UM enum lists are typically
        # "valid values + else invalid", not closed sets, and virgin
        # (0xFF-filled) UCB data would fail validation otherwise.
        vals = sorted(r.enum_names.keys())
        fit = [v for v in vals if 0 <= v < (1 << (size * 8))]
        if fit and len(fit) <= 16:
            prop_simple["x-enum-names"] = {str(v): r.enum_names[v] for v in fit}

    return [(name, prop_simple)]


def build_schema(spec: SlotSpec) -> dict[str, Any] | None:
    if not spec.regs:
        return None
    chip = spec.chip
    family = FAMILY[chip]
    ucb_size = spec.stride
    ucb_name = _canonical_ucb_name(spec.regs, spec.region, spec.slot)
    props = _emit_properties(spec, spec.tbd_notes)
    if not props:
        return None

    schema: dict[str, Any] = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": f"ucb://{chip}/{ucb_name}",
        "title": f"{ucb_name} ({family} {spec.region}_{spec.slot:02d})",
        "x-ucb-meta": {
            "name": ucb_name,
            "size": ucb_size,
            "has_orig_copy": False,
            "addresses": {
                family: {"orig": f"0x{spec.slot_base_abs:08X}"},
            },
            "source": (
                f"{family} UM §{CHAPTER[chip]}.4 ({UM_VERSION[chip]}) "
                f"slot {spec.region}_{spec.slot:02d}"
            ),
        },
        "type": "object",
        "properties": props,
    }
    if spec.tbd_notes:
        schema["x-ucb-meta"]["tbd"] = spec.tbd_notes[:10]
    return schema


# --- Driver ------------------------------------------------------------------

def generate_for_chip(chip: str, out_root: Path = SCHEMAS_ROOT,
                      verbose: bool = False) -> tuple[int, int, list[str]]:
    src = EXTRACT_ROOT / chip
    if not src.is_dir():
        raise SystemExit(f"no extract dir: {src}")
    dest = out_root / chip
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*.json"):
        old.unlink()

    results: list[tuple[SlotSpec, dict[str, Any]]] = []
    tbd_all: list[str] = []
    name_count: dict[str, int] = {}
    for path in sorted(src.glob("UCB*.txt")):
        try:
            spec = parse_slot_file(path, chip)
        except Exception as e:
            tbd_all.append(f"{path.name}: parse error: {e}")
            continue
        sch = build_schema(spec)
        if sch is None:
            tbd_all.append(f"{path.name}: empty (all-reserved)")
            continue
        nm = sch["x-ucb-meta"]["name"]
        name_count[nm] = name_count.get(nm, 0) + 1
        results.append((spec, sch))

    n_schemas = 0
    n_fields = 0
    per_name_idx: dict[str, int] = {}
    for spec, sch in results:
        nm = sch["x-ucb-meta"]["name"]
        if name_count[nm] > 1:
            # Disambiguate by slot.
            idx = per_name_idx.get(nm, 0)
            per_name_idx[nm] = idx + 1
            new_nm = f"{nm}_{spec.region}_{spec.slot:02d}"
            sch["x-ucb-meta"]["name"] = new_nm
            sch["$id"] = f"ucb://{chip}/{new_nm}"
            sch["title"] = (
                f"{new_nm} ({FAMILY[chip]} {spec.region}_{spec.slot:02d})"
            )
            out = dest / f"{new_nm}.json"
        else:
            out = dest / f"{nm}.json"
        out.write_text(json.dumps(sch, indent=2) + "\n", encoding="utf-8")
        n_schemas += 1
        n_fields += _count_fields(sch)
        tbd_all.extend(spec.tbd_notes)
        if verbose:
            print(f"  wrote {out}")
    return n_schemas, n_fields, tbd_all


def _count_fields(sch: dict[str, Any]) -> int:
    n = 0
    for _name, sub in (sch.get("properties") or {}).items():
        if sub.get("x-bitfield"):
            n += len(sub.get("properties") or {})
        elif sub.get("type") == "array":
            n += int(sub.get("maxItems", 1))
        else:
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chip", choices=sorted(STRIDE))
    ap.add_argument("--out", type=Path, default=SCHEMAS_ROOT)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)
    chips = [args.chip] if args.chip else sorted(STRIDE)
    total_s = total_f = 0
    all_tbd: list[str] = []
    for c in chips:
        s, f, t = generate_for_chip(c, args.out, args.verbose)
        print(f"{c}: {s} schemas, {f} fields, {len(t)} TBD notes")
        total_s += s
        total_f += f
        all_tbd.extend(t)
    print(f"\nTOTAL: {total_s} schemas, {total_f} fields, "
          f"{len(all_tbd)} TBD notes")
    if all_tbd:
        print("\nFirst 20 TBD notes:")
        for t in all_tbd[:20]:
            print(f"  - {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
