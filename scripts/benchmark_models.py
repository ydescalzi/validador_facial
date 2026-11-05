"""
FASE 2 / FASE 6 — Prueba real de los modelos con TUS fotografías.

Organiza una carpeta así (el nombre de la subcarpeta es la respuesta correcta):

    fotos_prueba/
      aprobar/        fotos que DEBEN aprobarse (formales, correctas)
      rechazar/       fotos que DEBEN rechazarse (polo, gorra, selfie, fondo, borrosa…)

Ejecuta:
    python scripts/benchmark_models.py fotos_prueba
    python scripts/benchmark_models.py fotos_prueba --csv resultados.csv

Muestra, por foto, lo que respondió cada modelo y la decisión final, y al final:
falsas aprobaciones, falsos rechazos, cuántas fueron a revisión manual y tiempos.
Estas son las métricas reales de TU institución (no se inventan métricas).
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import default_rules  # noqa: E402
from app.core.security import sanitize_image  # noqa: E402
from app.models.registry import registry  # noqa: E402
from app.services.pipeline import run_validation  # noqa: E402

EXT = {".jpg", ".jpeg", ".png", ".webp"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta")
    ap.add_argument("--csv")
    a = ap.parse_args()
    raiz = Path(a.carpeta)

    fotos = []
    for esperado in ("aprobar", "rechazar"):
        d = raiz / esperado
        d.mkdir(parents=True, exist_ok=True)
        fotos += [(p, esperado) for p in sorted(d.iterdir()) if p.suffix.lower() in EXT]
    if not fotos:
        sys.exit(f"No hay fotos todavía. Ya creé las carpetas:\n"
                 f"  {(raiz / 'aprobar').resolve()}   <- copia aquí fotos que SÍ deben aprobarse\n"
                 f"  {(raiz / 'rechazar').resolve()}  <- copia aquí fotos que NO deben aprobarse\n"
                 "Luego vuelve a ejecutar este comando.")

    print("Cargando modelos…")
    registry.load_all()
    for k, s in registry.status.items():
        print(f"  {k:<12} {'OK' if s.get('loaded') else 'NO'}  {s['name']}  {s.get('error', '')[:80]}")

    reglas = default_rules()
    filas, cuenta = [], {"ok": 0, "falsa_aprobacion": 0, "falso_rechazo": 0, "revision": 0}
    tiempos = []
    for p, esperado in fotos:
        img, _info = sanitize_image(p.read_bytes(), None)
        t = time.perf_counter()
        r = run_validation(img, reglas, registry, _info)
        tiempos.append((time.perf_counter() - t) * 1000)
        est = r["status"]
        if est == "MANUAL_REVIEW":
            cuenta["revision"] += 1
            res = "revision"
        elif (est == "APPROVED") == (esperado == "aprobar"):
            cuenta["ok"] += 1
            res = "ok"
        elif est == "APPROVED":
            cuenta["falsa_aprobacion"] += 1
            res = "FALSA APROBACION"
        else:
            cuenta["falso_rechazo"] += 1
            res = "FALSO RECHAZO"

        c = r["evidence"]["clothing"]
        yolos = ", ".join(f"{d['label']}:{d['score']:.2f}" for d in c["yolos"]["garments"][:5]) or "-"
        ft = (c["fashionclip"].get("torso") or {})
        ff = (c["fashionclip"].get("face") or {})
        print(f"\n[{res}] {p.parent.name}/{p.name} → {est} ({r['score']})")
        for cr in r["criteria"]:
            if cr["status"] != "PASS":
                print(f"     {cr['status']:<13} {cr['label']}: {cr['message']}")
        print(f"     YOLOS: {yolos}")
        print(f"     FashionCLIP torso formal_prob={ft.get('formal_prob')}  top='{ft.get('top_label')}'")
        if ff:
            print("     FashionCLIP rostro " + " ".join(f"{k}={v:.2f}" for k, v in ff.items()))
        filas.append({"archivo": str(p), "esperado": esperado, "estado": est, "resultado": res, "score": r["score"],
                      "fallos": " | ".join(r["rejection_reasons"]), "revision": " | ".join(r["review_reasons"]),
                      "yolos": yolos, "clip_formal_prob": ft.get("formal_prob"), "ms": round(tiempos[-1])})

    n = len(fotos)
    tiempos.sort()
    print("\n" + "=" * 70)
    print(f"Fotos: {n}   Correctas: {cuenta['ok']}   Falsas aprobaciones: {cuenta['falsa_aprobacion']}   "
          f"Falsos rechazos: {cuenta['falso_rechazo']}   A revisión manual: {cuenta['revision']}")
    print(f"Tiempo por foto: mediana {tiempos[n // 2]:.0f} ms, máximo {tiempos[-1]:.0f} ms")
    print("Objetivo: 0 falsas aprobaciones; los falsos rechazos y revisiones se reducen calibrando reglas.")

    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0]))
            w.writeheader()
            w.writerows(filas)
        print(f"Detalle guardado en {a.csv}")


if __name__ == "__main__":
    main()
