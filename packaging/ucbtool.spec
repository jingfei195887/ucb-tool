# packaging/ucbtool.spec
# Run: pyinstaller packaging/ucbtool.spec

from pathlib import Path

REPO = Path(SPECPATH).resolve().parent
SCHEMAS = REPO / "src" / "ucb_tool" / "schemas"

datas = [(str(SCHEMAS), "ucb_tool/schemas")]

gui_a = Analysis(
    [str(REPO / "src" / "ucb_tool" / "gui" / "__main__.py")],
    pathex=[str(REPO / "src")],
    datas=datas,
    hiddenimports=["ucb_tool.core", "ucb_tool.gui", "ucb_tool.cli"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
gui_pyz = PYZ(gui_a.pure, gui_a.zipped_data)
gui_exe = EXE(gui_pyz, gui_a.scripts, [],
              exclude_binaries=True,
              name="ucbtool-gui",
              debug=False, strip=False, upx=False, console=False)
gui_coll = COLLECT(gui_exe, gui_a.binaries, gui_a.zipfiles, gui_a.datas,
                   strip=False, upx=False, name="ucbtool-gui")

cli_a = Analysis(
    [str(REPO / "src" / "ucb_tool" / "cli" / "__main__.py")],
    pathex=[str(REPO / "src")],
    datas=datas,
    hiddenimports=["ucb_tool.core", "ucb_tool.cli"],
    excludes=["tkinter", "PySide6"],
    noarchive=False,
)
cli_pyz = PYZ(cli_a.pure, cli_a.zipped_data)
cli_exe = EXE(cli_pyz, cli_a.scripts, [],
              exclude_binaries=True,
              name="ucbtool",
              debug=False, strip=False, upx=False, console=True)
cli_coll = COLLECT(cli_exe, cli_a.binaries, cli_a.zipfiles, cli_a.datas,
                   strip=False, upx=False, name="ucbtool-cli")
