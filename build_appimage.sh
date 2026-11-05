#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(awk -F': ' '/^Versión:/ {print $2; exit}' "$ROOT/VERSION.txt")"
ARCH="${ARCH:-x86_64}"
if [[ "$ARCH" != "x86_64" ]]; then
  echo "Este paquete brscan5 incluido solo está preparado para x86_64/amd64." >&2
  exit 2
fi

PYTHON="${PYTHON:-python3}"
TOOL_DIR="$ROOT/build/tools"
APPDIR="$ROOT/build/AppDir"
DIST="$ROOT/dist"
mkdir -p "$TOOL_DIR" "$DIST"

"$PYTHON" -m pip install --disable-pip-version-check "pyinstaller==6.14.2"
"$PYTHON" -m PyInstaller --noconfirm --clean --windowed --onedir \
  --name brother-mfc-j5740dw \
  --icon "$ROOT/assets/brother-mfc-j5740dw.png" \
  --add-data "$ROOT/drivers:drivers" \
  --add-data "$ROOT/docs:docs" \
  --add-data "$ROOT/assets:assets" \
  --distpath "$ROOT/build/pyinstaller-dist" \
  --workpath "$ROOT/build/pyinstaller-work" \
  --specpath "$ROOT/build" \
  "$ROOT/app.py"

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$APPDIR/usr/share/metainfo"
cp -a "$ROOT/build/pyinstaller-dist/brother-mfc-j5740dw" "$APPDIR/usr/lib/"
cp "$ROOT/AppRun" "$APPDIR/AppRun"
cp "$ROOT/brother-mfc-j5740dw.desktop" "$APPDIR/brother-mfc-j5740dw.desktop"
cp "$ROOT/assets/brother-mfc-j5740dw.png" "$APPDIR/brother-mfc-j5740dw.png"
cp "$ROOT/assets/brother-mfc-j5740dw.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/brother-mfc-j5740dw.png"
cp "$ROOT/assets/org.puntosvuela.BrotherMFCJ5740DW.metainfo.xml" "$APPDIR/usr/share/metainfo/org.puntosvuela.BrotherMFCJ5740DW.metainfo.xml"
chmod +x "$APPDIR/AppRun"

cat > "$TOOL_DIR/appimagetool-x86_64.AppImage.url" <<'URL'
https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
URL
if [[ ! -x "$TOOL_DIR/appimagetool-x86_64.AppImage" ]]; then
  curl -fL --retry 3 "$(cat "$TOOL_DIR/appimagetool-x86_64.AppImage.url")" -o "$TOOL_DIR/appimagetool-x86_64.AppImage"
  chmod +x "$TOOL_DIR/appimagetool-x86_64.AppImage"
fi
OUTPUT="$DIST/Brother_MFC-J5740DW_SinRoot_${VERSION}-${ARCH}.AppImage"
rm -f "$OUTPUT"
APPIMAGE_EXTRACT_AND_RUN=1 ARCH="$ARCH" "$TOOL_DIR/appimagetool-x86_64.AppImage" "$APPDIR" "$OUTPUT"
chmod +x "$OUTPUT"
echo "AppImage creado: $OUTPUT"
