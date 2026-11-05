"""
Configuración del servicio (variables de entorno) y reglas de validación por defecto.

Las REGLAS (umbrales y políticas) se guardan en la base de datos y se editan desde
el panel administrativo (PUT /api/v1/photos/rules). DEFAULT_RULES solo se usa la
primera vez, o si se pide restablecerlas.
"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def _env(nombre: str, defecto: str = "") -> str:
    return os.getenv(nombre, defecto).strip()


def _bool(nombre: str, defecto: bool) -> bool:
    return _env(nombre, "1" if defecto else "0").lower() in {"1", "true", "yes", "si", "sí"}


def _cargar_dotenv():
    """Carga .env si existe (sin dependencias externas)."""
    archivo = BASE_DIR / ".env"
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_cargar_dotenv()


@dataclass
class Settings:
    app_name: str = "Photo Validator AI"
    environment: str = field(default_factory=lambda: _env("ENVIRONMENT", "development"))

    # PERSIST=false (por defecto): NO se usa base de datos ni se guarda nada en disco.
    # Todo vive en memoria y se borra al apagar el servidor.
    # PERSIST=true: se usa DATABASE_URL (MySQL) y las fotos se guardan en storage/.
    persist: bool = field(default_factory=lambda: _bool("PERSIST", False))
    database_url: str = field(default_factory=lambda: _env(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'storage' / 'validator.db').as_posix()}")
        if _bool("PERSIST", False) else "sqlite://")

    # Seguridad
    api_keys: list[str] = field(default_factory=lambda: [k for k in _env("API_KEYS").split(",") if k.strip()])
    jwt_secret: str = field(default_factory=lambda: _env("JWT_SECRET", "cambia-esta-clave-secreta"))
    jwt_minutes: int = field(default_factory=lambda: int(_env("JWT_MINUTES", "480")))
    admin_username: str = field(default_factory=lambda: _env("ADMIN_USERNAME", "admin"))
    admin_password_hash: str = field(default_factory=lambda: _env("ADMIN_PASSWORD_HASH"))
    cors_origins: list[str] = field(default_factory=lambda: [o.strip() for o in _env(
        "CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080").split(",") if o.strip()])
    # Interfaz pública del estudiante (subida sin API key). En producción, lo
    # recomendado es False y que tu plataforma llame a la API desde su backend.
    public_ui: bool = field(default_factory=lambda: _bool("PUBLIC_UI", True))
    rate_limit_per_minute: int = field(default_factory=lambda: int(_env("RATE_LIMIT_PER_MINUTE", "20")))

    # Archivos
    max_upload_mb: float = field(default_factory=lambda: float(_env("MAX_UPLOAD_MB", "5")))
    max_pixels: int = 40_000_000  # protección contra "bombas de descompresión"
    storage_dir: Path = field(default_factory=lambda: Path(_env("STORAGE_DIR", str(BASE_DIR / "storage"))))
    store_rejected: bool = field(default_factory=lambda: _bool("STORE_REJECTED", False))
    retention_review_days: int = field(default_factory=lambda: int(_env("RETENTION_REVIEW_DAYS", "30")))
    retention_approved_days: int = field(default_factory=lambda: int(_env("RETENTION_APPROVED_DAYS", "0")))  # 0 = no borrar

    # Modelos
    models_dir: Path = field(default_factory=lambda: Path(_env("MODELS_DIR", str(BASE_DIR / "models"))))
    device: str = field(default_factory=lambda: _env("DEVICE", "auto"))  # auto | cpu | cuda
    enable_yolos: bool = field(default_factory=lambda: _bool("ENABLE_YOLOS", True))
    enable_fashionclip: bool = field(default_factory=lambda: _bool("ENABLE_FASHIONCLIP", True))
    # MediaPipe es opcional (pesado para Vercel): requiere  pip install mediapipe  y ENABLE_MEDIAPIPE=1
    enable_mediapipe: bool = field(default_factory=lambda: _bool("ENABLE_MEDIAPIPE", False))
    yunet_file: str = "face_detection_yunet_2023mar.onnx"
    mediapipe_file: str = "face_landmarker.task"

    @property
    def yunet_path(self) -> Path:
        return self.models_dir / self.yunet_file

    @property
    def mediapipe_path(self) -> Path:
        return self.models_dir / self.mediapipe_file


settings = Settings()
if settings.persist:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
# Caché de Hugging Face dentro de models/ (solo lo usa scripts/exportar_onnx.py)
os.environ.setdefault("HF_HOME", str(settings.models_dir / "hf"))


# ---------------------------------------------------------------------------
# REGLAS POR DEFECTO (editables desde el panel administrativo)
# Mismos criterios para todas las personas: se evalúan prendas y foto, nunca el género.
# ---------------------------------------------------------------------------
DEFAULT_RULES: dict = {
    # Qué hacer cuando la IA no está segura (modelos que no coinciden, baja confianza):
    #   "reject"        → se rechaza y se pide al estudiante subir otra foto (sistema simple)
    #   "manual_review" → queda pendiente para que una persona la revise en /admin
    "decision": {"uncertain_as": "reject"},
    # Formato oficial del carné universitario (SUNEDU): 240×288 px, JPG, máx. 50 KB,
    # 300 ppp, fondo blanco, de hombros hacia arriba.
    #   mode "generate": el estudiante sube cualquier foto válida y el sistema genera
    #                    automáticamente el archivo con las medidas exactas.
    #   mode "validate": el archivo subido YA debe cumplir las medidas exactas.
    "carnet": {
        "enabled": True, "mode": "generate",
        "width": 240, "height": 288, "max_kb": 50, "min_kb": 0, "dpi": 300,
        "only_jpg": True,
        "face_height_ratio": 0.45,   # alto del rostro / alto de la foto de carné (generate)
        "top_space_ratio": 0.20,     # espacio desde el borde superior hasta la frente
    },
    "resolution": {
        "enabled": True, "min_width": 240, "min_height": 288, "require_portrait": True,
    },
    "face": {
        "enabled": True,
        "min_confidence": 0.70,          # confianza mínima de YuNet
        "secondary_face_ratio": 0.30,    # otro rostro >30 % del área del principal = otra persona
        "size_min": 0.22, "size_max": 0.70,   # ancho del rostro / ancho de la imagen
        "center_tolerance": 0.15,        # desvío horizontal máximo del centro (0-0.5)
        "top_margin_min": 0.02,          # espacio sobre la cabeza (fracción del alto)
        "shoulders_space_min": 0.18,     # espacio bajo el mentón para hombros/vestimenta
    },
    "orientation": {
        "enabled": True,
        # MediaPipe (pose 3D en grados)
        "max_roll_deg": 12, "max_yaw_deg": 15, "max_pitch_deg": 18,
        # YuNet (respaldo). Medido en pruebas: YuNet subestima el roll ≈50 %,
        # por eso su umbral es menor.
        "yunet_max_roll_deg": 7, "yunet_max_yaw_ratio": 0.18,
    },
    "eyes": {"enabled": True, "max_blink_score": 0.55},
    "quality": {
        "enabled": True, "sharpness_min": 12.0, "brightness_min": 60, "brightness_max": 215,
        "contrast_min": 20.0, "saturated_max_pct": 0.20,
    },
    # Fondo BLANCO (SUNEDU). require_white exige poca saturación: rechaza celeste, crema, etc.
    "background": {"enabled": True, "brightness_min": 185, "uniformity_min": 0.75,
                   "require_white": True, "max_saturation": 35},
    "clothing": {
        "enabled": True,
        "yolos_min_score": 0.50,         # detección válida
        "yolos_strong_score": 0.75,      # detección muy segura
        "formal_items": ["jacket", "vest", "tie", "lapel", "collar", "shirt, blouse"],
        "informal_items": ["top, t-shirt, sweatshirt", "hood"],
        "neutral_items": ["sweater", "cardigan", "coat", "dress", "neckline", "scarf"],
        "clip_formal_min": 0.65,         # FashionCLIP ≥ esto → formal
        "clip_informal_max": 0.35,       # FashionCLIP ≤ esto → informal
        "clip_strong_formal": 0.80,
        "clip_strong_informal": 0.20,
    },
    "accessories": {
        "enabled": True,
        # políticas: "reject" | "manual_review" | "allow"
        "sunglasses": "reject", "hat": "reject", "hood": "reject",
        "headphones": "reject", "face_mask": "reject",
        "head_covering": "manual_review",   # p. ej. prendas religiosas: decide una persona
        "eyeglasses": "reject",             # el carné SUNEDU pide foto sin lentes (configurable)
        "clip_min_prob": 0.55,              # FashionCLIP sobre el rostro
        "yolos_min_score": 0.60,
    },
    "weights": {  # peso de cada criterio en el puntaje 0-100
        "carnet_format": 10,
        "resolution": 5, "face_detected": 10, "single_person": 5, "face_position": 10,
        "orientation": 10, "eyes": 5, "sharpness": 10, "lighting": 10,
        "background": 15, "formal_clothing": 15, "accessories": 5,
    },
}


def default_rules() -> dict:
    return copy.deepcopy(DEFAULT_RULES)


def merge_rules(base: dict, cambios: dict) -> dict:
    """Mezcla recursiva: solo se aceptan claves que existen en las reglas por defecto."""
    salida = copy.deepcopy(base)
    for k, v in cambios.items():
        if k not in salida:
            raise ValueError(f"Regla desconocida: {k}")
        if isinstance(salida[k], dict):
            if not isinstance(v, dict):
                raise ValueError(f"La regla '{k}' debe ser un objeto")
            salida[k] = merge_rules(salida[k], v)
        else:
            tipo = type(salida[k])
            if tipo is float and isinstance(v, int):
                v = float(v)
            if tipo is not type(v) and not (tipo is int and isinstance(v, float)):
                raise ValueError(f"Tipo inválido para '{k}': se esperaba {tipo.__name__}")
            if isinstance(v, str) and k in ACCESSORY_POLICY_KEYS and v not in {"reject", "manual_review", "allow"}:
                raise ValueError(f"Política inválida para '{k}': use reject, manual_review o allow")
            if k == "mode" and v not in {"generate", "validate"}:
                raise ValueError("Modo de carné inválido: use generate o validate")
            if k == "uncertain_as" and v not in {"reject", "manual_review"}:
                raise ValueError("Decisión inválida: use reject o manual_review")
            salida[k] = v
    return salida


ACCESSORY_POLICY_KEYS = {"sunglasses", "hat", "hood", "headphones", "face_mask", "head_covering", "eyeglasses"}
