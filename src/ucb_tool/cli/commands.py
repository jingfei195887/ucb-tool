from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import click

import ucb_tool
from ucb_tool.core.chip_profile import get_profile, list_chips
from ucb_tool.core.errors import UcbError
from ucb_tool.core.ucb_bundle import UcbBundle
from ucb_tool.core.validator import validate_bundle


def _default_schema_dirs(chip_id: str) -> tuple[list[Path], Path | None]:
    root = Path(ucb_tool.__file__).parent / "schemas"
    chip_dir = root / get_profile(chip_id).schema_dir
    return [root / "common"], (chip_dir if chip_dir.is_dir() else None)


def _load_bundle(hex_path: Path, chip_id: str,
                 extra_schemas: Iterable[Path]) -> UcbBundle:
    common, chip_dir = _default_schema_dirs(chip_id)
    common = list(common) + list(extra_schemas)
    return UcbBundle.load(hex_path, chip_id, common_dirs=common, chip_schema_dir=chip_dir)


@click.command(name="show")
@click.argument("hex_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--chip", required=True,
              type=click.Choice(list_chips(), case_sensitive=False))
@click.option("--schemas", "schemas_dir", multiple=True,
              type=click.Path(exists=True, file_okay=False, path_type=Path))
def show_cmd(hex_path: Path, chip: str, schemas_dir: tuple[Path, ...]) -> None:
    """Print every UCB + field value in tree form."""
    try:
        bundle = _load_bundle(hex_path, chip.lower(), schemas_dir)
    except (UcbError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    for name, inst in bundle.instances.items():
        head = f"\n[{name}] @ 0x{inst.orig_addr:08X}"
        if inst.copy_addr:
            head += f" + COPY @ 0x{inst.copy_addr:08X}"
        click.echo(head)
        for f in inst.fields:
            if f.read_only and "x-computed" not in f.schema:
                continue
            try:
                val = inst.get(f.path)
            except Exception:  # noqa: BLE001
                continue
            render = f.schema.get("x-render")
            pretty = f"0x{val:X}" if render == "hex" else str(val)
            click.echo(f"  {f.path:28s} = {pretty}  [{f.danger}]")


@click.command(name="set")
@click.argument("hex_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--chip", required=True,
              type=click.Choice(list_chips(), case_sensitive=False))
@click.option("--field", "fields", multiple=True, required=True,
              help="UCB.path=value pairs, e.g. BMHD_0.STAD=0x80000000")
@click.option("--out", "out_path", required=True, type=click.Path(path_type=Path))
@click.option("--yes-i-know-lock", is_flag=True, default=False)
@click.option("--yes-i-know-brick", is_flag=True, default=False)
@click.option("--skip-checksum", is_flag=True, default=False)
@click.option("--schemas", "schemas_dir", multiple=True,
              type=click.Path(exists=True, file_okay=False, path_type=Path))
def set_cmd(hex_path: Path, chip: str, fields: tuple[str, ...], out_path: Path,
            yes_i_know_lock: bool, yes_i_know_brick: bool,
            skip_checksum: bool, schemas_dir: tuple[Path, ...]) -> None:
    """Change one or more fields and write a new hex."""
    try:
        bundle = _load_bundle(hex_path, chip.lower(), schemas_dir)
        baseline = _load_bundle(hex_path, chip.lower(), schemas_dir)
    except UcbError as exc:
        raise click.ClickException(str(exc)) from exc

    for spec in fields:
        if "=" not in spec:
            raise click.BadParameter(f"--field expects UCB.path=value, got {spec!r}")
        path_spec, raw_val = spec.split("=", 1)
        if "." not in path_spec:
            raise click.BadParameter(f"--field path must be UCB.path, got {path_spec!r}")
        ucb_name, dotted = path_spec.split(".", 1)
        try:
            value = int(raw_val, 0)
        except ValueError:
            try:
                f = bundle[ucb_name].field_by_path(dotted)
                names = f.schema.get("x-enum-names") or {}
                rev = {v: int(k) for k, v in names.items()}
                value = rev[raw_val]
            except Exception as exc:  # noqa: BLE001
                raise click.BadParameter(f"cannot parse value {raw_val!r}: {exc}") from exc
        bundle[ucb_name].set(dotted, value)

    report = validate_bundle(bundle, baseline=baseline)
    if report.has_blocking:
        msg = "\n".join(str(e) for e in report.errors + report.constraint_violations)
        raise click.ClickException(f"validation failed:\n{msg}")

    danger = report.danger_summary
    if danger:
        needs_brick = any(d in ("brick", "irreversible") for _, d in danger)
        needs_lock = any(d == "lock" for _, d in danger)
        if needs_brick and not yes_i_know_brick:
            raise click.ClickException(
                "Brick/irreversible changes present; pass --yes-i-know-brick to confirm:\n" +
                "\n".join(f"  {p} ({d})" for p, d in danger))
        if needs_lock and not (yes_i_know_lock or yes_i_know_brick):
            raise click.ClickException(
                "Lock-level changes present; pass --yes-i-know-lock to confirm:\n" +
                "\n".join(f"  {p} ({d})" for p, d in danger))

    bundle.save(out_path, recompute=not skip_checksum)
    suffix = ", checksums skipped" if skip_checksum else ""
    click.echo(f"wrote {out_path}  ({len(fields)} field(s) modified{suffix})")


@click.command(name="validate")
@click.argument("hex_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--chip", required=True,
              type=click.Choice(list_chips(), case_sensitive=False))
@click.option("--strict", is_flag=True, default=False)
@click.option("--schemas", "schemas_dir", multiple=True,
              type=click.Path(exists=True, file_okay=False, path_type=Path))
def validate_cmd(hex_path: Path, chip: str, strict: bool,
                 schemas_dir: tuple[Path, ...]) -> None:
    """Validate hex; exit 0 clean, 1 warnings, 2 errors."""
    try:
        bundle = _load_bundle(hex_path, chip.lower(), schemas_dir)
    except UcbError as exc:
        raise click.ClickException(str(exc)) from exc
    report = validate_bundle(bundle)
    for err in report.errors:
        click.echo(f"ERROR  {err}")
    for cv in report.constraint_violations:
        click.echo(f"ERROR  {cv}")
    if report.has_blocking:
        raise SystemExit(2)
    warn = report.danger_summary
    if warn and strict:
        for p, d in warn:
            click.echo(f"WARN   {p} [{d}]")
        raise SystemExit(1)
    click.echo("OK")


@click.command(name="export-xlsx")
@click.argument("hex_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--chip", required=True,
              type=click.Choice(list_chips(), case_sensitive=False))
@click.option("--out", "out_path", required=True, type=click.Path(path_type=Path))
@click.option("--schemas", "schemas_dir", multiple=True,
              type=click.Path(exists=True, file_okay=False, path_type=Path))
def export_xlsx_cmd(hex_path: Path, chip: str, out_path: Path,
                    schemas_dir: tuple[Path, ...]) -> None:
    """Export the full UCB bundle as a multi-sheet .xlsx snapshot."""
    from ucb_tool.core.xlsx_io import export_to_xlsx  # lazy import; module lands in M4.2
    try:
        bundle = _load_bundle(hex_path, chip.lower(), schemas_dir)
    except UcbError as exc:
        raise click.ClickException(str(exc)) from exc
    export_to_xlsx(bundle, out_path, source_hex=hex_path)
    click.echo(f"wrote {out_path}")


@click.command(name="apply-xlsx")
@click.argument("hex_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--chip", required=True,
              type=click.Choice(list_chips(), case_sensitive=False))
@click.option("--xlsx", "xlsx_path", required=True,
              type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--out", "out_path", required=True, type=click.Path(path_type=Path))
@click.option("--lenient-xlsx", is_flag=True, default=False)
@click.option("--yes-i-know-lock", is_flag=True, default=False)
@click.option("--yes-i-know-brick", is_flag=True, default=False)
@click.option("--schemas", "schemas_dir", multiple=True,
              type=click.Path(exists=True, file_okay=False, path_type=Path))
def apply_xlsx_cmd(hex_path: Path, chip: str, xlsx_path: Path, out_path: Path,
                   lenient_xlsx: bool, yes_i_know_lock: bool,
                   yes_i_know_brick: bool,
                   schemas_dir: tuple[Path, ...]) -> None:
    """Apply an edited .xlsx snapshot to produce a new hex."""
    from ucb_tool.core.xlsx_io import apply_xlsx
    try:
        bundle = _load_bundle(hex_path, chip.lower(), schemas_dir)
        baseline = _load_bundle(hex_path, chip.lower(), schemas_dir)
    except UcbError as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        apply_xlsx(bundle, xlsx_path, lenient=lenient_xlsx)
    except UcbError as exc:
        raise click.ClickException(str(exc)) from exc

    report = validate_bundle(bundle, baseline=baseline)
    if report.has_blocking:
        msg = "\n".join(str(e) for e in report.errors + report.constraint_violations)
        raise click.ClickException(f"validation failed:\n{msg}")

    danger = report.danger_summary
    needs_brick = any(d in ("brick", "irreversible") for _, d in danger)
    needs_lock = any(d == "lock" for _, d in danger)
    if needs_brick and not yes_i_know_brick:
        raise click.ClickException(
            "Brick/irreversible changes present; pass --yes-i-know-brick:\n" +
            "\n".join(f"  {p} ({d})" for p, d in danger))
    if needs_lock and not (yes_i_know_lock or yes_i_know_brick):
        raise click.ClickException(
            "Lock changes present; pass --yes-i-know-lock:\n" +
            "\n".join(f"  {p} ({d})" for p, d in danger))

    bundle.save(out_path, recompute=True)
    click.echo(f"wrote {out_path}")


@click.command(name="diff")
@click.argument("hex_a", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("hex_b", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--chip", required=True,
              type=click.Choice(list_chips(), case_sensitive=False))
@click.option("--out", "out_path", required=True, type=click.Path(path_type=Path))
@click.option("--schemas", "schemas_dir", multiple=True,
              type=click.Path(exists=True, file_okay=False, path_type=Path))
def diff_cmd(hex_a: Path, hex_b: Path, chip: str, out_path: Path,
             schemas_dir: tuple[Path, ...]) -> None:
    """Produce an Excel diff report between two ucb.hex files."""
    from ucb_tool.core.xlsx_io import diff_bundles
    a = _load_bundle(hex_a, chip.lower(), schemas_dir)
    b = _load_bundle(hex_b, chip.lower(), schemas_dir)
    n = diff_bundles(a, b, out_path)
    click.echo(f"wrote {out_path} ({n} changed field(s))")


@click.command(name="export-ucb")
@click.argument("hex_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--chip", required=True,
              type=click.Choice(list_chips(), case_sensitive=False))
@click.option("--name", "ucb_name", required=True,
              help="UCB name to export (e.g. BMHD0, USERCFG_ORIG_RTC). "
                   "Run `show` to list names.")
@click.option("--out", "out_path", required=True, type=click.Path(path_type=Path),
              help="Destination .hex path for this single UCB.")
@click.option("--no-copy", "skip_copy", is_flag=True, default=False,
              help="Emit ORIG only; skip the COPY mirror bytes.")
@click.option("--skip-checksum", is_flag=True, default=False,
              help="Don't auto-recompute CRC / confirmation before writing.")
@click.option("--schemas", "schemas_dir", multiple=True,
              type=click.Path(exists=True, file_okay=False, path_type=Path))
def export_ucb_cmd(hex_path: Path, chip: str, ucb_name: str, out_path: Path,
                   skip_copy: bool, skip_checksum: bool,
                   schemas_dir: tuple[Path, ...]) -> None:
    """Export a single UCB from a hex file as its own standalone .hex."""
    bundle = _load_bundle(hex_path, chip.lower(), schemas_dir)
    if ucb_name not in bundle.instances:
        known = ", ".join(sorted(bundle.instances.keys())[:10])
        raise click.ClickException(
            f"UCB {ucb_name!r} not found. Known (first 10): {known} ...",
        )
    bundle.export_ucb(ucb_name, out_path,
                      recompute=not skip_checksum,
                      include_copy=not skip_copy)
    click.echo(f"wrote {out_path} (UCB={ucb_name})")
