"""Pruebas del motor de reglas con evidencia construida a mano (sin modelos)."""
import copy

from app.core.config import default_rules, merge_rules
from app.services import validation_engine as E

import pytest

BASE = {
    "image": {"width": 600, "height": 800},
    "face": {"available": True, "count": 1, "other_people": 0, "haar_eyes": None,
             "primary": {"box": [200, 150, 200, 260], "confidence": 0.93, "size_ratio": 0.33,
                         "center_offset": 0.0, "top_margin": 0.19, "shoulders_space": 0.49,
                         "yunet_roll_deg": 1.0, "yunet_yaw_ratio": 0.02},
             "mediapipe": {"faces": 1, "yaw": 2.0, "pitch": 3.0, "roll": 1.0, "blink_left": 0.1, "blink_right": 0.1}},
    "quality": {"sharpness": 40.0, "brightness": 140.0, "contrast": 45.0, "overexposed_pct": 0.01,
                "underexposed_pct": 0.0, "background": {"brightness": 245.0, "uniformity": 0.95, "method": "borders",
                                                        "saturation": 4.0}},
    "carnet": {"mode": "generate", "generated": True, "width": 240, "height": 288, "kb": 31.5, "dpi": 300,
               "upscale": 0.6, "face_height_ratio": 0.5},
    "clothing": {"torso_visible": True,
                 "yolos": {"available": True, "garments": [], "accessories": []},
                 "fashionclip": {"available": True, "torso": {"formal_prob": 0.5}, "face": {"bare": 0.9}},
                 "segformer": {"available": False}},
}


def ev(**cambios):
    e = copy.deepcopy(BASE)
    for ruta, valor in cambios.items():
        d = e
        partes = ruta.split("__")
        for p in partes[:-1]:
            d = d[p]
        d[partes[-1]] = valor
    return e


def crit(res, key):
    return next(c for c in res["criteria"] if c["key"] == key)


R = merge_rules(default_rules(), {"decision": {"uncertain_as": "manual_review"}})
R_SIMPLE = default_rules()  # por defecto: lo dudoso se rechaza
FORMAL = [{"label": "lapel", "score": 0.9}, {"label": "jacket", "score": 0.88}]
POLO = [{"label": "top, t-shirt, sweatshirt", "score": 0.91}]


def test_formal_coincidente_aprueba():
    r = E.evaluate(ev(clothing__yolos__garments=FORMAL, clothing__fashionclip__torso={"formal_prob": 0.9}), R)
    assert r["status"] == "APPROVED" and r["score"] == 100


def test_informal_coincidente_rechaza():
    r = E.evaluate(ev(clothing__yolos__garments=POLO, clothing__fashionclip__torso={"formal_prob": 0.1}), R)
    assert r["status"] == "REJECTED"
    assert "Se detectó vestimenta informal." in r["rejection_reasons"]
    assert r["recommendations"]


def test_modelos_contradictorios_va_a_revision():
    r = E.evaluate(ev(clothing__yolos__garments=FORMAL, clothing__fashionclip__torso={"formal_prob": 0.1}), R)
    assert crit(r, "formal_clothing")["status"] == "REVIEW" and r["status"] == "MANUAL_REVIEW"


def test_saco_sobre_polo_es_conflicto():
    r = E.evaluate(ev(clothing__yolos__garments=FORMAL + POLO, clothing__fashionclip__torso={"formal_prob": 0.7}), R)
    assert crit(r, "formal_clothing")["status"] == "REVIEW"


def test_sin_prenda_identificada_no_rechaza():
    r = E.evaluate(ev(clothing__yolos__garments=[], clothing__fashionclip__torso={"formal_prob": 0.5}), R)
    assert crit(r, "formal_clothing")["status"] == "REVIEW"


def test_un_modelo_muy_seguro_y_otro_dudoso():
    r = E.evaluate(ev(clothing__yolos__garments=POLO, clothing__fashionclip__torso={"formal_prob": 0.5}), R)
    assert crit(r, "formal_clothing")["status"] == "FAIL"
    r = E.evaluate(ev(clothing__yolos__garments=[], clothing__fashionclip__torso={"formal_prob": 0.85}), R)
    assert crit(r, "formal_clothing")["status"] == "PASS"


def test_modelos_no_disponibles_nunca_aprueban():
    r = E.evaluate(ev(clothing__yolos__available=False, clothing__fashionclip__available=False,
                      clothing__fashionclip__torso=None, clothing__fashionclip__face=None), R)
    assert crit(r, "formal_clothing")["status"] == "REVIEW"
    assert crit(r, "accessories")["status"] == "REVIEW"
    assert r["status"] == "MANUAL_REVIEW"


def test_sin_rostro_rechaza():
    r = E.evaluate(ev(face__count=0, face__primary=None, clothing__torso_visible=None), R)
    assert r["status"] == "REJECTED"
    assert crit(r, "face_detected")["status"] == "FAIL"
    assert crit(r, "orientation")["status"] == "NOT_EVALUATED"


def test_dos_personas():
    r = E.evaluate(ev(face__other_people=1, clothing__yolos__garments=FORMAL,
                      clothing__fashionclip__torso={"formal_prob": 0.9}), R)
    assert "Aparece más de una persona en la foto." in r["rejection_reasons"]


def test_rostro_girado_mediapipe():
    r = E.evaluate(ev(face__mediapipe__yaw=30.0), R)
    assert crit(r, "orientation")["status"] == "FAIL"


def test_orientacion_respaldo_yunet():
    r = E.evaluate(ev(face__mediapipe=None, face__primary__yunet_roll_deg=12.0), R)
    assert crit(r, "orientation")["status"] == "FAIL"
    assert crit(r, "orientation")["values"]["source"] == "yunet"


def test_ojos_cerrados():
    r = E.evaluate(ev(face__mediapipe__blink_left=0.9), R)
    assert crit(r, "eyes")["status"] == "FAIL"


def test_haar_sin_ojos_no_rechaza_ni_duda():
    # Haar (respaldo sin MediaPipe) es poco fiable: si no ve ojos no penaliza
    r = E.evaluate(ev(face__mediapipe=None, face__haar_eyes=0), R_SIMPLE)
    assert crit(r, "eyes")["status"] == "NOT_EVALUATED"


def test_borrosa_oscura_fondo():
    r = E.evaluate(ev(quality__sharpness=3.0, quality__brightness=30.0,
                      quality__background={"brightness": 90.0, "uniformity": 0.4, "method": "borders"}), R)
    assert crit(r, "sharpness")["status"] == "FAIL"
    assert crit(r, "lighting")["status"] == "FAIL"
    assert crit(r, "background")["status"] == "FAIL"


def test_lentes_de_sol_fuerte_rechaza_y_debil_revisa():
    r = E.evaluate(ev(clothing__fashionclip__face={"sunglasses": 0.9}), R)
    assert crit(r, "accessories")["status"] == "FAIL"
    r = E.evaluate(ev(clothing__fashionclip__face={"sunglasses": 0.6}), R)
    assert crit(r, "accessories")["status"] == "REVIEW"


def test_prenda_en_cabeza_va_a_revision_por_politica():
    acc = [{"label": "headband, head covering, hair accessory", "score": 0.9}]
    r = E.evaluate(ev(clothing__yolos__accessories=acc), R)
    assert crit(r, "accessories")["status"] == "REVIEW"


def test_politica_configurable():
    reglas = merge_rules(R, {"accessories": {"sunglasses": "allow"}})
    r = E.evaluate(ev(clothing__fashionclip__face={"sunglasses": 0.95}), reglas)
    assert crit(r, "accessories")["status"] == "PASS"


def test_criterio_desactivado_no_cuenta():
    reglas = merge_rules(R, {"background": {"enabled": False}})
    r = E.evaluate(ev(quality__background={"brightness": 50.0, "uniformity": 0.1, "method": "borders"}), reglas)
    assert all(c["key"] != "background" for c in r["criteria"])


def test_merge_rules_valida_tipos_y_claves():
    with pytest.raises(ValueError):
        merge_rules(R, {"no_existe": 1})
    with pytest.raises(ValueError):
        merge_rules(R, {"background": {"brightness_min": "alto"}})
    with pytest.raises(ValueError):
        merge_rules(R, {"accessories": {"hat": "quizas"}})


def test_resumen_formato_pedido():
    r = E.evaluate(ev(clothing__yolos__garments=POLO, clothing__fashionclip__torso={"formal_prob": 0.1}), R)
    s = E.results_summary(r["criteria"])
    assert s["face_detected"] is True and s["single_person"] is True
    assert s["formal_clothing"] == "INCORRECT" and s["background"] == "CORRECT"


# --- Formato de carné ---------------------------------------------------------
def test_carnet_generado_correcto():
    r = E.evaluate(ev(), R)
    c = crit(r, "carnet_format")
    assert c["status"] == "PASS" and "240×288" in c["message"]


def test_carnet_sin_resolucion_suficiente():
    r = E.evaluate(ev(carnet__upscale=1.8), R)
    assert crit(r, "carnet_format")["status"] == "FAIL"


def test_carnet_modo_validar_exige_medidas_exactas():
    reglas = merge_rules(R, {"carnet": {"mode": "validate"}})
    malo = {"mode": "validate", "format": "PNG", "width": 600, "height": 800, "kb": 180.0, "dpi": 72}
    c = crit(E.evaluate(ev(carnet=malo), reglas), "carnet_format")
    assert c["status"] == "FAIL"
    for texto in ("JPG", "240×288", "50 KB", "300 ppp"):
        assert texto in c["message"]
    bueno = {"mode": "validate", "format": "JPEG", "width": 240, "height": 288, "kb": 38.0, "dpi": 300}
    assert crit(E.evaluate(ev(carnet=bueno), reglas), "carnet_format")["status"] == "PASS"


def test_modo_generar_no_exige_centrado_ni_tamano():
    # en modo generar el recorte corrige el centrado y el tamaño del rostro
    r = E.evaluate(ev(face__primary__center_offset=0.3, face__primary__size_ratio=0.1), R)
    assert crit(r, "face_position")["status"] == "PASS"
    reglas = merge_rules(R, {"carnet": {"mode": "validate"}})
    r = E.evaluate(ev(face__primary__center_offset=0.3), reglas)
    assert crit(r, "face_position")["status"] == "FAIL"


def test_fondo_celeste_no_es_blanco():
    r = E.evaluate(ev(quality__background={"brightness": 215.0, "uniformity": 0.95, "method": "borders",
                                           "saturation": 63.0}), R)
    c = crit(r, "background")
    assert c["status"] == "FAIL" and "blanco" in c["message"]


def test_lentes_rechazados_por_defecto():
    acc = [{"label": "glasses", "score": 0.85}]
    assert crit(E.evaluate(ev(clothing__yolos__accessories=acc), R), "accessories")["status"] == "FAIL"
    reglas = merge_rules(R, {"accessories": {"eyeglasses": "allow"}})
    assert crit(E.evaluate(ev(clothing__yolos__accessories=acc), reglas), "accessories")["status"] == "PASS"


def test_modo_carnet_invalido():
    with pytest.raises(ValueError):
        merge_rules(R, {"carnet": {"mode": "otro"}})


def test_por_defecto_lo_dudoso_se_rechaza_con_motivo_claro():
    r = E.evaluate(ev(clothing__yolos__garments=FORMAL, clothing__fashionclip__torso={"formal_prob": 0.1}), R_SIMPLE)
    assert r["status"] == "REJECTED"
    assert "No se pudo confirmar que tu vestimenta sea formal." in r["rejection_reasons"]
    assert any("saco o blazer" in x for x in r["recommendations"])


def test_por_defecto_formal_sigue_aprobando():
    r = E.evaluate(ev(clothing__yolos__garments=FORMAL, clothing__fashionclip__torso={"formal_prob": 0.9}), R_SIMPLE)
    assert r["status"] == "APPROVED"
