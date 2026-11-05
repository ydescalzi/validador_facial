# 1) Compila el frontend React + TypeScript
FROM node:22-slim AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

# 2) Backend Python
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1


WORKDIR /app
# Sin PyTorch: los modelos van en ONNX (models/onnx, generados con scripts/exportar_onnx.py)
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY models ./models
COPY --from=frontend /web/dist ./frontend/dist

RUN useradd -m validador && mkdir -p /app/storage && chown -R validador /app/storage
USER validador
# Sin base de datos ni archivos (cambiar a PERSIST=true y DATABASE_URL para guardar)
ENV PERSIST=false PUBLIC_UI=true PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:'+__import__('os').environ.get('PORT','8080')+'/api/v1/health')"
# --forwarded-allow-ips="*": detrás del proxy de Vercel / Cloud Run se usa la IP real del
# estudiante (X-Forwarded-For) para el límite de solicitudes.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
