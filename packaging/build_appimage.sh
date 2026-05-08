#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

pyinstaller packaging/ucbtool.spec
APPDIR="$PWD/dist/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR"
cp -r dist/ucbtool-gui "$APPDIR/"
cp packaging/appimage/AppRun "$APPDIR/AppRun" && chmod +x "$APPDIR/AppRun"
cp packaging/appimage/ucbtool-gui.desktop "$APPDIR/"
cp packaging/appimage/ucbtool.png "$APPDIR/ucbtool.png" 2>/dev/null || true

if [ ! -x /tmp/appimagetool ]; then
    curl -L -o /tmp/appimagetool \
      "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x /tmp/appimagetool
fi
ARCH=x86_64 /tmp/appimagetool "$APPDIR" dist/ucbtool-x86_64.AppImage
echo "built dist/ucbtool-x86_64.AppImage"
