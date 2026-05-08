from pathlib import Path

from ucb_tool.core.hex_io import write_hex
from ucb_tool.core.ucb_bundle import UcbBundle
from ucb_tool.core.validator import ValidationReport, validate_bundle

FIX = Path(__file__).parent / "fixtures_schemas"


def _make_bundle(tmp_path: Path) -> UcbBundle:
    hex_path = tmp_path / "u.hex"
    data = {0x1000 + i: 0x00 for i in range(32)} | {0x1020 + i: 0x00 for i in range(32)}
    data |= {0x3000 + i: 0x00 for i in range(32)} | {0x3020 + i: 0x00 for i in range(32)}
    write_hex(hex_path, data)
    return UcbBundle.load(hex_path, "tc4d9",
                          common_dirs=[FIX / "common"],
                          chip_schema_dir=FIX / "tc4dx")


def test_clean_bundle_reports_no_errors(tmp_path):
    bundle = _make_bundle(tmp_path)
    report = validate_bundle(bundle)
    assert report.errors == []
    assert report.constraint_violations == []


def test_danger_changes_tracked_when_baseline_provided(tmp_path):
    bundle = _make_bundle(tmp_path)
    baseline = _make_bundle(tmp_path)  # identical copy
    # Mutate BASE_FIELD (danger defaults to 'safe' in DEMO.json)
    bundle["DEMO"].set("BASE_FIELD", 0xDEADBEEF)
    report = validate_bundle(bundle, baseline=baseline)
    # Some change detected; danger is 'safe' here
    assert len(report.danger_changes) >= 1
    assert all(d == "safe" for _, d in report.danger_changes)


def test_report_summary_flags_empty_cleanly(tmp_path):
    bundle = _make_bundle(tmp_path)
    report = validate_bundle(bundle)
    assert report.has_blocking is False
    assert report.danger_summary == []  # only non-safe changes


def test_validation_report_is_dataclass_like():
    r = ValidationReport()
    assert r.errors == []
    assert r.constraint_violations == []
    assert r.danger_changes == []
