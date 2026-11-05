"""Tablas: validaciones, versiones de reglas y auditoría."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base


def ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Validation(Base):
    __tablename__ = "photo_validations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    access_token: Mapped[str] = mapped_column(String(64))
    student_code: Mapped[str | None] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)          # estado vigente
    auto_status: Mapped[str] = mapped_column(String(20))                 # decisión automática original
    score: Mapped[int] = mapped_column(Integer)
    results: Mapped[dict] = mapped_column(JSON)
    criteria: Mapped[list] = mapped_column(JSON)
    rejection_reasons: Mapped[list] = mapped_column(JSON)
    review_reasons: Mapped[list] = mapped_column(JSON)
    recommendations: Mapped[list] = mapped_column(JSON)
    evidence: Mapped[dict] = mapped_column(JSON)                         # puntuaciones de cada modelo
    models_used: Mapped[list] = mapped_column(JSON)
    timings: Mapped[dict] = mapped_column(JSON)
    rules_version: Mapped[int] = mapped_column(Integer)
    image_path: Mapped[str | None] = mapped_column(String(255))
    image_sha256: Mapped[str] = mapped_column(String(64), index=True)
    client: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(80))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_comment: Mapped[str | None] = mapped_column(Text)


class RuleSet(Base):
    __tablename__ = "photo_rule_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    created_by: Mapped[str] = mapped_column(String(80))


class AuditLog(Base):
    __tablename__ = "photo_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(50), index=True)
    target: Mapped[str | None] = mapped_column(String(50))
    ip: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(JSON)
