"""Acceso a datos."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import default_rules, merge_rules
from app.database.models import AuditLog, RuleSet, Validation, ahora


# -- reglas ------------------------------------------------------------------
def active_rules(db: Session) -> tuple[int, dict]:
    rs = db.scalars(select(RuleSet).order_by(RuleSet.id.desc()).limit(1)).first()
    if rs is None:
        rs = RuleSet(data=default_rules(), created_by="sistema")
        db.add(rs)
        db.commit()
    # mezcla con los valores por defecto por si se añadieron reglas nuevas
    return rs.id, merge_rules(default_rules(), rs.data)


def save_rules(db: Session, data: dict, usuario: str) -> RuleSet:
    rs = RuleSet(data=data, created_by=usuario)
    db.add(rs)
    db.commit()
    return rs


# -- validaciones ------------------------------------------------------------
def create_validation(db: Session, **campos) -> Validation:
    v = Validation(access_token=secrets.token_urlsafe(24), **campos)
    db.add(v)
    db.flush()
    v.code = f"VAL-{v.id:06d}"
    db.commit()
    return v


def get_validation(db: Session, ident: str) -> Validation | None:
    ident = ident.strip().upper()
    if ident.startswith("VAL-"):
        return db.scalars(select(Validation).where(Validation.code == ident)).first()
    if ident.isdigit():
        return db.get(Validation, int(ident))
    return None


def history(db: Session, student_code: str, limit: int = 50) -> list[Validation]:
    q = select(Validation).where(Validation.student_code == student_code).order_by(Validation.id.desc()).limit(limit)
    return list(db.scalars(q))


def list_validations(db: Session, status: str | None = None, student: str | None = None,
                     limit: int = 50, offset: int = 0) -> tuple[int, list[Validation]]:
    q = select(Validation)
    if status:
        q = q.where(Validation.status == status)
    if student:
        q = q.where(Validation.student_code == student)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = list(db.scalars(q.order_by(Validation.id.desc()).limit(limit).offset(offset)))
    return total, items


def stats(db: Session, dias: int = 30) -> dict:
    desde = ahora() - timedelta(days=dias)
    filas = db.execute(select(Validation.status, func.count()).where(Validation.created_at >= desde)
                       .group_by(Validation.status)).all()
    por_estado = {s: n for s, n in filas}
    auto = db.execute(select(Validation.auto_status, func.count()).where(Validation.created_at >= desde)
                      .group_by(Validation.auto_status)).all()
    total = sum(por_estado.values())

    # motivos de rechazo más frecuentes (agregado en Python: compatible con MySQL y SQLite)
    motivos: dict[str, int] = {}
    criterios: dict[str, dict] = {}
    tiempos = []
    for crit, rr, tm in db.execute(select(Validation.criteria, Validation.rejection_reasons, Validation.timings)
                                   .where(Validation.created_at >= desde)).all():
        for m in rr or []:
            motivos[m] = motivos.get(m, 0) + 1
        for c in crit or []:
            d = criterios.setdefault(c["key"], {"label": c.get("label", c["key"]), "PASS": 0, "FAIL": 0,
                                                "REVIEW": 0, "NOT_EVALUATED": 0})
            d[c["status"]] = d.get(c["status"], 0) + 1
        if tm and "total_ms" in tm:
            tiempos.append(tm["total_ms"])

    diario = db.execute(select(func.date(Validation.created_at), Validation.status, func.count())
                        .where(Validation.created_at >= desde)
                        .group_by(func.date(Validation.created_at), Validation.status)).all()
    por_dia: dict[str, dict] = {}
    for d, s, n in diario:
        por_dia.setdefault(str(d), {})[s] = n

    # revisiones humanas que cambiaron la decisión automática (mide falsos rechazos/aprobaciones)
    revisadas = db.execute(select(Validation.auto_status, Validation.status, func.count())
                           .where(Validation.reviewed_at.is_not(None), Validation.created_at >= desde)
                           .group_by(Validation.auto_status, Validation.status)).all()
    tiempos.sort()
    return {
        "period_days": dias,
        "total": total,
        "by_status": por_estado,
        "by_auto_status": {s: n for s, n in auto},
        "approval_rate": round(por_estado.get("APPROVED", 0) / total, 3) if total else None,
        "top_rejection_reasons": sorted(motivos.items(), key=lambda x: -x[1])[:10],
        "criteria": criterios,
        "daily": por_dia,
        "human_reviews": [{"auto": a, "final": f, "count": n} for a, f, n in revisadas],
        "processing_ms": {"median": tiempos[len(tiempos) // 2], "p95": tiempos[int(len(tiempos) * 0.95)]}
        if tiempos else None,
    }


# -- auditoría ---------------------------------------------------------------
def audit(db: Session, actor: str, action: str, target: str | None = None, ip: str | None = None,
          details: dict | None = None):
    db.add(AuditLog(actor=actor, action=action, target=target, ip=ip, details=details))
    db.commit()


def audit_list(db: Session, limit: int = 100) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)))


def expired(db: Session, status: str, dias: int) -> list[Validation]:
    limite: datetime = ahora() - timedelta(days=dias)
    return list(db.scalars(select(Validation).where(Validation.status == status, Validation.created_at < limite,
                                                    Validation.image_path.is_not(None))))
