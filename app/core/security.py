"""
Seguridad: API keys, JWT para administradores, límite de solicitudes y
saneamiento de imágenes subidas.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import sys
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from PIL import Image, ImageOps

from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Contraseñas (PBKDF2-SHA256, sin dependencias externas)
# ---------------------------------------------------------------------------
def hash_password(password: str, iteraciones: int = 310_000) -> str:
    sal = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), sal, iteraciones)
    return f"pbkdf2_sha256${iteraciones}${base64.b64encode(sal).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, almacenado: str) -> bool:
    try:
        _, it, sal, dk = almacenado.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(sal), int(it))
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT (administradores / revisores)
# ---------------------------------------------------------------------------
def create_token(usuario: str, rol: str = "admin") -> str:
    ahora = datetime.now(timezone.utc)
    payload = {"sub": usuario, "role": rol, "iat": ahora,
               "exp": ahora + timedelta(minutes=settings.jwt_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# Comprobante firmado del resultado (verificable SIN base de datos: sirve en Vercel)
# ---------------------------------------------------------------------------
def crear_comprobante(validation_id: str, estado: str, codigo: str | None, sha256_foto: str | None,
                      dias: int = 30) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {"typ": "comprobante-foto", "vid": validation_id, "est": estado, "cod": codigo,
               "foto": sha256_foto, "iat": ahora, "exp": ahora + timedelta(days=dias)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def leer_comprobante(token: str) -> dict | None:
    try:
        d = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return d if d.get("typ") == "comprobante-foto" else None


def secreto_por_defecto() -> bool:
    return settings.jwt_secret == "cambia-esta-clave-secreta"


def require_admin(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Se requiere iniciar sesión como administrador.")
    try:
        datos = jwt.decode(cred.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada.")
    if datos.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No autorizado.")
    return datos


def optional_admin(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict | None:
    if cred is None:
        return None
    try:
        return jwt.decode(cred.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------------------
# API keys (plataforma universitaria: Laravel, Node, etc.)
# ---------------------------------------------------------------------------
def api_key_valida(clave: str | None) -> bool:
    return bool(clave) and any(hmac.compare_digest(clave, k) for k in settings.api_keys)


def require_api_key(clave: str | None = Depends(api_key_header)) -> str:
    if not api_key_valida(clave):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key inválida o ausente (cabecera X-API-Key).")
    return clave  # type: ignore[return-value]


def client_identity(request: Request, clave: str | None = Depends(api_key_header)) -> str:
    """Quién hace la petición: 'apikey:xxxx' o 'public:IP'. Lanza 401 si no está permitido."""
    if api_key_valida(clave):
        return f"apikey:{clave[:6]}…"  # type: ignore[index]
    if settings.public_ui:
        return f"public:{request.client.host if request.client else 'desconocido'}"
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key inválida o ausente (cabecera X-API-Key).")


# ---------------------------------------------------------------------------
# Límite de solicitudes (ventana deslizante en memoria, por cliente).
# Con varios procesos/servidores, reemplazar por Redis.
# ---------------------------------------------------------------------------
class RateLimiter:
    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, clave: str, limite: int, ventana: int = 60):
        ahora = time.monotonic()
        with self._lock:
            q = self._hits[clave]
            while q and ahora - q[0] > ventana:
                q.popleft()
            if len(q) >= limite:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                    "Demasiadas solicitudes. Espera un minuto e inténtalo de nuevo.")
            q.append(ahora)


rate_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# Saneamiento de imágenes
# ---------------------------------------------------------------------------
FORMATOS_PERMITIDOS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
Image.MAX_IMAGE_PIXELS = settings.max_pixels


class ImagenInvalida(ValueError):
    pass


def sanitize_image(data: bytes, content_type: str | None) -> tuple[Image.Image, dict]:
    """
    Valida tamaño, tipo real (por contenido, no por extensión) y dimensiones.
    Devuelve la imagen en RGB, ya rotada según EXIF y SIN metadatos.
    """
    max_bytes = int(settings.max_upload_mb * 1024 * 1024)
    if not data:
        raise ImagenInvalida("El archivo está vacío.")
    if len(data) > max_bytes:
        raise ImagenInvalida(f"La imagen supera los {settings.max_upload_mb:g} MB.")
    if content_type and content_type not in FORMATOS_PERMITIDOS.values():
        raise ImagenInvalida("Formato no permitido. Sube una imagen JPG, PNG o WEBP.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            formato = probe.format
            probe.verify()  # detecta archivos corruptos o manipulados
        if formato not in FORMATOS_PERMITIDOS:
            raise ImagenInvalida("El contenido del archivo no es una imagen JPG, PNG o WEBP.")
        img = Image.open(io.BytesIO(data))
        img.load()
    except ImagenInvalida:
        raise
    except Image.DecompressionBombError:
        raise ImagenInvalida("La imagen tiene demasiados píxeles.")
    except Exception:
        raise ImagenInvalida("El archivo no es una imagen válida o está dañado.")

    if getattr(img, "n_frames", 1) > 1:
        raise ImagenInvalida("No se permiten imágenes animadas.")
    # Datos técnicos del archivo ORIGINAL (para el requisito de formato de carné)
    dpi = img.info.get("dpi")
    dpi_valor = round(float(min(dpi))) if dpi else None
    ancho_orig, alto_orig = img.size
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        fondo = Image.new("RGB", img.size, (255, 255, 255))
        img = img.convert("RGBA")
        fondo.paste(img, mask=img.split()[-1])
        img = fondo
    else:
        img = img.convert("RGB")
    info = {"format": formato, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "dpi": dpi_valor, "width": ancho_orig, "height": alto_orig}
    return img, info


def encode_clean_jpeg(img: Image.Image, calidad: int = 92) -> bytes:
    """Re-codifica la imagen (elimina EXIF, GPS y cualquier contenido incrustado)."""
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=calidad, optimize=True)
    return buf.getvalue()


if __name__ == "__main__":
    # python -m app.core.security "MiContraseña"  → imprime el hash para ADMIN_PASSWORD_HASH
    if len(sys.argv) < 2:
        print('Uso: python -m app.core.security "contraseña"')
        sys.exit(1)
    print(hash_password(sys.argv[1]))
