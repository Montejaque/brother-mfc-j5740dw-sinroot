# Guía de instalación

La documentación principal se encuentra en [Guía Brother MFC-J5740DW SinRoot (PDF)](Guia_Brother_MFC-J5740DW_SinRoot.pdf).

El PDF recoge requisitos del equipo, pasos de instalación sin root, detección Wi-Fi, configuración de Brother brscan5 y selección del alimentador automático ADF.

El archivo HTML editable está en `source/guia.html`. Para regenerar el PDF en un entorno de desarrollo con WeasyPrint e Inter instalados:

```bash
python3 - <<'PY'
from weasyprint import HTML
HTML(filename='docs/source/guia.html').write_pdf('docs/Guia_Brother_MFC-J5740DW_SinRoot.pdf')
PY
```
