from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from intelhex import IntelHex, IntelHexError

from ucb_tool.core.errors import HexParseError


def _to_sparse(ih: IntelHex) -> dict[int, int]:
    out: dict[int, int] = {}
    for seg_start, seg_end in ih.segments():
        for a in range(seg_start, seg_end):
            out[a] = ih[a]
    return out


def read_hex(path: str | Path) -> dict[int, int]:
    """Parse an Intel HEX file into a sparse {address: byte} map.

    Raises HexParseError on malformed input.
    """
    ih = IntelHex()
    try:
        ih.loadhex(str(path))
    except (IntelHexError, ValueError) as exc:
        raise HexParseError(f"{path}: {exc}") from exc
    return _to_sparse(ih)


def write_hex(path: str | Path, data: Mapping[int, int]) -> None:
    """Write a sparse address map back as Intel HEX (extended linear addressing)."""
    ih = IntelHex()
    for addr, byte in data.items():
        ih[addr] = byte
    ih.write_hex_file(str(path))


def slice_range(data: Mapping[int, int], start: int, length: int) -> bytes:
    """Extract a contiguous byte slice. Missing bytes default to 0xFF (erased flash)."""
    return bytes(data.get(start + i, 0xFF) for i in range(length))


def merge_range(data: dict[int, int], start: int, blob: bytes) -> None:
    """Overwrite `blob` into `data` starting at `start`."""
    for i, b in enumerate(blob):
        data[start + i] = b
