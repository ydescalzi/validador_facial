"""Modelos ONNX (los de Vercel): se generan versiones pequeñas aleatorias para probar el código."""
import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


@pytest.fixture(scope="module")
def carpeta_onnx(tmp_path_factory):
    torch = pytest.importorskip("torch")
    pytest.importorskip("transformers")
    pytest.importorskip("onnx")
    from transformers import CLIPConfig, CLIPModel, YolosConfig, YolosForObjectDetection, YolosImageProcessor
    from scripts.exportar_onnx import _procesador_clip_local, exportar_clip, exportar_yolos

    torch.manual_seed(0)
    out = tmp_path_factory.mktemp("onnx")
    small = {"hidden_size": 64, "intermediate_size": 128, "num_hidden_layers": 2, "num_attention_heads": 2}
    clip = CLIPModel(CLIPConfig(text_config=small, vision_config={**small, "patch_size": 32}, projection_dim=32)).eval()
    labels = ["shirt, blouse", "top, t-shirt, sweatshirt", "jacket", "glasses", "hat"]
    yolos = YolosForObjectDetection(YolosConfig(**small, image_size=[512, 864], patch_size=16, num_detection_tokens=20,
                                                use_mid_position_embeddings=True, id2label=dict(enumerate(labels)),
                                                label2id={})).eval()
    meta = {"clip": exportar_clip(clip, _procesador_clip_local(), out),
            "yolos": exportar_yolos(yolos, YolosImageProcessor(), out),
            "origen": {"clip": "prueba-clip", "yolos": "prueba-yolos", "cuantizado": True, "prueba": True}}
    (out / "meta.json").write_text(json.dumps(meta))
    return out


def test_fashionclip_onnx(carpeta_onnx):
    from app.models.onnx_models import FashionClipOnnx
    m = FashionClipOnnx(carpeta_onnx)
    img = Image.new("RGB", (480, 600), (200, 180, 160))
    t = m.torso(img)
    assert 0 <= t["formal_prob"] <= 1 and t["top_label"]
    f = m.face(img)
    assert set(f) == {"bare", "eyeglasses", "sunglasses", "hat", "headphones", "face_mask"}
    assert abs(sum(f.values()) - 1) < 0.01


def test_yolos_onnx(carpeta_onnx):
    from app.models.onnx_models import YolosOnnx
    dets = YolosOnnx(carpeta_onnx).detect(Image.new("RGB", (480, 600), (120, 120, 120)), min_score=0.0)
    assert dets and {"label", "score", "box"} <= set(dets[0])
    x0, y0, x1, y1 = dets[0]["box"]
    assert -600 < x0 < 1200 and -600 < y1 < 1300   # coordenadas en píxeles de la imagen original


def test_pipeline_completo_con_onnx(carpeta_onnx):
    skimage = pytest.importorskip("skimage")
    from skimage import data
    from app.core.config import default_rules, settings
    from app.models.face_model import YuNetDetector
    from app.models.onnx_models import FashionClipOnnx, YolosOnnx
    from app.models.registry import ModelRegistry
    from app.services.pipeline import run_validation

    reg = ModelRegistry()
    reg.yunet = YuNetDetector(settings.yunet_path)
    reg.fashionclip, reg.yolos = FashionClipOnnx(carpeta_onnx), YolosOnnx(carpeta_onnx)
    reg.status = {k: {"name": k, "loaded": True} for k in ("yunet", "fashionclip", "yolos")}
    cara = Image.fromarray(data.astronaut()).rotate(9, center=(230, 120), fillcolor=(240, 240, 240))
    img = Image.new("RGB", (900, 1200), (250, 250, 250))
    img.paste(cara.crop((120, 0, 340, 300)).resize((440, 600)), (230, 300))
    r = run_validation(img, default_rules(), reg)
    c = r["evidence"]["clothing"]
    assert c["fashionclip"]["torso"] is not None and c["fashionclip"]["face"] is not None
    ropa = next(x for x in r["criteria"] if x["key"] == "formal_clothing")
    assert ropa["message"] != "No se pudo analizar la vestimenta automáticamente."
