"""
Descarga todos los modelos preentrenados a la carpeta models/ (una sola vez).

    python scripts/download_models.py            # modelos principales
    python scripts/download_models.py --segformer  # incluye el opcional SegFormer

Después el servicio funciona sin internet.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings  # noqa: E402  (configura HF_HOME dentro de models/)

ARCHIVOS = {
    settings.yunet_file: (
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/"
        "face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",  # verificado 2026-11-05
    ),
    settings.mediapipe_file: (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/"
        "face_landmarker.task",
        None,
    ),
}


def descargar(nombre: str, url: str, sha: str | None):
    destino = settings.models_dir / nombre
    if destino.exists():
        print(f"[ya existe] {nombre}")
        return
    print(f"[descargando] {nombre} …")
    urllib.request.urlretrieve(url, destino)
    if sha and hashlib.sha256(destino.read_bytes()).hexdigest() != sha:
        destino.unlink()
        raise SystemExit(f"[ERROR] Checksum incorrecto en {nombre}")
    print(f"[ok] {nombre} ({destino.stat().st_size / 1024:.0f} KB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segformer", action="store_true")
    a = ap.parse_args()
    for n, (u, s) in ARCHIVOS.items():
        descargar(n, u, s)

    from huggingface_hub import snapshot_download

    hf = [settings.yolos_model, settings.fashionclip_model] + ([settings.segformer_model] if a.segformer else [])
    for repo in hf:
        print(f"[descargando] {repo} (Hugging Face) …")
        snapshot_download(repo, allow_patterns=["*.json", "*.txt", "*.safetensors", "*.model", "merges.txt"])
        print(f"[ok] {repo}")
    print(f"\nModelos guardados en: {settings.models_dir}")


if __name__ == "__main__":
    main()
