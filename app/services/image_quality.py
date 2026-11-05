"""Servicio de calidad de imagen (OpenCV)."""
from __future__ import annotations

import numpy as np

from app.models import quality_model as q


def analyze_quality(gray: np.ndarray, face_box: list[int] | None, seg_mask: np.ndarray | None,
                    saturation: np.ndarray | None = None) -> dict:
    h, w = gray.shape
    if face_box:
        x, y, fw, fh = (max(0, int(v)) for v in face_box)
        region = gray[y:y + fh, x:x + fw]
    else:  # sin rostro: zona central
        region = gray[h // 4: 3 * h // 4, w // 4: 3 * w // 4]

    brillo, contraste = q.brightness_contrast(region)
    quemado, negro = q.saturated_pct(region)
    ev = {
        "sharpness": round(q.sharpness(region), 1),
        "brightness": round(brillo, 1),
        "contrast": round(contraste, 1),
        "overexposed_pct": round(quemado, 3),
        "underexposed_pct": round(negro, 3),
    }

    fondo = None
    metodo = "borders"
    mascara = seg_mask == 0 if seg_mask is not None else None
    if mascara is not None:
        fondo = q.background_from_mask(gray, mascara)
        metodo = "segmentation"
    if fondo is None:
        fondo = q.background_from_borders(gray)
        metodo = "borders"
    ev["background"] = {"brightness": round(fondo[0], 1), "uniformity": round(fondo[1], 3), "method": metodo}

    # Saturación del fondo (0 = gris/blanco puro, alto = color: celeste, crema…)
    if saturation is not None:
        px = saturation[mascara] if metodo == "segmentation" else q.border_pixels(saturation)
        ev["background"]["saturation"] = round(float(np.median(px)), 1) if px.size else None
    return ev
