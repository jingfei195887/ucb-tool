# UCB Tool — User Guide

## Install

### Linux

1. Download `ucbtool-x86_64.AppImage` from the Releases page.
2. `chmod +x ucbtool-x86_64.AppImage`
3. Double-click, or from terminal: `./ucbtool-x86_64.AppImage`

### Windows

1. Download `ucbtool-setup.exe`.
2. Run the installer (admin required). It adds the CLI to your PATH.

### From source

```
git clone <repo>
cd ucb-tool
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ucbtool-gui      # launch GUI
ucbtool --help   # CLI
```

## GUI walkthrough

1. **File → Open** → choose your `ucb.hex`.
2. Select chip model in the dialog.
3. Left tree lists every UCB present. Click one → right panel shows the field form + hex dump.
4. Edit values. Danger icons mark fields that can lock or brick the chip.
5. **File → Save As…** → confirm any danger dialog → pick destination.
6. **File → Apply Excel Edits…** → round-trip a spreadsheet back into the hex.
7. **Advanced** checkbox in the status bar unlocks:
   - ORIG/COPY independent editing
   - Overriding auto-computed (CRC/Confirmation) fields
   - Editing `readOnly` fields

## CLI reference

See `ucbtool --help` and per-command `--help` pages.

### Common recipes

Inspect a hex:

```
ucbtool show ucb.hex --chip tc4d9
```

Set a brick-level field:

```
ucbtool set ucb.hex --chip tc4d9 \
    --field BMHD_0.STAD=0x80000000 \
    --out new.hex --yes-i-know-brick
```

Validate before flashing:

```
ucbtool validate new.hex --chip tc4d9 --strict   # exit 0 clean, 1 warn, 2 error
```

Excel round-trip:

```
ucbtool export-xlsx ucb.hex --chip tc4d9 --out ucb.xlsx
# edit ucb.xlsx
ucbtool apply-xlsx ucb.hex --chip tc4d9 --xlsx ucb.xlsx --out new.hex \
    --yes-i-know-brick
```

Diff two hex files:

```
ucbtool diff a.hex b.hex --chip tc4d9 --out changes.xlsx
```

## Safety model

| Level | Meaning |
|---|---|
| `safe` | Freely editable |
| `lock` | Wrong value may lock chip behavior (recoverable but difficult) |
| `brick` | Wrong value may permanently brick the chip |
| `irreversible` | Monotonic / one-shot field (e.g., rollback_index) |

CLI requires `--yes-i-know-lock` / `--yes-i-know-brick` for `lock` /
`brick|irreversible` changes respectively. GUI shows a danger-diff dialog
with a consent checkbox.
