import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Estadisticas } from "../api/types";
import { ESTADO_CORTO } from "../api/types";

export default function StatsTab() {
  const [s, setS] = useState<Estadisticas | null>(null);
  useEffect(() => { void api.estadisticas(30).then(setS); }, []);
  if (!s) return <p className="sub">Cargando…</p>;

  const n = (k: keyof Estadisticas["by_status"]) => s.by_status[k] ?? 0;
  const maxMotivo = Math.max(1, ...s.top_rejection_reasons.map(([, c]) => c));

  return (
    <>
      <p className="sub">Últimos {s.period_days} días</p>
      <div className="kpis">
        <div className="kpi"><b>{s.total}</b><small>Validaciones</small></div>
        <div className="kpi"><b style={{ color: "var(--ok)" }}>{n("APPROVED")}</b><small>Aprobadas</small></div>
        <div className="kpi"><b style={{ color: "var(--mal)" }}>{n("REJECTED")}</b><small>Rechazadas</small></div>
        <div className="kpi"><b style={{ color: "var(--rev)" }}>{n("MANUAL_REVIEW")}</b><small>Pendientes de revisión</small></div>
        <div className="kpi"><b>{s.approval_rate == null ? "—" : `${Math.round(s.approval_rate * 100)}%`}</b><small>Tasa de aprobación</small></div>
        <div className="kpi">
          <b>{s.processing_ms ? `${s.processing_ms.median} ms` : "—"}</b>
          <small>Tiempo mediano (p95 {s.processing_ms?.p95 ?? "—"} ms)</small>
        </div>
      </div>

      <div className="rejilla">
        <div>
          <h2>Motivos de rechazo más frecuentes</h2>
          {s.top_rejection_reasons.length === 0 ? <p className="sub">Sin datos</p> :
            s.top_rejection_reasons.map(([m, c]) => (
              <div className="barra-h" key={m}>
                <span className="et">{m}</span>
                <span className="pista"><i style={{ width: `${(100 * c) / maxMotivo}%`, background: "var(--mal)" }} /></span>
                <b>{c}</b>
              </div>
            ))}
        </div>
        <div>
          <h2>Resultado por criterio</h2>
          {Object.entries(s.criteria).map(([k, c]) => {
            const t = c.PASS + c.FAIL + c.REVIEW + c.NOT_EVALUATED || 1;
            return (
              <div className="barra-h" key={k}>
                <span className="et">{c.label}</span>
                <span className="pista">
                  <i style={{ width: `${(100 * c.PASS) / t}%`, background: "var(--ok)" }} />
                  <i style={{ width: `${(100 * c.REVIEW) / t}%`, background: "var(--rev)" }} />
                  <i style={{ width: `${(100 * c.FAIL) / t}%`, background: "var(--mal)" }} />
                </span>
              </div>
            );
          })}
          <p className="meta">Verde: cumple · Ámbar: revisión · Rojo: no cumple</p>
        </div>
      </div>

      <h2 style={{ marginTop: 18 }}>Revisiones humanas (calidad del sistema)</h2>
      <p className="sub">Cuando una persona revisa, se compara con la decisión automática. Úsalo para calibrar las reglas.</p>
      <table>
        <thead><tr><th>Decisión automática</th><th>Decisión final</th><th>Cantidad</th></tr></thead>
        <tbody>
          {s.human_reviews.length === 0 ? <tr><td colSpan={3}>Sin revisiones</td></tr> :
            s.human_reviews.map(h => (
              <tr key={`${h.auto}-${h.final}`}><td>{ESTADO_CORTO[h.auto]}</td><td>{ESTADO_CORTO[h.final]}</td><td>{h.count}</td></tr>
            ))}
        </tbody>
      </table>
    </>
  );
}
