# Publicar el sistema y enlazarlo desde otro sistema

```
 Estudiante (celular o PC)
        │
        ▼
 Frontend React  ── Vercel ──  https://tu-app.vercel.app
        │   /api/*  (vercel.json lo reenvía)
        ▼
 Backend Python + IA ── Docker en Cloud Run / VPS / servidor de la universidad
```

**Por qué el backend no va en Vercel:** las funciones Python de Vercel tienen un
límite de 500 MB, y el backend necesita torch y 4 modelos de IA (más de 1,5 GB).
Además, en cada arranque en frío tendría que volver a cargar los modelos.
Necesita un servidor con **mínimo 4 GB de RAM** (recomendado 8 GB) y 2 vCPU.

---

## 1. Backend (Docker)

La imagen ya incluye los modelos y el frontend; no usa base de datos.

### Opción A: Google Cloud Run (escala a cero, pagas por uso)
```bash
gcloud run deploy validador-fotos --source . --region us-central1 \
  --memory 4Gi --cpu 2 --timeout 120 --allow-unauthenticated \
  --set-env-vars ADMIN_PASSWORD_HASH='pbkdf2_sha256$...',JWT_SECRET='una-clave-larga'
```
Al terminar, Cloud Run te da una URL como `https://validador-fotos-xxxx.run.app`.
Si escala a cero, la primera petición tras un rato sin uso tarda ~20–40 s (cargando modelos);
para evitarlo usa `--min-instances 1`.

### Opción B: VPS o servidor de la universidad (con Docker)
```bash
docker build -t validador-fotos .
docker run -d --name validador --restart unless-stopped -p 8080:8080 \
  -e ADMIN_PASSWORD_HASH='pbkdf2_sha256$...' -e JWT_SECRET='una-clave-larga' validador-fotos
```
Ponlo detrás de Nginx con HTTPS (ver `03_seguridad_y_privacidad.md`).

Comprueba: `https://TU-BACKEND/api/v1/health` → `"status": "ok"` y los 4 modelos `loaded: true`.

---

## 2. Frontend (Vercel)

1. Edita **`frontend/vercel.json`**: reemplaza `https://CAMBIA-ESTO-POR-TU-BACKEND.com`
   por la URL de tu backend (sin `/` al final).
2. Edita **`frontend/src/config.ts`**:
   - `INSTITUCION`: el nombre de tu universidad.
   - `ORIGENES_PERMITIDOS`: el dominio del sistema que enlazará la página, por ejemplo
     `["https://intranet.miuniversidad.edu.pe"]`.
3. Sube el proyecto a GitHub y en Vercel elige **Add New → Project**:
   - **Root Directory:** `frontend`
   - **Framework:** Vite (lo detecta solo)
   - **Build Command:** `npm run build` · **Output:** `dist`
4. Deploy. Tu página queda en `https://tu-app.vercel.app`; el panel en `/admin`.

No necesitas variables de entorno en Vercel.

---

## 3. Enlazar desde el otro sistema

### Opción simple: un enlace
```
https://tu-app.vercel.app/?codigo=2026001234&nombre=Ana%20Pérez&retorno=https://intranet.miuniversidad.edu.pe/carnet/listo
```
| Parámetro | Para qué |
|---|---|
| `codigo` | Código del estudiante (se muestra fijo, no lo puede cambiar) |
| `nombre` | Saludo "Hola, Ana" (opcional) |
| `retorno` | Al aceptarse la foto aparece **"Continuar con mi trámite"**, que lleva a esa URL con `?validation_id=VAL-000123&estado=APPROVED&codigo=2026001234` |

`retorno` solo funciona si su dominio está en `ORIGENES_PERMITIDOS` (evita redirecciones maliciosas).

### Opción integrada: iframe o ventana emergente
```html
<iframe src="https://tu-app.vercel.app/?codigo=2026001234&retorno=https://intranet.miuniversidad.edu.pe"
        style="width:100%;height:900px;border:0" allow="camera"></iframe>
<script>
  window.addEventListener("message", (e) => {
    if (e.origin !== "https://tu-app.vercel.app") return;
    if (e.data?.tipo !== "validacion-foto-carnet") return;
    // e.data = { estado, validation_id, codigo, motivos, foto_carnet }
    if (e.data.estado === "APPROVED") {
      // foto_carnet: "data:image/jpeg;base64,..." (240×288, JPG, ≤50 KB, 300 ppp)
      guardarFotoDelEstudiante(e.data.codigo, e.data.foto_carnet);
    }
  });
</script>
```

### Verificación desde tu servidor (recomendado)
No confíes solo en lo que llega del navegador. Desde el backend de tu sistema:
```
GET https://TU-BACKEND/api/v1/photos/validation/VAL-000123
X-API-Key: <una de las claves de API_KEYS>
```
Responde con `status` = `APPROVED` si la foto fue aceptada. (Sin base de datos, los
resultados existen mientras el backend esté encendido; para guardarlos de forma
permanente usa `PERSIST=true` con MySQL.)

---

## 4. Comportamiento para el estudiante
- **Formal y cumple todo** → "¡Tu foto fue aceptada!" + descarga de la foto de carné.
- **No formal o no cumple** → "Vuelve a subir tu foto, ya que fue rechazada por no cumplir
  los requisitos", con los motivos, cómo corregirlo y el botón **"Volver a subir mi foto"**.
- **La IA no está segura** → se rechaza y se pide otra foto (configurable en
  *Panel → Configuración → Decisión*: cambiar a "Enviar a revisión manual").
