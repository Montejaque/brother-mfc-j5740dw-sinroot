# Guía de instalación y empaquetado

## Usuario final

**AppImage:** marca el archivo como ejecutable (o `chmod +x`) y ejecútalo con doble clic o desde terminal. El AppImage incluye Python y Tkinter. Para que el escáner funcione, `bwrap`, SANE y `simple-scan` deben existir en el sistema.

**ZIP de código fuente:** extrae toda la carpeta y ejecuta `./instalar.sh` como usuario normal. Python 3 y Tkinter deben estar disponibles.

## Construcción

`./build_appimage.sh` genera `dist/Brother_MFC-J5740DW_SinRoot_1.6.0-x86_64.AppImage`. Usa PyInstaller 6.14.2 y `appimagetool` continuo; se recomienda construir desde Ubuntu 20.04 x86_64 para mantener compatibilidad de glibc.

GitHub Actions (`.github/workflows/build-appimage.yml`) compila dentro de un contenedor Ubuntu 20.04, ejecuta validaciones y publica el AppImage y un ZIP completo como artefacto de Actions.
