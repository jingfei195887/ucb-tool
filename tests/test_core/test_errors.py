from ucb_tool.core.errors import (
    ComputedFieldError,
    ConstraintViolation,
    DangerWithoutConsent,
    HexParseError,
    SchemaError,
    UcbError,
    ValidationError,
)


def test_hierarchy():
    for cls in (HexParseError, SchemaError, ValidationError,
                ConstraintViolation, DangerWithoutConsent, ComputedFieldError):
        assert issubclass(cls, UcbError)


def test_constraint_violation_carries_message_and_path():
    err = ConstraintViolation(path="BMHD_0.CONFIRMATION", message="must be CONFIRMED")
    assert err.path == "BMHD_0.CONFIRMATION"
    assert "CONFIRMED" in str(err)


def test_danger_without_consent_lists_fields():
    err = DangerWithoutConsent(fields=[("BMHD_0.STAD", "brick")])
    assert "BMHD_0.STAD" in str(err)
    assert "brick" in str(err)
