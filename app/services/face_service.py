"""Servicio facial: ejecuta YuNet (+ MediaPipe si está disponible) y devuelve evidencia."""
from __future__ import annotations

import cv2
import numpy as np

from app.models.registry import ModelRegistry

_haar_ojos = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye_tree_eyeglasses.xml")


def analyze_face(bgr: np.ndarray, rgb: np.ndarray, rules: dict, reg: ModelRegistry) -> dict:
    h, w = bgr.shape[:2]
    ev: dict = {"available": reg.yunet is not None, "count": 0, "primary": None,
                "other_people": 0, "mediapipe": None, "haar_eyes": None}
    if reg.yunet is None:
        return ev

    r = rules["face"]
    caras = [c for c in reg.yunet.detect(bgr) if c.score >= r["min_confidence"]]
    ev["count"] = len(caras)
    if not caras:
        return ev

    p = caras[0]
    ev["other_people"] = sum(1 for c in caras[1:] if c.area >= r["secondary_face_ratio"] * p.area)
    ev["primary"] = {
        "box": [round(p.x), round(p.y), round(p.w), round(p.h)],
        "confidence": round(p.score, 3),
        "size_ratio": round(p.w / w, 3),
        "center_offset": round(abs((p.x + p.w / 2) / w - 0.5), 3),
        "top_margin": round(p.y / h, 3),
        "shoulders_space": round((h - (p.y + p.h)) / h, 3),
        "yunet_roll_deg": round(p.roll_deg(), 1),
        "yunet_yaw_ratio": round(p.yaw_ratio(), 3),
    }

    if reg.mediapipe is not None:
        try:
            ev["mediapipe"] = {k: (round(v, 3) if isinstance(v, float) else v)
                               for k, v in reg.mediapipe.analyze(rgb).items()}
        except Exception as e:
            ev["mediapipe"] = {"error": str(e)[:200]}
    else:
        # Respaldo poco fiable (Haar): solo puede enviar a revisión, nunca rechazar
        x, y, fw, fh = (int(max(0, v)) for v in (p.x, p.y, p.w, p.h))
        zona = cv2.equalizeHist(cv2.cvtColor(bgr[y:y + int(fh * 0.6), x:x + fw], cv2.COLOR_BGR2GRAY))
        if zona.size:
            ojos = _haar_ojos.detectMultiScale(zona, 1.1, 5, minSize=(max(8, fw // 10),) * 2)
            ev["haar_eyes"] = int(len(ojos))
    return ev
