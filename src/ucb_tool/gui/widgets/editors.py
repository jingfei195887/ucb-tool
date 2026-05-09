from __future__ import annotations

import contextlib

from PySide6.QtCore import QRegularExpression, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)


class HexIntEdit(QWidget):
    valueChanged = Signal(int)

    def __init__(self, max_bits: int = 32, parent=None):
        super().__init__(parent)
        self.max = (1 << max_bits) - 1
        self.edit = QLineEdit()
        self.edit.setValidator(QRegularExpressionValidator(
            QRegularExpression(r"^(0x)?[0-9a-fA-F]+$")))
        self.edit.editingFinished.connect(self._emit)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.edit)

    def _emit(self):
        text = self.edit.text().strip()
        if not text:
            return
        try:
            v = int(text, 16) if not text.startswith("0x") else int(text, 0)
        except ValueError:
            return
        if 0 <= v <= self.max:
            self.valueChanged.emit(v)

    def set_value(self, v: int) -> None:
        self.edit.setText(f"0x{v:X}")


class PasswordEdit(QWidget):
    valueChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setValidator(QRegularExpressionValidator(
            QRegularExpression(r"^(0x)?[0-9a-fA-F]+$")))
        self.btn = QPushButton("show")
        self.btn.setCheckable(True)
        self.btn.toggled.connect(lambda on: self.edit.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.edit)
        lay.addWidget(self.btn)
        self.edit.editingFinished.connect(self._emit)

    def _emit(self):
        with contextlib.suppress(ValueError):
            self.valueChanged.emit(int(self.edit.text(), 16))

    def set_value(self, v: int) -> None:
        self.edit.setText(f"{v:X}")


class EnumCombo(QComboBox):
    """Editable combo: known enum values shown with labels; user may type
    any other value as hex (e.g. ``0x12A4``) and it's accepted if parseable.

    Emits ``valueChanged(int)`` whenever the resolved numeric value changes.
    """

    valueChanged = Signal(int)

    def __init__(self, mapping: dict[int, str], parent=None):
        super().__init__(parent)
        self._mapping = mapping
        self.setEditable(True)
        for val, label in mapping.items():
            # Show both the hex value and the human label so the user always
            # sees the underlying number (e.g. "0x00F7 — Alternate Boot Mode").
            self.addItem(f"0x{val:04X} — {label}", val)
        self.currentIndexChanged.connect(self._on_index_change)
        self.lineEdit().editingFinished.connect(self._on_text_edit)

    def _on_index_change(self, i: int) -> None:
        data = self.itemData(i)
        if isinstance(data, int):
            self.valueChanged.emit(data)

    def _on_text_edit(self) -> None:
        text = self.currentText().strip()
        # If user picked a known label, index path already fired — skip.
        if self.currentIndex() >= 0 and self.itemText(self.currentIndex()) == text:
            return
        # Try to parse the typed text as a hex / dec integer.
        try:
            # Accept "0x12A4", "12A4", "0x12A4 — some label" (take leading token)
            token = text.split()[0] if text else ""
            v = int(token, 16) if not token.startswith(("0x", "0X")) else int(token, 0)
        except (ValueError, IndexError):
            return
        self.valueChanged.emit(v)

    def set_value(self, v: int) -> None:
        for i in range(self.count()):
            if self.itemData(i) == v:
                self.setCurrentIndex(i)
                return
        # Unknown value — show it as editable text.
        self.setEditText(f"0x{v:X}")


class BoolCombo(QComboBox):
    """Disabled / Enabled dropdown — replaces a plain checkbox for boolean
    fields so the value is as prominent as enum dropdowns elsewhere."""

    valueChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.addItem("Disabled (0)", 0)
        self.addItem("Enabled (1)", 1)
        self.currentIndexChanged.connect(
            lambda i: self.valueChanged.emit(self.itemData(i)))

    def set_value(self, v: int) -> None:
        self.setCurrentIndex(1 if bool(v) else 0)


# Backwards-compatible alias for tests / call sites that still reference
# BoolCheck; the new implementation is presented as a dropdown but still
# conforms to the same set_value / valueChanged protocol.
BoolCheck = BoolCombo
