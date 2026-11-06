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

# Release 1.6.1: current Puntos Vuela identity (corporate yellow + black).
app = app_path.read_text(encoding="utf-8")
app = app.replace('APP_VERSION = "1.6.0"', 'APP_VERSION = "1.6.1"', 1)
app = app.replace('# Paleta de identidad visual Puntos Vuela (amarillo principal y colores de apoyo).',
                  '# Identidad visual actual Puntos Vuela: amarillo corporativo y negro.')
app = app.replace('    "green": "#7BA880",\n', '    "black": "#000000",\n')
app = app.replace('    "green_soft": "#EDF4EE",\n', '')
app = app.replace('    "olive": "#AE9E3A",\n', '    "olive": "#C8A82E",\n')
app = app.replace('    "ink": "#26332C",\n', '    "ink": "#111111",\n')
app = app.replace('    "muted": "#66736B",\n', '    "muted": "#666666",\n')
app = app.replace('    "line": "#E8E4D8",\n', '    "line": "#E5E1D6",\n')
app = app.replace('    "log_bg": "#27332D",\n', '    "log_bg": "#111111",\n')
app = app.replace('BRAND["green"]', 'BRAND["black"]')
app = app.replace('BRAND["green_soft"]', 'BRAND["yellow_soft"]')
app = app.replace('1.6.0', '1.6.1')
app_path.write_text(app, encoding="utf-8")

html = html_path.read_text(encoding="utf-8")
html = html.replace("1.6.0", "1.6.1")
html = html.replace('--yellow:#F3D54E; --green:#7BA880; --coral:#E56359; --olive:#AE9E3A;',
                    '--yellow:#F3D54E; --black:#000000; --coral:#E56359; --olive:#C8A82E;')
html = html.replace('--blue:#87ACD4; --ink:#26332C; --muted:#68756D; --paper:#FBFAF6;',
                    '--blue:#87ACD4; --ink:#111111; --muted:#666666; --paper:#FBFAF6;')
html = html.replace('--line:#E6E1D5; --soft-yellow:#FFF7D8; --soft-green:#EDF4EE;',
                    '--line:#E5E1D6; --soft-yellow:#FFF8D9;')
html = html.replace('var(--green)', 'var(--black)').replace('var(--soft-green)', 'var(--soft-yellow)')
html = html.replace('.callout.green', '.callout.brand').replace('callout green', 'callout brand')
for old, new in [('#4F5D54','#555555'),('#3E6947','#111111'),('#EDF1EB','#F4F4F4'),
                 ('#BBD4BE','#F3D54E'),('#D8E3D8','#EEEEEE'),('#26332C','#111111'),('#DDE8DD','#EEEEEE')]:
    html = html.replace(old,new)
html = html.replace('border:3mm solid var(--black)', 'border:3mm solid var(--yellow)')
html = html.replace('color:var(--olive);', 'color:var(--black);').replace('color:var(--coral);', 'color:var(--black);')
html = html.replace('background:linear-gradient(90deg,var(--yellow) 0 35%,var(--green) 35% 55%,var(--coral) 55% 70%,var(--olive) 70% 85%,var(--blue) 85% 100%);',
                    'background:var(--yellow); border-right:35mm solid var(--black);')
html = html.replace('font-weight:750','font-weight:700').replace('font-weight:780','font-weight:800').replace('font-weight:730','font-weight:700').replace('font-weight:720','font-weight:700')
html = html.replace('La versión 1.6.0 incorpora','La versión 1.6.1 incorpora')
html = html.replace('1 / 4</div>', '1 / 5</div>').replace('2 / 4</div>', '2 / 5</div>').replace('3 / 4</div>', '3 / 5</div>')
marker = '<p class="lead">Guía de instalación, configuración y gestión del escáner por Wi-Fi en Ubuntu y Debian, sin privilegios de administrador.</p>'
if "Identidad visual actual Puntos Vuela" not in html:
    html = html.replace(marker, marker + '\n  <p class="small"><strong>Identidad visual actual Puntos Vuela:</strong> amarillo corporativo y negro.</p>')
html_path.write_text(html, encoding="utf-8")

readme_path = ROOT / "README.md"
readme = readme_path.read_text(encoding="utf-8").replace("1.6.0", "1.6.1")
if "## Identidad visual" not in readme:
    readme = readme.replace("## Descargas y formatos",
        "## Identidad visual\n\nLa interfaz, el icono y la documentación siguen la identidad visual actual de Puntos Vuela: amarillo corporativo #F3D54E y negro #000000. Se han retirado los tonos y fondos verdes heredados.\n\n## Descargas y formatos", 1)
readme_path.write_text(readme, encoding="utf-8")

version_path = ROOT / "VERSION.txt"
version = version_path.read_text(encoding="utf-8").replace("1.6.0", "1.6.1")
if "Identidad visual:" not in version:
    version += "Identidad visual: amarillo corporativo #F3D54E y negro #000000; sin tonos verdes.\n"
version_path.write_text(version, encoding="utf-8")

change_path = ROOT / "CHANGELOG.md"
change = change_path.read_text(encoding="utf-8")
if "## 1.6.1" not in change:
    change = change.replace("# Historial de cambios\n",
        "# Historial de cambios\n\n## 1.6.1\n- Actualizada la identidad visual de la interfaz y documentación al amarillo #F3D54E y negro #000000 de Puntos Vuela.\n- Eliminados los acentos y fondos verdes; los fondos suaves pasan a amarillo claro y neutros.\n- Actualizados el icono de aplicación, manual PDF, AppImage y ZIP.\n\n", 1)
change_path.write_text(change, encoding="utf-8")

for rel in ("docs/README_INSTALACION.md", "docs/REFERENCIAS.md", "brother-mfc-j5740dw.desktop"):
    p = ROOT / rel
    if not p.exists():
        continue
    content = p.read_text(encoding="utf-8").replace("1.6.0", "1.6.1")
    if rel == "docs/REFERENCIAS.md" and "identidad visual actual" not in content:
        content += "\n\nIdentidad visual actual: https://puntosvuela.es/ (amarillo corporativo y negro).\n"
    p.write_text(content, encoding="utf-8")

import base64
(ROOT / "assets/brother-mfc-j5740dw.png").write_bytes(base64.b64decode("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"))

print("Preparación 1.6.1 terminada")
