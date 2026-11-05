"""
Carga de los modelos (perezosa y una sola vez por proceso).

Funciona igual en tu PC, en Docker y en Vercel (función serverless): los modelos se
cargan con la primera petición. Si un modelo falla, el servicio sigue funcionando y
los criterios que dependen de él se tratan como dudosos (nunca se aprueba algo que no
se pudo evaluar).

Modelos:
  yunet        YuNet (OpenCV Zoo)                       models/face_detection_yunet_2023mar.onnx
  yolos        YOLOS Fashionpedia (ONNX int8)           models/onnx/yolos_fashionpedia.onnx
  fashionclip  FashionCLIP (ONNX int8 + textos)         models/onnx/fashionclip_vision.onnx
  mediapipe    MediaPipe Face Landmarker (opcional)     solo si instalas mediapipe y ENABLE_MEDIAPIPE=1
"""
from __future__ import annotations

import logging
import threading
import time

from app.core.config import settings

log = logging.getLogger("photo_validator.models")


class ModelRegistry:
    def __init__(self):
        self.yunet = None
        self.mediapipe = None
        self.yolos = None
        self.fashionclip = None
        self.segformer = None       # se conserva el atributo (ya no se usa)
        self.status: dict[str, dict] = {}
        self._cargado = False
        self._lock = threading.Lock()

    def _cargar(self, clave: str, habilitado: bool, fabrica, nombre: str):
        if not habilitado:
            self.status[clave] = {"name": nombre, "loaded": False, "enabled": False}
            return
        t = time.perf_counter()
        try:
            setattr(self, clave, fabrica())
            self.status[clave] = {"name": getattr(getattr(self, clave), "name", nombre), "loaded": True,
                                  "enabled": True, "load_seconds": round(time.perf_counter() - t, 2)}
            log.info("Modelo cargado: %s (%.1fs)", nombre, time.perf_counter() - t)
        except Exception as e:
            self.status[clave] = {"name": nombre, "loaded": False, "enabled": True, "error": str(e)[:300]}
            log.warning("No se pudo cargar %s: %s", nombre, e)

    def load_all(self):
        from app.models.face_model import MediaPipeLandmarker, YuNetDetector
        from app.models.onnx_models import FashionClipOnnx, YolosOnnx

        onnx = settings.models_dir / "onnx"
        self._cargar("yunet", True, lambda: YuNetDetector(settings.yunet_path), "YuNet (OpenCV Zoo)")
        self._cargar("mediapipe", settings.enable_mediapipe,
                     lambda: MediaPipeLandmarker(settings.mediapipe_path), "MediaPipe Face Landmarker")
        self._cargar("yolos", settings.enable_yolos, lambda: YolosOnnx(onnx), "YOLOS Fashionpedia (ONNX)")
        self._cargar("fashionclip", settings.enable_fashionclip, lambda: FashionClipOnnx(onnx), "FashionCLIP (ONNX)")
        self._cargado = True

    def ensure_loaded(self):
        """Carga los modelos la primera vez que se necesitan (seguro entre hilos)."""
        if self._cargado:
            return
        with self._lock:
            if not self._cargado:
                self.load_all()

    def loaded_names(self) -> list[str]:
        return [s["name"] for s in self.status.values() if s.get("loaded")]


registry = ModelRegistry()
