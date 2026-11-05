import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Salud } from "../api/types";

const FUNCION: Record<string, string> = {
  yunet: "Detección de rostros, posición y 5 puntos faciales",
  mediapipe: "Pose 3D de la cabeza y ojos abiertos/cerrados",
  yolos: "Detección de prendas: saco, camisa, cuello, solapa, corbata, polo, capucha, gorra",
  fashionclip: "Clasificación formal/informal del torso; lentes de sol, gorra, mascarilla",
  segformer: "Segmentación persona/fondo (opcional)",
};

export default function ModelsTab() {
  const [h, setH] = useState<Salud | null>(null);
  useEffect(() => { void api.salud().then(setH); }, []);
  if (!h) return <p className="sub">Cargando…</p>;

  const activos = Object.values(h.models).filter(m => m.loaded).length;
  return (
    <>
      <p className="sub">
        Estado: <b>{h.status === "ok" ? "Operativo" : "Degradado"}</b> · {activos} {activos === 1 ? "modelo de IA cargado" : "modelos de IA cargados"} · Base de datos: {h.database}
        {h.detail && <><br />{h.detail}</>}
      </p>
      <table>
        <thead><tr><th>Componente</th><th>Modelo</th><th>Función</th><th>Estado</th><th>Detalle</th></tr></thead>
        <tbody>
          {Object.entries(h.models).map(([k, m]) => (
            <tr key={k}>
              <td>{k}</td>
              <td>{m.name}</td>
              <td><small>{FUNCION[k] ?? ""}</small></td>
              <td>
                <span className={`chip ${m.loaded ? "APPROVED" : m.enabled ? "REJECTED" : "MANUAL_REVIEW"}`}>
                  {m.loaded ? "Cargado" : m.enabled ? "Error" : "Desactivado"}
                </span>
              </td>
              <td><small>{m.error ?? (m.load_seconds != null ? `cargó en ${m.load_seconds}s` : "")}</small></td>
            </tr>
          ))}
          <tr>
            <td>opencv</td><td>OpenCV (reglas clásicas)</td>
            <td><small>Resolución, nitidez, iluminación, contraste, fondo</small></td>
            <td><span className="chip APPROVED">Activo</span></td><td />
          </tr>
        </tbody>
      </table>
    </>
  );
}
