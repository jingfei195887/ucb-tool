from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit


class HexDumpView(QPlainTextEdit):
    BYTES_PER_ROW = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setReadOnly(True)

    def set_bytes(self, data: bytes) -> None:
        lines = []
        for i in range(0, len(data), self.BYTES_PER_ROW):
            row = data[i:i + self.BYTES_PER_ROW]
            hex_part = " ".join(f"{b:02x}" for b in row)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
            lines.append(
                f"{i:04x}: {hex_part:<{self.BYTES_PER_ROW * 3 - 1}}  {ascii_part}"
            )
        self.setPlainText("\n".join(lines))
