"""
Exporta los modelos de IA a ONNX (una sola vez, en tu PC) para que el sistema
funcione en Vercel sin PyTorch.

    pip install -r requirements-export.txt
    python scripts/exportar_onnx.py

Genera en models/onnx/:
    fashionclip_vision.onnx     FashionCLIP (patrickjohncyh/fashion-clip), visión, int8
    fashionclip_textos.npz      embeddings precalculados de las frases (app/models/prompts.py)
    yolos_fashionpedia.onnx     YOLOS Fashionpedia (valentinafeve/yolos-fashionpedia), int8
    meta.json                   preprocesamiento, etiquetas y verificación

Al final compara ONNX contra PyTorch con una imagen de prueba e imprime la similitud.
Si cambias las frases de app/models/prompts.py, vuelve a ejecutar este script.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.models import prompts  # noqa: E402

SALIDA = RAIZ / "models" / "onnx"
YOLOS_H, YOLOS_W = 640, 512   # entrada fija vertical (fotos de carné)
OPSET = 17


def _tensor(x):
    return x if hasattr(x, "norm") else x.pooler_output


def _dim(obj, clave: str, defecto: int) -> int:
    """Lee una medida de dict, SizeDict (transformers 5) o entero."""
    if obj is None:
        return defecto
    if isinstance(obj, (int, float)):
        return int(obj)
    v = getattr(obj, clave, None)
    if v is None and hasattr(obj, "get"):
        v = obj.get(clave)
    return int(v) if v else defecto


def exportar_clip(modelo, procesador, salida: Path, cuantizar: bool = True) -> dict:
    import torch

    class Vision(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, pixel_values):
            e = _tensor(self.m.get_image_features(pixel_values=pixel_values))
            return e / e.norm(dim=-1, keepdim=True)

    ip = procesador.image_processor
    lado = _dim(ip.crop_size, "height", 224)
    corto = _dim(ip.size, "shortest_edge", lado)
    x = torch.randn(1, 3, lado, lado)
    tmp = salida / "_clip_fp32.onnx"
    torch.onnx.export(Vision(modelo).eval(), (x,), str(tmp), input_names=["pixel_values"],
                      output_names=["image_embeds"], opset_version=OPSET, dynamo=False)
    final = salida / "fashionclip_vision.onnx"
    _cuantizar(tmp, final, cuantizar)

    with torch.no_grad():
        def textos(frases):
            tok = procesador(text=frases, return_tensors="pt", padding=True)
            e = _tensor(modelo.get_text_features(**tok))
            return (e / e.norm(dim=-1, keepdim=True)).numpy().astype(np.float32)

        np.savez(salida / "fashionclip_textos.npz",
                 torso=textos(prompts.TORSO_FORMAL + prompts.TORSO_INFORMAL),
                 face=textos(list(prompts.FACE.values())),
                 logit_scale=np.float32(modelo.logit_scale.exp().item()))
    return {"size": lado, "shortest_edge": corto, "mean": list(map(float, ip.image_mean)),
            "std": list(map(float, ip.image_std)), "n_formal": len(prompts.TORSO_FORMAL),
            "torso_prompts": prompts.TORSO_FORMAL + prompts.TORSO_INFORMAL,
            "face_keys": list(prompts.FACE)}


def exportar_yolos(modelo, procesador, salida: Path, cuantizar: bool = True) -> dict:
    import torch

    class Det(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, pixel_values):
            o = self.m(pixel_values=pixel_values)
            return o.logits, o.pred_boxes

    x = torch.randn(1, 3, YOLOS_H, YOLOS_W)
    tmp = salida / "_yolos_fp32.onnx"
    torch.onnx.export(Det(modelo).eval(), (x,), str(tmp), input_names=["pixel_values"],
                      output_names=["logits", "pred_boxes"], opset_version=OPSET, dynamo=False)
    _cuantizar(tmp, salida / "yolos_fashionpedia.onnx", cuantizar)
    return {"height": YOLOS_H, "width": YOLOS_W,
            "mean": list(map(float, procesador.image_mean)), "std": list(map(float, procesador.image_std)),
            "labels": {int(k): v for k, v in modelo.config.id2label.items()}}


def _cuantizar(origen: Path, destino: Path, cuantizar: bool):
    if cuantizar:
        from onnxruntime.quantization import QuantType, quantize_dynamic
        quantize_dynamic(str(origen), str(destino), weight_type=QuantType.QInt8)
        origen.unlink()
        datos = origen.with_suffix(".onnx.data")
        if datos.exists():
            datos.unlink()
    else:
        origen.replace(destino)


def verificar(clip_m, clip_p, yolos_m, yolos_p, meta: dict, salida: Path):
    """Compara ONNX vs PyTorch sobre la misma imagen."""
    import torch
    from PIL import Image

    from app.models.onnx_models import FashionClipOnnx, YolosOnnx

    rng = np.random.default_rng(0)
    img = Image.fromarray(rng.integers(0, 255, (600, 480, 3), dtype=np.uint8))
    try:  # si hay una foto real en prueba/, se usa
        fotos = sorted((RAIZ / "fotos_prueba").rglob("*.jp*g"))
        if fotos:
            img = Image.open(fotos[0]).convert("RGB")
    except Exception:
        pass

    fc = FashionClipOnnx(salida)
    with torch.no_grad():
        px = clip_p(images=img, return_tensors="pt")["pixel_values"]
        e = _tensor(clip_m.get_image_features(pixel_values=px))
        e = (e / e.norm(dim=-1, keepdim=True)).numpy()[0]
    sim = float(np.dot(e, fc.embed(img)))

    yo = YolosOnnx(salida)
    t = time.perf_counter()
    dets = yo.detect(img, min_score=0.3)
    ms = (time.perf_counter() - t) * 1000
    print(f"\n[verificación] similitud FashionCLIP ONNX vs PyTorch: {sim:.4f} (ideal > 0.97)")
    print(f"[verificación] YOLOS ONNX: {len(dets)} detecciones en {ms:.0f} ms {[d['label'] for d in dets[:5]]}")
    print(f"[verificación] torso: {fc.torso(img)}")
    meta["verificacion"] = {"clip_cosine_vs_torch": round(sim, 4)}
    if sim < 0.95:
        print("[AVISO] La similitud es baja: prueba con --sin-cuantizar")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", default="patrickjohncyh/fashion-clip")
    ap.add_argument("--yolos", default="valentinafeve/yolos-fashionpedia")
    ap.add_argument("--sin-cuantizar", action="store_true", help="ONNX fp32 (más grande, máxima fidelidad)")
    ap.add_argument("--prueba", action="store_true", help="usa modelos aleatorios pequeños (solo para probar el script)")
    a = ap.parse_args()
    SALIDA.mkdir(parents=True, exist_ok=True)
    cuant = not a.sin_cuantizar

    from transformers import (AutoImageProcessor, AutoModelForObjectDetection, CLIPConfig, CLIPModel,
                              CLIPProcessor, YolosConfig, YolosForObjectDetection, YolosImageProcessor)

    if a.prueba:
        print("[prueba] modelos aleatorios (no sirven para validar fotos)")
        cc = CLIPConfig(text_config={"hidden_size": 64, "intermediate_size": 128, "num_hidden_layers": 2,
                                     "num_attention_heads": 2},
                        vision_config={"hidden_size": 64, "intermediate_size": 128, "num_hidden_layers": 2,
                                       "num_attention_heads": 2, "patch_size": 32}, projection_dim=32)
        clip_m = CLIPModel(cc).eval()
        clip_p = CLIPProcessor.from_pretrained(a.clip) if False else _procesador_clip_local()
        labels = ["shirt, blouse", "top, t-shirt, sweatshirt", "jacket", "tie", "collar", "lapel", "hat", "glasses"]
        yc = YolosConfig(hidden_size=64, num_hidden_layers=2, num_attention_heads=2, intermediate_size=128,
                         image_size=[512, 864], patch_size=16, num_detection_tokens=20, use_mid_position_embeddings=True,
                         id2label=dict(enumerate(labels)), label2id={v: i for i, v in enumerate(labels)})
        yolos_m = YolosForObjectDetection(yc).eval()
        yolos_p = YolosImageProcessor()
    else:
        print(f"[descargando/cargando] {a.clip}")
        clip_m = CLIPModel.from_pretrained(a.clip).eval()
        clip_p = CLIPProcessor.from_pretrained(a.clip)
        print(f"[descargando/cargando] {a.yolos}")
        yolos_m = AutoModelForObjectDetection.from_pretrained(a.yolos).eval()
        yolos_p = AutoImageProcessor.from_pretrained(a.yolos)

    print("[exportando] FashionCLIP → ONNX")
    meta = {"clip": exportar_clip(clip_m, clip_p, SALIDA, cuant)}
    print("[exportando] YOLOS → ONNX")
    meta["yolos"] = exportar_yolos(yolos_m, yolos_p, SALIDA, cuant)
    meta["origen"] = {"clip": a.clip, "yolos": a.yolos, "cuantizado": cuant, "prueba": a.prueba}
    (SALIDA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    verificar(clip_m, clip_p, yolos_m, yolos_p, meta, SALIDA)
    (SALIDA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    for f in sorted(SALIDA.iterdir()):
        print(f"  {f.name:<28} {f.stat().st_size / 1e6:7.1f} MB")
    print(f"\nListo. Archivos en {SALIDA}")


def _procesador_clip_local():
    """Procesador CLIP mínimo sin descargar nada (solo para --prueba)."""
    import torch
    from transformers import CLIPImageProcessor

    class Proc:
        image_processor = CLIPImageProcessor()

        def __call__(self, text=None, images=None, return_tensors=None, padding=None):
            if images is not None:
                return self.image_processor(images=images, return_tensors="pt")
            ids = torch.tensor([[0] + [2 + (sum(map(ord, t)) + j) % 40 for j in range(6)] + [1] for t in text])
            return {"input_ids": ids, "attention_mask": torch.ones_like(ids)}

    return Proc()


if __name__ == "__main__":
    main()
