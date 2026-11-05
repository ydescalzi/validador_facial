"""
MOTOR DE DECISIÓN — independiente de los modelos de IA.

Recibe la EVIDENCIA (números y detecciones producidos por los servicios) y las
REGLAS configurables, y devuelve un resultado por criterio:

    PASS            cumple
    FAIL            no cumple (motivo de rechazo)
    REVIEW          dudoso: resultados contradictorios, baja confianza o modelo
                    no disponible → revisión manual
    NOT_EVALUATED   no se pudo evaluar porque falló un requisito previo (p. ej. sin rostro)

Estado final:
    algún FAIL          → REJECTED
    algún REVIEW        → MANUAL_REVIEW
    todo PASS           → APPROVED

Todos los motivos salen de comprobaciones realmente ejecutadas sobre la evidencia.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

PASS, FAIL, REVIEW, NOT_EVALUATED = "PASS", "FAIL", "REVIEW", "NOT_EVALUATED"
APPROVED, REJECTED, MANUAL_REVIEW = "APPROVED", "REJECTED", "MANUAL_REVIEW"

ETIQUETAS = {
    "carnet_format": "Formato de carné",
    "resolution": "Resolución y formato",
    "face_detected": "Rostro visible",
    "single_person": "Una sola persona",
    "face_position": "Encuadre y posición del rostro",
    "orientation": "Orientación frontal",
    "eyes": "Ojos visibles y abiertos",
    "sharpness": "Nitidez",
    "lighting": "Iluminación y contraste",
    "background": "Fondo blanco y uniforme",
    "formal_clothing": "Vestimenta formal",
    "accessories": "Accesorios",
}


@dataclass
class Criterio:
    key: str
    status: str
    message: str = ""
    recommendation: str = ""
    values: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return ETIQUETAS.get(self.key, self.key)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["label"] = self.label
        return d


# ---------------------------------------------------------------------------
def _carnet(ev: dict, r: dict) -> Criterio:
    c = ev.get("carnet")
    if not c:
        return Criterio("carnet_format", NOT_EVALUATED)
    espec = f"{r['width']}×{r['height']} px, JPG, máx. {r['max_kb']} KB, {r['dpi']} ppp"

    if c["mode"] == "generate":
        if not c.get("generated"):
            return Criterio("carnet_format", NOT_EVALUATED, "No se pudo generar sin un rostro detectado.")
        v = {k: c[k] for k in ("width", "height", "kb", "dpi", "upscale", "face_height_ratio")}
        if c["upscale"] > 1.15:
            return Criterio("carnet_format", FAIL,
                            "Tu foto no tiene suficiente resolución para el carné.",
                            f"Usa una foto más nítida y cercana: el rostro y los hombros deben ocupar al menos "
                            f"{r['width']}×{r['height']} píxeles.", v)
        if c["kb"] > r["max_kb"]:
            return Criterio("carnet_format", FAIL, f"No se pudo reducir la foto a {r['max_kb']} KB.",
                            "Usa una foto con fondo liso y sin ruido.", v)
        if c["face_height_ratio"] > r["face_height_ratio"] + 0.18:
            return Criterio("carnet_format", FAIL, "El rostro queda demasiado grande en el formato de carné.",
                            "Aléjate un poco de la cámara para que se vean los hombros.", v)
        return Criterio("carnet_format", PASS, f"Foto de carné generada: {c['width']}×{c['height']} px, "
                                               f"JPG, {c['kb']} KB, {c['dpi']} ppp.", values=v)

    # modo "validate": el archivo subido debe cumplir la especificación exacta
    v = {k: c.get(k) for k in ("format", "width", "height", "kb", "dpi")}
    problemas = []
    if r["only_jpg"] and c.get("format") != "JPEG":
        problemas.append(f"el formato es {c.get('format')} (debe ser JPG)")
    if (c.get("width"), c.get("height")) != (r["width"], r["height"]):
        problemas.append(f"mide {c.get('width')}×{c.get('height')} px (debe medir {r['width']}×{r['height']} px)")
    if c["kb"] > r["max_kb"]:
        problemas.append(f"pesa {c['kb']} KB (máximo {r['max_kb']} KB)")
    if r["min_kb"] and c["kb"] < r["min_kb"]:
        problemas.append(f"pesa {c['kb']} KB (mínimo {r['min_kb']} KB)")
    if not c.get("dpi") or c["dpi"] < r["dpi"]:
        problemas.append(f"tiene {c.get('dpi') or 'sin dato de'} ppp (debe tener {r['dpi']} ppp)")
    if problemas:
        return Criterio("carnet_format", FAIL, "La foto no cumple el formato de carné: " + "; ".join(problemas) + ".",
                        f"Ajusta tu foto a {espec}.", v)
    return Criterio("carnet_format", PASS, f"Cumple el formato de carné ({espec}).", values=v)


def _resolucion(ev: dict, r: dict) -> Criterio:
    w, h = ev["image"]["width"], ev["image"]["height"]
    v = {"width": w, "height": h}
    if w < r["min_width"] or h < r["min_height"]:
        return Criterio("resolution", FAIL, f"La resolución es muy baja ({w}x{h} px).",
                        f"Usa una foto de al menos {r['min_width']}x{r['min_height']} píxeles.", v)
    if r["require_portrait"] and w >= h:
        return Criterio("resolution", FAIL, "La foto está en horizontal.",
                        "Toma la foto en vertical (más alta que ancha).", v)
    return Criterio("resolution", PASS, "Resolución y formato correctos.", values=v)


def _rostro(ev: dict, r: dict, recorte_auto: bool = False) -> list[Criterio]:
    """recorte_auto=True (modo generar carné): el tamaño y el centrado se corrigen
    al recortar, así que solo se exige que la cabeza no esté cortada y que se vean los hombros."""
    f = ev["face"]
    if not f["available"]:
        msg = "El detector facial no está disponible."
        return [Criterio(k, REVIEW, msg) for k in ("face_detected", "single_person", "face_position")]
    if f["count"] == 0:
        return [Criterio("face_detected", FAIL, "No se detectó ningún rostro.",
                         "Mira directamente a la cámara con el rostro descubierto y bien iluminado."),
                Criterio("single_person", NOT_EVALUATED), Criterio("face_position", NOT_EVALUATED)]

    p = f["primary"]
    salida = [Criterio("face_detected", PASS, "Rostro detectado.", values={"confidence": p["confidence"]})]
    if f["other_people"] > 0:
        salida.append(Criterio("single_person", FAIL, "Aparece más de una persona en la foto.",
                               "Toma la foto solo, sin otras personas ni fotos al fondo.",
                               {"faces": f["count"]}))
    else:
        salida.append(Criterio("single_person", PASS, "Una sola persona.", values={"faces": f["count"]}))

    problemas, recs = [], []
    if not recorte_auto and p["size_ratio"] < r["size_min"]:
        problemas.append("El rostro se ve muy pequeño o lejano.")
        recs.append("Acércate a la cámara: la foto debe ser desde la cabeza hasta el pecho.")
    elif not recorte_auto and p["size_ratio"] > r["size_max"]:
        problemas.append("El rostro está demasiado cerca.")
        recs.append("Aléjate un poco para que se vean los hombros.")
    if not recorte_auto and p["center_offset"] > r["center_tolerance"]:
        problemas.append("El rostro no está centrado.")
        recs.append("Ubica tu rostro en el centro de la foto.")
    if p["top_margin"] < r["top_margin_min"]:
        problemas.append("La cabeza está cortada en la parte superior.")
        recs.append("Deja un pequeño espacio sobre la cabeza.")
    if p["shoulders_space"] < r["shoulders_space_min"]:
        problemas.append("No se ven los hombros ni la vestimenta.")
        recs.append("Encuadra desde la cabeza hasta el pecho para que se vea tu vestimenta.")
    vals = {k: p[k] for k in ("size_ratio", "center_offset", "top_margin", "shoulders_space")}
    if problemas:
        salida.append(Criterio("face_position", FAIL, " ".join(problemas), " ".join(recs), vals))
    else:
        salida.append(Criterio("face_position", PASS, "Encuadre correcto.", values=vals))
    return salida


def _orientacion(ev: dict, r: dict) -> Criterio:
    f = ev["face"]
    if not f.get("primary"):
        return Criterio("orientation", NOT_EVALUATED)
    mp = f.get("mediapipe") or {}
    rec = "Mira de frente a la cámara, con la cabeza recta."
    if "yaw" in mp:
        v = {"source": "mediapipe", "yaw": mp["yaw"], "pitch": mp["pitch"], "roll": mp["roll"]}
        if abs(mp["roll"]) > r["max_roll_deg"]:
            return Criterio("orientation", FAIL, "La cabeza está inclinada hacia un lado.", rec, v)
        if abs(mp["yaw"]) > r["max_yaw_deg"]:
            return Criterio("orientation", FAIL, "El rostro está girado hacia un lado.", rec, v)
        if abs(mp["pitch"]) > r["max_pitch_deg"]:
            return Criterio("orientation", FAIL, "La cabeza está inclinada hacia arriba o hacia abajo.", rec, v)
        return Criterio("orientation", PASS, "Rostro de frente.", values=v)

    p = f["primary"]
    v = {"source": "yunet", "roll": p["yunet_roll_deg"], "yaw_ratio": p["yunet_yaw_ratio"]}
    if abs(p["yunet_roll_deg"]) > r["yunet_max_roll_deg"]:
        return Criterio("orientation", FAIL, "La cabeza está inclinada hacia un lado.", rec, v)
    if abs(p["yunet_yaw_ratio"]) > r["yunet_max_yaw_ratio"]:
        return Criterio("orientation", FAIL, "El rostro está girado hacia un lado.", rec, v)
    return Criterio("orientation", PASS, "Rostro de frente.", values=v)


def _ojos(ev: dict, r: dict) -> Criterio:
    f = ev["face"]
    if not f.get("primary"):
        return Criterio("eyes", NOT_EVALUATED)
    mp = f.get("mediapipe") or {}
    rec = "Mantén los ojos abiertos y sin cabello ni lentes oscuros que los cubran."
    if mp.get("blink_left") is not None:
        v = {"source": "mediapipe", "blink_left": mp["blink_left"], "blink_right": mp["blink_right"]}
        if max(mp["blink_left"], mp["blink_right"]) > r["max_blink_score"]:
            return Criterio("eyes", FAIL, "Los ojos aparecen cerrados o entrecerrados.", rec, v)
        return Criterio("eyes", PASS, "Ojos visibles.", values=v)
    if f.get("haar_eyes") is not None:
        v = {"source": "opencv_haar", "eyes": f["haar_eyes"]}
        if f["haar_eyes"] == 0:  # detector clásico poco fiable → ni rechaza ni duda
            return Criterio("eyes", NOT_EVALUATED, "No se pudo confirmar automáticamente.", values=v)
        return Criterio("eyes", PASS, "Ojos visibles.", values=v)
    return Criterio("eyes", REVIEW, "No se pudo evaluar si los ojos están visibles.")


def _nitidez(ev: dict, r: dict) -> Criterio:
    s = ev["quality"]["sharpness"]
    if s < r["sharpness_min"]:
        return Criterio("sharpness", FAIL, "La foto está borrosa o desenfocada.",
                        "Limpia la cámara, enfoca el rostro y evita moverte al tomar la foto.", {"sharpness": s})
    return Criterio("sharpness", PASS, "Foto nítida.", values={"sharpness": s})


def _iluminacion(ev: dict, r: dict) -> Criterio:
    qd = ev["quality"]
    v = {k: qd[k] for k in ("brightness", "contrast", "overexposed_pct", "underexposed_pct")}
    if qd["brightness"] < r["brightness_min"] or qd["underexposed_pct"] > r["saturated_max_pct"]:
        return Criterio("lighting", FAIL, "La foto está muy oscura.",
                        "Toma la foto con luz natural frente a ti o con buena iluminación frontal.", v)
    if qd["brightness"] > r["brightness_max"] or qd["overexposed_pct"] > r["saturated_max_pct"]:
        return Criterio("lighting", FAIL, "La foto tiene demasiada luz (sobreexpuesta).",
                        "Evita el flash directo y la luz fuerte sobre el rostro.", v)
    if qd["contrast"] < r["contrast_min"]:
        return Criterio("lighting", FAIL, "La foto tiene muy poco contraste (se ve lavada).",
                        "Usa iluminación uniforme y evita filtros.", v)
    return Criterio("lighting", PASS, "Iluminación adecuada.", values=v)


def _fondo(ev: dict, r: dict) -> Criterio:
    b = ev["quality"]["background"]
    blanco = r.get("require_white", False)
    rec = ("Usa una pared lisa de color blanco, bien iluminada y sin objetos detrás." if blanco else
           "Usa una pared lisa de color claro, sin objetos detrás.")
    if b["brightness"] < r["brightness_min"]:
        return Criterio("background", FAIL, "El fondo no es blanco (es oscuro o gris)." if blanco
                        else "El fondo es oscuro.", rec, b)
    if blanco and b.get("saturation") is not None and b["saturation"] > r["max_saturation"]:
        return Criterio("background", FAIL, "El fondo tiene color; debe ser blanco.", rec, b)
    if b["uniformity"] < r["uniformity_min"]:
        return Criterio("background", FAIL, "El fondo no es uniforme (se ven objetos o detalles).", rec, b)
    return Criterio("background", PASS, "Fondo blanco y uniforme." if blanco else "Fondo claro y uniforme.", values=b)


def _voto_yolos(garments: list[dict], r: dict) -> tuple[str, float, list]:
    """FORMAL | INFORMAL | CONFLICT | UNKNOWN y la confianza máxima usada."""
    val = [g for g in garments if g["score"] >= r["yolos_min_score"]]
    formal = [g for g in val if g["label"] in r["formal_items"]]
    informal = [g for g in val if g["label"] in r["informal_items"]]
    usados = [{"label": g["label"], "score": g["score"]} for g in formal + informal]
    if formal and informal:
        return "CONFLICT", max(g["score"] for g in formal + informal), usados
    if formal:
        return "FORMAL", max(g["score"] for g in formal), usados
    if informal:
        return "INFORMAL", max(g["score"] for g in informal), usados
    return "UNKNOWN", 0.0, usados


def _vestimenta(ev: dict, r: dict) -> Criterio:
    c = ev.get("clothing") or {}
    if c.get("torso_visible") is None:
        return Criterio("formal_clothing", NOT_EVALUATED)
    if c["torso_visible"] is False:
        return Criterio("formal_clothing", FAIL, "No se ve la vestimenta.",
                        "Encuadra desde la cabeza hasta el pecho.")
    rec = "Usa saco o blazer con camisa o blusa formal con cuello (no polos, camisetas, polerones ni capuchas)."

    y_ok = c["yolos"]["available"] and "error" not in c["yolos"]
    torso = c["fashionclip"].get("torso")
    f_ok = c["fashionclip"]["available"] and torso is not None

    y_voto, y_conf, y_usados = _voto_yolos(c["yolos"]["garments"], r) if y_ok else ("UNAVAILABLE", 0.0, [])
    if f_ok:
        fp = torso["formal_prob"]
        f_voto = "FORMAL" if fp >= r["clip_formal_min"] else "INFORMAL" if fp <= r["clip_informal_max"] else "UNCERTAIN"
    else:
        fp, f_voto = None, "UNAVAILABLE"

    v = {"yolos_vote": y_voto, "yolos_items": y_usados, "fashionclip_vote": f_voto, "fashionclip_formal_prob": fp}
    y_fuerte = y_conf >= r["yolos_strong_score"]
    f_fuerte_formal = fp is not None and fp >= r["clip_strong_formal"]
    f_fuerte_informal = fp is not None and fp <= r["clip_strong_informal"]

    if y_voto == "UNAVAILABLE" and f_voto == "UNAVAILABLE":
        return Criterio("formal_clothing", REVIEW, "No se pudo analizar la vestimenta automáticamente.", values=v)
    if y_voto == "FORMAL" and f_voto == "FORMAL":
        return Criterio("formal_clothing", PASS, "Vestimenta formal.", values=v)
    if y_voto == "INFORMAL" and f_voto == "INFORMAL":
        return Criterio("formal_clothing", FAIL, "Se detectó vestimenta informal.", rec, v)
    if {y_voto, f_voto} == {"FORMAL", "INFORMAL"} or y_voto == "CONFLICT":
        return Criterio("formal_clothing", REVIEW,
                        "Los modelos no coinciden sobre la vestimenta; una persona la revisará.", values=v)
    # Un modelo decide y el otro no es concluyente (UNKNOWN / UNCERTAIN / UNAVAILABLE)
    if y_voto == "INFORMAL" and y_fuerte and f_voto != "FORMAL":
        return Criterio("formal_clothing", FAIL, "Se detectó vestimenta informal.", rec, v)
    if f_voto == "INFORMAL" and f_fuerte_informal and y_voto not in ("FORMAL", "CONFLICT"):
        return Criterio("formal_clothing", FAIL, "Se detectó vestimenta informal.", rec, v)
    if (y_voto == "FORMAL" and y_fuerte and f_voto != "INFORMAL") or \
       (f_voto == "FORMAL" and f_fuerte_formal and y_voto not in ("INFORMAL", "CONFLICT")):
        return Criterio("formal_clothing", PASS, "Vestimenta formal.", values=v)
    return Criterio("formal_clothing", REVIEW,
                    "La confianza sobre la vestimenta es insuficiente; una persona la revisará.", values=v)


NOMBRES_ACC = {
    "sunglasses": "lentes de sol", "hat": "gorra o sombrero", "hood": "capucha",
    "headphones": "audífonos", "face_mask": "mascarilla", "head_covering": "prenda en la cabeza",
    "eyeglasses": "lentes",
}


def _accesorios(ev: dict, r: dict) -> Criterio:
    c = ev.get("clothing") or {}
    if c.get("torso_visible") is None:
        return Criterio("accessories", NOT_EVALUATED)
    y_ok = c["yolos"]["available"] and "error" not in c["yolos"]
    cf = c["fashionclip"].get("face")
    seg = c.get("segformer") or {}
    if not y_ok and cf is None and not seg.get("available"):
        return Criterio("accessories", REVIEW, "No se pudieron analizar los accesorios automáticamente.")

    # evidencia por accesorio: lista de (fuente, valor, fuerte?)
    hallazgos: dict[str, list] = {}
    if y_ok:
        mapa = {"hat": "hat", "hood": "hood", "headband, head covering, hair accessory": "head_covering",
                "glasses": "eyeglasses"}
        for d in c["yolos"]["accessories"]:
            if d["label"] in mapa and d["score"] >= r["yolos_min_score"]:
                hallazgos.setdefault(mapa[d["label"]], []).append(("yolos", d["score"], True))
    if cf:
        for k in ("sunglasses", "eyeglasses", "hat", "headphones", "face_mask"):
            if cf.get(k, 0) >= r["clip_min_prob"]:
                fuerte = cf[k] >= r["clip_min_prob"] + 0.15
                hallazgos.setdefault(k, []).append(("fashionclip", cf[k], fuerte))
    if seg.get("available"):
        if seg.get("sunglasses_frac", 0) >= 0.02:
            hallazgos.setdefault("sunglasses", []).append(("segformer", seg["sunglasses_frac"], True))
        if seg.get("hat_frac", 0) >= 0.08:
            hallazgos.setdefault("hat", []).append(("segformer", seg["hat_frac"], True))

    v = {"found": {k: [{"source": s, "value": val} for s, val, _ in lst] for k, lst in hallazgos.items()},
         "fashionclip_face": cf}
    rechazos, revisiones = [], []
    for acc, lst in hallazgos.items():
        politica = r.get(acc, "reject")
        if politica == "allow":
            continue
        # un único indicio débil nunca rechaza: pasa a revisión
        if politica == "reject" and any(f for _, _, f in lst):
            rechazos.append(NOMBRES_ACC[acc])
        else:
            revisiones.append(NOMBRES_ACC[acc])
    if rechazos:
        return Criterio("accessories", FAIL, f"Se detectó: {', '.join(rechazos)}.",
                        "Retira lentes, gorras, capuchas, audífonos o mascarilla antes de tomar la foto.", v)
    if revisiones:
        return Criterio("accessories", REVIEW, f"Posible accesorio ({', '.join(revisiones)}); una persona lo revisará.",
                        values=v)
    return Criterio("accessories", PASS, "Sin accesorios no permitidos.", values=v)


# ---------------------------------------------------------------------------
def evaluate(ev: dict, rules: dict) -> dict:
    criterios: list[Criterio] = []

    def activo(grupo):
        return rules.get(grupo, {}).get("enabled", True)

    carnet = rules.get("carnet", {})
    recorte_auto = bool(carnet.get("enabled") and carnet.get("mode") == "generate")
    if carnet.get("enabled"):
        criterios.append(_carnet(ev, carnet))
    if activo("resolution"):
        criterios.append(_resolucion(ev, rules["resolution"]))
    if activo("face"):
        criterios.extend(_rostro(ev, rules["face"], recorte_auto))
    if activo("orientation"):
        criterios.append(_orientacion(ev, rules["orientation"]))
    if activo("eyes"):
        criterios.append(_ojos(ev, rules["eyes"]))
    if activo("quality"):
        criterios.append(_nitidez(ev, rules["quality"]))
        criterios.append(_iluminacion(ev, rules["quality"]))
    if activo("background"):
        criterios.append(_fondo(ev, rules["background"]))
    if activo("clothing"):
        criterios.append(_vestimenta(ev, rules["clothing"]))
    if activo("accessories"):
        criterios.append(_accesorios(ev, rules["accessories"]))

    estados = {c.status for c in criterios}
    estado = REJECTED if FAIL in estados else MANUAL_REVIEW if REVIEW in estados else APPROVED
    # Sistema simple: lo dudoso también se rechaza y se pide otra foto
    dudoso_rechaza = rules.get("decision", {}).get("uncertain_as", "manual_review") == "reject"
    if estado == MANUAL_REVIEW and dudoso_rechaza:
        estado = REJECTED

    pesos = rules.get("weights", {})
    total = sum(pesos.get(c.key, 0) for c in criterios) or 1
    puntos = sum(pesos.get(c.key, 0) * {PASS: 1.0, REVIEW: 0.5}.get(c.status, 0.0) for c in criterios)

    def unicos(xs):
        return list(dict.fromkeys(x for x in xs if x))

    motivos = unicos(c.message for c in criterios if c.status == FAIL)
    recomendaciones = unicos(c.recommendation for c in criterios if c.status == FAIL)
    if dudoso_rechaza and REVIEW in estados:
        # los criterios dudosos se explican al estudiante como motivos de rechazo
        motivos += unicos(MOTIVO_DUDOSO.get(c.key, c.message) for c in criterios if c.status == REVIEW)
        recomendaciones += unicos(RECOM_DUDOSO.get(c.key, "") for c in criterios if c.status == REVIEW)
    return {
        "status": estado,
        "score": round(100 * puntos / total),
        "criteria": [c.to_dict() for c in criterios],
        "rejection_reasons": unicos(motivos),
        "review_reasons": unicos(c.message for c in criterios if c.status == REVIEW),
        "recommendations": unicos(recomendaciones),
    }


# Cómo se explica al estudiante un criterio dudoso cuando se rechaza (uncertain_as = reject)
MOTIVO_DUDOSO = {
    "formal_clothing": "No se pudo confirmar que tu vestimenta sea formal.",
    "accessories": "No se pudo confirmar que estés sin lentes, gorra u otros accesorios.",
    "eyes": "No se ven claramente tus ojos.",
    "face_detected": "No se pudo analizar tu rostro.",
    "single_person": "No se pudo analizar tu rostro.",
    "face_position": "No se pudo analizar tu rostro.",
}
RECOM_DUDOSO = {
    "formal_clothing": "Usa saco o blazer con camisa o blusa formal con cuello, bien visible en la foto.",
    "accessories": "Retira lentes, gorras, capuchas, audífonos o mascarilla.",
    "eyes": "Mira de frente a la cámara con los ojos abiertos y buena iluminación.",
}


RESULT_MAP = {PASS: "CORRECT", FAIL: "INCORRECT", REVIEW: "REVIEW", NOT_EVALUATED: "NOT_EVALUATED"}


def results_summary(criteria: list[dict]) -> dict:
    """Resumen compacto con el formato pedido (face_detected: true, background: 'CORRECT'…)."""
    por = {c["key"]: c["status"] for c in criteria}
    out = {}
    if "face_detected" in por:
        out["face_detected"] = por["face_detected"] == PASS
    if "single_person" in por:
        out["single_person"] = None if por["single_person"] == NOT_EVALUATED else por["single_person"] == PASS
    for k in ("carnet_format", "face_position", "orientation", "eyes", "background", "lighting", "sharpness",
              "resolution", "formal_clothing", "accessories"):
        if k in por:
            out[k] = RESULT_MAP[por[k]]
    return out
