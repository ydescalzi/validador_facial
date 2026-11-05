"""
Modelos de vestimenta ejecutados con ONNX Runtime (sin PyTorch), para Vercel.

Los archivos se generan una vez con  python scripts/exportar_onnx.py  y quedan en
models/onnx/. La interfaz es la misma que usaban las versiones PyTorch:
    YolosOnnx.detect(img)            → [{"label", "score", "box":[x0,y0,x1,y1]}]
    FashionClipOnnx.torso(img)       → {"formal_prob", "top_label", "top_prob"}
    FashionClipOnnx.face(img)        → {"bare": p, "eyeglasses": p, "sunglasses": p, ...}
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np
from PIL import Image


def _sesion(ruta: Path):
    import onnxruntime as ort
    if not ruta.exists():
        raise FileNotFoundError(f"No existe {ruta}. Ejecuta en tu PC: python scripts/exportar_onnx.py")
    op = ort.SessionOptions()
    op.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    op.intra_op_num_threads = 2
    return ort.InferenceSession(str(ruta), sess_options=op, providers=["CPUExecutionProvider"])


def _meta(carpeta: Path) -> dict:
    return json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))


def _softmax(x: np.ndarray, eje: int = -1) -> np.ndarray:
    x = x - x.max(axis=eje, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=eje, keepdims=True)


def _normalizar(arr: np.ndarray, mean, std) -> np.ndarray:
    a = arr.astype(np.float32) / 255.0
    a = (a - np.array(mean, np.float32)) / np.array(std, np.float32)
    return a.transpose(2, 0, 1)[None]


class FashionClipOnnx:
    def __init__(self, carpeta: Path):
        m = _meta(carpeta)
        self.cfg = m["clip"]
        self.name = f"{m['origen']['clip']} (ONNX)"
        self.sesion = _sesion(carpeta / "fashionclip_vision.onnx")
        t = np.load(carpeta / "fashionclip_textos.npz")
        self.torso_txt, self.face_txt = t["torso"], t["face"]
        self.escala = float(t["logit_scale"])
        self.n_formal = self.cfg["n_formal"]
        self.frases = self.cfg["torso_prompts"]
        self.face_keys = self.cfg["face_keys"]
        self._lock = threading.Lock()

    def _preparar(self, img: Image.Image) -> np.ndarray:
        """Igual que CLIPImageProcessor: lado corto → 224 (bicúbico), recorte central 224."""
        corto, lado = self.cfg["shortest_edge"], self.cfg["size"]
        w, h = img.size
        f = corto / min(w, h)
        img = img.convert("RGB").resize((max(lado, round(w * f)), max(lado, round(h * f))), Image.Resampling.BICUBIC)
        w, h = img.size
        x0, y0 = (w - lado) // 2, (h - lado) // 2
        return _normalizar(np.asarray(img.crop((x0, y0, x0 + lado, y0 + lado))), self.cfg["mean"], self.cfg["std"])

    def embed(self, img: Image.Image) -> np.ndarray:
        with self._lock:
            e = self.sesion.run(None, {"pixel_values": self._preparar(img)})[0][0]
        return e / np.linalg.norm(e)

    def torso(self, img: Image.Image) -> dict:
        p = _softmax(self.escala * (self.torso_txt @ self.embed(img)))
        i = int(p.argmax())
        return {"formal_prob": round(float(p[:self.n_formal].sum()), 3), "top_label": self.frases[i],
                "top_prob": round(float(p[i]), 3)}

    def face(self, img: Image.Image) -> dict:
        p = _softmax(self.escala * (self.face_txt @ self.embed(img)))
        return {k: round(float(v), 3) for k, v in zip(self.face_keys, p)}


class YolosOnnx:
    def __init__(self, carpeta: Path):
        m = _meta(carpeta)
        self.cfg = m["yolos"]
        self.name = f"{m['origen']['yolos']} (ONNX)"
        self.labels = {int(k): v for k, v in self.cfg["labels"].items()}
        self.sesion = _sesion(carpeta / "yolos_fashionpedia.onnx")
        self._lock = threading.Lock()

    def detect(self, img: Image.Image, min_score: float = 0.3) -> list[dict]:
        W, H = img.size
        x = img.convert("RGB").resize((self.cfg["width"], self.cfg["height"]), Image.Resampling.BILINEAR)
        with self._lock:
            logits, boxes = self.sesion.run(None, {"pixel_values": _normalizar(np.asarray(x), self.cfg["mean"],
                                                                                self.cfg["std"])})
        prob = _softmax(logits[0])[:, :-1]          # la última clase es "sin objeto"
        etiqueta, score = prob.argmax(-1), prob.max(-1)
        dets = []
        for i in np.where(score >= min_score)[0]:
            cx, cy, bw, bh = boxes[0, i]
            dets.append({"label": self.labels.get(int(etiqueta[i]), str(int(etiqueta[i]))),
                         "score": round(float(score[i]), 3),
                         "box": [round(float((cx - bw / 2) * W), 1), round(float((cy - bh / 2) * H), 1),
                                 round(float((cx + bw / 2) * W), 1), round(float((cy + bh / 2) * H), 1)]})
        return sorted(dets, key=lambda d: d["score"], reverse=True)
