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


def test_help_about_menu_present(qtbot, qapp):
    """Help menu exists and About action is reachable."""
    win = MainWindow()
    qtbot.addWidget(win)
    # Read top-level menu titles via their parent QAction.text() — this is a
    # stable reference and avoids shiboken transient-delete of QMenu proxies.
    titles = [a.text() for a in win.menuBar().actions() if a.text()]
    assert "&Help" in titles, f"Help menu missing; found {titles}"
    # About action is wired and named correctly.
    assert hasattr(win, "action_about")
    assert win.action_about.text() == "&About..."


def test_on_about_shows_author(qtbot, qapp, monkeypatch):
    """on_about() should display author name+email via QMessageBox.about()."""
    win = MainWindow()
    qtbot.addWidget(win)
    captured = []
    def fake_about(parent, title, text):
        captured.append((title, text))
    monkeypatch.setattr(
        "ucb_tool.gui.main_window.QMessageBox.about",
        staticmethod(fake_about),
    )
    win.on_about()
    assert len(captured) == 1
    title, text = captured[0]
    assert "UCB Tool" in title
    assert "景飞" in text
    assert "jingfei@xiaomi.com" in text
