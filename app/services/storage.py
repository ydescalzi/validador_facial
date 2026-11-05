"""
Almacenamiento privado de fotografías.

PERSIST=false (por defecto): NO se escribe nada en disco. Solo las fotos que van a
REVISIÓN MANUAL se mantienen en memoria (máx. 200) para que el administrador
pueda verlas; al resolverlas o al apagar el servidor se descartan.

PERSIST=true: se guardan en disco, fuera de cualquier carpeta pública:
    storage/approved/<codigo_estudiante>/<VAL-xxxxxx>.jpg
    storage/review/<VAL-xxxxxx>.jpg
    storage/rejected/<VAL-xxxxxx>.jpg   (solo si STORE_REJECTED=true)

Las imágenes se guardan re-codificadas (sin EXIF/GPS). Nunca se usan para
reconocimiento ni identificación biométrica.
"""
from __future__ import annotations

import re
import shutil
import threading
from collections import OrderedDict
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import repository as repo

_SEGURO = re.compile(r"[^A-Za-z0-9_-]")
_MEMORIA: "OrderedDict[str, bytes]" = OrderedDict()
_MAX_MEMORIA = 200
_lock = threading.Lock()


def _limpio(texto: str | None) -> str:
    return (_SEGURO.sub("_", texto or "sin_codigo"))[:50] or "sin_codigo"


def save(carpeta: str, code: str, jpeg: bytes, student: str | None = None) -> str | None:
    if not settings.persist:
        if carpeta != "review":
            return None  # sin persistencia: aprobadas/rechazadas no se guardan
        with _lock:
            _MEMORIA[code] = jpeg
            while len(_MEMORIA) > _MAX_MEMORIA:
                _MEMORIA.popitem(last=False)
        return f"mem:{code}"
    base = settings.storage_dir / carpeta
    destino = base / _limpio(student) / f"{code}.jpg" if carpeta == "approved" else base / f"{code}.jpg"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(jpeg)
    return destino.relative_to(settings.storage_dir).as_posix()


def absolute(rel: str) -> Path:
    p = (settings.storage_dir / rel).resolve()
    if settings.storage_dir.resolve() not in p.parents:
        raise ValueError("Ruta fuera del almacenamiento")
    return p


def read(rel: str) -> bytes | None:
    if rel.startswith("mem:"):
        return _MEMORIA.get(rel[4:])
    try:
        p = absolute(rel)
        return p.read_bytes() if p.exists() else None
    except ValueError:
        return None


def move_to_approved(rel: str, code: str, student: str | None) -> str | None:
    if rel.startswith("mem:"):
        delete(rel)  # sin persistencia: no se conserva
        return None
    destino = settings.storage_dir / "approved" / _limpio(student) / f"{code}.jpg"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(absolute(rel)), destino)
    return destino.relative_to(settings.storage_dir).as_posix()


def delete(rel: str | None):
    if not rel:
        return
    if rel.startswith("mem:"):
        with _lock:
            _MEMORIA.pop(rel[4:], None)
        return
    try:
        absolute(rel).unlink(missing_ok=True)
    except ValueError:
        pass


def purge(db: Session) -> dict:
    """Aplica la política de retención. Se ejecuta al iniciar y desde el panel."""
    borradas = {"MANUAL_REVIEW": 0, "REJECTED": 0, "APPROVED": 0}
    if not settings.persist:
        return borradas
    reglas = [("MANUAL_REVIEW", settings.retention_review_days), ("REJECTED", settings.retention_review_days)]
    if settings.retention_approved_days > 0:
        reglas.append(("APPROVED", settings.retention_approved_days))
    for estado, dias in reglas:
        for v in repo.expired(db, estado, dias):
            delete(v.image_path)
            v.image_path = None
            borradas[estado] += 1
    db.commit()
    return borradas
