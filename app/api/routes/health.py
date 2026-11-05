"""Estado del servicio."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import secreto_por_defecto
from app.database.db import get_db
from app.models.registry import registry

router = APIRouter(prefix="/api/v1", tags=["Estado"])


@router.get("/health", summary="Estado del servicio y modelos cargados")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        bd = "ok" if settings.persist else "ok (en memoria: no se guarda nada)"
    except Exception as e:
        bd = f"error: {str(e)[:120]}"
    esenciales = ["yunet", "yolos", "fashionclip"]
    faltan = [k for k in esenciales if not registry.status.get(k, {}).get("loaded")]
    return {
        "status": "ok" if bd.startswith("ok") and not faltan else "degraded",
        "persist": settings.persist,
        "warning": "Define la variable JWT_SECRET: los comprobantes usan la clave de ejemplo."
        if secreto_por_defecto() else None,
        "detail": None if not faltan else
        f"Modelos no disponibles: {', '.join(faltan)}. Los criterios que dependen de ellos irán a revisión manual.",
        "database": bd,
        "environment": settings.environment,
        "public_ui": settings.public_ui,
        "models": registry.status,
    }
