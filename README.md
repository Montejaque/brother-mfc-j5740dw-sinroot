# Brother MFC-J5740DW SinRoot

**Asistente gráfico para Ubuntu/Debian · Wi-Fi · Brother brscan5 · sin privilegios de administrador**

**Versión:** 1.3.0 · **Desarrollador:** Francisco Javier Gallego Orellana  
**Centro de referencia:** Punto Vuela Montejaque · Avenida Andalucía, 48 · 29360 Montejaque (Málaga)  
**Contacto:** 633 402 959 · montejaque@puntosvuela.es · [Web](https://puntosvuela.es/centros/montejaque)

## Guía de instalación y uso

[**Abrir o descargar la guía PDF**](docs/Guia_Brother_MFC-J5740DW_SinRoot.pdf) · 4 páginas A4 · Inter incrustada.

## Controlador Brother incluido

El proyecto contiene el paquete original `brscan5-1.8.0-0.amd64.deb` en `drivers/`. Se valida mediante SHA-256 y se extrae dentro del perfil del usuario. No se ejecuta `dpkg -i` ni el script `postinst`.

- Paquete: `brscan5`
- Versión: `1.8.0-0`
- Arquitectura: `amd64 / x86_64`
- SHA-256: `27bf1d561da2223c9807726cc3ec1bd9e7cdce419a27ee79b31a642073174d46`

## Funciones

1. Busca la MFC-J5740DW en la red local mediante eSCL.
2. Comprueba que anuncia capacidades del alimentador automático ADF.
3. Prioriza el paquete DEB incluido y valida su identidad e integridad.
4. Extrae las bibliotecas en el espacio privado del usuario.
5. Registra el dispositivo mediante `brsaneconfig5` dentro de `bwrap`.
6. Abre Escáner de documentos (`simple-scan`) con Brother 5.
7. Crea accesos directos en el menú de aplicaciones y, cuando es posible, en el escritorio.

## Instalación rápida

1. Descarga el repositorio como ZIP y extrae la carpeta completa.
2. No separes `drivers/` del resto del proyecto.
3. Abre una terminal dentro de la carpeta y ejecuta:

```bash
./instalar.sh
```

4. Pulsa **Detectar automáticamente** (o introduce la IP).
5. Pulsa **Instalar y configurar**.
6. Pulsa **Abrir Escáner de documentos** y selecciona **Alimentador automático / ADF**.

No ejecutes el instalador con `sudo` ni como root.

## Requisitos

El equipo debe tener previamente Ubuntu/Debian x86_64, Python 3, Tkinter, `bubblewrap` (`bwrap`) con espacios de nombres de usuario permitidos, SANE (`libsane`) y Escáner de documentos (`simple-scan`). El procedimiento no necesita Internet para descargar el controlador, pero el equipo debe alcanzar la impresora por la red local.

Sin permisos root no se pueden instalar dependencias globales que falten; el asistente las comprueba y explica cualquier requisito pendiente para que una persona administradora lo instale una sola vez.

## Tipografía e identidad visual

La guía PDF incorpora Inter como fuente incrustada. La interfaz usa Inter si está instalada y, en caso contrario, la fuente Tk disponible. Paleta de referencia de Puntos Vuela: amarillo `#F3D54E`, verde `#7BA880`, coral `#E56359`, ocre `#AE9E3A` y azul `#87ACD4`.

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
    ├── README_INSTALACION.md
    ├── REFERENCIAS.md
    └── source/guia.html
```

## Seguridad

- No utiliza `sudo`, `pkexec` ni solicita contraseña de administrador.
- No modifica CUPS, colas de impresión, `brscan4`, `/usr`, `/opt` ni `/etc` reales.
- `bwrap` simula las rutas absolutas que espera Brother dentro de un espacio de nombres aislado.
- Los escaneos se gestionan localmente con Escáner de documentos; no se transmiten a servidores.
- El estado eSCL de papel cargado no demuestra por sí solo que el ADF haya sido el origen: la guía explica cómo verificar la alimentación física.

El paquete brscan5 es software propietario de Brother Industries, Ltd. y se conserva sin modificar. Este proyecto es una herramienta de apoyo técnico y no es una aplicación oficial de Brother.

Página oficial: [Brother MFC-J5740DW](https://support.brother.com/g/b/downloadtop.aspx?c=es&lang=es&prod=mfcj5740dw_eu_as).
