# ucb-tool

**Infineon AURIX TC4x UCB (User Configuration Block) hex editor** — cross-platform GUI + CLI for reading, editing and round-tripping `ucb.hex` files on TC4Dx / TC48x / TC4Zx chips.

> Wrong UCB values can permanently brick a chip. This tool exists to make those values safer to edit: schema-driven field forms, graded danger warnings, auto-computed CRC / Confirmation codes, and ORIG/COPY mirroring.

---

## At a glance

- **135 UCB schemas** (24 TC4Dx + 53 TC48x + 53 TC4Zx) extracted directly from Infineon AURIX user manuals (v1.10 / v0.90). Every field carries a UM section reference in `x-ucb-meta.source`.
- **5523 fields** with byte-level layout: offset, size, endianness, bit ranges, enum tables — all from the UM text.
- **Graded safety**: every field tagged `safe` / `lock` / `brick` / `irreversible`. CLI requires `--yes-i-know-brick` to write brick-level changes; GUI pops a consent dialog.
- **Auto-computed fields**: CRC-32 (AURIX IEEE 802.3), CONFIRMATION (UNLOCKED/CONFIRMED magic), zero-padding — recomputed on save so users can't break invariants.
- **ORIG/COPY mirroring**: most AURIX UCBs have paired ORIG+COPY regions that must match. Tool auto-mirrors by default; unlock via Advanced mode for debugging.
- **Excel round-trip**: one-click export to multi-sheet `.xlsx` for review/archival; apply edits back with strict schema-version checking.

## Install

### Windows (pre-built)

Download the latest release, unzip, and run:

```
ucbtool-gui/ucbtool-gui.exe    # GUI
ucbtool-cli/ucbtool.exe        # CLI
```

No Python install needed. Windows 10 build 1903+ / Windows 11 required.

### Linux AppImage (pre-built)

```bash
chmod +x ucbtool-x86_64.AppImage
./ucbtool-x86_64.AppImage
```

### From source (developer install)

```bash
git clone https://github.com/jingfei195887/ucb-tool.git
cd ucb-tool
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

ucbtool --help            # CLI
ucbtool-gui               # GUI (needs libxcb-cursor0 on Linux)
```

Python 3.10+ required.

## Quick recipes

```bash
# Inspect a hex
ucbtool show my_ucb.hex --chip tc4d9

# Change STAD (brick-level field → need consent flag)
ucbtool set my_ucb.hex --chip tc4d9 \
    --field BMHD0.STAD=0x80000000 \
    --out new.hex --yes-i-know-brick

# Validate before flashing
ucbtool validate my_ucb.hex --chip tc4d9 --strict   # exit 0 OK, 1 warn, 2 error

# Excel round-trip
ucbtool export-xlsx my_ucb.hex --chip tc4d9 --out snapshot.xlsx
# ...edit snapshot.xlsx in Excel, modify the Value column...
ucbtool apply-xlsx my_ucb.hex --chip tc4d9 --xlsx snapshot.xlsx --out new.hex \
    --yes-i-know-brick

# Diff two hex files as an Excel report
ucbtool diff a.hex b.hex --chip tc4d9 --out changes.xlsx
```

Supported `--chip` values: `tc4d9`, `tc4d7`, `tc489`, `tc4z9`.

## Architecture

```
src/ucb_tool/
├── core/                  zero-Qt business logic; mypy strict
│   ├── errors.py          exception hierarchy
│   ├── hex_io.py          Intel HEX read/write (round-trip, slice, merge)
│   ├── chip_profile.py    chip family + stride + schema dir registry
│   ├── schema_loader.py   JSON Schema loader with common→chip overlay merge
│   ├── field_codec.py     int / bitfield / CRC32 / Confirmation encode-decode
│   ├── validator.py       jsonschema + asteval constraints + danger diff
│   ├── ucb_bundle.py      UcbBundle (load/save), UcbInstance (get/set/mirror)
│   └── xlsx_io.py         openpyxl export + apply + diff
├── schemas/
│   ├── common/            shared schemas (currently empty — per-chip below)
│   ├── tc4dx/*.json       24 UCB schemas for TC4D7/TC4D9
│   ├── tc48x/*.json       53 UCB schemas for TC489
│   └── tc4zx/*.json       53 UCB schemas for TC4Z9
├── cli/                   click-based CLI, shares core
└── gui/                   PySide6 GUI, shares core
    ├── main_window.py     tree / form / hex dump
    ├── views/field_form.py
    ├── widgets/           hex / password / enum / bool / hex-dump editors
    └── dialogs/           chip picker, danger confirm
```

**Design goals**:
- `core/` must never import Qt — makes headless automation trivial.
- Schemas are **data**, not code — extending to a new chip is a data change, not a code change.
- CLI and GUI are thin façades over the same `UcbBundle` model.
- Every byte that leaves the tool has been validated by schema + constraints + danger gate.

## Schema authoring

Every UCB is described by a JSON Schema Draft-07 file with `x-*` extensions for byte-level layout. Example (`BMHD0` for TC4Dx):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "ucb://tc4dx/BMHD0",
  "title": "BMHD0 (TC4Dx UCB0_09)",
  "x-ucb-meta": {
    "name": "BMHD0", "size": 2048, "has_orig_copy": false,
    "addresses": { "TC4Dx": { "orig": "0xAE404800" } },
    "source": "TC4Dx UM §49.4 (v1.10) slot UCB0_09"
  },
  "type": "object",
  "properties": {
    "SAL":  { "type": "integer", "x-offset": 0, "x-size": 4,
              "x-endian": "little", "x-render": "hex",
              "x-help": "System Address of this Location" },
    "BMI_BMHDID": {
      "type": "object", "x-offset": 4, "x-size": 4, "x-bitfield": true,
      "properties": {
        "BMI":    { "type": "integer", "x-bits": [0, 15],
                    "x-danger": "brick" },
        "BMHDID": { "type": "integer", "x-bits": [16, 31],
                    "x-danger": "brick" }
      }
    },
    "STAD":    { "type": "integer", "x-offset": 8,  "x-size": 4,
                 "x-render": "hex", "x-danger": "brick" },
    "CRCBMHD": { "type": "integer", "x-offset": 12, "x-size": 4,
                 "x-computed": "crc32-aurix", "readOnly": true },
    "PW0":     { "type": "integer", "x-offset": 2000, "x-size": 4,
                 "x-render": "password", "x-danger": "lock" },
    "CONFIRMATION": { "type": "integer", "x-offset": 2032, "x-size": 8,
                      "x-computed": "confirmation" }
  }
}
```

See `docs/schema_authoring.md` for the full `x-*` keyword reference (offsets, bitfields, arrays, constraints, computed fields, enum names).

## Safety model

| Level | Meaning | CLI gate | GUI gate |
|---|---|---|---|
| `safe` | Free to edit; informational or low-stakes | none | none |
| `lock` | Wrong value may lock chip (passwords, PROCON, HSM) | `--yes-i-know-lock` | confirm dialog |
| `brick` | Wrong value may permanently brick the chip (STAD, BMI, OCDS) | `--yes-i-know-brick` | consent dialog |
| `irreversible` | Monotonic one-shot (rollback_index, HSM keys) | `--yes-i-know-brick` | consent dialog |

Auto-computed fields (`CRC`, `CONFIRMATION`, `ecc-aurix`) are recomputed on save — users can't forget them. Use `--skip-checksum` only when deliberately preserving broken values (bug reproduction).

## UCB state encoding (CONFIRMATION field)

| Byte pattern (little-endian 64-bit) | UCB state |
|---|---|
| `34 12 21 43 00 00 00 00` = `0x43211234` | **UNLOCKED** (password-less, user-writable) |
| `7F 32 B5 57 00 00 00 00` = `0x57B5327F` | **CONFIRMED** (password-locked) |
| anything else | **ERRORED** (uninitialized, CRC fail, corrupted) |

UNLOCKED magic is verified against a real TC4Dx dump. Source: see `src/ucb_tool/core/field_codec.py`.

## Mandatory UCBs & reference templates

Some UCBs are **mandatory** — the AURIX boot ROM refuses to boot or enters a
degraded state if they are not populated.  Every chip family ships with a
**reference template hex** that defines its mandatory set:

```
src/ucb_tool/templates/
├── tc4dx.hex     ← TC4Dx mandatory UCBs (16): BMHD0-3 + _CS,
│                   USERCFG ORIG/COPY RTC+CS, SWAP ORIG/COPY RTC+CS
├── tc48x.hex     ← TC48x mandatory UCBs (12): BMHD0-3 + _CS,
│                   SWAP_ORIG_RTC slots 02/06, SWAP_ORIG_CS slots 07/12
└── tc4zx.hex     ← TC4Zx mandatory UCBs (12): same as TC48x
```

A UCB is considered mandatory if **at least one byte of its ORIG (or COPY)
address range is populated in the template**.  At load time the tool
computes this set and:

- GUI tree: shows `★ mandatory` (present) or `⚠ MISSING mandatory` (absent,
  amber-coloured) next to each UCB; region headers display
  `(present/total, ⚠N missing)`.
- Field form header: `[EMPTY — not in loaded hex]` if the selected UCB is
  absent.
- Save / apply: **absent** UCBs are NOT written back so a partial-hex input
  round-trips to a partial-hex output; **user edits** are never overwritten.

### Expanding the mandatory set

To add more UCBs to the mandatory set for a chip, add their address ranges
to the corresponding template hex:

```bash
# 1. Work from a known-good UCB dump for your project/board
cp my_board_golden_ucb.hex src/ucb_tool/templates/tc4dx.hex

# 2. Or extend the existing template with more UCBs (e.g. using an Intel HEX
#    editor or the tool's `set` command to merge a partial hex in)
ucbtool set src/ucb_tool/templates/tc4dx.hex --chip tc4d9 \
    --field HOST_PFPROCON_ORIG.WP0=0x5A5A5A5A \
    --out src/ucb_tool/templates/tc4dx.hex --yes-i-know-lock
```

After the change, `ucbtool show ...` will mark the newly-covered UCBs as
`★ mandatory`, and `--fill-missing` will pull their bytes for users who
load hex files without them.

### Per-project custom templates (`--template`)

Different projects / boards may disagree about what's mandatory (e.g., one
project uses HSM, another doesn't).  Instead of editing the bundled
template, override it for a single invocation:

```bash
# Use a project-specific template for mandatory-UCB detection AND fill
ucbtool set partial.hex --chip tc4d9 \
    --template /path/to/project_golden_ucb.hex \
    --fill-missing \
    --field BMHD0.STAD=0x80000000 \
    --out new.hex --yes-i-know-brick

# Same for Excel round-trip
ucbtool apply-xlsx partial.hex --chip tc4d9 \
    --xlsx edits.xlsx --out new.hex \
    --template /path/to/project_golden_ucb.hex \
    --yes-i-know-brick
```

The bundled template is the **default**; `--template` only affects the
current invocation.  Python API equivalent:

```python
bundle = UcbBundle.load(hex_path, chip_id,
                        common_dirs=[...], chip_schema_dir=...,
                        template_path="/path/to/project_golden_ucb.hex")
bundle.fill_missing_mandatory(template_path="/path/to/project_golden_ucb.hex")
```

### Programmatic fill

```python
bundle = UcbBundle.load(...)
missing = bundle.missing_mandatory()     # list of UCB names absent in input
filled  = bundle.fill_missing_mandatory() # copies from template; returns filled names
bundle.save(out_path)                     # emits completed hex
```

GUI equivalent: **Tools → Fill missing mandatory UCBs from template**.

## Build system

- **Dev loop**: `pytest` (261 tests, 88%+ coverage), `ruff check`, `mypy src/ucb_tool/core` (strict).
- **Windows exe**: `pyinstaller packaging/ucbtool.spec` → `dist/ucbtool-gui/` + `dist/ucbtool-cli/`. Cross-build from Linux via wine works (see `packaging/` for scripts).
- **Linux AppImage**: `bash packaging/build_appimage.sh`.
- **CI**: `.github/workflows/ci.yml` runs test matrix on Ubuntu 22.04 + Windows 2022 × Python 3.10/3.11/3.12 with 85% coverage gate. `release.yml` builds artifacts on tag push.

## Known limitations (v0.1.x)

1. **ECC algorithm**: only CRC-32/IEEE 802.3 is wired. If AURIX UM defines a separate ECC for protected pages, it is not implemented yet. CRC covers the cases documented in the reference `aurix_ucb.c`.
2. **Common-tier schemas empty**: per-chip schemas (tc4dx/tc48x/tc4zx) differ structurally (stride 0x800 vs 0x100); we didn't find a clean common subset to share. Acceptable trade-off.
3. **SWAP 16-byte entries are flattened**: each SWAP log entry's 16-byte record is exposed as 4 separate 4-byte fields (`SAL_N`, `STATUS_N`, `MARKER_N`, `CRCSE_N`) rather than one struct-valued field. Done because openpyxl's float precision corrupts 128-bit values round-tripping through Excel. No functional loss — bytes are identical; UI is slightly noisier.
4. **`enum` constraints relaxed**: UM enum tables describe the valid encoded values with "else reserved" semantics. Virgin (all-0xFF) UCBs would fail such `enum` constraints. We kept `x-enum-names` (labels in UI) but dropped the hard `enum` JSON-Schema clause. Tightening this requires fuzzy-matching "reserved" against actual chip behavior.
5. **Standalone project**: this is not a submodule of a Google `repo`-managed super-project. Fine for a tool; not a limitation of the design.

## Contributing

- Follow existing style: `ruff check src tests` + `mypy src/ucb_tool/core` must pass.
- New schemas: drop into `src/ucb_tool/schemas/{tc4dx,tc48x,tc4zx}/` and run `pytest tests/test_core/test_schemas_lint.py` — the linter checks `x-*` invariants (offset+size ≤ UCB size, bitfield children within parent byte range, no x-computed + x-bits, etc.).
- Commit messages follow conventional-commits style: `feat(core): ...`, `fix(schemas): ...`, `test: ...`, `docs: ...`.

## License

Apache-2.0. See `LICENSE` (or the Apache 2.0 header in each source file).

## Reference material

- Infineon AURIX **TC4Dx** User Manual, v1.10 (2025-04-22) — §49 Firmware, §6.3.13 UCB handling
- Infineon AURIX **TC48x** User Manual, v0.90 — §44 Firmware
- Infineon AURIX **TC4Zx** User Manual, v0.90 — §47 Firmware
- `vendor/infineon/chips/aurix/aurix_ucb.{c,h}` (from the companion CarOS repository) — runtime UCB access, CRC algorithm, confirmation-code constants

## Project status

- **v0.1.x** — initial release: core pipeline, 135 schemas, CLI + GUI + Excel round-trip, Windows/Linux builds. Used by the CarOS team on TC4D9 EVB / LZCU boards.
- **Next**: verify CONFIRMED-state dumps on real hardware; add remaining chip family UCB schemas if user manuals publish more; productize schema authoring.
