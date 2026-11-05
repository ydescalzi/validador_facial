import type { Criterio, Estado, Validacion } from "../api/types";
import { FotoCarnetLista } from "./FotoCarnetLista";

const ICONO: Record<Criterio["status"], string> = { PASS: "✓", FAIL: "✕", REVIEW: "!", NOT_EVALUATED: "–" };
const COLOR: Record<Estado, string> = { APPROVED: "var(--ok)", REJECTED: "var(--mal)", MANUAL_REVIEW: "var(--rev)" };

export function ScoreRing({ score, estado }: { score: number; estado: Estado }) {
  return (
    <div className="anillo" style={{ "--p": score, "--c": COLOR[estado] } as React.CSSProperties}>
      <span>{score}</span>
    </div>
  );
}

export function ListaCriterios({ criterios }: { criterios: Criterio[] }) {
  return (
    <div className="criterios">
      {criterios.map(c => (
        <div key={c.key} className={`crit ${c.status}`}>
          <span className="ic">{ICONO[c.status]}</span>
          <div>
            <b>{c.label}</b>
            <small>{c.message || (c.status === "NOT_EVALUATED" ? "No evaluado" : "")}</small>
          </div>
        </div>
      ))}
    </div>
  );
}

interface Props {
  v: Validacion;
  onReintentar: () => void;
  onContinuar?: () => void;
}

/** Resultado para el estudiante: claro y con una sola acción principal. */
export function Resultado({ v, onReintentar, onContinuar }: Props) {
  const aprobada = v.status === "APPROVED";
  const revision = v.status === "MANUAL_REVIEW";

  return (
    <div className="resultado activo" aria-live="polite">
      <div className={`aviso ${v.status}`}>
        <div className="aviso-icono" aria-hidden="true">{aprobada ? "✓" : revision ? "⏳" : "✕"}</div>
        <h2>{aprobada ? "¡Tu foto fue aceptada!" : revision ? "Tu foto está en revisión" : "Tu foto fue rechazada"}</h2>
        <p>{v.message}</p>
      </div>

      {aprobada && <FotoCarnetLista v={v} />}

      {!aprobada && v.rejection_reasons.length > 0 && (
        <div className="caja motivos">
          <h4>¿Por qué fue rechazada?</h4>
          <ul>{v.rejection_reasons.map(x => <li key={x}>{x}</li>)}</ul>
        </div>
      )}
      {!aprobada && v.recommendations.length > 0 && (
        <div className="caja recom">
          <h4>Cómo corregirlo</h4>
          <ul>{v.recommendations.map(x => <li key={x}>{x}</li>)}</ul>
        </div>
      )}

      <div className="acciones">
        {aprobada && onContinuar && <button className="btn bloque" onClick={onContinuar}>Continuar con mi trámite →</button>}
        {!aprobada && <button className="btn bloque grande" onClick={onReintentar}>📷 Volver a subir mi foto</button>}
        {aprobada && <button className="btn sec bloque" onClick={onReintentar}>Subir otra foto</button>}
      </div>

      <details className="detalle">
        <summary>Ver el detalle de la revisión</summary>
        <ListaCriterios criterios={v.criteria} />
        <p className="meta">Código de validación: <b>{v.validation_id}</b></p>
      </details>
    </div>
  );
}
