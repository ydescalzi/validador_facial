import { useEffect, useState } from "react";
import { api, fecha } from "../api/client";
import type { Estado, Validacion } from "../api/types";
import { ESTADO_CORTO } from "../api/types";

const FILTROS: (Estado | "")[] = ["", "APPROVED", "REJECTED", "MANUAL_REVIEW"];

export default function ValidationsTab() {
  const [estado, setEstado] = useState<Estado | "">("");
  const [datos, setDatos] = useState<{ total: number; items: Validacion[] } | null>(null);

  useEffect(() => { void api.listar(estado).then(setDatos); }, [estado]);

  return (
    <>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        {FILTROS.map(s => (
          <button key={s} className={`btn peq ${s === estado ? "" : "sec"}`} onClick={() => setEstado(s)}>
            {s ? ESTADO_CORTO[s] : "Todas"}
          </button>
        ))}
      </div>
      {!datos ? <p className="sub">Cargando…</p> : (
        <>
          <p className="sub">{datos.total} validaciones</p>
          <div className="tabla-scroll">
            <table>
              <thead><tr><th>Código</th><th>Estudiante</th><th>Fecha</th><th>Estado</th><th>Puntaje</th><th>Motivos</th><th>Revisó</th></tr></thead>
              <tbody>
                {datos.items.map(v => (
                  <tr key={v.validation_id}>
                    <td>{v.validation_id}</td>
                    <td>{v.student_code ?? "—"}</td>
                    <td>{fecha(v.created_at)}</td>
                    <td><span className={`chip ${v.status}`}>{ESTADO_CORTO[v.status]}</span></td>
                    <td>{v.score}</td>
                    <td>{[...v.rejection_reasons, ...v.review_reasons].join(" · ")}</td>
                    <td>{v.reviewed_by ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
