# Schema Authoring Guide

ucb-tool consumes one JSON Schema Draft-07 file per UCB kind, with `x-*`
extensions describing byte-level layout.

## File layout

```
src/ucb_tool/schemas/
├── common/         # applies to all chip families
├── tc4dx/          # TC4Dx-only or overrides
├── tc48x/
└── tc4zx/
```

At load time, the tool first loads every `common/*.json`, then overlays any
file in the chip-specific folder with the same `$id` (deep-merged).

## Mandatory fields

Every schema must have:

- `$schema` — `"http://json-schema.org/draft-07/schema#"`
- `$id` — stable unique ID like `"ucb://common/BMHD_0"`
- `title` — human label
- `x-ucb-meta` — object with `name` / `size` / `addresses`
  - `addresses` — per-family `orig` + optional `copy`
  - Use literal `"__COMPUTE_FROM_PROFILE__"` to defer to `chip_profile.py`
    when addresses depend on the chip family's slot stride

## Field properties

Each entry in `properties` declares a field:

```json
"STAD": {
  "type": "integer",
  "minimum": 0, "maximum": 4294967295,
  "x-offset": 0, "x-size": 4, "x-endian": "little",
  "x-render": "hex",
  "x-danger": "brick",
  "x-help": "Entry PC"
}
```

### Bitfields

Wrap sub-bits in a parent with `"x-bitfield": true`:

```json
"BMI": {
  "type": "object",
  "x-offset": 4, "x-size": 2, "x-endian": "little",
  "x-bitfield": true,
  "properties": {
    "PINDIS": { "type": "boolean", "x-bits": [0, 0] },
    "HWCFG":  { "type": "integer", "x-bits": [1, 3],
                "enum": [0, 1, 3, 7],
                "x-enum-names": {
                  "0": "Internal flash", "1": "External SPI",
                  "3": "ASC bootstrap",  "7": "CAN bootstrap"
                } }
  }
}
```

### Arrays

Fixed-length arrays of primitives:

```json
"PASSWORD": {
  "type": "array",
  "items": { "type": "integer", "minimum": 0, "maximum": 4294967295 },
  "minItems": 8, "maxItems": 8,
  "x-offset": 64, "x-size": 32, "x-endian": "little",
  "x-render": "password",
  "x-danger": "lock"
}
```

### Computed fields

Auto-filled by the tool on save:

```json
"CRC": {
  "type": "integer",
  "x-offset": 248, "x-size": 4, "x-endian": "little",
  "x-computed": "crc32-aurix", "readOnly": true
}
```

Supported algorithms: `crc32-aurix`, `ecc-aurix`, `confirmation`, `zero_pad`.

### Cross-field constraints

```json
"x-constraints": [
  { "when":    "PASSWORD_0 != 0",
    "require": "CONFIRMATION == 'CONFIRMED'",
    "message": "Password set but not confirmed" }
]
```

Expressions use a Python-subset evaluated by `asteval`. Field references
use double-underscore notation internally (`BMI.HWCFG` → `BMI__HWCFG`).

## Local testing

Drop your schema into `schemas/<family>/` and run:

```
pytest tests/test_core/test_schemas_lint.py -v
```

For live smoke testing with external schemas:

```
ucbtool show ucb.hex --chip tc4d9 --schemas /path/to/my/schemas
```
