from pathlib import Path

from click.testing import CliRunner

from ucb_tool.cli.__main__ import main
from ucb_tool.core.hex_io import read_hex, slice_range, write_hex


def test_set_then_show_and_export(tmp_path: Path):
    src = tmp_path / "u.hex"
    data = {0xAF400000 + i: 0xFF for i in range(256)}
    write_hex(src, data)

    runner = CliRunner()
    out_hex = tmp_path / "new.hex"
    # STAD danger=brick -> need --yes-i-know-brick
    result = runner.invoke(main, [
        "set", str(src), "--chip", "tc4d9",
        "--field", "BMHD_0.STAD=0x80000000",
        "--out", str(out_hex),
        "--yes-i-know-brick",
    ])
    assert result.exit_code == 0, result.output
    assert slice_range(read_hex(out_hex), 0xAF400000, 4) == b"\x00\x00\x00\x80"

    result = runner.invoke(main, ["show", str(out_hex), "--chip", "tc4d9"])
    assert result.exit_code == 0
    assert "0x80000000" in result.output

    xlsx_path = tmp_path / "u.xlsx"
    result = runner.invoke(main, [
        "export-xlsx", str(out_hex), "--chip", "tc4d9", "--out", str(xlsx_path),
    ])
    assert result.exit_code == 0, result.output
    assert xlsx_path.exists()


def test_set_without_consent_refuses(tmp_path: Path):
    src = tmp_path / "u.hex"
    data = {0xAF400000 + i: 0xFF for i in range(256)}
    write_hex(src, data)

    runner = CliRunner()
    result = runner.invoke(main, [
        "set", str(src), "--chip", "tc4d9",
        "--field", "BMHD_0.STAD=0x80000000",
        "--out", str(tmp_path / "x.hex"),
    ])
    assert result.exit_code != 0
    assert "brick" in result.output.lower()


def test_validate_clean_hex_returns_zero(tmp_path: Path):
    src = tmp_path / "u.hex"
    data = {0xAF400000 + i: 0xFF for i in range(256)}
    write_hex(src, data)

    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(src), "--chip", "tc4d9"])
    # Unlocked UCBs (all 0xFF) validate cleanly
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
