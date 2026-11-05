# Seguridad y privacidad

| Requisito | Implementación |
|---|---|
| HTTPS | Despliega detrás de Nginx/Apache con certificado (ejemplo abajo). La API envía `Strict-Transport-Security` cuando la solicitud llega por HTTPS. |
| Control de acceso | `X-API-Key` para la plataforma; JWT (`/api/v1/auth/login`) para el panel; `access_token` único por validación para que el estudiante vea solo la suya. |
| Archivos maliciosos | Se valida el contenido real (no la extensión): solo JPEG/PNG/WEBP, `verify()` de Pillow, límite de píxeles (bombas de descompresión), sin animaciones; la imagen se **re-codifica** antes de guardarse (se eliminan EXIF, GPS y datos incrustados). |
| MIME y tamaño | `MAX_UPLOAD_MB` (5 MB por defecto) y lista blanca de MIME. |
| Límite de solicitudes | `RATE_LIMIT_PER_MINUTE` por cliente; login limitado a 10/min por IP. (En varios servidores, usar Redis o el límite del proxy.) |
| Almacenamiento privado | `storage/` no se publica; la imagen solo se ve con JWT de administrador y cada acceso queda auditado. |
| Retención | Revisión/rechazadas: `RETENTION_REVIEW_DAYS`. Aprobadas: `RETENTION_APPROVED_DAYS` (0 = no borrar). Las rechazadas no se guardan salvo `STORE_REJECTED=true`. Purga al iniciar y desde el panel. |
| Auditoría | Tabla `photo_audit_logs`: validaciones, archivos rechazados, logins (también fallidos), cambios de reglas, revisiones, vistas de imágenes, purgas. |
| Biometría | Los modelos faciales solo **detectan** posición, pose y ojos. **No** se calculan *embeddings* faciales, ni se compara ni identifica a personas. |

## Nginx (HTTPS + proxy)
```nginx
server {
    listen 443 ssl;
    server_name validador.tu-universidad.edu.pe;
    ssl_certificate     /etc/letsencrypt/live/validador.../fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/validador.../privkey.pem;
    client_max_body_size 6m;
    limit_req_zone $binary_remote_addr zone=fotos:10m rate=30r/m;
    location / {
        limit_req zone=fotos burst=10;
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 120s;
    }
}
```

Recomendaciones adicionales: informa al estudiante (aviso de privacidad) sobre el
tratamiento de su imagen conforme a la ley de protección de datos personales
aplicable (en Perú, Ley N.º 29733); restringe el acceso a la carpeta `storage/`
y a la base de datos; rota `API_KEYS` y `JWT_SECRET` periódicamente.
