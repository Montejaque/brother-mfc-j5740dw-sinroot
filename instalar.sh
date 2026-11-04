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
  echo "Falta Python Tkinter. No se puede instalar a nivel de sistema sin permisos de administrador."
  echo "Solicita al administrador que instale python3-tk una sola vez."
  exit 1
fi
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/brother-mfc-j5740dw/app"
mkdir -p "$DEST"
if [[ -f "$SRC/drivers/brscan5-1.8.0-0.amd64.deb" ]]; then
  echo "Controlador Brother brscan5 1.8.0-0 incluido."
else
  echo "Aviso: no se encuentra el DEB incluido; la aplicación intentará descargarlo desde Brother."
fi
for item in app.py iniciar.sh README.md drivers docs; do
  if [[ -e "$SRC/$item" ]]; then
    rm -rf "$DEST/$item"
    cp -a "$SRC/$item" "$DEST/$item"
  fi
done
chmod +x "$DEST/iniciar.sh" "$DEST/app.py"
echo "Aplicación copiada a: $DEST"
exec "$DEST/iniciar.sh"
