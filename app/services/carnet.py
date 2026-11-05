"""
Formato de carné universitario (por defecto, especificación SUNEDU):
240×288 px (proporción 5:6), JPG, máx. 50 KB, 300 ppp, de hombros hacia arriba.

- generate_carnet(): recorta la foto centrada en el rostro con proporción 5:6,
  la redimensiona a la medida exacta y la comprime hasta cumplir el peso máximo.
- check_upload():    mide si el archivo subido ya cumple la especificación (modo "validate").

No aplica filtros ni retoques: solo recorte, redimensión y compresión.
"""
from __future__ import annotations

import io

from PIL import Image


def _jpeg(img: Image.Image, calidad: int, dpi: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=calidad, optimize=True, dpi=(dpi, dpi), subsampling=0 if calidad >= 90 else 2)
    return buf.getvalue()


def _recorte(img: Image.Image, face_box: list[int], r: dict) -> tuple[tuple[int, int, int, int], float]:
    """Caja de recorte 5:6 centrada en el rostro. Devuelve (caja, escala_necesaria)."""
    x, y, fw, fh = face_box
    aspecto = r["width"] / r["height"]
    alto = fh / r["face_height_ratio"]
    # si la foto no alcanza, se reduce la caja manteniendo el rostro centrado
    alto = min(alto, img.height, img.width / aspecto)
    ancho = alto * aspecto
    cx = x + fw / 2
    top = y - alto * r["top_space_ratio"]
    left = cx - ancho / 2
    left = min(max(0.0, left), img.width - ancho)
    top = min(max(0.0, top), img.height - alto)
    caja = (round(left), round(top), round(left + ancho), round(top + alto))
    return caja, r["height"] / alto   # >1 significa que hay que ampliar (pérdida de calidad)


def generate_carnet(img: Image.Image, face_box: list[int] | None, r: dict) -> dict:
    """Genera el archivo de carné. Nunca lanza excepción: devuelve el diagnóstico."""
    if not face_box:
        return {"generated": False, "reason": "no_face"}
    caja, escala = _recorte(img, face_box, r)
    recorte = img.crop(caja).resize((r["width"], r["height"]), Image.Resampling.LANCZOS)

    datos, calidad = b"", 95
    for calidad in (95, 92, 90, 87, 85, 82, 80, 77, 75, 72, 70, 65, 60):
        datos = _jpeg(recorte, calidad, r["dpi"])
        if len(datos) <= r["max_kb"] * 1024:
            break
    # relación del rostro dentro del recorte final (para verificar el encuadre)
    x, y, fw, fh = face_box
    alto_caja = caja[3] - caja[1]
    return {
        "generated": True,
        "bytes": datos,
        "width": r["width"], "height": r["height"], "dpi": r["dpi"], "format": "JPEG",
        "kb": round(len(datos) / 1024, 1),
        "jpeg_quality": calidad,
        "upscale": round(escala, 2),
        "crop_box": list(caja),
        "face_height_ratio": round(fh / alto_caja, 2),
        "shoulders_visible": (caja[3] - (y + fh)) / alto_caja >= 0.18,
    }


def check_upload(info: dict, r: dict) -> dict:
    """Mide el archivo subido tal cual (modo 'validate')."""
    return {
        "format": info.get("format"),
        "width": info.get("width"),
        "height": info.get("height"),
        "kb": round(info.get("bytes", 0) / 1024, 1),
        "dpi": info.get("dpi"),
    }
