#!/usr/bin/env python3
"""Actualiza desde la base 1.5.0 la versión 1.6.0 para el pipeline de publicación."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
app_path = ROOT / "app.py"
app = app_path.read_text(encoding="utf-8")

app = app.replace('APP_VERSION = "1.5.0"', 'APP_VERSION = "1.6.0"', 1)
app = app.replace(
    'APP_DIR = Path(__file__).resolve().parent',
    '''# En PyInstaller, los recursos se ubican en sys._MEIPASS; en código, junto a app.py.
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
IS_FROZEN = bool(getattr(sys, "frozen", False))
APPIMAGE_PATH = Path(os.environ.get("BROTHER_APPIMAGE") or os.environ.get("APPIMAGE") or sys.argv[0]).expanduser().resolve() if IS_FROZEN else None


def get_icon_resource():
    candidates = [APP_DIR / "assets" / "brother-mfc-j5740dw.png", APP_DIR / "brother-mfc-j5740dw.png"]
    return next((p for p in candidates if p.is_file()), None)''',
    1,
)

shortcut_start = app.index("def create_shortcuts(log=None):")
shortcut_end = app.index("def launch_simple_scan(", shortcut_start)
new_shortcuts = '''def create_shortcuts(log=None):
    """Crea accesos del menú y escritorio tanto en modo fuente como AppImage."""
    if IS_FROZEN:
        launcher = APPIMAGE_PATH
        if not launcher or not launcher.is_file():
            raise SetupError("No se ha podido localizar el archivo AppImage original. Inicia la aplicación directamente desde el archivo .AppImage.")
    else:
        launcher = APP_DIR / "iniciar.sh"
        if not launcher.exists():
            raise SetupError("No se encuentra iniciar.sh junto a la aplicación.")

    applications = XDG_DATA_HOME / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    icon_value = "scanner"
    icon_source = get_icon_resource()
    if icon_source:
        icon_target = XDG_DATA_HOME / "icons" / "hicolor" / "256x256" / "apps" / "brother-mfc-j5740dw.png"
        icon_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon_source, icon_target)
        icon_value = str(icon_target)

    exec_path = str(launcher).replace("\\\\", "\\\\\\\\").replace('"', '\\\\"')
    launcher_command = f'"{exec_path}"'
    entries = [
        ("brother-mfc-j5740dw-assistant.desktop", "Asistente Brother MFC-J5740DW", "Gestionar instalación, diagnóstico y configuración Brother", launcher_command),
        ("brother-mfc-j5740dw-scanner.desktop", "Escáner Brother MFC-J5740DW", "Escanear con el alimentador automático Brother", launcher_command + " --scan"),
    ]
    desktop_contents = {}
    for filename, name, comment, command in entries:
        contents = (
            "[Desktop Entry]\\n"
            "Version=1.0\\n"
            "Type=Application\\n"
            f"Name={name}\\n"
            f"Comment={comment}\\n"
            f"Exec={command}\\n"
            f"Icon={icon_value}\\n"
            "Terminal=false\\n"
            "Categories=Graphics;Utility;\\n"
            "StartupNotify=true\\n"
        )
        target = applications / filename
        target.write_text(contents, encoding="utf-8")
        target.chmod(0o755)
        desktop_contents[filename] = contents

    desktop_dir = None
    try:
        r = run_capture(["xdg-user-dir", "DESKTOP"], timeout=5)
        candidate = Path(r.stdout.strip()) if r.returncode == 0 else None
        if candidate and str(candidate) not in ("", "/dev/null"):
            desktop_dir = candidate
    except Exception:
        pass
    if desktop_dir is None:
        for name in ("Escritorio", "Desktop"):
            candidate = HOME / name
            if candidate.exists():
                desktop_dir = candidate
                break
    if desktop_dir:
        desktop_dir.mkdir(parents=True, exist_ok=True)
        names = ["Asistente-Brother-MFC-J5740DW.desktop", "Escaner-Brother-MFC-J5740DW.desktop"]
        for (filename, _, _, _), dest_name in zip(entries, names):
            copy = desktop_dir / dest_name
            copy.write_text(desktop_contents[filename], encoding="utf-8")
            copy.chmod(0o755)
            if shutil.which("gio"):
                run_capture(["gio", "set", str(copy), "metadata::trusted", "true"], timeout=5)
    if log:
        log("Accesos del asistente y del escáner creados" + (" desde el AppImage" if IS_FROZEN else " desde el proyecto") + (" en el menú de aplicaciones y en el escritorio." if desktop_dir else " en el menú de aplicaciones."))


'''
app = app[:shortcut_start] + new_shortcuts + app[shortcut_end:]

uninstall_start = app.index("    def uninstall_application(self):")
uninstall_end = app.index("\ndef main():", uninstall_start)
new_uninstall = '''    def uninstall_application(self):
        if IS_FROZEN:
            if not messagebox.askyesno("Quitar accesos directos", "Se eliminarán los accesos directos creados por el asistente. El archivo AppImage no se borrará; podrás eliminarlo manualmente cuando quieras. La configuración Brother/SANE y el controlador extraído se conservarán. ¿Continuar?"):
                return
            try:
                applications = XDG_DATA_HOME / "applications"
                for name in ("brother-mfc-j5740dw-assistant.desktop", "brother-mfc-j5740dw-scanner.desktop"):
                    (applications / name).unlink(missing_ok=True)
                for folder in (HOME / "Desktop", HOME / "Escritorio"):
                    for name in ("Asistente-Brother-MFC-J5740DW.desktop", "Escaner-Brother-MFC-J5740DW.desktop"):
                        (folder / name).unlink(missing_ok=True)
                messagebox.showinfo("Accesos retirados", "Se han eliminado los accesos directos. Para desinstalar el formato AppImage, elimina el archivo .AppImage. Los datos del escáner no se han borrado.")
                self.destroy()
            except Exception as exc:
                messagebox.showerror("No se pudieron retirar los accesos", str(exc))
            return
        script = APP_DIR / "desinstalar.sh"
        if not script.is_file():
            messagebox.showerror("Desinstalador no encontrado", f"No se encuentra {script}")
            return
        if not messagebox.askyesno("Desinstalar aplicación", "Se eliminarán la aplicación y sus accesos directos. Se conservarán el controlador extraído y la configuración Brother/SANE. ¿Continuar?"):
            return
        try:
            subprocess.Popen(["bash", str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            self.destroy()
        except Exception as exc:
            messagebox.showerror("No se pudo desinstalar", str(exc))
'''
app = app[:uninstall_start] + new_uninstall + app[uninstall_end:]

faq_marker = '            ("¿Cómo selecciono el alimentador?",'
faq_add = '''            ("¿Cómo ejecuto la versión AppImage?", "Descarga Brother_MFC-J5740DW_SinRoot_1.6.0-x86_64.AppImage, marca el archivo como ejecutable y ábrelo. No necesita instalar Python/Tkinter. Para escanear siguen siendo necesarios bubblewrap, SANE y simple-scan en el sistema."),
'''
if faq_marker in app and "¿Cómo ejecuto la versión AppImage?" not in app:
    app = app.replace(faq_marker, faq_add + faq_marker, 1)

diag_marker = '        rows.append(("OK" if self.inter_available else "AVISO", "Tipografía", "Inter disponible" if self.inter_available else f"Se está usando {self.ui_font_family}", "ok" if self.inter_available else "warn"))'
diag_add = diag_marker + '\n        rows.append(("OK" if IS_FROZEN else "INFO", "Formato de aplicación", f"AppImage portable: {APPIMAGE_PATH}" if IS_FROZEN else "Ejecución desde carpeta de proyecto", "ok" if IS_FROZEN else "warn"))'
if diag_marker in app and '"Formato de aplicación"' not in app:
    app = app.replace(diag_marker, diag_add, 1)

app_path.write_text(app, encoding="utf-8")

html_path = ROOT / "docs/source/guia.html"
html = html_path.read_text(encoding="utf-8")
html = html.replace("Versión 1.5.0", "Versión 1.6.0")
html = html.replace("Guía PDF de cuatro páginas", "Guía PDF de cinco páginas")
html = html.replace("<div class=\"right\">4 / 4</div>", "<div class=\"right\">4 / 5</div>")
if "04 · Distribución AppImage y ZIP" not in html:
    page5 = '''
<section class="page">
  <div class="topline"></div>
  <div class="eyebrow">04 · Distribución AppImage y ZIP</div>
  <h2>Ejecuta la herramienta sin instalar Python</h2>
  <p>La versión 1.6.0 incorpora un paquete AppImage de 64 bits. Incluye el intérprete Python y Tkinter utilizados por la interfaz, junto con el controlador DEB original, la guía y el icono. Se abre directamente desde el escritorio Linux.</p>
  <div class="callout green"><strong>Formato recomendado:</strong> AppImage para el uso diario. No necesita ejecutar el instalador del proyecto ni instalar Python/Tkinter por separado.</div>
  <h3>Primer inicio</h3>
  <div class="step"><div class="step-no"><span>1</span></div><div class="step-body"><strong>Descarga el archivo AppImage.</strong><p>Nombre: <strong>Brother_MFC-J5740DW_SinRoot_1.6.0-x86_64.AppImage</strong>.</p></div></div>
  <div class="step"><div class="step-no"><span>2</span></div><div class="step-body"><strong>Permite su ejecución.</strong><p>En Propiedades, activa «Permitir ejecutar como programa», o abre una terminal en su carpeta.</p></div></div>
  <div class="code">chmod +x Brother_MFC-J5740DW_SinRoot_1.6.0-x86_64.AppImage<br>./Brother_MFC-J5740DW_SinRoot_1.6.0-x86_64.AppImage</div>
  <div class="step"><div class="step-no"><span>3</span></div><div class="step-body"><strong>Detecta y configura la impresora.</strong><p>En Inicio, pulsa Detectar o introduce la IP; continúa con Instalar y configurar. Desde Gestión puedes crear accesos directos persistentes.</p></div></div>
  <h3 style="margin-top:5mm">Qué incluye cada formato</h3>
  <table class="ui-list">
    <tr><td>AppImage</td><td>Ejecutable único, interfaz incluida, recursos del controlador Brother, guía PDF e icono. No escribe en el sistema hasta que el usuario ejecuta las acciones de instalación por perfil.</td></tr>
    <tr><td>ZIP completo</td><td>Código fuente, scripts de instalación y desinstalación, PDF, HTML editable, referencias, icono, DEB y el AppImage compilado.</td></tr>
    <tr><td>Accesos</td><td>Gestión &gt; Crear accesos directos registra el AppImage original en el menú y en el escritorio. Quitar accesos no elimina el archivo ni los datos del escáner.</td></tr>
  </table>
  <div class="warning"><strong>Dependencias del sistema:</strong> AppImage no incluye ni instala bubblewrap, SANE/libsane o simple-scan. Estos componentes deben estar disponibles en el equipo y bwrap debe poder utilizar espacios de nombres de usuario. No se eluden las políticas del sistema ni se requieren permisos root para las operaciones que el asistente realiza en el perfil personal.</div>
  <p class="small">Construcción: Ubuntu 20.04 x86_64 · PyInstaller 6.14.2 · AppImageKit appimagetool. El artefacto de AppImage y el ZIP se generan en GitHub Actions; el repositorio es privado y requiere una cuenta autorizada para acceder a la descarga.</p>
  <div class="footer"><div class="left">Punto Vuela Montejaque · AppImage · ZIP · documentación</div><div class="right">5 / 5</div></div>
</section>
'''
    html = html.replace("</body>", page5 + "\n</body>", 1)
html_path.write_text(html, encoding="utf-8")
print("Preparación 1.6.0 terminada")
