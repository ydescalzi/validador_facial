"""Orquesta: imagen → servicios de IA/visión (evidencia) → motor de reglas (decisión)."""
from __future__ import annotations

import time

import cv2
import numpy as np
from PIL import Image

from app.models.registry import ModelRegistry
from app.services import validation_engine as engine
from app.services.carnet import check_upload, generate_carnet
from app.services.clothing_service import analyze_clothing
from app.services.face_service import analyze_face
from app.services.image_quality import analyze_quality

MENSAJES = {
    engine.APPROVED: "Cumple con los requisitos para el carné universitario.",
    engine.REJECTED: "Vuelve a subir tu foto, ya que fue rechazada por no cumplir los requisitos.",
    engine.MANUAL_REVIEW: "Tu fotografía será revisada por el personal de la universidad. "
                          "Te avisaremos cuando tenga un resultado.",
}


def gather_evidence(img: Image.Image, rules: dict, reg: ModelRegistry) -> tuple[dict, dict]:
    tiempos: dict[str, float] = {}
    t = time.perf_counter()
    rgb = np.array(img)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    ev: dict = {"image": {"width": img.width, "height": img.height}}

    t0 = time.perf_counter()
    ev["face"] = analyze_face(bgr, rgb, rules, reg)
    tiempos["face_ms"] = (time.perf_counter() - t0) * 1000
    box = ev["face"]["primary"]["box"] if ev["face"].get("primary") else None

    seg = None
    if reg.segformer is not None:
        t0 = time.perf_counter()
        try:
            seg = reg.segformer.segment(img)
        except Exception:
            seg = None
        tiempos["segmentation_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    saturacion = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[:, :, 1]
    ev["quality"] = analyze_quality(gray, box, seg, saturacion)
    tiempos["quality_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    ev["clothing"] = analyze_clothing(img, box, reg, seg)
    tiempos["clothing_ms"] = (time.perf_counter() - t0) * 1000

    tiempos["total_ms"] = (time.perf_counter() - t) * 1000
    return ev, {k: round(v) for k, v in tiempos.items()}


def run_validation(img: Image.Image, rules: dict, reg: ModelRegistry, info: dict | None = None) -> dict:
    ev, tiempos = gather_evidence(img, rules, reg)

    # Formato de carné: generar el archivo exacto o medir el archivo subido
    carnet_bytes = None
    rc = rules.get("carnet", {})
    if rc.get("enabled"):
        box = ev["face"]["primary"]["box"] if ev["face"].get("primary") else None
        if rc["mode"] == "generate":
            g = generate_carnet(img, box, rc)
            carnet_bytes = g.pop("bytes", None)
            ev["carnet"] = {"mode": "generate", **g}
        else:
            ev["carnet"] = {"mode": "validate", **check_upload(info or {}, rc)}

    res = engine.evaluate(ev, rules)
    res["carnet_bytes"] = carnet_bytes
    res["results"] = engine.results_summary(res["criteria"])
    res["message"] = MENSAJES[res["status"]]
    res["evidence"] = ev
    res["timings"] = tiempos
    res["models_used"] = [s["name"] for k, s in reg.status.items() if s.get("loaded")] + ["OpenCV (calidad de imagen)"]
    return res
