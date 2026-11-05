"""
Punto de entrada para Vercel (función Python serverless).
Vercel ejecuta la app FastAPI `app`; vercel.json reenvía /api/* aquí.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402,F401
