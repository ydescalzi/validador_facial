"""
Photo Validator AI — microservicio de validación de fotografías para carnet universitario.

Ejecutar:   uvicorn app.main:app --port 8080
Swagger:    http://localhost:8080/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, health, rules, validation
from app.core.config import settings
from app.database.db import SessionLocal, init_db
from app.models.registry import registry
from app.services import storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Frontend React + TypeScript ya compilado (frontend/dist, generado con `npm run build`)
FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "dist"


_listo = False


def preparar():
    """Inicializa BD y modelos una vez por proceso. En Vercel (serverless) no siempre se
    ejecuta el evento de inicio, por eso también se llama con la primera petición."""
    global _listo
    if _listo:
        return
    init_db()
    registry.ensure_loaded()
    with SessionLocal() as db:
        storage.purge(db)
    _listo = True


@asynccontextmanager
async def lifespan(_: FastAPI):
    preparar()
    yield


app = FastAPI(
    title="Photo Validator AI",
    version="1.0.0",
    description="Validación de fotografías para carnet universitario con modelos preentrenados "
                "(YuNet, YOLOS Fashionpedia y FashionCLIP en ONNX) y un motor de reglas configurable.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"], allow_headers=["X-API-Key", "Authorization", "Content-Type"],
)


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    if not _listo and request.url.path.startswith("/api"):
        from starlette.concurrency import run_in_threadpool
        await run_in_threadpool(preparar)
    r = await call_next(request)
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["X-Frame-Options"] = "DENY"
    r.headers["Referrer-Policy"] = "no-referrer"
    if request.url.scheme == "https":
        r.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return r


@app.exception_handler(Exception)
async def error_inesperado(_: Request, exc: Exception):
    logging.getLogger("photo_validator").exception("Error no controlado: %s", exc)
    return JSONResponse(status_code=500, content={"success": False, "detail": "Error interno del servidor."})


app.include_router(validation.router)
app.include_router(rules.router)
app.include_router(health.router)
app.include_router(admin.auth)
app.include_router(admin.router)
if (FRONTEND / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")


def _spa():
    """La app React decide qué pantalla mostrar (/ estudiante, /admin panel)."""
    index = FRONTEND / "index.html"
    if not index.exists():
        return JSONResponse(status_code=503, content={
            "detail": "Frontend no compilado. Ejecuta: cd frontend && npm install && npm run build"})
    return FileResponse(index)


@app.get("/", include_in_schema=False)
def ui_estudiante():
    return _spa()


@app.get("/admin", include_in_schema=False)
def ui_admin():
    return _spa()
