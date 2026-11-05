"""
Modelos faciales preentrenados.

- YuNet (OpenCV Zoo, MIT): detección de rostros + 5 puntos. Principal.
- MediaPipe Face Landmarker (Google): 478 puntos, blendshapes (ojos cerrados) y
  matriz de pose 3D. Segunda opinión para orientación y ojos.

Estos wrappers SOLO ejecutan los modelos y devuelven datos; las decisiones las
toma el motor de reglas (services/validation_engine.py).
"""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class FaceDetection:
    x: float
    y: float
    w: float
    h: float
    score: float
    right_eye: tuple[float, float]
    left_eye: tuple[float, float]
    nose: tuple[float, float]
    mouth_right: tuple[float, float]
    mouth_left: tuple[float, float]

    @property
    def area(self) -> float:
        return self.w * self.h

    def roll_deg(self) -> float:
        dx = self.left_eye[0] - self.right_eye[0]
        dy = self.left_eye[1] - self.right_eye[1]
        return math.degrees(math.atan2(dy, dx))

    def yaw_ratio(self) -> float:
        """Desplazamiento horizontal de la nariz respecto al centro de los ojos,
        normalizado por la distancia entre ojos (0 = frontal)."""
        cx = (self.left_eye[0] + self.right_eye[0]) / 2
        iod = math.dist(self.left_eye, self.right_eye) or 1.0
        return (self.nose[0] - cx) / iod


class YuNetDetector:
    name = "YuNet face_detection_yunet_2023mar (OpenCV Zoo)"

    def __init__(self, model_path: Path, score_threshold: float = 0.6):
        if not model_path.exists():
            raise FileNotFoundError(f"No existe {model_path}. Ejecuta: python scripts/exportar_onnx.py")
        self._det = cv2.FaceDetectorYN.create(str(model_path), "", (320, 320), score_threshold, 0.3, 5000)
        self._lock = threading.Lock()

    def detect(self, bgr: np.ndarray) -> list[FaceDetection]:
        h, w = bgr.shape[:2]
        # YuNet trabaja mejor con imágenes de tamaño moderado
        escala = min(1.0, 1280 / max(h, w))
        img = cv2.resize(bgr, (int(w * escala), int(h * escala))) if escala < 1 else bgr
        with self._lock:
            self._det.setInputSize((img.shape[1], img.shape[0]))
            _, caras = self._det.detect(img)
        salida = []
        for f in ([] if caras is None else caras):
            v = [float(t) / escala for t in f[:14]]
            salida.append(FaceDetection(v[0], v[1], v[2], v[3], float(f[14]),
                                        (v[4], v[5]), (v[6], v[7]), (v[8], v[9]), (v[10], v[11]), (v[12], v[13])))
        return sorted(salida, key=lambda d: d.area, reverse=True)


class MediaPipeLandmarker:
    name = "MediaPipe Face Landmarker (float16)"

    def __init__(self, model_path: Path):
        if not model_path.exists():
            raise FileNotFoundError(f"No existe {model_path}. Ejecuta: python scripts/exportar_onnx.py")
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        opciones = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=3,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._lm = vision.FaceLandmarker.create_from_options(opciones)
        self._lock = threading.Lock()

    def analyze(self, rgb: np.ndarray) -> dict:
        imagen = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        with self._lock:
            r = self._lm.detect(imagen)
        n = len(r.face_landmarks)
        if n == 0:
            return {"faces": 0}
        salida = {"faces": n}
        if r.facial_transformation_matrixes:
            m = np.array(r.facial_transformation_matrixes[0])[:3, :3]
            salida["pitch"] = math.degrees(math.atan2(m[2, 1], m[2, 2]))
            salida["yaw"] = math.degrees(math.atan2(-m[2, 0], math.hypot(m[2, 1], m[2, 2])))
            salida["roll"] = math.degrees(math.atan2(m[1, 0], m[0, 0]))
        if r.face_blendshapes:
            bs = {c.category_name: float(c.score) for c in r.face_blendshapes[0]}
            salida["blink_left"] = bs.get("eyeBlinkLeft")
            salida["blink_right"] = bs.get("eyeBlinkRight")
        return salida
