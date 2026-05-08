from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)


class DangerConfirmDialog(QDialog):
    def __init__(self, changes: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm dangerous changes")
        self.message_label = QLabel()
        lines = ["The following changes carry risk:"]
        for path, danger in changes:
            lines.append(f"  * {path}  [{danger}]")
        self.message_label.setText("\n".join(lines))

        self.consent_checkbox = QCheckBox("I understand the risk and want to proceed")

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = btns.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        self.consent_checkbox.toggled.connect(self.ok_button.setEnabled)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(self.message_label)
        lay.addWidget(self.consent_checkbox)
        lay.addWidget(btns)
