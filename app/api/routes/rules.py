"""Consulta y edición de los requisitos de validación."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import default_rules, merge_rules
from app.core.security import require_admin
from app.database import repository as repo
from app.database.db import get_db

router = APIRouter(prefix="/api/v1/photos", tags=["Reglas"])


@router.get("/rules", summary="Requisitos configurados (público)")
def get_rules(db: Session = Depends(get_db)):
    version, rules = repo.active_rules(db)
    return {"version": version, "rules": rules}


@router.put("/rules", summary="Actualizar requisitos (solo administradores)")
def put_rules(request: Request, cambios: dict = Body(..., examples=[{"background": {"brightness_min": 130}}]),
              admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    _, actuales = repo.active_rules(db)
    try:
        nuevas = merge_rules(actuales, cambios)
    except ValueError as e:
        raise HTTPException(422, str(e))
    rs = repo.save_rules(db, nuevas, admin["sub"])
    repo.audit(db, admin["sub"], "rules_update", str(rs.id), request.client.host if request.client else None, cambios)
    return {"version": rs.id, "rules": nuevas}


@router.post("/rules/reset", summary="Restablecer requisitos por defecto (solo administradores)")
def reset_rules(request: Request, admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    rs = repo.save_rules(db, default_rules(), admin["sub"])
    repo.audit(db, admin["sub"], "rules_reset", str(rs.id), request.client.host if request.client else None)
    return {"version": rs.id, "rules": rs.data}
