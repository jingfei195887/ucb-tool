from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
)

import ucb_tool
from ucb_tool.core.chip_profile import get_profile
from ucb_tool.core.ucb_bundle import UcbBundle
from ucb_tool.core.validator import validate_bundle
from ucb_tool.gui.dialogs.chip_picker import ChipPickerDialog
from ucb_tool.gui.dialogs.danger_confirm import DangerConfirmDialog
from ucb_tool.gui.views.field_form import FieldForm
from ucb_tool.gui.widgets.hex_dump_view import HexDumpView


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("UCB Tool")
        self.resize(1200, 800)
        self._bundle: UcbBundle | None = None
        self._current_chip: str | None = None
        self._source_path: Path | None = None

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["UCB"])
        self.tree.currentItemChanged.connect(self._on_select)

        self.form = FieldForm()

        split = QSplitter()
        split.addWidget(self.tree)
        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(self.form)
        self.hex_dump = HexDumpView()
        right.addWidget(self.hex_dump)
        right.setSizes([600, 200])
        split.addWidget(right)
        split.setSizes([320, 880])
        self.setCentralWidget(split)

        self.advanced_check = QCheckBox("Advanced")
        self.statusBar().addPermanentWidget(self.advanced_check)
        self.advanced_check.toggled.connect(self._on_advanced_toggle)

        bar = self.menuBar().addMenu("&File")
        open_act = QAction("&Open...", self)
        open_act.triggered.connect(self.on_open)
        save_act = QAction("&Save As...", self)
        save_act.triggered.connect(self.on_save)
        self.action_open = open_act
        self.action_save = save_act
        self.action_save.setEnabled(False)
        bar.addAction(open_act)
        bar.addAction(save_act)
        apply_act = QAction("&Apply Excel Edits...", self)
        apply_act.triggered.connect(self.on_apply_xlsx)
        bar.addAction(apply_act)

    # ---- Slots ----
    def on_open(self) -> None:
        path_s, _ = QFileDialog.getOpenFileName(self, "Open ucb.hex", "", "Intel HEX (*.hex)")
        if not path_s:
            return
        dlg = ChipPickerDialog(self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        chip = dlg.chip_id
        try:
            bundle = self._load(path_s, chip)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", str(exc))
            return
        self._bundle = bundle
        self._current_chip = chip
        self._source_path = Path(path_s)
        self._populate_tree()
        self.action_save.setEnabled(True)
        self.statusBar().showMessage(f"Loaded {path_s} (chip={chip})")

    def on_save(self) -> None:
        if self._bundle is None or self._current_chip is None or self._source_path is None:
            return
        # Re-load source as baseline (pre-edit state)
        baseline = self._load(str(self._source_path), self._current_chip)
        report = validate_bundle(self._bundle, baseline=baseline)
        if report.has_blocking:
            QMessageBox.critical(
                self, "Validation errors",
                "\n".join(str(e) for e in report.errors + report.constraint_violations),
            )
            return
        danger = report.danger_summary
        if danger:
            dlg = DangerConfirmDialog(danger, self)
            if dlg.exec() != dlg.DialogCode.Accepted:
                return
        path_s, _ = QFileDialog.getSaveFileName(
            self, "Save ucb.hex", "", "Intel HEX (*.hex)"
        )
        if not path_s:
            return
        try:
            self._bundle.save(path_s)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.statusBar().showMessage(f"Wrote {path_s}")

    def on_apply_xlsx(self) -> None:
        if self._bundle is None or self._current_chip is None or self._source_path is None:
            return
        path_s, _ = QFileDialog.getOpenFileName(
            self, "Apply Excel", "", "Excel Workbook (*.xlsx)"
        )
        if not path_s:
            return
        from ucb_tool.core.xlsx_io import apply_xlsx
        try:
            apply_xlsx(self._bundle, path_s)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Apply failed", str(exc))
            return
        baseline = self._load(str(self._source_path), self._current_chip)
        report = validate_bundle(self._bundle, baseline=baseline)
        if report.has_blocking:
            QMessageBox.critical(
                self, "Validation errors",
                "\n".join(str(e) for e in report.errors + report.constraint_violations),
            )
            return
        danger = report.danger_summary
        if danger:
            dlg = DangerConfirmDialog(danger, self)
            if dlg.exec() != dlg.DialogCode.Accepted:
                return
        self.statusBar().showMessage(f"Applied {path_s}")

    # ---- Helpers ----

    #: Tests may append additional schema directories here before calling
    #: :meth:`_load`; the GUI never touches this list itself.
    _extra_common_dirs: list[Path] = []  # noqa: RUF012

    def _load(self, path: str, chip: str) -> UcbBundle:
        root = Path(ucb_tool.__file__).parent / "schemas"
        chip_dir = root / get_profile(chip).schema_dir
        common_dirs = [root / "common", *self._extra_common_dirs]
        return UcbBundle.load(Path(path), chip,
                              common_dirs=common_dirs,
                              chip_schema_dir=chip_dir if chip_dir.is_dir() else None)

    def _populate_tree(self) -> None:
        self.tree.clear()
        assert self._bundle is not None
        for name in self._bundle.instances:
            QTreeWidgetItem(self.tree, [name])

    def _on_select(self, current, previous) -> None:
        if current is None or self._bundle is None:
            return
        name = current.text(0)
        inst = self._bundle.instances.get(name)
        if inst is not None:
            self.form.set_instance(inst)
            self.hex_dump.set_bytes(bytes(inst.buf_orig))

    def _on_advanced_toggle(self, on: bool) -> None:
        if self._bundle:
            for inst in self._bundle.instances.values():
                inst.advanced = on
