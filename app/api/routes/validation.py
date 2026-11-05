"""Endpoints de validación de fotografías."""
from __future__ import annotations

import hmac
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (ImagenInvalida, api_key_header, api_key_valida, client_identity, leer_comprobante,
                               encode_clean_jpeg, optional_admin, rate_limiter, require_api_key, sanitize_image)
from app.database import repository as repo
from app.database.db import get_db, session_scope
from app.models.registry import registry
from app.schemas.validation import HistoryItem, ValidationOut, to_out
from app.services import storage
from app.services.pipeline import run_validation

router = APIRouter(prefix="/api/v1/photos", tags=["Validación de fotografías"])
CODIGO = re.compile(r"^[A-Za-z0-9_.-]{1,50}$")


@router.post("/validate", response_model=ValidationOut, summary="Validar una fotografía")
def validate_photo(
    request: Request,
    photo: UploadFile = File(..., description="JPG, PNG o WEBP"),
    student_code: str | None = Form(None, description="Código del estudiante"),
    cliente: str = Depends(client_identity),
):
    # Función síncrona: FastAPI la ejecuta en un hilo aparte, así el análisis de IA
    # no bloquea las demás peticiones. La BD se usa solo en tramos cortos.
    rate_limiter.check(cliente, settings.rate_limit_per_minute)
    if student_code and not CODIGO.match(student_code):
        raise HTTPException(422, "Código de estudiante inválido (solo letras, números, '-', '_' y '.').")

    data = photo.file.read(int(settings.max_upload_mb * 1024 * 1024) + 1)
    try:
        img, info = sanitize_image(data, photo.content_type)
    except ImagenInvalida as e:
        with session_scope() as db:
            repo.audit(db, cliente, "upload_rejected_file", ip=_ip(request), details={"error": str(e)})
        raise HTTPException(400, str(e))

    with session_scope() as db:
        version, rules = repo.active_rules(db)
    res = run_validation(img, rules, registry, info)   # análisis de IA (sin tocar la BD)
    carnet_bytes = res.pop("carnet_bytes", None)

    with session_scope() as db:
        v = repo.create_validation(
            db, student_code=student_code, status=res["status"], auto_status=res["status"], score=res["score"],
            results=res["results"], criteria=res["criteria"], rejection_reasons=res["rejection_reasons"],
            review_reasons=res["review_reasons"], recommendations=res["recommendations"], evidence=res["evidence"],
            models_used=res["models_used"], timings=res["timings"], rules_version=version,
            image_sha256=info["sha256"], client=cliente[:80])

        carpeta = {"APPROVED": "approved", "MANUAL_REVIEW": "review"}.get(v.status)
        if carpeta is None and settings.store_rejected:
            carpeta = "rejected"
        if carpeta:
            # aprobada → se guarda el archivo de carné (240×288); revisión → la foto completa
            archivo = carnet_bytes if (carpeta == "approved" and carnet_bytes) else encode_clean_jpeg(img)
            v.image_path = storage.save(carpeta, v.code, archivo, student_code)
            db.commit()

        repo.audit(db, cliente, "validate", v.code, _ip(request),
                   {"status": v.status, "score": v.score, "student": student_code})
        return to_out(v, incluir_token=True, carnet_bytes=carnet_bytes)


@router.get("/validation/{validation_id}", response_model=ValidationOut, summary="Consultar una validación")
def get_validation(
    validation_id: str,
    token: str | None = Query(None, description="access_token devuelto al validar (alternativa a la API key)"),
    clave: str | None = Depends(api_key_header),
    admin: dict | None = Depends(optional_admin),
    db: Session = Depends(get_db),
):
    v = repo.get_validation(db, validation_id)
    if v is None:
        raise HTTPException(404, "Validación no encontrada.")
    autorizado = api_key_valida(clave) or admin is not None or (token and hmac.compare_digest(token, v.access_token))
    if not autorizado:
        raise HTTPException(401, "No autorizado para ver esta validación.")
    return to_out(v)


@router.get("/verify", summary="Verificar un comprobante (sin base de datos)")
def verify(comprobante: str = Query(..., description="El campo 'comprobante' que devolvió /validate")):
    """El otro sistema llama aquí para confirmar que el resultado es auténtico.
    `foto_sha256` permite comprobar que la foto recibida es la que se aprobó."""
    d = leer_comprobante(comprobante)
    if d is None:
        return {"valid": False}
    return {"valid": True, "validation_id": d["vid"], "status": d["est"], "student_code": d.get("cod"),
            "foto_sha256": d.get("foto"), "issued_at": d["iat"], "expires_at": d["exp"]}


@router.get("/history", response_model=list[HistoryItem], summary="Historial de un estudiante")
def student_history(student_code: str, limit: int = Query(20, le=100), _: str = Depends(require_api_key),
                    db: Session = Depends(get_db)):
    return [HistoryItem(validation_id=v.code, status=v.status, score=v.score,
                        rejection_reasons=v.rejection_reasons, created_at=v.created_at)
            for v in repo.history(db, student_code, limit)]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
