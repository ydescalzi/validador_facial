# Fase 2 y Fase 6 — Pruebas realizadas y limitaciones

## Lo que se verificó en el entorno de desarrollo (2026-11-05)

| Componente | Resultado | Cómo |
|---|---|---|
| YuNet (`face_detection_yunet_2023mar.onnx`) | **Descargado y ejecutado.** SHA-256 `8f2383e4…52fa4`, 232 KB | Fotos reales de estudiantes (2), foto de muestra, composición de 2 personas, imagen sin rostro |
| Conteo de rostros | 1 / 1 / 2 / 0 detectados correctamente | ídem |
| Tiempo YuNet | 4–25 ms por foto (CPU) | medido |
| Precisión del ángulo (roll) de YuNet | **Subestima ≈50 %**: real 10°→6,3°, 20°→12,2°, 30°→14,7° | rotación controlada de una foto |
| Motor de reglas | 21 pruebas unitarias (tabla de decisión completa de vestimenta y accesorios) | `pytest tests/test_engine.py` |
| API, seguridad y base de datos | 16 pruebas: archivos maliciosos, tamaño, MIME falso, JPEG corrupto, API key, JWT, permisos, token por validación, revisión manual de punta a punta, borrado de EXIF, límite de solicitudes, cabeceras | `pytest tests/test_api.py` (SQLite) |
| Interfaz | Estudiante (escritorio y móvil) y panel admin, sin errores de consola | Playwright |

## Lo que NO se pudo verificar aquí (debes hacerlo en tu equipo)

El entorno de desarrollo no tenía acceso a `huggingface.co` ni a
`storage.googleapis.com`, por lo que **YOLOS Fashionpedia, FashionCLIP,
MediaPipe y SegFormer no se ejecutaron**. El código usa sus APIs oficiales,
pero sus resultados con tus fotos son desconocidos hasta que corras:

```bash
python scripts/exportar_onnx.py
python scripts/benchmark_models.py fotos_prueba --csv resultados.csv
```

con al menos **30 fotos en `fotos_prueba/aprobar/` y 30 en `fotos_prueba/rechazar/`**
(polos, polerones, gorras, lentes de sol, selfies, fondos con objetos, borrosas,
dos personas, varones y mujeres por igual). Calibra las reglas desde el panel
hasta tener **0 falsas aprobaciones**; lo dudoso debe ir a revisión manual.

## Comportamiento cuando un modelo falta o falla
Nunca se aprueba lo que no se pudo evaluar: el criterio pasa a `REVIEW` y la
foto a `MANUAL_REVIEW`. `GET /api/v1/health` muestra `degraded` y qué modelo falta.

## Limitaciones conocidas por modelo
- **YuNet:** subestima la inclinación lateral (medido). Su umbral propio es 7° (≈13–15° reales). No detecta oclusiones de los ojos; para eso se usa MediaPipe.
- **MediaPipe Face Landmarker:** sus blendshapes (`eyeBlink*`) están pensados para expresiones. Lentes de sol oscuros pueden dar valores ambiguos, y esos casos se cubren con FashionCLIP.
- **YOLOS Fashionpedia:** entrenado con fotos de moda de cuerpo entero, no con fotos de carnet recortadas al pecho. La clase `glasses` no distingue lentes de sol. `top, t-shirt, sweatshirt` agrupa camiseta y polerón. La ficha no publica métricas.
- **FashionCLIP:** su autor advierte que no fue desarrollado para despliegue sin estudio previo, que hereda los sesgos de CLIP y que sus datos asocian prendas a géneros. Para mitigarlo, las frases del sistema son neutras en género y de estructura idéntica, y FashionCLIP nunca decide solo con confianza media.
- **Fondo (sin SegFormer):** se mide en los bordes de la imagen. Un fondo con objetos solo en el centro, detrás de la persona, puede no detectarse.
- **Decisión "polo con cuello":** YOLOS lo puede ver como `collar` (formal) y FashionCLIP como `polo shirt` (informal). En ese caso el motor lo manda a revisión manual por contradicción, lo cual es intencional.

## Criterio de equidad
Las reglas y frases son las mismas para todas las personas. Ninguna regla usa el
género. Las prendas en la cabeza que pueden ser religiosas (`head covering`) van a
**revisión manual** por defecto, no a rechazo automático (configurable).
