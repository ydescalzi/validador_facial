"""
Conexión a la base de datos.

PERSIST=false (por defecto): NO se usa ninguna base de datos real. Los resultados
viven en memoria (SQLite en RAM) mientras el servidor está encendido y se borran
al apagarlo. No se escribe ningún archivo.

PERSIST=true: se usa DATABASE_URL (MySQL). Si MySQL no está disponible, el
sistema avisa y usa un archivo local SQLite (storage/validator.db).
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

log = logging.getLogger("photo_validator.db")
SQLITE_LOCAL = f"sqlite:///{(settings.storage_dir / 'validator.db').as_posix()}"


def _crear_engine(url: str):
    if url == "sqlite://":  # memoria: una sola conexión compartida
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(pool_size=10, max_overflow=20, pool_recycle=1800, connect_args={"connect_timeout": 5})
    return create_engine(url, **kwargs)


engine = _crear_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# En modo memoria hay UNA sola conexión compartida: SQLite no permite usarla desde
# varios hilos a la vez, así que se serializa el acceso con un candado.
# (threading.Lock, no RLock: FastAPI puede abrir y cerrar la dependencia en hilos distintos.)
_lock_bd = threading.Lock() if settings.database_url == "sqlite://" else None


@contextmanager
def session_scope():
    if _lock_bd:
        _lock_bd.acquire()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        if _lock_bd:
            _lock_bd.release()


def get_db():
    with session_scope() as db:
        yield db


def init_db():
    global engine
    from sqlalchemy.exc import OperationalError

    from app.database import models  # noqa: F401  (registra las tablas)
    try:
        Base.metadata.create_all(engine)
    except OperationalError as e:
        if settings.database_url.startswith("sqlite"):
            raise
        log.warning("No se pudo conectar a %s (%s). Se usará el archivo local %s",
                    engine.url.render_as_string(hide_password=True), e.orig, SQLITE_LOCAL)
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        engine = _crear_engine(SQLITE_LOCAL)
        SessionLocal.configure(bind=engine)
        Base.metadata.create_all(engine)
    if settings.persist:
        log.info("Base de datos: %s", engine.url.render_as_string(hide_password=True))
    else:
        log.info("Modo SIN base de datos: nada se guarda; los resultados se borran al apagar el servidor.")
