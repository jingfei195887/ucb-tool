from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ucb_tool.core.ucb_bundle import FieldDescriptor, UcbInstance
from ucb_tool.gui.widgets.editors import (
    BoolCheck,
    EnumCombo,
    HexIntEdit,
    PasswordEdit,
)


class _ToggleLabel(QLabel):
    """QLabel that toggles visibility of a paired widget on single-click.

    Used for field rows and bitfield group headers: user clicks the label,
    the paired editor or child group hides; click again to show.
    """

    def __init__(self, text: str, target: QWidget, parent=None):
        super().__init__(text, parent)
        self._target = target
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to hide/show this field")

    def mousePressEvent(self, ev: QMouseEvent) -> None:  # noqa: N802 (Qt API)
        if ev.button() == Qt.MouseButton.LeftButton:
            self._target.setVisible(not self._target.isVisible())
            # Prepend a visual marker so user sees which rows are collapsed.
            t = self.text()
            if self._target.isVisible():
                if t.startswith("⊞ "):
                    self.setText(t[2:])
            else:
                if not t.startswith("⊞ "):
                    self.setText(f"⊞ {t}")
        super().mousePressEvent(ev)


class FieldForm(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._inner = QWidget()
        self._outer_layout = QVBoxLayout(self._inner)
        self._outer_layout.setContentsMargins(4, 4, 4, 4)
        # Header label shows selected UCB's name + address + state.
        self._header = QLabel("(no UCB selected)")
        hdr_font = QFont()
        hdr_font.setBold(True)
        hdr_font.setPointSize(hdr_font.pointSize() + 1)
        self._header.setFont(hdr_font)
        self._outer_layout.addWidget(self._header)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        self._outer_layout.addWidget(sep)
        self._form_holder = QWidget()
        self._layout = QFormLayout(self._form_holder)
        self._layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._outer_layout.addWidget(self._form_holder)
        self._outer_layout.addStretch(1)
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

    def _clear_form(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._widgets.clear()

    def _set_header(self, inst: UcbInstance | None) -> None:
        if inst is None:
            self._header.setText("(no UCB selected)")
            return
        name = inst.schema.name
        addr = f"0x{inst.orig_addr:08X}"
        copy = f" + COPY @ 0x{inst.copy_addr:08X}" if inst.copy_addr else ""
        tag = "" if inst.present else "   [EMPTY — not in loaded hex]"
        self._header.setText(f"[{name}]  @ {addr}{copy}{tag}")

    def set_instance(self, inst: UcbInstance) -> None:
        self._clear_form()
        self._inst = inst
        self._set_header(inst)

        # Disable editing + show empty placeholders when UCB isn't present in hex.
        self._form_holder.setEnabled(inst.present)

        for f in inst.fields:
            label_text = f"{f.path}  [{f.danger}]"
            if f.schema.get("x-bitfield"):
                # Show bitfield parent as a non-editing group header — clicking
                # it toggles display of the parent value row (a read-only hex
                # dump of the packed word).  Children appear as separate rows
                # below (emitted with full dotted paths by _walk_fields).
                parent_lbl_widget = QLabel(f"— {f.path}  (bitfield, {f.size}B)")
                parent_lbl_widget.setStyleSheet("color: #666; font-style: italic;")
                hex_widget = QLabel()
                try:
                    packed = inst.get(f.path)
                    hex_widget.setText(f"0x{packed:0{f.size * 2}X}")
                except Exception:  # noqa: BLE001
                    hex_widget.setText("—")
                hex_widget.setStyleSheet("color: #888;")
                toggle = _ToggleLabel(label_text, hex_widget)
                self._layout.addRow(toggle, hex_widget)
                # Use parent_lbl_widget as a stash to retain reference; otherwise
                # it'd be garbage-collected.  (Kept simple: we don't show it
                # separately from toggle since toggle already labels the row.)
                parent_lbl_widget.setParent(hex_widget)
                parent_lbl_widget.hide()
                continue

            # Regular leaf field: real editor.
            editor = self._make_editor(f)
            try:
                current = inst.get(f.path)
            except Exception:  # noqa: BLE001
                current = 0
            if inst.present:
                editor.set_value(current)
            else:
                # Empty placeholder for missing UCB: leave editors blank where
                # possible so 0xFFFFFFFF isn't shown as if it were real data.
                import contextlib
                with contextlib.suppress(Exception):
                    editor.set_value(0)
            if not f.read_only:
                editor.valueChanged.connect(
                    lambda v, path=f.path: self._inst.set(path, int(v)))
            self._widgets[f.path] = editor
            toggle = _ToggleLabel(label_text, editor)
            self._layout.addRow(toggle, editor)

    def row_count(self) -> int:
        return self._layout.rowCount()

    def set_value(self, path: str, value: int) -> None:
        w = self._widgets.get(path)
        if w is None:
            raise KeyError(path)
        w.set_value(value)
        if self._inst is not None:
            self._inst.set(path, value)
