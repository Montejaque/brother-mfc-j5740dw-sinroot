#!/usr/bin/env python3
# Brother MFC-J5740DW - Asistente de instalación y gestión sin root
# Requiere Python 3 + Tkinter, bubblewrap (bwrap) y simple-scan ya presentes en el sistema.

from __future__ import annotations

import concurrent.futures
import ctypes.util
import ipaddress
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "Brother MFC-J5740DW · Punto Vuela Montejaque"
APP_VERSION = "1.5.0"
MODEL = "MFC-J5740DW"
DEVICE_NAME = "Brother_MFC-J5740DW"
DEVELOPER_NAME = "Francisco Javier Gallego Orellana"
CENTER_NAME = "Punto Vuela Montejaque"
CENTER_ADDRESS = "Avenida Andalucía, 48 · 29360 Montejaque (Málaga)"
CENTER_PHONE = "633 402 959"
CENTER_EMAIL = "montejaque@puntosvuela.es"

# Paleta de identidad visual Puntos Vuela (amarillo principal y colores de apoyo).
BRAND = {
    "yellow": "#F3D54E",
    "green": "#7BA880",
    "coral": "#E56359",
    "olive": "#AE9E3A",
    "blue": "#87ACD4",
    "ink": "#26332C",
    "muted": "#66736B",
    "canvas": "#FBFAF6",
    "white": "#FFFFFF",
    "line": "#E8E4D8",
    "yellow_soft": "#FFF9E5",
    "green_soft": "#EDF4EE",
    "blue_soft": "#EEF4FA",
    "coral_soft": "#FFF0ED",
    "log_bg": "#27332D",
    "log_fg": "#F6F7F3",
}
SUPPORT_URL = "https://support.brother.com/g/b/downloadtop.aspx?c=es&lang=es&prod=mfcj5740dw_eu_as"
# Enlace oficial de Brother para la familia brscan5 (dlf104033).
# Se intenta primero la versión 1.8.0-0, utilizada en la instalación validada,
# y luego versiones publicadas anteriormente por Brother como alternativa.
BUNDLED_DRIVER_NAME = "brscan5-1.8.0-0.amd64.deb"
BUNDLED_DRIVER_SHA256 = "27bf1d561da2223c9807726cc3ec1bd9e7cdce419a27ee79b31a642073174d46"
DRIVER_URLS = [
    "https://download.brother.com/welcome/dlf104033/brscan5-1.8.0-0.amd64.deb",
    "https://download.brother.com/welcome/dlf104033/brscan5-1.7.0-0.amd64.deb",
    "https://download.brother.com/welcome/dlf104033/brscan5-1.6.2-0.amd64.deb",
]

HOME = Path.home()
XDG_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
APP_DATA = XDG_DATA_HOME / "brother-mfc-j5740dw"
CACHE_DIR = APP_DATA / "cache"
EXTRACT_DIR = APP_DATA / "driver-extracted"
DRIVER_ROOT = EXTRACT_DIR / "opt/brother/scanner/brscan5"
USER_CFG = HOME / ".config/brother/brscan5/brsanenetdevice/brsanenetdevice.cfg"
SANE_DIR = HOME / ".config/sane-brscan5"
SANE_DLL = SANE_DIR / "dll.conf"
APP_DIR = Path(__file__).resolve().parent


class SetupError(RuntimeError):
    pass


def run_capture(args, timeout=30):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise SetupError(f"No se encuentra el programa necesario: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SetupError(f"La operación superó el tiempo límite: {args[0]}") from exc


def bwrap_base(driver_root: Path, writable_cfg: bool = True):
    """Construye el espacio de nombres privado usado y probado para Brother 5."""
    etc_base = "/etc/opt/brother/scanner/brscan5"
    opt_base = "/opt/brother/scanner/brscan5"
    cfg = str(USER_CFG)
    args = [
        "bwrap", "--ro-bind", "/", "/",
        "--bind", str(HOME), str(HOME),
        "--bind", "/tmp", "/tmp",
        "--tmpfs", "/opt",
        "--dir", "/opt/brother",
        "--dir", "/opt/brother/scanner",
        "--ro-bind", str(driver_root), opt_base,
        "--tmpfs", "/etc/opt",
        "--dir", "/etc/opt/brother",
        "--dir", "/etc/opt/brother/scanner",
        "--dir", etc_base,
        "--dir", etc_base + "/models",
        "--dir", etc_base + "/brsanenetdevice",
        "--ro-bind", str(driver_root / "models"), etc_base + "/models",
        "--ro-bind", str(driver_root / "brscan5.ini"), etc_base + "/brscan5.ini",
    ]
    if writable_cfg:
        args += ["--bind", cfg, etc_base + "/brsanenetdevice/brsanenetdevice.cfg"]
    else:
        args += ["--ro-bind", cfg, etc_base + "/brsanenetdevice/brsanenetdevice.cfg"]
    args += ["--setenv", "LD_LIBRARY_PATH", opt_base]
    return args


def get_networks():
    nets = set()
    ip_cmd = shutil.which("ip")
    if ip_cmd:
        res = run_capture([ip_cmd, "-o", "-4", "addr", "show", "scope", "global"], timeout=8)
        for line in res.stdout.splitlines():
            m = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+/\d+)", line)
            if not m:
                continue
            try:
                iface = ipaddress.ip_interface(m.group(1))
                net = iface.network
                if iface.ip.is_loopback or iface.ip.is_link_local or not iface.ip.is_private:
                    continue
                if net.num_addresses > 1024:
                    # En redes grandes se limita el sondeo a la subred /24 local.
                    net = ipaddress.ip_network(f"{iface.ip}/24", strict=False)
                nets.add(net)
            except ValueError:
                pass
    if not nets:
        try:
            host = socket.gethostbyname(socket.gethostname())
            ip = ipaddress.ip_address(host)
            if ip.is_private:
                nets.add(ipaddress.ip_network(f"{ip}/24", strict=False))
        except Exception:
            pass
    return sorted(nets, key=lambda n: (n.num_addresses, str(n)))


def probe_escl(ip: str, timeout=1.5):
    url = f"http://{ip}/eSCL/ScannerCapabilities"
    req = urllib.request.Request(url, headers={"User-Agent": "Brother-MFC-J5740DW-Setup/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read(250000).decode("utf-8", "replace")
        if MODEL.lower() in body.lower() and "AdfSimplexInputCaps" in body:
            return ip
    except Exception:
        return None
    return None


def discover_by_network(log=None):
    networks = get_networks()
    if not networks:
        raise SetupError("No se ha podido averiguar la subred Wi-Fi. Introduce la IP manualmente.")
    candidates = []
    for net in networks:
        candidates.extend(str(ip) for ip in net.hosts())
    if not candidates:
        raise SetupError("No hay direcciones de red que comprobar. Introduce la IP manualmente.")
    if log:
        log(f"Buscando {MODEL} en {len(candidates)} direcciones de la red local…")
    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        futures = {pool.submit(probe_escl, ip): ip for ip in candidates}
        for fut in concurrent.futures.as_completed(futures):
            ip = fut.result()
            if ip:
                found.append(ip)
                if log:
                    log(f"Impresora Brother MFC-J5740DW encontrada en {ip}.")
                break
    if not found:
        raise SetupError("No se ha encontrado la MFC-J5740DW automáticamente. Comprueba que el ordenador y la impresora estén en la misma Wi-Fi o introduce la IP manualmente.")
    return found[0]


def verify_device(ip: str):
    try:
        ipaddress.ip_address(ip)
    except ValueError as exc:
        raise SetupError("La dirección IP no es válida.") from exc
    req = urllib.request.Request(f"http://{ip}/eSCL/ScannerCapabilities",
                                 headers={"User-Agent": "Brother-MFC-J5740DW-Setup/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            body = response.read(250000).decode("utf-8", "replace")
    except Exception as exc:
        raise SetupError(f"No se puede consultar el escáner en {ip}: {exc}") from exc
    if MODEL.lower() not in body.lower():
        raise SetupError(f"El equipo {ip} responde, pero no se identifica como {MODEL}.")
    if "AdfSimplexInputCaps" not in body:
        raise SetupError("La impresora responde, pero no anuncia el alimentador ADF en eSCL.")
    status_text = ""
    try:
        with urllib.request.urlopen(f"http://{ip}/eSCL/ScannerStatus", timeout=5) as response:
            status_text = response.read(100000).decode("utf-8", "replace")
    except Exception:
        pass
    adf_loaded = "ScannerAdfLoaded" in status_text
    return adf_loaded


def validate_driver_deb(deb: Path):
    if not deb.is_file() or deb.stat().st_size < 100_000:
        raise SetupError("El archivo DEB está vacío o es demasiado pequeño.")
    with open(deb, "rb") as stream:
        if stream.read(8) != b"!<arch>\n":
            raise SetupError("El archivo seleccionado no tiene formato DEB/ar válido.")
    if deb.name == BUNDLED_DRIVER_NAME and deb.parent.resolve() == (APP_DIR / "drivers").resolve():
        import hashlib
        digest = hashlib.sha256(deb.read_bytes()).hexdigest()
        if digest != BUNDLED_DRIVER_SHA256:
            raise SetupError("El controlador Brother incluido no supera la comprobación de integridad SHA-256. Vuelve a extraer el paquete original.")
    if shutil.which("dpkg-deb"):
        pkg = run_capture(["dpkg-deb", "-f", str(deb), "Package"], timeout=15)
        arch = run_capture(["dpkg-deb", "-f", str(deb), "Architecture"], timeout=15)
        version = run_capture(["dpkg-deb", "-f", str(deb), "Version"], timeout=15)
        if pkg.returncode == 0 and pkg.stdout.strip() != "brscan5":
            raise SetupError(f"El paquete seleccionado no es brscan5 (Package={pkg.stdout.strip()}).")
        if arch.returncode == 0 and arch.stdout.strip() not in ("amd64", "all"):
            raise SetupError(f"El paquete no es para amd64 (Architecture={arch.stdout.strip()}).")
        if version.returncode == 0 and deb.name == BUNDLED_DRIVER_NAME and version.stdout.strip() != "1.8.0-0":
            raise SetupError(f"La versión del controlador incluido no es la esperada (Version={version.stdout.strip()}).")
    return deb


def find_local_deb():
    candidates = []
    bundled = APP_DIR / "drivers"
    preferred = bundled / BUNDLED_DRIVER_NAME
    if preferred.is_file():
        candidates.append(preferred)
    if bundled.exists():
        candidates += [p for p in sorted(bundled.glob("brscan5-*.amd64.deb"), reverse=True) if p != preferred]
    candidates += sorted((HOME / "Downloads").glob("brscan5-*.amd64.deb"), reverse=True) if (HOME / "Downloads").exists() else []
    candidates += sorted((HOME / "Descargas").glob("brscan5-*.amd64.deb"), reverse=True) if (HOME / "Descargas").exists() else []
    candidates += sorted(CACHE_DIR.glob("brscan5-*.amd64.deb"), reverse=True) if CACHE_DIR.exists() else []
    for path in candidates:
        if path.is_file() and path.stat().st_size > 100_000:
            try:
                return validate_driver_deb(path)
            except SetupError:
                continue
    return None


def download_driver(log):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    local = find_local_deb()
    if local:
        if local.resolve().parent == (APP_DIR / "drivers").resolve():
            log(f"Controlador oficial Brother incluido en la aplicación: {local.name}. No se necesita conexión a Internet para descargarlo.")
        else:
            log(f"Se utilizará el paquete Brother disponible localmente: {local}")
        return local
    errors = []
    for url in DRIVER_URLS:
        name = url.rsplit("/", 1)[-1]
        target = CACHE_DIR / name
        tmp = target.with_suffix(target.suffix + ".part")
        log(f"Descargando controlador oficial Brother: {name}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Brother-MFC-J5740DW-Setup/1.0"})
            with urllib.request.urlopen(req, timeout=60) as response, open(tmp, "wb") as out:
                shutil.copyfileobj(response, out)
            if tmp.stat().st_size < 100_000 or tmp.read_bytes()[:8] != b"!<arch>\n":
                raise SetupError("El servidor no ha entregado un paquete DEB válido.")
            tmp.replace(target)
            validate_driver_deb(target)
            log(f"Descarga terminada ({target.stat().st_size // 1024} KB).")
            return target
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            log(f"No se pudo descargar {name}: {exc}")
    raise SetupError("No se ha podido descargar el controlador desde Brother. Comprueba Internet o pulsa «Seleccionar paquete DEB» y elige brscan5-*.amd64.deb.\n\n" + "\n".join(errors))


def ensure_soname_links(driver_root: Path):
    # Replica los enlaces de compatibilidad creados durante la prueba validada.
    patterns = [driver_root / "libsane-brother5.so.1.0.7"]
    patterns += list(driver_root.glob("libLxBs*.so.*.*.*"))
    for lib in patterns:
        if not lib.exists():
            continue
        name = lib.name
        if ".so." not in name:
            continue
        prefix, version = name.split(".so.", 1)
        bits = version.split(".")
        if len(bits) >= 2:
            for count in (1, 2):
                if len(bits) >= count:
                    link = driver_root / (prefix + ".so." + ".".join(bits[:count]))
                    if link == lib:
                        continue
                    if link.exists() or link.is_symlink():
                        if link.is_symlink() and link.resolve() == lib.resolve():
                            continue
                        if link.is_file() and not link.is_symlink():
                            continue
                        link.unlink(missing_ok=True)
                    try:
                        link.symlink_to(lib.name)
                    except OSError:
                        pass


def extract_deb(deb: Path, log):
    if shutil.which("dpkg-deb"):
        shutil.rmtree(EXTRACT_DIR, ignore_errors=True)
        EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        res = run_capture(["dpkg-deb", "-x", str(deb), str(EXTRACT_DIR)], timeout=90)
        if res.returncode != 0:
            raise SetupError("No se pudo extraer el controlador DEB:\n" + res.stdout)
    else:
        # Fallback para sistemas mínimos sin dpkg-deb: desempaqueta data.tar.* del archivo ar.
        import io, tarfile, gzip, lzma, bz2
        shutil.rmtree(EXTRACT_DIR, ignore_errors=True)
        EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        raw = deb.read_bytes()
        if not raw.startswith(b"!<arch>\n"):
            raise SetupError("El archivo no es un paquete DEB válido.")
        pos = 8
        data_blob = None
        data_name = ""
        while pos + 60 <= len(raw):
            header = raw[pos:pos+60]
            if header[58:60] != b"`\n":
                break
            name = header[:16].decode("ascii", "replace").strip().rstrip("/")
            size = int(header[48:58].decode("ascii", "replace").strip() or "0")
            start = pos + 60
            blob = raw[start:start+size]
            if name.startswith("data.tar"):
                data_blob, data_name = blob, name
                break
            pos = start + size + (size % 2)
        if data_blob is None:
            raise SetupError("El DEB no contiene data.tar.")
        if data_name.endswith(".gz"):
            data_blob = gzip.decompress(data_blob)
        elif data_name.endswith(".xz"):
            data_blob = lzma.decompress(data_blob)
        elif data_name.endswith(".bz2"):
            data_blob = bz2.decompress(data_blob)
        with tarfile.open(fileobj=io.BytesIO(data_blob), mode="r:") as tf:
            for member in tf.getmembers():
                p = Path(member.name)
                if p.is_absolute() or ".." in p.parts:
                    continue
                tf.extract(member, EXTRACT_DIR)
    log("Controlador extraído en el espacio privado del usuario.")
    if not (DRIVER_ROOT / "brsaneconfig5").is_file() or not (DRIVER_ROOT / "brscan_cnetconfig").is_file():
        raise SetupError("El paquete no contiene las herramientas brscan5 esperadas.")
    if not (DRIVER_ROOT / "libsane-brother5.so.1.0.7").exists():
        # No fijar un nombre de biblioteca si Brother cambia su versión interna.
        if not list(DRIVER_ROOT.glob("libsane-brother5.so*")):
            raise SetupError("No se encuentra la biblioteca SANE de Brother 5.")
    ensure_soname_links(DRIVER_ROOT)
    backend = next(iter(DRIVER_ROOT.glob("libsane-brother5.so*")), None)
    if backend and shutil.which("ldd"):
        deps = run_capture(["ldd", str(backend)], timeout=15)
        missing = [line.strip() for line in deps.stdout.splitlines() if "not found" in line]
        if missing:
            raise SetupError("Faltan bibliotecas del sistema que el controlador Brother necesita:\n" + "\n".join(missing) + "\n\nEl asistente no puede instalarlas globalmente sin permisos de administrador.")
    log("Dependencias dinámicas del controlador comprobadas.")


def ensure_user_config():
    USER_CFG.parent.mkdir(parents=True, exist_ok=True)
    if not USER_CFG.exists():
        USER_CFG.write_text("", encoding="utf-8")
    SANE_DIR.mkdir(parents=True, exist_ok=True)
    # Mantener eSCL disponible y añadir el backend Brother5.
    entries = [x.strip() for x in SANE_DLL.read_text(encoding="utf-8").splitlines()] if SANE_DLL.exists() else []
    for backend in ("escl", "brother5"):
        if backend not in entries:
            entries.append(backend)
    SANE_DLL.write_text("\n".join(entries) + "\n", encoding="utf-8")


def register_scanner(ip: str, log):
    ensure_user_config()
    driver_root = DRIVER_ROOT
    args = bwrap_base(driver_root, writable_cfg=True)
    binary = "/opt/brother/scanner/brscan5/brsaneconfig5"
    # La configuración puede proceder de una instalación anterior: eliminar la entrada
    # con el mismo nombre antes de crearla de nuevo. Un -r sin entrada se ignora.
    rm_cmd = args + [binary, "-r", DEVICE_NAME]
    run_capture(rm_cmd, timeout=20)
    add_cmd = args + [binary, "-a", f"name={DEVICE_NAME}", f"model={MODEL}", f"ip={ip}"]
    res = run_capture(add_cmd, timeout=30)
    current = USER_CFG.read_text(encoding="utf-8", errors="replace")
    if res.returncode != 0 and not (DEVICE_NAME in current and ip in current):
        raise SetupError("Brother no ha podido registrar el equipo.\n" + res.stdout)
    if DEVICE_NAME not in current or ip not in current:
        raise SetupError("El configurador terminó, pero no apareció la entrada esperada en el archivo personal de dispositivos.")
    q = run_capture(args + [binary, "-q"], timeout=20)
    log("Registro guardado en ~/.config/brother/brscan5/brsanenetdevice/brsanenetdevice.cfg")
    if q.stdout.strip():
        log(q.stdout.strip())


def create_shortcuts(log=None):
    launcher = APP_DIR / "iniciar.sh"
    if not launcher.exists():
        raise SetupError("No se encuentra iniciar.sh junto a la aplicación.")
    applications = XDG_DATA_HOME / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    exec_path = str(launcher).replace("\\", "\\\\").replace('"', '\\"')
    entries = [
        ("brother-mfc-j5740dw-assistant.desktop", "Asistente Brother MFC-J5740DW", "Gestionar instalación, diagnóstico y configuración Brother", f'"{exec_path}"'),
        ("brother-mfc-j5740dw-scanner.desktop", "Escáner Brother MFC-J5740DW", "Escanear con el alimentador automático Brother", f'"{exec_path}" --scan'),
    ]
    desktop_contents = {}
    for filename, name, comment, command in entries:
        contents = (
            "[Desktop Entry]\n"
            "Version=1.0\n"
            "Type=Application\n"
            f"Name={name}\n"
            f"Comment={comment}\n"
            f"Exec={command}\n"
            "Icon=scanner\n"
            "Terminal=false\n"
            "Categories=Graphics;Utility;\n"
            "StartupNotify=true\n"
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
        log("Accesos del asistente y del escáner creados en el menú de aplicaciones" + (" y en el escritorio." if desktop_dir else "."))

def launch_simple_scan(log=None):
    if not DRIVER_ROOT.exists():
        raise SetupError("Primero debes pulsar «Instalar y configurar».")
    if not shutil.which("simple-scan"):
        raise SetupError("No se encuentra Escáner de documentos (simple-scan). Debe estar instalado por el administrador o venir con el sistema.")
    if not shutil.which("bwrap"):
        raise SetupError("No se encuentra bubblewrap (bwrap). No se puede simular /opt y /etc/opt sin permisos de administrador.")
    if not USER_CFG.exists() or DEVICE_NAME not in USER_CFG.read_text(encoding="utf-8", errors="replace"):
        raise SetupError("El escáner aún no está registrado. Pulsa «Instalar y configurar».")
    args = bwrap_base(DRIVER_ROOT, writable_cfg=True)
    args += ["--setenv", "SANE_CONFIG_DIR", str(SANE_DIR), "/usr/bin/simple-scan"]
    if log:
        log("Abriendo Escáner de documentos con Brother 5…")
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except Exception as exc:
        raise SetupError(f"No se pudo abrir Escáner de documentos: {exc}") from exc


def check_prerequisites():
    results = []
    if os.geteuid() == 0:
        results.append(("error", "No ejecutes esta aplicación como root. Cierra la sesión y ábrela con tu usuario normal."))
    if os.uname().machine not in ("x86_64", "amd64"):
        results.append(("error", "El controlador oficial DEB incluido en este asistente es de 64 bits x86_64."))
    for cmd, label in (("bwrap", "bubblewrap (bwrap)"), ("simple-scan", "Escáner de documentos (simple-scan)")):
        if shutil.which(cmd):
            results.append(("ok", f"{label}: disponible"))
        else:
            results.append(("error", f"{label}: no está instalado en el sistema"))
    try:
        r = run_capture(["bwrap", "--ro-bind", "/", "/", "/bin/true"], timeout=6)
        if r.returncode == 0:
            results.append(("ok", "bwrap puede ejecutarse sin root"))
        else:
            results.append(("error", "bwrap está instalado, pero el aislamiento de usuario está bloqueado por el sistema"))
    except Exception as exc:
        results.append(("error", str(exc)))
    if ctypes.util.find_library("sane"):
        results.append(("ok", "Biblioteca SANE: disponible"))
    else:
        results.append(("error", "No se encuentra libsane. Escáner de documentos necesita el sistema SANE instalado."))
    try:
        import tkinter  # noqa: F401
        results.append(("ok", "Interfaz gráfica Python/Tk: disponible"))
    except Exception:
        results.append(("error", "Python Tkinter no está instalado. No se puede añadir globalmente sin permisos de administrador."))
    return results


class App(tk.Tk):
    """Interfaz de gestión unificada para instalación y mantenimiento Brother 5."""

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x820")
        self.minsize(940, 700)
        self.configure(bg=BRAND["canvas"])
        try:
            installed_fonts = list(tkfont.families(self))
            inter_family = next((name for name in installed_fonts if name.casefold() == "inter"), None)
            self.inter_available = inter_family is not None
            self.ui_font_family = inter_family or str(tkfont.nametofont("TkDefaultFont").actual("family"))
        except Exception:
            self.inter_available = False
            self.ui_font_family = "TkDefaultFont"

        self.events = queue.Queue()
        self.busy = False
        self.ip_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Preparado. Detecta tu impresora para comenzar.")
        self.adf_var = tk.StringVar(value="Sin comprobar")
        self.driver_var = tk.StringVar(value="Comprobando controlador incluido…")
        self.action_buttons = []
        self._build_ui()
        self.after(150, self._drain_events)
        self.after(450, self.diagnose)

    def _register_button(self, button):
        self.action_buttons.append(button)
        return button

    def _button(self, parent, label, command, primary=False, **kwargs):
        style = "Primary.TButton" if primary else "TButton"
        b = ttk.Button(parent, text=label, command=command, style=style, **kwargs)
        self._register_button(b)
        return b

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        fam = self.ui_font_family
        normal = (fam, 10)
        self.option_add("*Font", normal)
        style.configure(".", font=normal, background=BRAND["canvas"], foreground=BRAND["ink"])
        style.configure("TFrame", background=BRAND["canvas"])
        style.configure("TLabel", background=BRAND["canvas"], foreground=BRAND["ink"], font=normal)
        style.configure("Muted.TLabel", background=BRAND["canvas"], foreground=BRAND["muted"], font=(fam, 9))
        style.configure("Title.TLabel", background=BRAND["canvas"], foreground=BRAND["ink"], font=(fam, 23, "bold"))
        style.configure("Section.TLabel", background=BRAND["canvas"], foreground=BRAND["green"], font=(fam, 10, "bold"))
        style.configure("TButton", font=(fam, 10), padding=(12, 8), background=BRAND["white"], foreground=BRAND["ink"], bordercolor=BRAND["line"])
        style.map("TButton", background=[("active", BRAND["yellow_soft"]), ("pressed", BRAND["yellow"])])
        style.configure("Primary.TButton", font=(fam, 10, "bold"), padding=(13, 9), background=BRAND["yellow"], foreground=BRAND["ink"], bordercolor=BRAND["yellow"])
        style.map("Primary.TButton", background=[("active", "#E8C63D"), ("pressed", BRAND["olive"])])
        style.configure("TLabelframe", background=BRAND["canvas"], bordercolor=BRAND["line"], relief="solid")
        style.configure("TLabelframe.Label", background=BRAND["canvas"], foreground=BRAND["green"], font=(fam, 10, "bold"))
        style.configure("TEntry", font=normal, fieldbackground=BRAND["white"], foreground=BRAND["ink"], padding=6)
        style.configure("TNotebook", background=BRAND["canvas"], borderwidth=0)
        style.configure("TNotebook.Tab", font=(fam, 10, "bold"), padding=(18, 10), background="#F0EEE6", foreground=BRAND["muted"])
        style.map("TNotebook.Tab", background=[("selected", BRAND["white"])], foreground=[("selected", BRAND["ink"])])
        style.configure("Treeview", font=(fam, 9), rowheight=27, background=BRAND["white"], fieldbackground=BRAND["white"], foreground=BRAND["ink"])
        style.configure("Treeview.Heading", font=(fam, 9, "bold"), background=BRAND["green_soft"], foreground=BRAND["ink"])

        root = ttk.Frame(self, padding=(18, 14, 18, 12))
        root.pack(fill="both", expand=True)
        tk.Frame(root, bg=BRAND["yellow"], height=6).pack(fill="x", pady=(0, 12))

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 10))
        title_col = ttk.Frame(header)
        title_col.pack(side="left", fill="x", expand=True)
        ttk.Label(title_col, text="Brother MFC-J5740DW", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_col, text=f"ASISTENTE DE ESCÁNER · PUNTO VUELA MONTEJAQUE · VERSIÓN {APP_VERSION}", style="Muted.TLabel").pack(anchor="w", pady=(2, 0))
        brand_tag = tk.Label(header, text="SIN ROOT", bg=BRAND["green_soft"], fg=BRAND["ink"], font=(fam, 9, "bold"), padx=14, pady=8)
        brand_tag.pack(side="right", anchor="center", padx=(10, 0))

        status = tk.Frame(root, bg=BRAND["green_soft"], highlightbackground=BRAND["green"], highlightthickness=1)
        status.pack(fill="x", pady=(0, 12))
        tk.Label(status, textvariable=self.status_var, bg=BRAND["green_soft"], fg=BRAND["ink"], font=(fam, 10, "bold"), anchor="w", padx=13, pady=10).pack(fill="x")

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True)
        self.home_tab = ttk.Frame(self.tabs, padding=15)
        self.manage_tab = ttk.Frame(self.tabs, padding=15)
        self.diagnosis_tab = ttk.Frame(self.tabs, padding=15)
        self.help_tab = ttk.Frame(self.tabs, padding=15)
        self.tabs.add(self.home_tab, text="Inicio")
        self.tabs.add(self.manage_tab, text="Gestión")
        self.tabs.add(self.diagnosis_tab, text="Diagnóstico y actividad")
        self.tabs.add(self.help_tab, text="Ayuda y acerca de")
        self._build_home()
        self._build_management()
        self._build_diagnostics()
        self._build_help()

        footer = ttk.Frame(root)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(footer, text=f"Desarrollador: {DEVELOPER_NAME}  ·  {CENTER_NAME}", style="Muted.TLabel").pack(side="left")
        ttk.Label(footer, text=f"{CENTER_PHONE}  ·  {CENTER_EMAIL}", style="Muted.TLabel").pack(side="right")

    def _build_home(self):
        top = ttk.Frame(self.home_tab)
        top.pack(fill="x", pady=(0, 11))
        ttk.Label(top, text="Configura y empieza a escanear", font=(self.ui_font_family, 16, "bold")).pack(anchor="w")
        ttk.Label(top, text="El asistente utiliza el paquete Brother brscan5 incluido en esta carpeta y lo prepara dentro de tu perfil de usuario.", style="Muted.TLabel", wraplength=980).pack(anchor="w", pady=(3, 0))

        cards = ttk.Frame(self.home_tab)
        cards.pack(fill="x", pady=(0, 10))
        net = ttk.LabelFrame(cards, text="1 · Conexión Wi-Fi", padding=13)
        net.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ttk.Label(net, text="IP de la MFC-J5740DW (opcional):", style="Muted.TLabel").pack(anchor="w")
        iprow = ttk.Frame(net)
        iprow.pack(fill="x", pady=(5, 8))
        ttk.Entry(iprow, textvariable=self.ip_var).pack(side="left", fill="x", expand=True)
        self._button(iprow, "Detectar", self.detect).pack(side="left", padx=(7, 0))
        self._button(net, "Comprobar conexión", self.verify_connection).pack(fill="x")

        driver = ttk.LabelFrame(cards, text="2 · Controlador Brother 5", padding=13)
        driver.pack(side="left", fill="both", expand=True, padx=(6, 0))
        tk.Label(driver, textvariable=self.driver_var, bg=BRAND["yellow_soft"], fg=BRAND["ink"], font=(self.ui_font_family, 9, "bold"), anchor="w", justify="left", padx=9, pady=8, wraplength=420).pack(fill="x", pady=(0, 8))
        drow = ttk.Frame(driver)
        drow.pack(fill="x")
        self._button(drow, "Instalar y configurar", self.configure_scanner, primary=True).pack(side="left", fill="x", expand=True)
        self._button(drow, "Elegir otro DEB…", self.select_deb).pack(side="left", padx=(7, 0))

        scan = ttk.LabelFrame(self.home_tab, text="3 · Escanear documentos", padding=13)
        scan.pack(fill="x", pady=(0, 11))
        row = ttk.Frame(scan)
        row.pack(fill="x")
        left = ttk.Frame(row)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="Escáner de documentos", font=(self.ui_font_family, 12, "bold")).pack(anchor="w")
        ttk.Label(left, text="Al abrirlo, selecciona el origen Alimentador automático / ADF. La prueba definitiva es comprobar que la hoja entra por los rodillos superiores.", style="Muted.TLabel", wraplength=680).pack(anchor="w", pady=(3, 0))
        self._button(row, "Abrir escáner", self.open_scanner, primary=True).pack(side="right", padx=(10, 0))

        mini = ttk.Frame(self.home_tab)
        mini.pack(fill="x", expand=True)
        leftbox = ttk.LabelFrame(mini, text="Estado del alimentador", padding=12)
        leftbox.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ttk.Label(leftbox, textvariable=self.adf_var, font=(self.ui_font_family, 11, "bold")).pack(anchor="w")
        ttk.Label(leftbox, text="El estado de papel se consulta en eSCL; no sustituye la prueba física de alimentación.", style="Muted.TLabel", wraplength=420).pack(anchor="w", pady=(4, 0))
        rightbox = ttk.LabelFrame(mini, text="Accesos rápidos", padding=12)
        rightbox.pack(side="left", fill="both", expand=True, padx=(6, 0))
        actions = ttk.Frame(rightbox)
        actions.pack(fill="x")
        self._button(actions, "Abrir manual PDF", self.open_manual).pack(side="left", fill="x", expand=True)
        self._button(actions, "Ver diagnóstico", lambda: self.tabs.select(self.diagnosis_tab)).pack(side="left", fill="x", expand=True, padx=(7, 0))
        ttk.Label(self.home_tab, text="El programa no instala paquetes globales ni modifica CUPS, brscan4, /usr, /opt o /etc reales.", style="Muted.TLabel", wraplength=980).pack(anchor="w", pady=(10, 0))

    def _management_button(self, parent, title, description, command, primary=False):
        box = ttk.LabelFrame(parent, text=title, padding=11)
        ttk.Label(box, text=description, style="Muted.TLabel", wraplength=390, justify="left").pack(anchor="w", pady=(0, 8))
        self._button(box, "Abrir" if title.startswith("Abrir") else "Ejecutar", command, primary=primary).pack(anchor="w", fill="x")
        return box

    def _build_management(self):
        ttk.Label(self.manage_tab, text="Herramientas de gestión", font=(self.ui_font_family, 16, "bold")).pack(anchor="w")
        ttk.Label(self.manage_tab, text="Mantenimiento, rutas, copias de seguridad y documentos desde una sola pantalla.", style="Muted.TLabel").pack(anchor="w", pady=(3, 12))
        grid = ttk.Frame(self.manage_tab)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)
        grid.rowconfigure(2, weight=1)

        b1 = self._management_button(grid, "Reparar registro Brother", "Vuelve a validar la impresora y actualiza su registro de red sin reinstalar paquetes del sistema.", self.repair_registration, True)
        b1.grid(row=0, column=0, sticky="nsew", padx=(0, 7), pady=(0, 7))
        b2 = self._management_button(grid, "Crear accesos directos", "Crea accesos al asistente y al escáner en el menú de aplicaciones y en el escritorio cuando esté disponible.", self.shortcuts)
        b2.grid(row=0, column=1, sticky="nsew", padx=(7, 0), pady=(0, 7))
        b3 = self._management_button(grid, "Copia de seguridad", "Guarda el registro Brother y la lista de backends SANE en un archivo ZIP que puedes conservar o mover a otro equipo.", self.backup_configuration)
        b3.grid(row=1, column=0, sticky="nsew", padx=(0, 7), pady=7)
        b4 = self._management_button(grid, "Restaurar configuración", "Restaura exclusivamente los archivos de configuración Brother y SANE incluidos en una copia generada por esta aplicación.", self.restore_configuration)
        b4.grid(row=1, column=1, sticky="nsew", padx=(7, 0), pady=7)
        b5 = self._management_button(grid, "Abrir ubicaciones", "Accede a la carpeta de la aplicación, al controlador DEB y al perfil de datos privado del usuario.", self.open_locations)
        b5.grid(row=2, column=0, sticky="nsew", padx=(0, 7), pady=7)
        b6 = self._management_button(grid, "Diagnóstico completo", "Comprueba dependencias, entorno aislado, controlador, registro de red y estado eSCL.", self.diagnose)
        b6.grid(row=2, column=1, sticky="nsew", padx=(7, 0), pady=7)

        bottom = ttk.Frame(self.manage_tab)
        bottom.pack(fill="x", pady=(10, 0))
        self._button(bottom, "Abrir guía PDF", self.open_manual).pack(side="left")
        self._button(bottom, "Soporte oficial Brother", self.open_support).pack(side="left", padx=7)
        self._button(bottom, "Desinstalar aplicación…", self.uninstall_application).pack(side="right")

    def _build_diagnostics(self):
        ttk.Label(self.diagnosis_tab, text="Diagnóstico y registro de actividad", font=(self.ui_font_family, 16, "bold")).pack(anchor="w")
        ttk.Label(self.diagnosis_tab, text="Los estados se calculan en este ordenador. Los elementos ausentes que requieran instalación global no se modificarán sin privilegios.", style="Muted.TLabel", wraplength=990).pack(anchor="w", pady=(3, 10))
        top = ttk.Frame(self.diagnosis_tab)
        top.pack(fill="x", pady=(0, 7))
        self._button(top, "Actualizar diagnóstico", self.diagnose, primary=True).pack(side="left")
        self._button(top, "Guardar informe…", self.save_diagnostic).pack(side="left", padx=7)
        self._button(top, "Copiar informe", self.copy_diagnostic).pack(side="left")
        cols = ("state", "check", "detail")
        self.diag_tree = ttk.Treeview(self.diagnosis_tab, columns=cols, show="headings", height=9)
        self.diag_tree.heading("state", text="Estado")
        self.diag_tree.heading("check", text="Comprobación")
        self.diag_tree.heading("detail", text="Resultado")
        self.diag_tree.column("state", width=90, anchor="center", stretch=False)
        self.diag_tree.column("check", width=260, anchor="w", stretch=False)
        self.diag_tree.column("detail", width=620, anchor="w")
        self.diag_tree.pack(fill="both", expand=False)
        self.diag_tree.tag_configure("ok", foreground="#356D42")
        self.diag_tree.tag_configure("error", foreground="#B44A42")
        self.diag_tree.tag_configure("warn", foreground="#8B6B18")

        logframe = ttk.LabelFrame(self.diagnosis_tab, text="Actividad reciente", padding=8)
        logframe.pack(fill="both", expand=True, pady=(9, 0))
        self.log_text = tk.Text(logframe, height=8, wrap="word", bg=BRAND["log_bg"], fg=BRAND["log_fg"], insertbackground=BRAND["white"], relief="flat", font=(self.ui_font_family, 9), padx=9, pady=8)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.insert("end", f"Asistente {APP_VERSION} iniciado.\n")
        self.log_text.insert("end", "El controlador brscan5 1.8.0-0 se busca en la carpeta drivers/ del proyecto.\n")
        self.log_text.insert("end", "No se utiliza sudo, pkexec ni dpkg -i.\n")
        if self.inter_available:
            self.log_text.insert("end", "Inter detectada y activa en la interfaz.\n")
        else:
            self.log_text.insert("end", f"Inter no detectada; se usa {self.ui_font_family}.\n")
        self.log_text.configure(state="disabled")

    def _build_help(self):
        ttk.Label(self.help_tab, text="Ayuda y acerca de", font=(self.ui_font_family, 16, "bold")).pack(anchor="w")
        ttk.Label(self.help_tab, text="La instalación se realiza en el perfil del usuario y utiliza bubblewrap para simular las rutas absolutas que espera el controlador Brother.", style="Muted.TLabel", wraplength=980).pack(anchor="w", pady=(3, 12))
        center = tk.Frame(self.help_tab, bg=BRAND["ink"], padx=18, pady=16)
        center.pack(fill="x", pady=(0, 12))
        tk.Label(center, text=CENTER_NAME, bg=BRAND["ink"], fg=BRAND["yellow"], font=(self.ui_font_family, 14, "bold")).pack(anchor="w")
        tk.Label(center, text=CENTER_ADDRESS, bg=BRAND["ink"], fg=BRAND["white"], font=(self.ui_font_family, 10)).pack(anchor="w", pady=(5, 0))
        tk.Label(center, text=f"Tel. {CENTER_PHONE}   ·   {CENTER_EMAIL}", bg=BRAND["ink"], fg=BRAND["white"], font=(self.ui_font_family, 10)).pack(anchor="w", pady=(3, 0))
        tk.Label(center, text=f"Desarrollador: {DEVELOPER_NAME}", bg=BRAND["ink"], fg=BRAND["white"], font=(self.ui_font_family, 9)).pack(anchor="w", pady=(9, 0))

        info = ttk.LabelFrame(self.help_tab, text="Preguntas frecuentes", padding=13)
        info.pack(fill="both", expand=True)
        faq = [
            ("¿Necesito permisos de administrador?", "No para instalar y configurar brscan5 con este asistente. El equipo sí debe tener previamente Python/Tkinter, SANE, bubblewrap y Escáner de documentos. Si falta alguno, una persona administradora debe instalarlo una sola vez."),
            ("¿Dónde está el controlador?", f"Dentro del proyecto, en drivers/{BUNDLED_DRIVER_NAME}. La aplicación valida su SHA-256, versión y arquitectura antes de extraerlo en ~/.local/share/brother-mfc-j5740dw/driver-extracted/."),
            ("¿Cómo selecciono el alimentador?", "Abre Escáner de documentos y elige Alimentador automático / ADF como origen. Para originales a doble cara, activa dúplex cuando esté disponible. Comprueba que la hoja entra por los rodillos superiores."),
            ("¿Qué se conserva al desinstalar?", "El desinstalador elimina la aplicación y sus accesos directos. Conserva el controlador extraído y la configuración personal para evitar pérdidas accidentales. Puedes revisarlos desde Gestión > Abrir ubicaciones."),
            ("¿Qué no modifica?", "No instala DEB en el sistema ni ejecuta postinst. No modifica CUPS, brscan4, /usr, /opt ni /etc reales. La simulación de rutas se limita al proceso ejecutado dentro de bubblewrap."),
        ]
        for q, a in faq:
            block = ttk.Frame(info)
            block.pack(fill="x", pady=5)
            ttk.Label(block, text=q, font=(self.ui_font_family, 10, "bold")).pack(anchor="w")
            ttk.Label(block, text=a, style="Muted.TLabel", wraplength=940, justify="left").pack(anchor="w", pady=(2, 0))
        bottom = ttk.Frame(self.help_tab)
        bottom.pack(fill="x", pady=(12, 0))
        self._button(bottom, "Abrir manual PDF", self.open_manual).pack(side="left")
        self._button(bottom, "Web Punto Vuela", self.open_center_site).pack(side="left", padx=7)
        self._button(bottom, "Soporte Brother", self.open_support).pack(side="left")

    def log(self, message):
        self.events.put(("log", str(message)))

    def set_status(self, message):
        self.events.put(("status", str(message)))

    def _drain_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.log_text.configure(state="normal")
                    self.log_text.insert("end", f"{time.strftime('%H:%M:%S')}  {value}\n")
                    self.log_text.see("end")
                    self.log_text.configure(state="disabled")
                elif kind == "status":
                    self.status_var.set(value)
                elif kind == "ip":
                    self.ip_var.set(value)
                elif kind == "adf":
                    self.adf_var.set(value)
                elif kind == "driver":
                    self.driver_var.set(value)
                elif kind == "diagnosis":
                    self._render_diagnosis(value)
                elif kind == "done":
                    self.busy = False
                    self._set_buttons(True)
                elif kind == "error":
                    self.busy = False
                    self._set_buttons(True)
                    messagebox.showerror("No se pudo completar la operación", value)
                elif kind == "info":
                    messagebox.showinfo("Brother MFC-J5740DW", value)
        except queue.Empty:
            pass
        self.after(150, self._drain_events)

    def _set_buttons(self, enabled):
        state = "normal" if enabled else "disabled"
        for button in self.action_buttons:
            try:
                button.configure(state=state)
            except tk.TclError:
                pass

    def _worker(self, fn, status):
        if self.busy:
            return
        self.busy = True
        self._set_buttons(False)
        self.set_status(status)
        def go():
            try:
                fn()
            except Exception as exc:
                self.set_status("La operación no se ha completado.")
                self.events.put(("error", str(exc)))
            else:
                self.events.put(("done", None))
        threading.Thread(target=go, daemon=True).start()

    def detect(self):
        def work():
            ip = discover_by_network(self.log)
            adf_loaded = verify_device(ip)
            self.events.put(("ip", ip))
            self.events.put(("adf", "Papel detectado en el alimentador" if adf_loaded else "ADF disponible; no se detecta papel cargado"))
            self.log("Comprobación eSCL correcta: modelo y capacidades ADF identificados.")
            self.set_status(f"Brother {MODEL} encontrada en {ip}.")
        self._worker(work, "Buscando la Brother en la red local…")

    def verify_connection(self):
        ip = self.ip_var.get().strip()
        if not ip:
            messagebox.showwarning("Falta la IP", "Escribe la IP o utiliza Detectar.")
            return
        def work():
            adf_loaded = verify_device(ip)
            self.events.put(("adf", "Papel detectado en el alimentador" if adf_loaded else "ADF disponible; no se detecta papel cargado"))
            self.log(f"Conexión eSCL validada para {MODEL} en {ip}.")
            self.set_status(f"Conexión correcta con {ip}.")
        self._worker(work, "Comprobando la impresora…")

    def select_deb(self):
        filename = filedialog.askopenfilename(title="Selecciona el controlador oficial Brother brscan5", filetypes=[("Paquete DEB Brother", "brscan5-*.amd64.deb"), ("Paquetes DEB", "*.deb"), ("Todos los archivos", "*")])
        if filename:
            try:
                validate_driver_deb(Path(filename))
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                target = CACHE_DIR / Path(filename).name
                shutil.copy2(filename, target)
                self.log(f"Paquete seleccionado y validado: {target}")
                self.driver_var.set(f"Paquete alternativo preparado: {target.name}")
                messagebox.showinfo("Paquete preparado", "El paquete se ha validado y está listo. Pulsa Instalar y configurar.")
            except Exception as exc:
                messagebox.showerror("Paquete no válido", str(exc))

    def configure_scanner(self):
        ip = self.ip_var.get().strip()
        if not ip:
            messagebox.showwarning("Falta la impresora", "Pulsa Detectar o escribe la IP de la impresora.")
            return
        def work():
            self.log("Comprobando los requisitos del ordenador…")
            errs = [message for level, message in check_prerequisites() if level == "error"]
            if errs:
                raise SetupError("Este ordenador no cumple los requisitos para el modo sin root:\n\n" + "\n".join(errs) + "\n\nEl asistente no instalará paquetes globales ni pedirá la contraseña de administrador.")
            adf_loaded = verify_device(ip)
            self.log(f"Conexión con {MODEL} comprobada en {ip}.")
            self.events.put(("adf", "Papel detectado en el alimentador" if adf_loaded else "ADF disponible; no se detecta papel cargado"))
            deb = download_driver(self.log)
            self.events.put(("driver", f"Controlador validado: {deb.name} · SHA-256 comprobado" if deb.name == BUNDLED_DRIVER_NAME else f"Controlador seleccionado: {deb.name}"))
            extract_deb(deb, self.log)
            self.log("Registrando el dispositivo con brsaneconfig5 dentro de bubblewrap…")
            register_scanner(ip, self.log)
            create_shortcuts(self.log)
            self.set_status(f"Configuración terminada. Brother {MODEL} en {ip}.")
            self.events.put(("info", "Controlador preparado y escáner registrado sin permisos de administrador.\n\nAbre Escáner de documentos y selecciona Alimentador automático / ADF."))
        self._worker(work, "Preparando controlador Brother 5 y registrando el escáner…")

    def repair_registration(self):
        ip = self.ip_var.get().strip()
        if not ip:
            messagebox.showwarning("Falta la IP", "Detecta la impresora o escribe su IP primero.")
            return
        def work():
            if not DRIVER_ROOT.exists():
                raise SetupError("Todavía no se ha extraído el controlador. Ejecuta primero Instalar y configurar.")
            verify_device(ip)
            register_scanner(ip, self.log)
            create_shortcuts(self.log)
            self.set_status(f"Registro actualizado para {ip}.")
            self.events.put(("info", "Se ha actualizado el registro Brother y los accesos directos."))
        self._worker(work, "Reparando el registro Brother…")

    def open_scanner(self):
        def work():
            launch_simple_scan(self.log)
            self.set_status("Escáner de documentos iniciado con Brother 5.")
            self.events.put(("info", "Escáner de documentos se ha abierto.\n\nEn el selector de origen, elige Alimentador automático / ADF. Para originales a doble cara, activa dúplex si aparece."))
        self._worker(work, "Abriendo Escáner de documentos…")

    def shortcuts(self):
        try:
            create_shortcuts(self.log)
            messagebox.showinfo("Accesos directos", "Se han creado o actualizado los accesos del asistente y del escáner donde el escritorio lo permite.")
        except Exception as exc:
            messagebox.showerror("No se pudieron crear los accesos", str(exc))

    def open_path(self, path: Path, label: str):
        try:
            path.mkdir(parents=True, exist_ok=True)
            opener = shutil.which("xdg-open") or shutil.which("gio")
            if not opener:
                raise SetupError("No se encuentra xdg-open ni gio para abrir carpetas desde el escritorio.")
            args = [opener, str(path)] if Path(opener).name == "xdg-open" else [opener, "open", str(path)]
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            self.log(f"Abierta ubicación: {path}")
        except Exception as exc:
            messagebox.showerror(f"No se pudo abrir {label}", str(exc))

    def open_locations(self):
        top = tk.Toplevel(self)
        top.title("Ubicaciones del asistente")
        top.geometry("760x430")
        top.configure(bg=BRAND["canvas"])
        frame = ttk.Frame(top, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Ubicaciones de trabajo", font=(self.ui_font_family, 15, "bold")).pack(anchor="w")
        rows = [
            ("Aplicación y archivos incluidos", APP_DIR),
            ("Controlador DEB incluido", APP_DIR / "drivers"),
            ("Controlador extraído", DRIVER_ROOT),
            ("Datos privados de la aplicación", APP_DATA),
            ("Configuración Brother", USER_CFG.parent),
            ("Configuración SANE", SANE_DIR),
        ]
        for label, path in rows:
            r = ttk.Frame(frame)
            r.pack(fill="x", pady=5)
            ttk.Label(r, text=label, width=30).pack(side="left", anchor="w")
            ttk.Label(r, text=str(path), style="Muted.TLabel", wraplength=440).pack(side="left", fill="x", expand=True, padx=8)
            self._button(r, "Abrir", lambda p=path, l=label: self.open_path(p, l)).pack(side="right")

    def open_manual(self):
        pdf = APP_DIR / "docs" / "Guia_Brother_MFC-J5740DW_SinRoot.pdf"
        if not pdf.is_file():
            messagebox.showerror("No se encuentra la guía", f"No se ha encontrado el PDF en:\n{pdf}")
            return
        try:
            opener = shutil.which("xdg-open")
            if not opener:
                raise SetupError("No se encuentra xdg-open para abrir el PDF.")
            subprocess.Popen([opener, str(pdf)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            self.log("Guía PDF abierta.")
        except Exception as exc:
            messagebox.showerror("No se pudo abrir el PDF", str(exc))

    def open_support(self):
        import webbrowser
        webbrowser.open(SUPPORT_URL)

    def open_center_site(self):
        import webbrowser
        webbrowser.open("https://puntosvuela.es/centros/montejaque")

    def backup_configuration(self):
        import zipfile, json
        filename = filedialog.asksaveasfilename(title="Guardar copia de configuración", defaultextension=".zip", filetypes=[("Copia Brother SinRoot", "*.zip")], initialfile="Brother_MFC-J5740DW_configuracion.zip")
        if not filename:
            return
        try:
            payload = {}
            if USER_CFG.is_file():
                payload["brsanenetdevice.cfg"] = USER_CFG.read_text(encoding="utf-8", errors="replace")
            if SANE_DLL.is_file():
                payload["dll.conf"] = SANE_DLL.read_text(encoding="utf-8", errors="replace")
            manifest = {"application": APP_TITLE, "version": APP_VERSION, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "files": list(payload)}
            with zipfile.ZipFile(filename, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                for name, content in payload.items():
                    zf.writestr(name, content)
            self.log(f"Copia de configuración creada: {filename}")
            messagebox.showinfo("Copia creada", "La copia contiene únicamente el registro Brother y la configuración de backend SANE. No contiene documentos escaneados.")
        except Exception as exc:
            messagebox.showerror("No se pudo crear la copia", str(exc))

    def restore_configuration(self):
        import zipfile
        filename = filedialog.askopenfilename(title="Selecciona una copia de configuración", filetypes=[("Copia Brother SinRoot", "*.zip")])
        if not filename:
            return
        if not messagebox.askyesno("Restaurar configuración", "Se sustituirán el registro Brother y el archivo dll.conf del perfil de usuario cuando estén presentes en la copia. ¿Continuar?"):
            return
        try:
            with zipfile.ZipFile(filename, "r") as zf:
                names = set(zf.namelist())
                if not names.intersection({"brsanenetdevice.cfg", "dll.conf"}):
                    raise SetupError("El ZIP no contiene archivos de configuración reconocidos.")
                if "brsanenetdevice.cfg" in names:
                    text = zf.read("brsanenetdevice.cfg").decode("utf-8")
                    USER_CFG.parent.mkdir(parents=True, exist_ok=True)
                    USER_CFG.write_text(text, encoding="utf-8")
                if "dll.conf" in names:
                    text = zf.read("dll.conf").decode("utf-8")
                    SANE_DIR.mkdir(parents=True, exist_ok=True)
                    # Evitar perder los backends básicos si la copia proviene de otra versión.
                    entries = [line.strip() for line in text.splitlines() if line.strip()]
                    for backend in ("escl", "brother5"):
                        if backend not in entries:
                            entries.append(backend)
                    SANE_DLL.write_text("\n".join(entries) + "\n", encoding="utf-8")
            self.log(f"Configuración restaurada desde {filename}")
            messagebox.showinfo("Restauración terminada", "Se han restaurado los archivos de configuración seleccionados. Si la IP cambió, vuelve a Gestión > Reparar registro Brother.")
            self.diagnose()
        except Exception as exc:
            messagebox.showerror("No se pudo restaurar", str(exc))

    def build_diagnostic_report(self):
        rows = []
        for level, message in check_prerequisites():
            rows.append(("OK" if level == "ok" else "FALTA", "Requisitos", message, level))
        rows.append(("OK" if self.inter_available else "AVISO", "Tipografía", "Inter disponible" if self.inter_available else f"Se está usando {self.ui_font_family}", "ok" if self.inter_available else "warn"))
        bundled = APP_DIR / "drivers" / BUNDLED_DRIVER_NAME
        if bundled.is_file():
            try:
                validate_driver_deb(bundled)
                driver_result = "brscan5 1.8.0-0 · DEB incluido y SHA-256 correcto"
                driver_level = "ok"
            except Exception as exc:
                driver_result = f"DEB incluido, pero no supera la validación: {exc}"
                driver_level = "error"
        else:
            driver_result = "No se encuentra en drivers/; se intentará una descarga oficial"
            driver_level = "warn"
        rows.append(("OK" if driver_level == "ok" else "AVISO" if driver_level == "warn" else "ERROR", "Controlador", driver_result, driver_level))
        rows.append(("OK" if DRIVER_ROOT.exists() else "PENDIENTE", "Extracción", str(DRIVER_ROOT) if DRIVER_ROOT.exists() else "El controlador todavía no se ha extraído", "ok" if DRIVER_ROOT.exists() else "warn"))
        cfg_text = USER_CFG.read_text(encoding="utf-8", errors="replace") if USER_CFG.exists() else ""
        registered = DEVICE_NAME in cfg_text
        rows.append(("OK" if registered else "PENDIENTE", "Registro Brother", f"{USER_CFG} · {'dispositivo registrado' if registered else 'sin registro todavía'}", "ok" if registered else "warn"))
        rows.append(("OK" if SANE_DLL.exists() and "brother5" in SANE_DLL.read_text(encoding="utf-8", errors="replace") else "PENDIENTE", "Configuración SANE", str(SANE_DLL), "ok" if SANE_DLL.exists() and "brother5" in SANE_DLL.read_text(encoding="utf-8", errors="replace") else "warn"))
        ip = self.ip_var.get().strip()
        if ip:
            try:
                loaded = verify_device(ip)
                rows.append(("OK", "Conexión eSCL", f"{MODEL} en {ip}; ADF anunciado; {'papel detectado' if loaded else 'sin papel detectado'}", "ok"))
            except Exception as exc:
                rows.append(("ERROR", "Conexión eSCL", str(exc), "error"))
        else:
            rows.append(("PENDIENTE", "Conexión eSCL", "Todavía no se ha indicado ni detectado una IP", "warn"))
        return rows

    def diagnose(self):
        def work():
            rows = self.build_diagnostic_report()
            self.events.put(("diagnosis", rows))
            self.log("Diagnóstico actualizado.")
        self._worker(work, "Revisando dependencias, controlador y registro…")

    def _render_diagnosis(self, rows):
        for item in self.diag_tree.get_children():
            self.diag_tree.delete(item)
        for state, check, detail, level in rows:
            self.diag_tree.insert("", "end", values=(state, check, detail), tags=(level,))

    def diagnostic_text(self):
        parts = [f"{APP_TITLE} · versión {APP_VERSION}", f"Desarrollador: {DEVELOPER_NAME}", f"Centro: {CENTER_NAME}", f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
        for state, check, detail, level in self.build_diagnostic_report():
            parts.append(f"{state} | {check} | {detail}")
        return "\n".join(parts) + "\n"

    def save_diagnostic(self):
        filename = filedialog.asksaveasfilename(title="Guardar informe de diagnóstico", defaultextension=".txt", filetypes=[("Informe de texto", "*.txt")], initialfile="Brother_MFC-J5740DW_diagnostico.txt")
        if not filename:
            return
        try:
            Path(filename).write_text(self.diagnostic_text(), encoding="utf-8")
            messagebox.showinfo("Informe guardado", f"Se ha guardado el informe en:\n{filename}")
        except Exception as exc:
            messagebox.showerror("No se pudo guardar", str(exc))

    def copy_diagnostic(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.diagnostic_text())
            messagebox.showinfo("Informe copiado", "El informe de diagnóstico se ha copiado al portapapeles.")
        except Exception as exc:
            messagebox.showerror("No se pudo copiar", str(exc))

    def uninstall_application(self):
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

def main():
    if "--scan" in sys.argv:
        try:
            launch_simple_scan()
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return 0
    try:
        app = App()
        app.mainloop()
        return 0
    except Exception as exc:
        print(f"No se pudo iniciar la interfaz: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
