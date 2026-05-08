from __future__ import annotations

import contextlib

from PySide6.QtCore import QRegularExpression, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
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
    valueChanged = Signal(int)

    def __init__(self, mapping: dict[int, str], parent=None):
        super().__init__(parent)
        self._mapping = mapping
        for val, label in mapping.items():
            self.addItem(label, val)
        self.currentIndexChanged.connect(
            lambda i: self.valueChanged.emit(self.itemData(i)))

    def set_value(self, v: int) -> None:
        for i in range(self.count()):
            if self.itemData(i) == v:
                self.setCurrentIndex(i)
                return


class BoolCheck(QCheckBox):
    valueChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.toggled.connect(lambda on: self.valueChanged.emit(1 if on else 0))

    def set_value(self, v: int) -> None:
        self.setChecked(bool(v))
