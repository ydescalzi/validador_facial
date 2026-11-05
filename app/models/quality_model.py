"""
Métricas de calidad de imagen con OpenCV (visión artificial clásica, sin IA).
Funciones puras: reciben arrays y devuelven números.
"""
from __future__ import annotations

import cv2
import numpy as np


def sharpness(gray_region: np.ndarray) -> float:
    """Varianza del Laplaciano sobre la región normalizada a 256 px de ancho."""
    if gray_region.size == 0:
        return 0.0
    h, w = gray_region.shape[:2]
    r = cv2.resize(gray_region, (256, max(1, int(256 * h / max(w, 1)))))
    return float(cv2.Laplacian(r, cv2.CV_64F).var())


def brightness_contrast(gray_region: np.ndarray) -> tuple[float, float]:
    if gray_region.size == 0:
        return 0.0, 0.0
    return float(gray_region.mean()), float(gray_region.std())


def saturated_pct(gray_region: np.ndarray) -> tuple[float, float]:
    """Porcentaje de píxeles quemados (>250) y negros (<5)."""
    if gray_region.size == 0:
        return 0.0, 0.0
    return float((gray_region > 250).mean()), float((gray_region < 5).mean())


def background_from_borders(gray: np.ndarray, borde: float = 0.06) -> tuple[float, float]:
    """
    Tono (mediana) y uniformidad (fracción de píxeles a ±30 del tono) de la franja
    superior y los bordes laterales de la mitad superior. Evita la zona central
    para no confundir el cabello con el fondo.
    """
    return _tono_uniformidad(border_pixels(gray, borde))


def border_pixels(arr: np.ndarray, borde: float = 0.06) -> np.ndarray:
    """Píxeles de la franja superior y de los bordes laterales de la mitad superior."""
    h, w = arr.shape[:2]
    bw, bh = max(2, int(w * borde)), max(2, int(h * borde))
    alto = int(h * 0.45)
    return np.concatenate([arr[:bh, :].ravel(), arr[:alto, :bw].ravel(), arr[:alto, w - bw:].ravel()])


def background_from_mask(gray: np.ndarray, mask_fondo: np.ndarray) -> tuple[float, float] | None:
    """Igual que arriba, pero usando la máscara de fondo de un segmentador."""
    px = gray[mask_fondo]
    if px.size < 0.03 * gray.size:
        return None
    return _tono_uniformidad(px)


def _tono_uniformidad(px: np.ndarray) -> tuple[float, float]:
    px = px.astype(np.int16)
    tono = float(np.median(px))
    return tono, float((np.abs(px - tono) <= 30).mean())
