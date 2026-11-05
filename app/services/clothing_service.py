"""
Servicio de vestimenta y accesorios: ejecuta YOLOS Fashionpedia, FashionCLIP y
(opcional) SegFormer, y devuelve evidencia estructurada.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from app.models.registry import ModelRegistry

ACCESORIOS_YOLOS = {"hat", "hood", "glasses", "headband, head covering, hair accessory"}


def torso_crop(img: Image.Image, face_box: list[int]) -> Image.Image | None:
    """Recorte desde el mentón hacia abajo, centrado en el rostro."""
    x, y, fw, fh = face_box
    top = int(y + fh * 0.95)
    if img.height - top < fh * 0.35:
        return None
    izq, der = max(0, int(x - fw * 0.9)), min(img.width, int(x + fw * 1.9))
    return img.crop((izq, top, der, img.height))


def face_crop(img: Image.Image, face_box: list[int], margen: float = 0.45) -> Image.Image:
    x, y, fw, fh = face_box
    mx, my = fw * margen, fh * margen
    return img.crop((max(0, int(x - mx)), max(0, int(y - my * 1.3)),
                     min(img.width, int(x + fw + mx)), min(img.height, int(y + fh + my * 0.6))))


def analyze_clothing(img: Image.Image, face_box: list[int] | None, reg: ModelRegistry,
                     seg_mask: np.ndarray | None) -> dict:
    ev: dict = {
        "torso_visible": None,
        "yolos": {"available": reg.yolos is not None, "garments": [], "accessories": []},
        "fashionclip": {"available": reg.fashionclip is not None, "torso": None, "face": None},
        "segformer": {"available": seg_mask is not None},
    }
    if face_box is None:
        return ev

    x, y, fw, fh = face_box
    torso = torso_crop(img, face_box)
    ev["torso_visible"] = torso is not None

    if reg.yolos is not None:
        try:
            for d in reg.yolos.detect(img, min_score=0.3):
                bx0, by0, bx1, by1 = d["box"]
                cy = (by0 + by1) / 2
                if d["label"] in ACCESORIOS_YOLOS:
                    # accesorio cerca de la cabeza
                    if by0 < y + fh and bx1 > x - fw * 0.5 and bx0 < x + fw * 1.5:
                        ev["yolos"]["accessories"].append(d)
                elif cy > y + fh * 0.7:  # prendas/partes bajo el rostro
                    ev["yolos"]["garments"].append(d)
        except Exception as e:
            ev["yolos"]["error"] = str(e)[:200]

    if reg.fashionclip is not None:
        try:
            if torso is not None:
                ev["fashionclip"]["torso"] = reg.fashionclip.torso(torso)
            ev["fashionclip"]["face"] = reg.fashionclip.face(face_crop(img, face_box))
        except Exception as e:
            ev["fashionclip"]["error"] = str(e)[:200]

    if seg_mask is not None:
        xs, ys = slice(max(0, int(x)), int(x + fw)), slice(max(0, int(y - fh * 0.3)), int(y + fh))
        zona = seg_mask[ys, xs]
        total = max(1, zona.size)
        ev["segformer"].update({
            "sunglasses_frac": round(float((zona == 3).sum() / total), 3),
            "hat_frac": round(float((zona == 1).sum() / total), 3),
            "upper_clothes_frac": round(float((seg_mask == 4).mean()), 3),
        })
    return ev
