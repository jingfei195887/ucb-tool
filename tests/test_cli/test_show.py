from pathlib import Path

from click.testing import CliRunner

from ucb_tool.cli.__main__ import main
from ucb_tool.core.hex_io import write_hex


def test_show_prints_ucb_tree(tmp_path: Path):
    hex_path = tmp_path / "u.hex"
    data = {0xAF400000 + i: 0xFF for i in range(256)}
    write_hex(hex_path, data)

    runner = CliRunner()
    result = runner.invoke(main, ["show", str(hex_path), "--chip", "tc4d9"])
    assert result.exit_code == 0, result.output
    assert "BMHD_0" in result.output
    assert "STAD" in result.output


def test_show_unknown_chip_errors(tmp_path: Path):
    hex_path = tmp_path / "u.hex"
    write_hex(hex_path, {0: 0xFF})
    runner = CliRunner()
    # click's Choice will reject "stm32" with exit 2 and its own error message
    result = runner.invoke(main, ["show", str(hex_path), "--chip", "stm32"])
    assert result.exit_code != 0
    assert "invalid" in result.output.lower() or "stm32" in result.output.lower()
