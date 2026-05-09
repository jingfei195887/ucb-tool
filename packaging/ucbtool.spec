# packaging/ucbtool.spec
# Run: pyinstaller packaging/ucbtool.spec

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

REPO = Path(SPECPATH).resolve().parent
SCHEMAS = REPO / "src" / "ucb_tool" / "schemas"

schema_data = [(str(SCHEMAS), "ucb_tool/schemas")]

# PySide6: pull in Qt DLLs, platform plugins (qwindows.dll), style plugins,
# translations, and all hidden imports.  Without this, `ucbtool-gui.exe`
# raises "no Qt platform plugin could be initialized" on Windows.
pyside_datas, pyside_binaries, pyside_hiddenimports = collect_all("PySide6")

# Strip unused Qt submodules.  The tool only uses QtCore / QtGui / QtWidgets.
# Removing WebEngine / Qt3D / Charts / DataVisualization / Multimedia / OpenGL /
# Quick / Qml / Pdf / NetworkAuth / RemoteObjects / etc. cuts the bundle from
# ~650 MB back down to ~80 MB.
_HEAVY_QT_MODULES = {
    "PySide6.Qt3D", "PySide6.Qt3DAnimation", "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtHttpServer",
    "PySide6.QtLocation", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetwork", "PySide6.QtNetworkAuth", "PySide6.QtNfc",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtPositioning",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2", "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSensors",
    "PySide6.QtSerialBus", "PySide6.QtSerialPort", "PySide6.QtSpatialAudio",
    "PySide6.QtSql", "PySide6.QtStateMachine", "PySide6.QtSvg",
    "PySide6.QtSvgWidgets", "PySide6.QtTest", "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools", "PySide6.QtWebChannel", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets", "PySide6.QtXml",
}
_pyside_hiddenimports = [m for m in pyside_hiddenimports
                         if not any(m == h or m.startswith(h + ".")
                                    for h in _HEAVY_QT_MODULES)]


def _drop_heavy(items):
    # collect_all returns tuples like (src_path, dest_path); filter on dest path
    out = []
    for src, dest in items:
        dest_low = dest.replace("\\", "/").lower()
        if any(("pyside6/" + h.split(".", 1)[1].lower()) in dest_low
               for h in _HEAVY_QT_MODULES if "." in h):
            continue
        if "qt6webengine" in dest_low or "qt6web" in dest_low or \
           "qt63d" in dest_low or "qt6quick" in dest_low or \
           "qt6qml" in dest_low or "qt6multimedia" in dest_low or \
           "qt6charts" in dest_low or "qt6pdf" in dest_low:
            continue
        out.append((src, dest))
    return out


_pyside_datas = _drop_heavy(pyside_datas)
_pyside_binaries = _drop_heavy(pyside_binaries)

gui_a = Analysis(
    [str(REPO / "src" / "ucb_tool" / "gui" / "__main__.py")],
    pathex=[str(REPO / "src")],
    binaries=_pyside_binaries,
    datas=schema_data + _pyside_datas,
    hiddenimports=["ucb_tool.core", "ucb_tool.gui", "ucb_tool.cli"]
                  + _pyside_hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"] + list(_HEAVY_QT_MODULES),
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
    datas=schema_data,
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
