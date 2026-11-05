# Photo Validator AI — validación de fotografías para carnet universitario

Microservicio (FastAPI) que analiza la fotografía con modelos de IA
preentrenados y decide **APROBADA**, **RECHAZADA** (con motivos y
recomendaciones) o **REVISIÓN MANUAL**. Se conecta a cualquier plataforma (PHP,
Laravel, Node, React) por API REST con API key.

## Publicar en Vercel y enlazar desde otro sistema
Ver [`docs/04_publicar_y_enlazar.md`](docs/04_publicar_y_enlazar.md). Solo editas `frontend/src/config.ts` y `frontend/vercel.json`.

## Arquitectura

```
Foto ─► Saneamiento (MIME real, tamaño, sin EXIF)
     ─► SERVICIOS DE IA (solo producen evidencia)
          YuNet ............ rostros, posición, 5 puntos
          MediaPipe ........ pose 3D, ojos abiertos
          YOLOS Fashionpedia prendas y partes: saco, cuello, solapa, corbata, polo, capucha…
          FashionCLIP ...... torso formal/informal · rostro: lentes de sol, gorra, mascarilla
          OpenCV ........... resolución, nitidez, luz, contraste, fondo
     ─► MOTOR DE REGLAS (independiente; reglas editables en el panel)
     ─► APPROVED | REJECTED | MANUAL_REVIEW  + motivos + recomendaciones + puntajes
     ─► MySQL (validaciones, reglas versionadas, auditoría) + almacenamiento privado
```

La comparativa de modelos y por qué se eligieron está en
[`docs/01_comparativa_modelos.md`](docs/01_comparativa_modelos.md). Las pruebas y
limitaciones están en [`docs/02_pruebas_y_limitaciones.md`](docs/02_pruebas_y_limitaciones.md).

### Cómo se decide la vestimenta (los dos modelos deben coincidir)

| YOLOS \ FashionCLIP | Formal | Dudoso | Informal |
|---|---|---|---|
| **Formal** (saco, cuello, solapa, corbata, camisa) | ✅ Aprobada | ✅ si YOLOS ≥ 0,75, si no 🔍 | 🔍 Revisión |
| **Nada identificado** | ✅ si CLIP ≥ 0,80, si no 🔍 | 🔍 Revisión | ❌ si CLIP ≤ 0,20, si no 🔍 |
| **Informal** (camiseta/polo, capucha) | 🔍 Revisión | ❌ si YOLOS ≥ 0,75, si no 🔍 | ❌ Rechazada |
| **Formal + informal** (saco sobre polo) | 🔍 | 🔍 | 🔍 |

Si un modelo no puede identificar la prenda, la foto **no** se rechaza: va a revisión.

## Instalación (Windows / Linux, Python 3.11+)

```powershell
cd photo-validator-ai
python -m venv venv
.\venv\Scripts\Activate.ps1          # Linux: source venv/bin/activate
pip install -r requirements-export.txt   # incluye PyTorch, solo para exportar los modelos
python scripts/exportar_onnx.py          # una vez: genera models/onnx (~120 MB)
copy .env.example .env               # Linux: cp .env.example .env
python -m app.core.security "MiContraseñaAdmin"   # pega el resultado en ADMIN_PASSWORD_HASH
uvicorn app.main:app --port 8080
```

> **Subir a Vercel:** sigue [`docs/05_subir_a_vercel.md`](docs/05_subir_a_vercel.md).
> El servicio usa ONNX Runtime (sin PyTorch), por eso cabe en una función de Vercel.

- Estudiante: <http://localhost:8080> (si `PUBLIC_UI=true`)
- Panel: <http://localhost:8080/admin> (revisión manual, validaciones, estadísticas, configuración, auditoría, modelos)
- Swagger: <http://localhost:8080/docs>

Por defecto (`PERSIST=false`) no usa base de datos ni guarda nada: todo vive en memoria.

### Frontend (React + TypeScript)
El zip trae el frontend **ya compilado** en `frontend/dist`, y el backend Python lo
sirve en `/` y `/admin`. Solo necesitas Node.js (18 o superior) si vas a modificarlo:

```powershell
cd frontend
npm install
npm run dev      # desarrollo con recarga: http://localhost:5173 (usa la API en :8080)
npm run build    # vuelve a compilar a frontend/dist
```

```
frontend/src/
  api/types.ts        tipos de la API (Validacion, Criterio, Reglas…)
  api/client.ts       llamadas a la API
  pages/StudentPage.tsx   carga, vista previa, análisis, resultado, historial
  pages/AdminPage.tsx     login + pestañas
  admin/*.tsx         Revisión manual, Validaciones, Estadísticas, Configuración, Auditoría, Modelos
  components/*.tsx    ZonaCarga, PasosAnalisis, Resultado (ScoreRing, ListaCriterios)
```

**Docker (con MySQL):** `docker compose up -d --build`

## Endpoints

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| POST | `/api/v1/photos/validate` | API key (o público si `PUBLIC_UI`) | `multipart`: `photo`, `student_code` |
| GET | `/api/v1/photos/validation/{id}` | API key, admin o `?token=` | Resultado de una validación |
| GET | `/api/v1/photos/history?student_code=` | API key | Historial del estudiante |
| GET | `/api/v1/photos/rules` | público | Requisitos vigentes |
| PUT | `/api/v1/photos/rules` | admin (JWT) | Cambiar requisitos (parcial) |
| GET | `/api/v1/health` | público | Estado del servicio y modelos |
| POST | `/api/v1/auth/login` | — | JWT de administrador |
| GET | `/api/v1/admin/validations?status=MANUAL_REVIEW` | admin | Pendientes, filtros |
| POST | `/api/v1/admin/reviews/{id}` | admin | `{"decision":"APPROVED"\|"REJECTED","comment":"…"}` |
| GET | `/api/v1/admin/stats?days=30` | admin | Estadísticas |
| GET | `/api/v1/admin/audit` | admin | Auditoría |

### Ejemplo de respuesta
```json
{
  "success": true,
  "validation_id": "VAL-000014",
  "status": "REJECTED",
  "message": "Tu fotografía ha sido rechazada porque no cumple con los requisitos.",
  "score": 78,
  "results": {"face_detected": true, "single_person": true, "face_position": "CORRECT",
              "orientation": "CORRECT", "background": "CORRECT", "lighting": "CORRECT",
              "sharpness": "CORRECT", "formal_clothing": "INCORRECT", "accessories": "CORRECT"},
  "rejection_reasons": ["Se detectó vestimenta informal."],
  "recommendations": ["Usa saco o blazer con camisa o blusa formal con cuello (no polos, camisetas, polerones ni capuchas)."],
  "criteria": [{"key": "formal_clothing", "status": "FAIL", "values": {"yolos_vote": "INFORMAL", "fashionclip_formal_prob": 0.12}}],
  "scores": {"clothing": {"yolos": [{"label": "top, t-shirt, sweatshirt", "score": 0.91}], "fashionclip_torso": {"formal_prob": 0.12}}},
  "models_used": ["YuNet (OpenCV Zoo)", "MediaPipe Face Landmarker", "valentinafeve/yolos-fashionpedia", "patrickjohncyh/fashion-clip", "OpenCV (calidad de imagen)"],
  "timings_ms": {"face_ms": 30, "quality_ms": 3, "clothing_ms": 950, "total_ms": 990},
  "created_at": "2026-11-05T14:20:11"
}
```
*(Ejemplo ilustrativo del formato; los valores reales salen de cada análisis.)*

## Integración
- **Laravel:** `integration/laravel/PhotoValidatorService.php` + `CarnetFotoController.php`
- **PHP puro:** `integration/php/validar.php`
- **Node/Express:** `integration/node/validar.js`
- **React + TypeScript:** `integration/react/ValidarFoto.tsx` (envía a tu backend; la API key nunca va al navegador)

## Calibración (antes de producción)
```bash
python scripts/benchmark_models.py fotos_prueba --csv resultados.csv
```
Ajusta los umbrales en **Panel → Configuración** hasta tener 0 falsas aprobaciones. Revisa en
**Estadísticas → Revisiones humanas** cuántas decisiones automáticas corrigió el personal.

## Pruebas
```bash
pytest -q
```

## Estructura
```
app/  main.py · api/routes/ (validation, rules, health, admin) · models/ (face, clothing, quality, registry)
      services/ (face_service, clothing_service, image_quality, validation_engine, pipeline, storage)
      core/ (config, security) · schemas/ · database/
frontend/ (React + TypeScript, Vite) · dist/ (compilado, lo sirve FastAPI)
models/ (pesos descargados) · storage/ (fotos privadas) · scripts/ · tests/ · integration/ · docs/
```

## Seguridad y privacidad
Ver [`docs/03_seguridad_y_privacidad.md`](docs/03_seguridad_y_privacidad.md). Las fotos no se usan para
reconocimiento ni identificación biométrica.

## Licencias de los modelos
YuNet (MIT) · MediaPipe (Google, Apache 2.0) · YOLOS Fashionpedia (MIT) · FashionCLIP (MIT) ·
SegFormer clothes (opcional, licencia "other"). RetinaFace/SCRFD de InsightFace se descartaron porque solo permiten uso no comercial.
