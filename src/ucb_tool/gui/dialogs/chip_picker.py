from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from ucb_tool.core.chip_profile import list_chips


class ChipPickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Chip")
        self.combo = QComboBox()
        self.combo.addItems(list_chips())
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Target chip:"))
        lay.addWidget(self.combo)
        lay.addWidget(btns)

    @property
    def chip_id(self) -> str:
        return self.combo.currentText()
