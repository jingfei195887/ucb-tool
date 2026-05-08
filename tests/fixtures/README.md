# tests/fixtures/

Real-chip UCB dumps used for end-to-end regression tests.

**Sanitization requirement:** Before committing a dump, overwrite any
HSM passwords and secure-boot public-key material with 0xFF. See
`tools/sanitize_fixture.py`.

Include a header comment at the top of each `.hex` with:
- Source board (e.g., tc4d9_evb B0)
- Capture tool and command (e.g., `openocd flash read_bank ...`)
- Capture date
- Sanitization commit hash applied

`*.hex` files in this directory are loaded by `tests/test_e2e/test_roundtrip.py`.
