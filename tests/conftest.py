"""Top-level pytest config.

Exposes :data:`LEGACY_SCHEMAS_DIR`, a small hand-written BMHD_0 schema
preserved as a legacy fixture. A number of tests (xlsx/CLI/GUI round-
trips) were authored against the pre-UM-extract placeholder schemas;
rather than rewrite them all, they now load this fixture dir instead of
the bundled ``src/ucb_tool/schemas/common/`` tree (which is empty post-
regen).
"""

from pathlib import Path

LEGACY_SCHEMAS_DIR = Path(__file__).parent / "fixtures" / "legacy_schemas"
LEGACY_COMMON_DIR = LEGACY_SCHEMAS_DIR / "common"
