# Subir el sistema a Vercel (todo en Vercel: página + IA)

```
https://tu-app.vercel.app        → página del estudiante (React)
https://tu-app.vercel.app/api/…  → función Python con la IA (ONNX Runtime)
```

La IA corre en una **función Python de Vercel** usando **ONNX Runtime**, sin PyTorch.
Así entra en el límite de 500 MB de Vercel: dependencias ≈ 333 MB + modelos ≈ 120 MB.

---

## Paso 1 · Exportar los modelos a ONNX (una sola vez, en tu PC)

```powershell
cd "C:\Users\YDESCALZI\Desktop\sistema validador\photo-validator-ai"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
pip install -r requirements-export.txt
python scripts/exportar_onnx.py
```

Al terminar debe mostrar algo así:
```
[verificación] similitud FashionCLIP ONNX vs PyTorch: 0.99xx (ideal > 0.97)
  fashionclip_textos.npz         0.0 MB
  fashionclip_vision.onnx       ~88 MB
  meta.json                      0.0 MB
  yolos_fashionpedia.onnx       ~31 MB
```
Los archivos quedan en `models\onnx\`. **Tienen que subirse con el proyecto.**

Para probar en tu PC antes de subir:
```powershell
python -m uvicorn app.main:app --port 8080
```
Abre http://localhost:8080/api/v1/health: `yunet`, `yolos` y `fashionclip` deben decir `"loaded": true`.

## Paso 2 · Ajustar la configuración (opcional)

Edita **`frontend/src/config.ts`**:
- `INSTITUCION`: el nombre de tu universidad.
- `ORIGENES_PERMITIDOS`: el dominio del sistema que enlazará la página, por ejemplo
  `["https://intranet.miuniversidad.edu.pe"]`.

Los requisitos (medidas del carné, fondo, lentes…) están en `DEFAULT_RULES`, en
`app/core/config.py`.

## Paso 3 · Subir a Vercel

### Opción A: desde GitHub (recomendada)
1. Crea un repositorio en GitHub y sube la carpeta `photo-validator-ai`, **incluida**
   `models/onnx`. Cada archivo pesa menos de 100 MB, así que GitHub lo acepta.
   ```powershell
   git init
   git add .
   git commit -m "Validador de fotos"
   git branch -M main
   git remote add origin https://github.com/TU-USUARIO/validador-fotos.git
   git push -u origin main
   ```
   El `.gitignore` ya excluye `venv`, `.env`, `models/hf` y `node_modules`.
2. En https://vercel.com elige **Add New… → Project → Import** tu repositorio.
3. Configuración del proyecto:
   - **Root Directory:** déjalo vacío (la raíz del repositorio).
   - **Framework Preset:** `Other`. El archivo `vercel.json` ya define cómo se compila.
4. En **Environment Variables** agrega:

   | Nombre | Valor |
   |---|---|
   | `JWT_SECRET` | una clave larga y aleatoria (mínimo 32 caracteres) |
   | `API_KEYS` | *(opcional)* clave para que el otro sistema consulte la API |

   Para generar una clave: `python -c "import secrets; print(secrets.token_urlsafe(40))"`
5. Pulsa **Deploy**.

### Opción B: desde tu PC con Vercel CLI
```powershell
npm install -g vercel
vercel login
vercel                 # primera vez: responde las preguntas (directorio: ./)
vercel env add JWT_SECRET
vercel --prod
```

## Paso 4 · Comprobar

1. Abre `https://tu-app.vercel.app/api/v1/health`:
   - `"status": "ok"`
   - `yunet`, `yolos` y `fashionclip` con `"loaded": true`
   - `"warning": null`. Si dice que falta `JWT_SECRET`, revisa el paso 3.4.
2. Abre `https://tu-app.vercel.app` y sube una foto formal y otra informal.

La **primera petición** después de un rato sin uso tarda unos segundos más, porque
Vercel arranca la función y carga los modelos. Las siguientes tardan 1–3 s.

---

## Cómo lo usa el otro sistema

Enlace:
```
https://tu-app.vercel.app/?codigo=2026001234&nombre=Ana&retorno=https://intranet.miuniversidad.edu.pe/carnet
```
Cuando la foto se acepta, el botón **"Continuar con mi trámite"** vuelve a `retorno` con:
```
?validation_id=VAL-000001&estado=APPROVED&codigo=2026001234&comprobante=eyJhbGciOi...
```

**Verificar que el resultado es auténtico** (no basta con confiar en la URL):
```
GET https://tu-app.vercel.app/api/v1/photos/verify?comprobante=eyJhbGciOi...
→ {"valid": true, "status": "APPROVED", "student_code": "2026001234",
   "foto_sha256": "…", "validation_id": "VAL-000001", ...}
```
El comprobante está firmado con `JWT_SECRET`, así que nadie puede fabricarlo. Funciona
sin base de datos. `foto_sha256` permite comprobar que la foto recibida (por
`postMessage` o subida por el estudiante) es exactamente la que se aprobó.

---

## Límites de Vercel que conviene conocer
- **Tamaño de la función:** ≈ 455 MB de 500 MB. No agregues dependencias pesadas a `requirements.txt`.
- **Memoria:** `vercel.json` pide 2048 MB. Si el plan no lo permite, Vercel avisará al desplegar.
- **Cuerpo de la petición: máx. 4,5 MB.** La página reduce la foto en el celular antes de subirla.
- **Plan Hobby:** es para uso personal y no comercial. Para uso institucional, revisa los términos de Vercel (plan Pro).
- **Sin base de datos:** cada instancia de la función tiene su propia memoria. Por eso
  el resultado se entrega como **comprobante firmado**. El **panel /admin** (estadísticas,
  revisión manual y cambios de reglas) solo es fiable con una base de datos
  (`PERSIST=true` + `DATABASE_URL` de MySQL). En Vercel, los requisitos se cambian en
  `app/core/config.py` y se vuelve a desplegar.
- **MediaPipe** no se incluye por tamaño. La orientación del rostro se mide con YuNet.

## Si algo falla
| Síntoma | Causa / solución |
|---|---|
| `/api/v1/health` dice `yolos`/`fashionclip` con error "No existe … exportar_onnx.py" | No se subieron los archivos de `models/onnx`. Ejecuta el paso 1 y súbelos |
| Todas las fotos salen rechazadas por "No se pudo confirmar que tu vestimenta sea formal" | Mismo caso anterior: faltan los modelos ONNX |
| Error de despliegue "exceeds the maximum size" | Se coló algo pesado en la función. Revisa que `models/hf` y `venv` no estén en el repositorio |
| Error 413 al subir | La foto supera 4,5 MB. La página la reduce sola, así que comprueba que estás usando la versión compilada actual |
| `/api/...` responde 404 | `vercel.json` debe estar en la raíz del repositorio y el Root Directory vacío |
