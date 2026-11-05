# Brother MFC-J5740DW SinRoot

**Asistente gráfico para Ubuntu/Debian de 64 bits · Wi-Fi · Brother brscan5 · sin privilegios de administrador**

**Versión:** 1.5.0  
**Desarrollador:** Francisco Javier Gallego Orellana  
**Centro de referencia:** Punto Vuela Montejaque · Avenida Andalucía, 48 · 29360 Montejaque (Málaga)  
**Contacto:** 633 402 959 · montejaque@puntosvuela.es · [Web oficial](https://puntosvuela.es/centros/montejaque)

## Guía PDF

[**Abrir o descargar la guía Brother MFC-J5740DW SinRoot (PDF)**](docs/Guia_Brother_MFC-J5740DW_SinRoot.pdf)  
Cuatro páginas A4, diseño con la paleta de Puntos Vuela y tipografía Inter incrustada.

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

La aplicación lo busca primero en `drivers/`, valida el SHA-256 y lo utiliza automáticamente. El instalador copia esta carpeta al perfil del usuario para que el programa siga encontrándolo.

## Qué hace la aplicación

La interfaz gráfica integra cuatro secciones:

- **Inicio:** detección Wi-Fi/eSCL, IP manual, comprobación de conexión, instalación/configuración y apertura de Escáner de documentos.
- **Gestión:** reparación del registro, creación de accesos directos, apertura de ubicaciones, copia de seguridad y restauración de la configuración, guía PDF y desinstalación.
- **Diagnóstico y actividad:** comprobación de requisitos, bwrap, SANE, controlador, SHA-256, extracción, registro y conectividad; permite guardar o copiar el informe.
- **Ayuda y acerca de:** preguntas frecuentes, datos del centro, desarrollador y enlaces de soporte.

El controlador se extrae en `~/.local/share/brother-mfc-j5740dw/driver-extracted/`. La configuración se guarda en `~/.config/brother/brscan5/` y `~/.config/sane-brscan5/`.

## Instalación rápida

1. Descarga el repositorio como ZIP y extrae la carpeta completa.
2. No separes `drivers/` del resto del proyecto.
3. Abre una terminal dentro de la carpeta extraída y ejecuta:

```bash
./instalar.sh
```

4. En **Inicio**, pulsa **Detectar**. Si no aparece, introduce la IP manualmente y pulsa **Comprobar conexión**.
5. Pulsa **Instalar y configurar**. El asistente comprobará los requisitos, validará y extraerá el DEB incluido y registrará la Brother.
6. Pulsa **Abrir escáner**. En Escáner de documentos, selecciona **Alimentador automático / ADF**; activa dúplex para originales a dos caras cuando esté disponible.

No ejecutes el instalador con `sudo` ni como root.

## Requisitos del ordenador

Ubuntu/Debian x86_64, Python 3, Tkinter, biblioteca SANE (`libsane`), `bubblewrap` (`bwrap`) con espacios de nombres de usuario permitidos y Escáner de documentos (`simple-scan`). El equipo debe alcanzar la impresora en la red local.

Sin root no se pueden instalar dependencias globales ausentes ni cambiar políticas del sistema. La interfaz detecta estos requisitos y explica cuáles faltan; no solicita contraseñas de administrador.

## Seguridad y límites

- No ejecuta `dpkg -i` ni el `postinst` de Brother.
- No modifica CUPS, colas de impresión, `brscan4`, `/usr`, `/opt` ni `/etc` reales.
- Simula las rutas absolutas necesarias para el software Brother dentro de `bwrap`.
- Las copias de seguridad contienen configuración Brother/SANE, no los documentos escaneados.
- El estado eSCL de papel cargado no demuestra por sí solo que se haya utilizado el ADF: la prueba física es observar que el original entra por los rodillos superiores.

## Estructura

```text
.
├── app.py
├── instalar.sh
├── iniciar.sh
├── desinstalar.sh
├── VERSION.txt
├── CHANGELOG.md
├── drivers/
│   ├── brscan5-1.8.0-0.amd64.deb
│   └── README.txt
└── docs/
    ├── Guia_Brother_MFC-J5740DW_SinRoot.pdf
    ├── REFERENCIAS.md
    └── source/guia.html
```

## Créditos

Aplicación de apoyo técnico desarrollada por Francisco Javier Gallego Orellana para el entorno de Punto Vuela Montejaque. Brother y MFC-J5740DW son marcas de Brother Industries, Ltd. El controlador incluido es software propietario de Brother, sin modificación. Este proyecto no es una aplicación oficial de Brother ni implica su respaldo.
