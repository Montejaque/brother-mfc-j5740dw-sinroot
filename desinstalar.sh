#!/usr/bin/env bash
set -euo pipefail
if [[ "$(id -u)" -eq 0 ]]; then
  echo "No ejecutes este desinstalador como root."
  exit 1
fi
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_HOME="$DATA_HOME/brother-mfc-j5740dw/app"
rm -f "$DATA_HOME/applications/brother-mfc-j5740dw-assistant.desktop"
rm -f "$DATA_HOME/applications/brother-mfc-j5740dw-scanner.desktop"
for d in "$HOME/Desktop" "$HOME/Escritorio"; do
  rm -f "$d/Asistente-Brother-MFC-J5740DW.desktop"
  rm -f "$d/Escaner-Brother-MFC-J5740DW.desktop"
done
rm -rf "$APP_HOME"
echo "Se ha eliminado la aplicación y sus accesos directos."
echo "Se conservan el controlador extraído y la configuración Brother/SANE."
echo "Para eliminarlos también, borra manualmente $DATA_HOME/brother-mfc-j5740dw y ~/.config/brother/brscan5 y ~/.config/sane-brscan5."
