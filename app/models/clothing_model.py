"""
Modelos de vestimenta preentrenados (Hugging Face, ejecución local).

- YOLOS Fashionpedia: detecta prendas y PARTES de prendas (cuello, solapa,
  corbata, capucha...). 46 clases.
- FashionCLIP: CLIP afinado con productos de moda. Clasificación zero-shot del
  recorte del torso (formal vs. informal) y del rostro (lentes de sol, gorra...).
- SegFormer B2 Clothes (opcional): segmentación persona/fondo/prendas.

Solo producen datos; la decisión la toma el motor de reglas.
"""
from __future__ import annotations

import threading

import numpy as np
from PIL import Image


def _device(pref: str) -> str:
    import torch
    if pref == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return pref


def _as_tensor(x):
    """transformers 5 puede devolver un objeto de salida en lugar de un tensor."""
    return x if hasattr(x, "norm") else x.pooler_output


class YolosFashionpedia:
    def __init__(self, model_id: str, device: str = "auto"):
        import torch
        from transformers import AutoImageProcessor, AutoModelForObjectDetection

        self.name = model_id
        self.torch = torch
        self.device = _device(device)
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = AutoModelForObjectDetection.from_pretrained(model_id).to(self.device).eval()
        self.labels = self.model.config.id2label
        self._lock = threading.Lock()

    def detect(self, img: Image.Image, min_score: float = 0.3) -> list[dict]:
        torch = self.torch
        with self._lock, torch.no_grad():
            inputs = self.processor(images=img, return_tensors="pt").to(self.device)
            out = self.model(**inputs)
            res = self.processor.post_process_object_detection(
                out, threshold=min_score, target_sizes=[(img.height, img.width)])[0]
        dets = []
        for s, l, b in zip(res["scores"], res["labels"], res["boxes"]):
            dets.append({"label": self.labels[int(l)], "score": round(float(s), 3),
                         "box": [round(float(v), 1) for v in b.tolist()]})
        return sorted(dets, key=lambda d: d["score"], reverse=True)


class FashionCLIP:
    """Zero-shot con frases de estructura idéntica y neutras en género."""

    TORSO_FORMAL = [
        "a person wearing a suit jacket over a dress shirt",
        "a person wearing a blazer over a collared shirt",
        "a person wearing a buttoned collared dress shirt",
        "a person wearing a formal blouse with a collar",
        "a person wearing a shirt and tie",
    ]
    TORSO_INFORMAL = [
        "a person wearing a crew neck t-shirt",
        "a person wearing a colored cotton t-shirt",
        "a person wearing a polo shirt",
        "a person wearing a hoodie or sweatshirt",
        "a person wearing a tank top",
        "a person wearing a sports jersey or tracksuit",
    ]
    FACE = {
        "bare": ["a close-up photo of a face with bare eyes and uncovered hair"],
        "eyeglasses": ["a close-up photo of a face wearing clear prescription eyeglasses"],
        "sunglasses": ["a close-up photo of a face wearing dark sunglasses"],
        "hat": ["a close-up photo of a face wearing a baseball cap or hat"],
        "headphones": ["a close-up photo of a face wearing headphones"],
        "face_mask": ["a close-up photo of a face wearing a medical face mask"],
    }

    def __init__(self, model_id: str, device: str = "auto"):
        import torch
        from transformers import CLIPModel, CLIPProcessor

        self.name = model_id
        self.torch = torch
        self.device = _device(device)
        self.model = CLIPModel.from_pretrained(model_id).to(self.device).eval()
        self.processor = CLIPProcessor.from_pretrained(model_id)
        self._lock = threading.Lock()
        self._torso_txt = self._encode_text(self.TORSO_FORMAL + self.TORSO_INFORMAL)
        self._face_keys = list(self.FACE)
        self._face_txt = self._encode_text([v[0] for v in self.FACE.values()])

    def _encode_text(self, frases: list[str]):
        with self.torch.no_grad():
            tok = self.processor(text=frases, return_tensors="pt", padding=True).to(self.device)
            e = _as_tensor(self.model.get_text_features(**tok))
            return e / e.norm(dim=-1, keepdim=True)

    def _probs(self, img: Image.Image, txt):
        with self._lock, self.torch.no_grad():
            px = self.processor(images=img, return_tensors="pt").to(self.device)
            e = _as_tensor(self.model.get_image_features(**px))
            e = e / e.norm(dim=-1, keepdim=True)
            return (self.model.logit_scale.exp() * e @ txt.T).softmax(dim=-1)[0].cpu().numpy()

    def torso(self, img: Image.Image) -> dict:
        p = self._probs(img, self._torso_txt)
        n = len(self.TORSO_FORMAL)
        frases = self.TORSO_FORMAL + self.TORSO_INFORMAL
        i = int(np.argmax(p))
        return {"formal_prob": round(float(p[:n].sum()), 3), "top_label": frases[i], "top_prob": round(float(p[i]), 3)}

    def face(self, img: Image.Image) -> dict:
        p = self._probs(img, self._face_txt)
        return {k: round(float(v), 3) for k, v in zip(self._face_keys, p)}


class SegformerClothes:
    """Etiquetas ATR: 0 fondo, 1 sombrero, 2 cabello, 3 lentes de sol, 4 prenda superior, 11 rostro..."""

    def __init__(self, model_id: str, device: str = "auto"):
        import torch
        from transformers import AutoModelForSemanticSegmentation, SegformerImageProcessor

        self.name = model_id
        self.torch = torch
        self.device = _device(device)
        self.processor = SegformerImageProcessor.from_pretrained(model_id)
        self.model = AutoModelForSemanticSegmentation.from_pretrained(model_id).to(self.device).eval()
        self._lock = threading.Lock()

    def segment(self, img: Image.Image) -> np.ndarray:
        torch = self.torch
        with self._lock, torch.no_grad():
            inputs = self.processor(images=img, return_tensors="pt").to(self.device)
            logits = self.model(**inputs).logits
            up = torch.nn.functional.interpolate(logits, size=(img.height, img.width), mode="bilinear",
                                                 align_corners=False)
            return up.argmax(dim=1)[0].cpu().numpy().astype(np.uint8)
