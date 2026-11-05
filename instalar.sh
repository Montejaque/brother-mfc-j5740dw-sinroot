#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  echo "No ejecutes este instalador como root. Inicia sesión con tu usuario normal."
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "No se encuentra Python 3. Debe estar disponible en el sistema."
  exit 1
fi
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
  echo "Falta Python Tkinter. Sin permisos de administrador no se puede instalar globalmente."
  echo "Solicita al administrador que instale python3-tk una sola vez."
  exit 1
fi

SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DEST="$DATA_HOME/brother-mfc-j5740dw/app"
APPS="$DATA_HOME/applications"
mkdir -p "$DEST" "$APPS"

for item in app.py iniciar.sh desinstalar.sh README.md VERSION.txt CHANGELOG.md drivers docs; do
  if [[ -e "$SRC/$item" ]]; then
    rm -rf "$DEST/$item"
    cp -a "$SRC/$item" "$DEST/$item"
  fi
done
chmod +x "$DEST/iniciar.sh" "$DEST/desinstalar.sh" "$DEST/app.py"

if [[ -f "$DEST/drivers/brscan5-1.8.0-0.amd64.deb" ]]; then
  echo "Controlador Brother original incluido: $DEST/drivers/brscan5-1.8.0-0.amd64.deb"
else
  echo "AVISO: no se encuentra el DEB incluido; se intentará descargar desde Brother."
fi

cat > "$APPS/brother-mfc-j5740dw-assistant.desktop" <<DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=Asistente Brother MFC-J5740DW
Comment=Instalación, configuración, diagnóstico y copias de seguridad
Exec="$DEST/iniciar.sh"
Icon=scanner
Terminal=false
Categories=Graphics;Utility;
StartupNotify=true
DESKTOP
chmod +x "$APPS/brother-mfc-j5740dw-assistant.desktop"

DESKTOP_DIR=""
if command -v xdg-user-dir >/dev/null 2>&1; then
  DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
fi
if [[ -n "$DESKTOP_DIR" && "$DESKTOP_DIR" != "/dev/null" ]]; then
  mkdir -p "$DESKTOP_DIR"
  cp "$APPS/brother-mfc-j5740dw-assistant.desktop" "$DESKTOP_DIR/Asistente-Brother-MFC-J5740DW.desktop"
  chmod +x "$DESKTOP_DIR/Asistente-Brother-MFC-J5740DW.desktop"
  if command -v gio >/dev/null 2>&1; then
    gio set "$DESKTOP_DIR/Asistente-Brother-MFC-J5740DW.desktop" metadata::trusted true 2>/dev/null || true
  fi
fi

echo "Aplicación instalada en: $DEST"
echo "No se han utilizado sudo, dpkg -i ni cambios globales del sistema."
exec "$DEST/iniciar.sh"
