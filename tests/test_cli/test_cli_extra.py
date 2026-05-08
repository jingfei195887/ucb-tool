from click.testing import CliRunner

from ucb_tool.cli.__main__ import main
from ucb_tool.core.hex_io import write_hex


def test_set_bad_field_format_errors(tmp_path):
    src = tmp_path / "u.hex"
    write_hex(src, {0xAF400000 + i: 0xFF for i in range(256)})
    runner = CliRunner()
    result = runner.invoke(main, [
        "set", str(src), "--chip", "tc4d9",
        "--field", "NO_EQUALS_SIGN",
        "--out", str(tmp_path / "x.hex"),
    ])
    assert result.exit_code != 0


def test_set_bad_path_format_errors(tmp_path):
    src = tmp_path / "u.hex"
    write_hex(src, {0xAF400000 + i: 0xFF for i in range(256)})
    runner = CliRunner()
    result = runner.invoke(main, [
        "set", str(src), "--chip", "tc4d9",
        "--field", "NODOTPATH=0x10",
        "--out", str(tmp_path / "x.hex"),
    ])
    assert result.exit_code != 0


def test_set_unparseable_value_errors(tmp_path):
    src = tmp_path / "u.hex"
    write_hex(src, {0xAF400000 + i: 0xFF for i in range(256)})
    runner = CliRunner()
    result = runner.invoke(main, [
        "set", str(src), "--chip", "tc4d9",
        "--field", "BMHD_0.BMI.HWCFG=not_a_real_label",
        "--out", str(tmp_path / "x.hex"),
    ])
    assert result.exit_code != 0


def test_set_enum_label_value(tmp_path):
    src = tmp_path / "u.hex"
    write_hex(src, {0xAF400000 + i: 0xFF for i in range(256)})
    runner = CliRunner()
    result = runner.invoke(main, [
        "set", str(src), "--chip", "tc4d9",
        "--field", "BMHD_0.BMI.HWCFG=ASC bootstrap",
        "--out", str(tmp_path / "out.hex"),
        "--yes-i-know-brick",
    ])
    assert result.exit_code == 0, result.output


def test_set_skip_checksum_flag(tmp_path):
    src = tmp_path / "u.hex"
    write_hex(src, {0xAF400000 + i: 0xFF for i in range(256)})
    runner = CliRunner()
    result = runner.invoke(main, [
        "set", str(src), "--chip", "tc4d9",
        "--field", "BMHD_0.BMI.HWCFG=ASC bootstrap",
        "--out", str(tmp_path / "out.hex"),
        "--yes-i-know-brick",
        "--skip-checksum",
    ])
    assert result.exit_code == 0, result.output
    assert "checksums skipped" in result.output


def test_validate_strict_with_no_warnings(tmp_path):
    src = tmp_path / "u.hex"
    write_hex(src, {0xAF400000 + i: 0xFF for i in range(256)})
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(src), "--chip", "tc4d9", "--strict"])
    assert result.exit_code == 0


def test_validate_non_strict_ok(tmp_path):
    src = tmp_path / "u.hex"
    write_hex(src, {0xAF400000 + i: 0xFF for i in range(256)})
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(src), "--chip", "tc4d9"])
    assert result.exit_code == 0
    assert "OK" in result.output
