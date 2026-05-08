from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any

import jsonschema
from asteval import Interpreter

from ucb_tool.core.errors import ConstraintViolation, ValidationError
from ucb_tool.core.ucb_bundle import FieldDescriptor, UcbBundle, UcbInstance


@dataclass
class ValidationReport:
    errors: list[ValidationError] = field(default_factory=list)
    constraint_violations: list[ConstraintViolation] = field(default_factory=list)
    danger_changes: list[tuple[str, str]] = field(default_factory=list)  # (path, danger)

    @property
    def has_blocking(self) -> bool:
        return bool(self.errors or self.constraint_violations)

    @property
    def danger_summary(self) -> list[tuple[str, str]]:
        return [(p, d) for p, d in self.danger_changes if d != "safe"]


def _coerce_for_schema(schema: dict[str, Any], value: Any) -> Any:
    """Decode integer storage into the type the JSON schema expects.

    Bitfield reads always return ``int`` (see UcbInstance._read), but a
    boolean-typed field in the schema will fail jsonschema validation on a
    bare ``0``/``1``. Coerce on the read side.
    """
    t = schema.get("type")
    if t == "boolean" and isinstance(value, int) and not isinstance(value, bool):
        return bool(value)
    return value


def _validate_value(descriptor: FieldDescriptor, value: Any) -> list[ValidationError]:
    coerced = _coerce_for_schema(descriptor.schema, value)
    try:
        jsonschema.validate(coerced, descriptor.schema)
    except jsonschema.ValidationError as exc:
        return [ValidationError(descriptor.path, exc.message)]
    return []


def _collect_field_dict(inst: UcbInstance) -> dict[str, int]:
    d: dict[str, int] = {}
    for f in inst.fields:
        if f.read_only:
            continue
        with contextlib.suppress(Exception):
            d[f.path] = inst.get(f.path)
    return d


def _sanitize(s: str) -> str:
    return s.replace(".", "__").replace("[", "_").replace("]", "")


def _eval_constraints(inst: UcbInstance) -> list[ConstraintViolation]:
    rules = inst.schema.schema.get("x-constraints") or []
    if not rules:
        return []
    env = _collect_field_dict(inst)
    aeval = Interpreter(minimal=True, use_numpy=False)
    for k, v in env.items():
        aeval.symtable[_sanitize(k)] = v
    out: list[ConstraintViolation] = []
    for rule in rules:
        when_src = _sanitize(rule.get("when", "True"))
        require_src = _sanitize(rule.get("require", "True"))
        msg = rule.get("message", "constraint failed")
        try:
            cond = aeval(when_src)
            if cond:
                ok = aeval(require_src)
                if not ok:
                    out.append(ConstraintViolation(path=inst.schema.name, message=msg))
        except Exception as exc:  # noqa: BLE001
            out.append(ConstraintViolation(
                path=inst.schema.name,
                message=f"constraint eval failed: {exc}",
            ))
    return out


def _diff_danger(inst: UcbInstance,
                 baseline: UcbInstance | None) -> list[tuple[str, str]]:
    if baseline is None:
        return []
    changes: list[tuple[str, str]] = []
    for f in inst.fields:
        if f.read_only:
            continue
        try:
            new = inst.get(f.path)
            old = baseline.get(f.path)
        except Exception:  # noqa: BLE001
            continue
        if new != old:
            changes.append((f"{inst.schema.name}.{f.path}", f.danger))
    return changes


def validate_bundle(bundle: UcbBundle,
                    baseline: UcbBundle | None = None) -> ValidationReport:
    rep = ValidationReport()
    for name, inst in bundle.instances.items():
        for f in inst.fields:
            if f.read_only:
                continue
            try:
                val = inst.get(f.path)
            except Exception as exc:  # noqa: BLE001
                rep.errors.append(ValidationError(f"{name}.{f.path}", str(exc)))
                continue
            rep.errors.extend(_validate_value(f, val))
        rep.constraint_violations.extend(_eval_constraints(inst))
        base_inst = baseline.instances.get(name) if baseline else None
        rep.danger_changes.extend(_diff_danger(inst, base_inst))
    return rep
