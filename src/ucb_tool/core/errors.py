from __future__ import annotations


class UcbError(Exception):
    """Base class for all ucb_tool errors."""


class HexParseError(UcbError):
    """Intel HEX file malformed or unreadable."""


class SchemaError(UcbError):
    """JSON Schema or x-* extension malformed."""


class ValidationError(UcbError):
    """Schema validation failed on a field value."""

    def __init__(self, path: str, message: str):
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


class ConstraintViolation(UcbError):
    """x-constraint failed."""

    def __init__(self, path: str, message: str):
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


class DangerWithoutConsent(UcbError):
    """Save blocked: danger-level field modified without user consent."""

    def __init__(self, fields: list[tuple[str, str]]):
        lines = [f"  {p} (danger={d})" for p, d in fields]
        super().__init__("Danger fields modified without --yes-i-know-*:\n" + "\n".join(lines))
        self.fields = fields


class ComputedFieldError(UcbError):
    """x-computed algorithm unknown or failed."""
