"""Autenticación y panel administrativo: revisión manual, estadísticas y auditoría."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_token, rate_limiter, require_admin, verify_password
from app.database import repository as repo
from app.database.db import get_db
from app.database.models import ahora
from app.schemas.validation import LoginIn, ReviewIn, TokenOut, to_out
from app.services import storage

auth = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])
router = APIRouter(prefix="/api/v1/admin", tags=["Administración"])


def _ip(r: Request):
    return r.client.host if r.client else None


@auth.post("/login", response_model=TokenOut, summary="Iniciar sesión de administrador (JWT)")
def login(datos: LoginIn, request: Request, db: Session = Depends(get_db)):
    rate_limiter.check(f"login:{_ip(request)}", 10)
    if not settings.admin_password_hash:
        raise HTTPException(503, "Administrador no configurado: define ADMIN_PASSWORD_HASH en .env")
    if datos.username != settings.admin_username or not verify_password(datos.password, settings.admin_password_hash):
        repo.audit(db, datos.username[:80], "login_failed", ip=_ip(request))
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    repo.audit(db, datos.username, "login", ip=_ip(request))
    return TokenOut(access_token=create_token(datos.username), expires_minutes=settings.jwt_minutes)


@router.get("/validations", summary="Listar validaciones (filtros por estado o estudiante)")
def list_validations(status: str | None = None, student_code: str | None = None,
                     limit: int = Query(50, le=200), offset: int = 0,
                     _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    total, items = repo.list_validations(db, status, student_code, limit, offset)
    return {"total": total, "items": [to_out(v).model_dump(mode="json") | {"has_image": bool(v.image_path)}
                                      for v in items]}


@router.get("/validations/{validation_id}/image", summary="Ver la fotografía (privada)")
def view_image(validation_id: str, request: Request, admin: dict = Depends(require_admin),
               db: Session = Depends(get_db)):
    v = repo.get_validation(db, validation_id)
    if v is None or not v.image_path:
        raise HTTPException(404, "Imagen no disponible.")
    datos = storage.read(v.image_path)
    if datos is None:
        raise HTTPException(404, "Imagen no disponible.")
    repo.audit(db, admin["sub"], "image_view", v.code, _ip(request))
    return Response(datos, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/reviews/{validation_id}", summary="Resolver una revisión manual")
def resolve_review(validation_id: str, datos: ReviewIn, request: Request,
                   admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    v = repo.get_validation(db, validation_id)
    if v is None:
        raise HTTPException(404, "Validación no encontrada.")
    if v.status != "MANUAL_REVIEW":
        raise HTTPException(409, f"La validación está en estado {v.status}, no en revisión manual.")
    v.status = datos.decision
    v.reviewed_by, v.reviewed_at, v.review_comment = admin["sub"], ahora(), datos.comment
    if datos.decision == "APPROVED":
        if v.image_path:
            v.image_path = storage.move_to_approved(v.image_path, v.code, v.student_code)
    else:
        v.rejection_reasons = datos.reasons or v.review_reasons or ["Rechazada tras revisión manual."]
        if not settings.store_rejected:
            storage.delete(v.image_path)
            v.image_path = None
    db.commit()
    repo.audit(db, admin["sub"], "review", v.code, _ip(request), {"decision": datos.decision,
                                                                   "comment": datos.comment})
    return to_out(v)


@router.get("/stats", summary="Estadísticas de validaciones")
def get_stats(days: int = Query(30, ge=1, le=365), _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return repo.stats(db, days)


@router.get("/audit", summary="Registro de auditoría")
def get_audit(limit: int = Query(100, le=500), _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"time": a.created_at, "actor": a.actor, "action": a.action, "target": a.target, "ip": a.ip,
             "details": a.details} for a in repo.audit_list(db, limit)]


@router.post("/maintenance/purge", summary="Aplicar política de retención de imágenes")
def purge(request: Request, admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    r = storage.purge(db)
    repo.audit(db, admin["sub"], "purge", ip=_ip(request), details=r)
    return {"deleted_images": r}
