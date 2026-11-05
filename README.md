# Brother MFC-J5740DW SinRoot

**Asistente gráfico para Ubuntu/Debian de 64 bits · Wi-Fi · Brother brscan5 · sin privilegios de administrador**

**Versión:** 1.6.0  
**Desarrollador:** Francisco Javier Gallego Orellana  
**Centro de referencia:** Punto Vuela Montejaque · Avenida Andalucía, 48 · 29360 Montejaque (Málaga)  
**Contacto:** 633 402 959 · montejaque@puntosvuela.es · [Web oficial](https://puntosvuela.es/centros/montejaque)

## Descargas y formatos

La distribución de esta versión ofrece dos opciones:

1. **AppImage (recomendada):** un único ejecutable para Linux x86_64. Incluye el intérprete Python y Tkinter necesarios para abrir la interfaz. No requiere ejecutar `instalar.sh`.
2. **ZIP del proyecto:** contiene el código fuente, instaladores por usuario, documentación, controlador DEB original, icono y AppImage generado. Mantiene también la opción de ejecutar desde código cuando Python 3 y Tkinter ya están instalados.

Los archivos se publican como artefactos de GitHub Actions en el repositorio privado: abre [Actions](https://github.com/Montejaque/brother-mfc-j5740dw-sinroot/actions), selecciona la ejecución más reciente de **Build AppImage and ZIP** y descarga el artefacto `Brother_MFC-J5740DW_SinRoot-1.6.0-linux-x86_64` (la sesión de GitHub debe tener acceso al repositorio).

### Ejecutar AppImage

1. Descarga `Brother_MFC-J5740DW_SinRoot_1.6.0-x86_64.AppImage`.
2. En Propiedades, marca **Permitir ejecutar como programa**, o usa:

   ```bash
   chmod +x Brother_MFC-J5740DW_SinRoot_1.6.0-x86_64.AppImage
   ./Brother_MFC-J5740DW_SinRoot_1.6.0-x86_64.AppImage
   ```

3. En la interfaz, usa **Inicio > Detectar**; si no encuentra la impresora, introduce su IP.
4. Pulsa **Instalar y configurar** y después **Abrir escáner**.
5. En Escáner de documentos, selecciona **Alimentador automático / ADF** y activa dúplex para originales a dos caras si aparece esa opción.

Desde **Gestión > Crear accesos directos**, la aplicación puede crear accesos persistentes en el menú y en el escritorio. En el modo AppImage, la opción de desinstalar retira esos accesos, pero no borra el archivo AppImage ni la configuración del escáner.

### Ejecutar desde el ZIP / código fuente

1. Extrae la carpeta completa; no separes `drivers/`.
2. Abre una terminal dentro de ella.
3. Ejecuta:

   ```bash
   ./instalar.sh
   ```

No ejecutes el instalador con `sudo` ni como root. Para ejecución sin instalar el proyecto, puedes usar `./iniciar.sh` cuando estén presentes Python 3 y Tkinter.

## Controlador Brother original incluido

El proyecto incorpora el archivo DEB original proporcionado para el proyecto:

`drivers/brscan5-1.8.0-0.amd64.deb`

| Propiedad | Valor |
|---|---|
| Paquete | `brscan5` |
| Versión | `1.8.0-0` |
| Arquitectura | `amd64` |
| Tamaño | `871290` bytes |
| SHA-256 | `27bf1d561da2223c9807726cc3ec1bd9e7cdce419a27ee79b31a642073174d46` |

La aplicación lo busca primero en `drivers/`, valida el SHA-256 y lo utiliza automáticamente. En el AppImage los recursos están integrados; en la instalación portable por código, el instalador copia el archivo al perfil del usuario.

## Interfaz y funciones

La interfaz de gestión integra cuatro secciones:

- **Inicio:** detección Wi-Fi/eSCL, IP manual, comprobación de conexión, instalación/configuración y apertura de Escáner de documentos.
- **Gestión:** reparación del registro, creación de accesos directos, apertura de ubicaciones, copia de seguridad/restauración, guía PDF y retirada de accesos o desinstalación según el formato utilizado.
- **Diagnóstico y actividad:** comprobación de requisitos, bwrap, SANE, controlador, SHA-256, extracción/registro y eSCL; permite guardar o copiar el informe.
- **Ayuda y acerca de:** preguntas frecuentes, datos del centro, desarrollador y enlaces de soporte.

El controlador se extrae en `~/.local/share/brother-mfc-j5740dw/driver-extracted/`. La configuración se guarda en `~/.config/brother/brscan5/` y `~/.config/sane-brscan5/`.

## Requisitos del ordenador

**AppImage:** Ubuntu/Debian x86_64 con soporte AppImage (FUSE 2 o ejecución mediante extracción compatible), acceso a escritorio gráfico, y estos componentes disponibles en el sistema: `bubblewrap` (`bwrap`) con espacios de nombres de usuario permitidos, biblioteca SANE (`libsane`) y Escáner de documentos (`simple-scan`). El AppImage incluye Python/Tkinter, pero no reemplaza estos servicios nativos ni sus dependencias.

**Código fuente:** además de lo anterior, Python 3 y Tkinter.

Sin root no se pueden instalar dependencias globales ausentes ni cambiar políticas del sistema. La aplicación detecta estos requisitos y explica cuáles faltan; no solicita contraseñas de administrador.

## Construcción del AppImage

El AppImage se construye en Ubuntu 20.04 x86_64 para mantener una base de glibc compatible con esa versión de Ubuntu y posteriores. En un equipo de desarrollo que tenga Python 3, pip, curl y las herramientas de empaquetado disponibles, ejecuta:

```bash
./build_appimage.sh
```

El script usa PyInstaller 6.14.2 y AppImageKit `appimagetool` (canal continuous). GitHub Actions automatiza también la validación del código, una prueba de arranque de interfaz con pantalla virtual y la generación del ZIP. El contenedor de compilación utiliza repositorios históricos de Ubuntu 20.04 para conservar la base glibc 2.31; la guía PDF se genera y verifica en un paso independiente.

## Seguridad y límites

- No ejecuta `dpkg -i` ni el `postinst` de Brother.
- No modifica CUPS, colas de impresión, `brscan4`, `/usr`, `/opt` ni `/etc` reales.
- Simula las rutas absolutas necesarias para el software Brother dentro de `bwrap`.
- Las copias de seguridad contienen configuración Brother/SANE, no los documentos escaneados.
- El estado eSCL de papel cargado no demuestra por sí solo que se haya utilizado el ADF: la prueba física es observar que el original entra por los rodillos superiores.
- El AppImage no instala `bwrap`, SANE ni `simple-scan`, ni elude las restricciones de seguridad del sistema.

## Estructura

```text
.
├── app.py
├── instalar.sh / iniciar.sh / desinstalar.sh
├── build_appimage.sh
├── AppRun
├── brother-mfc-j5740dw.desktop
├── assets/
├── drivers/brscan5-1.8.0-0.amd64.deb
├── docs/Guia_Brother_MFC-J5740DW_SinRoot.pdf
├── docs/source/guia.html
└── .github/workflows/build-appimage.yml
```

## Créditos

Aplicación de apoyo técnico desarrollada por Francisco Javier Gallego Orellana para el entorno de Punto Vuela Montejaque. Brother y MFC-J5740DW son marcas de Brother Industries, Ltd. El controlador incluido es software propietario de Brother, sin modificación. Este proyecto no es una aplicación oficial de Brother ni implica su respaldo.
