# Changelog

## v0.1.0 — 2026-05-08

Initial release.

- Core: Intel HEX I/O, chip profile registry, JSON Schema loader with common→chip overlay, bitfield/endian/CRC-32/Confirmation codec, validator with jsonschema + asteval constraints + danger diff, `UcbBundle` with ORIG/COPY mirror and auto-recompute on save, Excel round-trip.
- CLI: `show`, `set`, `validate`, `export-xlsx`, `apply-xlsx`, `diff`.
- GUI: chip picker, schema-driven field form with hex/enum/bool/password editors, hex dump view, danger-confirm dialog, File → Apply Excel Edits.
- Packaging: Linux AppImage, Windows NSIS installer, CI matrix on Ubuntu 22.04 / Windows 2022 / Python 3.10–3.12.
- Docs: user guide, schema authoring guide.
- Sample schemas: `BMHD_0`, `SWAP` (skeletons).

Known gaps:
- ECC algorithm: CRC-32 wired; full ECC requires extraction at implementation time.
- Schema content: real field catalogs for TC4Dx / TC48x / TC4Zx to be delivered by the CarOS team (not part of this repo).
- UNLOCKED / ERRORED confirmation magic: CONFIRMED extracted from `aurix_ucb.c:173/178`; UNLOCKED/ERRORED require additional extraction.
