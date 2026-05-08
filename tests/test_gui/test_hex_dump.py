from ucb_tool.gui.widgets.hex_dump_view import HexDumpView


def test_renders_16byte_rows(qtbot, qapp):
    v = HexDumpView()
    qtbot.addWidget(v)
    v.set_bytes(bytes(range(32)))
    text = v.toPlainText()
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 2
    assert "00 01 02 03" in lines[0]
    assert "10 11 12 13" in lines[1]
