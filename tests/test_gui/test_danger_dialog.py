from ucb_tool.gui.dialogs.danger_confirm import DangerConfirmDialog


def test_shows_all_changes(qtbot, qapp):
    dlg = DangerConfirmDialog(changes=[
        ("BMHD_0.STAD", "brick"),
        ("BMHD_0.BMI.HWCFG", "brick"),
        ("USERCFG.PASSWORD[0]", "lock"),
    ])
    qtbot.addWidget(dlg)
    text = dlg.message_label.text()
    assert "STAD" in text and "HWCFG" in text and "PASSWORD" in text
    assert dlg.ok_button.isEnabled() is False  # disabled until checkbox


def test_ok_enables_after_consent(qtbot, qapp):
    dlg = DangerConfirmDialog(changes=[("BMHD_0.STAD", "brick")])
    qtbot.addWidget(dlg)
    dlg.consent_checkbox.setChecked(True)
    assert dlg.ok_button.isEnabled() is True
