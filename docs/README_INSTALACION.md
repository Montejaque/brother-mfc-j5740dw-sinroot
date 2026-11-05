# Guía y fuentes

La guía principal es [Guía Brother MFC-J5740DW SinRoot (PDF)](Guia_Brother_MFC-J5740DW_SinRoot.pdf).

Su fuente HTML editable está en `source/guia.html`. El PDF tiene cuatro páginas A4, incorpora la tipografía Inter y recoge los datos del desarrollador y del Punto Vuela Montejaque, la paleta de colores de referencia, los pasos de instalación, el uso ADF, la gestión visual y la resolución de problemas.

Para regenerar el PDF en un equipo de desarrollo con WeasyPrint y la familia Inter disponibles:

```bash
python3 - <<'PY'
from weasyprint import HTML
HTML(filename='docs/source/guia.html', base_url='docs/source').write_pdf(
    'docs/Guia_Brother_MFC-J5740DW_SinRoot.pdf'
)
PY
```
