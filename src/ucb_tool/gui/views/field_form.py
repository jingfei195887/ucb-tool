from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QScrollArea, QWidget

from ucb_tool.core.ucb_bundle import FieldDescriptor, UcbInstance
from ucb_tool.gui.widgets.editors import (
    BoolCheck,
    EnumCombo,
    HexIntEdit,
    PasswordEdit,
)


class FieldForm(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._inner = QWidget()
        self._layout = QFormLayout(self._inner)
        self.setWidget(self._inner)
        self._inst: UcbInstance | None = None
        self._widgets: dict[str, object] = {}

    def _make_editor(self, f: FieldDescriptor):
        render = f.schema.get("x-render")
        if f.schema.get("type") == "boolean":
            return BoolCheck()
        enums = f.schema.get("x-enum-names") or {}
        if enums:
            mapping = {int(k): v for k, v in enums.items()}
            return EnumCombo(mapping)
        if render == "password":
            return PasswordEdit()
        return HexIntEdit(max_bits=f.size * 8)

    def set_instance(self, inst: UcbInstance) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._widgets.clear()
        self._inst = inst
        for f in inst.fields:
            if f.schema.get("x-bitfield"):
                continue  # skip parent display row
            label = QLabel(f"{f.path}  [{f.danger}]")
            editor = self._make_editor(f)
            try:
                current = inst.get(f.path)
            except Exception:  # noqa: BLE001
                current = 0
            editor.set_value(current)
            if not f.read_only:
                editor.valueChanged.connect(
                    lambda v, path=f.path: self._inst.set(path, int(v)))
            self._widgets[f.path] = editor
            self._layout.addRow(label, editor)

    def row_count(self) -> int:
        return self._layout.rowCount()

    def set_value(self, path: str, value: int) -> None:
        w = self._widgets.get(path)
        if w is None:
            raise KeyError(path)
        w.set_value(value)
        if self._inst is not None:
            self._inst.set(path, value)
