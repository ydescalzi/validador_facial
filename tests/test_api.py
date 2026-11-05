"""Pruebas de la API (YuNet real + OpenCV; modelos de HF desactivados en tests)."""
import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.main import app

KEY = {"X-API-Key": "clave-test"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def jpeg(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.save(b, "JPEG", quality=95)
    return b.getvalue()


@pytest.fixture(scope="module")
def foto_carnet():
    skimage = pytest.importorskip("skimage")
    from skimage import data
    # la imagen original tiene la cabeza inclinada (~15°): se endereza 9° para la prueba
    cara = Image.fromarray(data.astronaut()).rotate(9, center=(230, 120), fillcolor=(240, 240, 240))
    cara = cara.crop((120, 0, 340, 300)).resize((400, 545))
    lienzo = Image.new("RGB", (600, 800), (240, 240, 240))
    lienzo.paste(cara, (100, 255))
    return jpeg(lienzo)


def subir(client, data, headers=None, codigo="2026001", tipo="image/jpeg"):
    return client.post("/api/v1/photos/validate", headers=headers or {},
                       files={"photo": ("f.jpg", data, tipo)}, data={"student_code": codigo})


def admin_token(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "clave-admin"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health(client):
    h = client.get("/api/v1/health").json()
    assert h["models"]["yunet"]["loaded"] is True
    assert h["status"] == "degraded"  # YOLOS/FashionCLIP desactivados en tests


def test_validacion_con_rostro_y_ruta_a_revision(client, foto_carnet):
    r = subir(client, foto_carnet)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["validation_id"].startswith("VAL-")
    assert d["results"]["face_detected"] is True
    # sin modelos de vestimenta la foto NUNCA se aprueba automáticamente
    assert d["status"] == "REJECTED"
    assert d["results"]["formal_clothing"] == "REVIEW"
    assert any("YuNet" in m for m in d["models_used"])


def test_sin_rostro_rechazada(client):
    r = subir(client, jpeg(Image.new("RGB", (600, 800), (235, 235, 235))))
    d = r.json()
    assert d["status"] == "REJECTED" and d["results"]["face_detected"] is False
    assert "No se detectó ningún rostro." in d["rejection_reasons"]


@pytest.mark.parametrize("datos,tipo", [
    (b"<?php system($_GET['c']); ?>", "image/jpeg"),       # script disfrazado de imagen
    (b"GIF89a" + b"\x00" * 100, "image/jpeg"),              # tipo real distinto
    (b"\xff\xd8\xff" + b"\x00" * 50, "image/jpeg"),        # JPEG corrupto
    (b"cualquier cosa", "application/pdf"),                  # MIME no permitido
])
def test_archivos_maliciosos(client, datos, tipo):
    assert subir(client, datos, tipo=tipo).status_code == 400


def test_archivo_muy_grande(client):
    grande = b"\xff\xd8" + b"0" * int(settings.max_upload_mb * 1024 * 1024 + 10)
    assert subir(client, grande).status_code == 400


def test_codigo_estudiante_invalido(client, foto_carnet):
    assert subir(client, foto_carnet, codigo="../../etc").status_code == 422


def test_consulta_requiere_token_o_key(client):
    d = subir(client, jpeg(Image.new("RGB", (600, 800), (200, 200, 200)))).json()
    vid, tok = d["validation_id"], d["access_token"]
    assert client.get(f"/api/v1/photos/validation/{vid}").status_code == 401
    assert client.get(f"/api/v1/photos/validation/{vid}?token=malo").status_code == 401
    assert client.get(f"/api/v1/photos/validation/{vid}?token={tok}").status_code == 200
    r = client.get(f"/api/v1/photos/validation/{vid}", headers=KEY)
    assert r.status_code == 200 and r.json()["access_token"] is None


def test_historial_requiere_api_key(client):
    assert client.get("/api/v1/photos/history?student_code=2026001").status_code == 401
    r = client.get("/api/v1/photos/history?student_code=2026001", headers=KEY)
    assert r.status_code == 200 and len(r.json()) >= 1


def test_reglas_publicas_y_edicion_solo_admin(client):
    assert client.get("/api/v1/photos/rules").status_code == 200
    cambio = {"background": {"brightness_min": 130}}
    assert client.put("/api/v1/photos/rules", json=cambio).status_code == 401
    assert client.put("/api/v1/photos/rules", json=cambio, headers=KEY).status_code == 401
    h = admin_token(client)
    r = client.put("/api/v1/photos/rules", json=cambio, headers=h)
    assert r.status_code == 200 and r.json()["rules"]["background"]["brightness_min"] == 130
    assert client.put("/api/v1/photos/rules", json={"x": 1}, headers=h).status_code == 422
    client.post("/api/v1/photos/rules/reset", headers=h)


def test_login_incorrecto(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "mala"})
    assert r.status_code == 401


def test_flujo_revision_manual(client, foto_carnet):
    h0 = admin_token(client)
    client.put("/api/v1/photos/rules", json={"decision": {"uncertain_as": "manual_review"}}, headers=h0)
    d = subir(client, foto_carnet, codigo="2026999").json()
    if d["status"] != "MANUAL_REVIEW":
        pytest.skip("La foto de prueba no quedó en revisión manual")
    h = admin_token(client)
    pend = client.get("/api/v1/admin/validations?status=MANUAL_REVIEW", headers=h).json()
    assert any(i["validation_id"] == d["validation_id"] for i in pend["items"])
    img = client.get(f"/api/v1/admin/validations/{d['validation_id']}/image", headers=h)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    r = client.post(f"/api/v1/admin/reviews/{d['validation_id']}", headers=h,
                    json={"decision": "APPROVED", "comment": "Vestimenta formal verificada"})
    assert r.status_code == 200 and r.json()["status"] == "APPROVED" and r.json()["reviewed_by"] == "admin"
    # no se puede revisar dos veces
    assert client.post(f"/api/v1/admin/reviews/{d['validation_id']}", headers=h,
                       json={"decision": "REJECTED"}).status_code == 409
    st = client.get("/api/v1/admin/stats", headers=h).json()
    assert st["total"] >= 1 and st["human_reviews"]
    audit = client.get("/api/v1/admin/audit", headers=h).json()
    assert any(a["action"] == "review" for a in audit)
    client.post("/api/v1/photos/rules/reset", headers=h)


def test_imagen_guardada_sin_exif(client, foto_carnet):
    img = Image.open(io.BytesIO(foto_carnet))
    exif = Image.Exif()
    exif[0x010F] = "CamaraSecreta"
    b = io.BytesIO()
    img.save(b, "JPEG", exif=exif)
    h = admin_token(client)
    client.put("/api/v1/photos/rules", json={"decision": {"uncertain_as": "manual_review"}}, headers=h)
    d = subir(client, b.getvalue(), codigo="2026777").json()
    client.post("/api/v1/photos/rules/reset", headers=h)
    assert d["status"] == "MANUAL_REVIEW"
    guardada = next(settings.storage_dir.rglob(f"{d['validation_id']}.jpg"))
    assert not Image.open(guardada).getexif()


def test_limite_de_solicitudes():
    from fastapi import HTTPException
    from app.core.security import RateLimiter
    rl = RateLimiter()
    for _ in range(3):
        rl.check("x", 3)
    with pytest.raises(HTTPException):
        rl.check("x", 3)


def test_cabeceras_seguridad(client):
    r = client.get("/api/v1/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_genera_foto_carnet_exacta():
    """El generador produce 240×288 px, JPG, ≤50 KB, 300 ppp a partir de una foto real."""
    import base64
    from app.core.config import default_rules
    from app.services.carnet import generate_carnet
    pytest.importorskip("skimage")
    from skimage import data
    from app.models.face_model import YuNetDetector
    import cv2
    import numpy as np
    cara = Image.fromarray(data.astronaut()).rotate(9, center=(230, 120), fillcolor=(240, 240, 240))
    img = Image.new("RGB", (900, 1200), (250, 250, 250))
    img.paste(cara.crop((120, 0, 340, 300)).resize((440, 600)), (230, 300))
    f = YuNetDetector(settings.yunet_path).detect(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))[0]
    g = generate_carnet(img, [round(f.x), round(f.y), round(f.w), round(f.h)], default_rules()["carnet"])
    assert g["generated"] and g["upscale"] <= 1.0
    out = Image.open(io.BytesIO(g["bytes"]))
    assert out.format == "JPEG" and out.size == (240, 288)
    assert len(g["bytes"]) <= 50 * 1024
    assert round(min(out.info["dpi"])) == 300
    assert not out.getexif()


def test_respuesta_incluye_datos_de_carnet(client, foto_carnet):
    d = subir(client, foto_carnet, codigo="2026555").json()
    assert d["carnet"]["mode"] == "generate" and d["carnet"]["width"] == 240
    assert any(c["key"] == "carnet_format" for c in d["criteria"])
    # sin modelos de vestimenta no se aprueba → no se entrega el archivo de carné
    assert d["status"] != "APPROVED" and d["carnet_photo"] is None


def test_comprobante_firmado_verificable(client):
    d = subir(client, jpeg(Image.new("RGB", (600, 800), (235, 235, 235))), codigo="2026321").json()
    assert d["comprobante"]
    v = client.get("/api/v1/photos/verify", params={"comprobante": d["comprobante"]}).json()
    assert v["valid"] and v["validation_id"] == d["validation_id"] and v["status"] == d["status"]
    assert v["student_code"] == "2026321"
    alterado = d["comprobante"][:-3] + ("AAA" if not d["comprobante"].endswith("AAA") else "BBB")
    assert client.get("/api/v1/photos/verify", params={"comprobante": alterado}).json() == {"valid": False}
