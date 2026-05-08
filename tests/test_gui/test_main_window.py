from ucb_tool.gui.main_window import MainWindow


def test_window_starts_empty(qtbot, qapp):
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.isEnabled()
    assert win.windowTitle().startswith("UCB Tool")
    assert win.tree.topLevelItemCount() == 0
    assert win.action_save.isEnabled() is False


def test_chip_picker_populated(qtbot, qapp):
    from ucb_tool.gui.dialogs.chip_picker import ChipPickerDialog
    dlg = ChipPickerDialog()
    qtbot.addWidget(dlg)
    items = [dlg.combo.itemText(i) for i in range(dlg.combo.count())]
    assert "tc4d9" in items
    assert "tc489" in items
