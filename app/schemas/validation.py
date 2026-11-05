"""Esquemas JSON (aparecen documentados en Swagger: /docs)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Estado = Literal["APPROVED", "REJECTED", "MANUAL_REVIEW"]


class CriterionOut(BaseModel):
    key: str
    label: str
    status: Literal["PASS", "FAIL", "REVIEW", "NOT_EVALUATED"]
    message: str = ""
    recommendation: str = ""
    values: dict[str, Any] = {}


class ValidationOut(BaseModel):
    success: bool = True
    validation_id: str = Field(examples=["VAL-000001"])
    access_token: str | None = Field(None, description="Permite al estudiante consultar su resultado sin API key")
    student_code: str | None = None
    status: Estado
    message: str
    score: int = Field(ge=0, le=100)
    results: dict[str, Any]
    criteria: list[CriterionOut]
    rejection_reasons: list[str]
    review_reasons: list[str]
    recommendations: list[str]
    scores: dict[str, Any] = Field(description="Puntuaciones individuales de cada modelo")
    models_used: list[str]
    timings_ms: dict[str, int]
    rules_version: int
    created_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    carnet: dict[str, Any] | None = Field(None, description="Datos técnicos del formato de carné")
    carnet_photo: str | None = Field(
        None, description="Foto de carné lista (data:image/jpeg;base64,…). Solo si fue APROBADA y en modo generate")
    comprobante: str | None = Field(
        None, description="Resultado firmado; el otro sistema lo verifica en GET /api/v1/photos/verify")


class HistoryItem(BaseModel):
    validation_id: str
    status: Estado
    score: int
    rejection_reasons: list[str]
    created_at: datetime


class ReviewIn(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    comment: str | None = Field(None, max_length=1000)
    reasons: list[str] = Field(default_factory=list, description="Motivos visibles para el estudiante si se rechaza")


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_minutes: int


def scores_from_evidence(ev: dict) -> dict:
    """Extrae solo las puntuaciones de modelos (sin coordenadas sensibles innecesarias)."""
    ev = ev or {}
    f, q, c = ev.get("face", {}), ev.get("quality", {}), ev.get("clothing", {})
    p = f.get("primary") or {}
    return {
        "face": {"faces": f.get("count"), "confidence": p.get("confidence"), "size_ratio": p.get("size_ratio"),
                 "center_offset": p.get("center_offset"), "yunet_roll_deg": p.get("yunet_roll_deg"),
                 "yunet_yaw_ratio": p.get("yunet_yaw_ratio"), "mediapipe": f.get("mediapipe")},
        "quality": q,
        "clothing": {
            "yolos": [{"label": d["label"], "score": d["score"]} for d in (c.get("yolos") or {}).get("garments", [])],
            "yolos_accessories": [{"label": d["label"], "score": d["score"]}
                                  for d in (c.get("yolos") or {}).get("accessories", [])],
            "fashionclip_torso": (c.get("fashionclip") or {}).get("torso"),
            "fashionclip_face": (c.get("fashionclip") or {}).get("face"),
            "segformer": c.get("segformer"),
        },
    }


def to_out(v, incluir_token: bool = False, carnet_bytes: bytes | None = None) -> ValidationOut:
    import base64
    import hashlib

    from app.core.security import crear_comprobante
    foto = (f"data:image/jpeg;base64,{base64.b64encode(carnet_bytes).decode()}"
            if carnet_bytes and v.status == "APPROVED" else None)
    sha = hashlib.sha256(carnet_bytes).hexdigest() if foto else None
    return ValidationOut(
        carnet=(v.evidence or {}).get("carnet"), carnet_photo=foto,
        comprobante=crear_comprobante(v.code, v.status, v.student_code, sha) if incluir_token else None,
        validation_id=v.code, access_token=v.access_token if incluir_token else None,
        student_code=v.student_code, status=v.status, message=_mensaje(v), score=v.score, results=v.results,
        criteria=v.criteria, rejection_reasons=v.rejection_reasons, review_reasons=v.review_reasons,
        recommendations=v.recommendations, scores=scores_from_evidence(v.evidence), models_used=v.models_used,
        timings_ms=v.timings, rules_version=v.rules_version, created_at=v.created_at, reviewed_by=v.reviewed_by,
        reviewed_at=v.reviewed_at, review_comment=v.review_comment)


def _mensaje(v) -> str:
    from app.services.pipeline import MENSAJES
    return MENSAJES[v.status]
