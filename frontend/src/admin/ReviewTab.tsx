import { useCallback, useEffect, useState } from "react";
import { api, fecha } from "../api/client";
import type { Validacion } from "../api/types";
import { ListaCriterios } from "../components/Resultado";

function Imagen({ id }: { id: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [falla, setFalla] = useState(false);
  useEffect(() => {
    let u: string | null = null;
    api.imagen(id).then(b => { u = URL.createObjectURL(b); setUrl(u); }).catch(() => setFalla(true));
    return () => { if (u) URL.revokeObjectURL(u); };
  }, [id]);
  if (falla) return <p className="sub">Imagen no disponible</p>;
  return url ? <img src={url} alt={`Foto ${id}`} /> : <div style={{ minHeight: 120 }} />;
}

function Tarjeta({ v, onListo }: { v: Validacion; onListo: () => void }) {
  const [comentario, setComentario] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");

  async function resolver(decision: "APPROVED" | "REJECTED") {
    setEnviando(true); setError("");
    const c = comentario.trim();
    try {
      await api.revisar(v.validation_id, decision, c || null, decision === "REJECTED" && c ? [c] : []);
      onListo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
      setEnviando(false);
    }
  }

  return (
    <div className="revision">
      <div><Imagen id={v.validation_id} /></div>
      <div>
        <h2>{v.validation_id} · estudiante {v.student_code ?? "—"} <span className="chip MANUAL_REVIEW">{v.score}</span></h2>
        <p className="sub">{fecha(v.created_at)} — {v.review_reasons.join(" ")}</p>
        <ListaCriterios criterios={v.criteria} />
        <details style={{ marginTop: 10 }}>
          <summary>Puntuaciones de los modelos</summary>
          <pre>{JSON.stringify(v.scores, null, 2)}</pre>
        </details>
        <label className="campo">Comentario / motivo (visible para el estudiante si se rechaza)</label>
        <textarea rows={2} maxLength={1000} value={comentario} onChange={e => setComentario(e.target.value)} />
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <button className="btn ok" disabled={enviando} onClick={() => resolver("APPROVED")}>Aprobar</button>
          <button className="btn mal" disabled={enviando} onClick={() => resolver("REJECTED")}>Rechazar</button>
        </div>
        {error && <div className="error">{error}</div>}
      </div>
    </div>
  );
}

export default function ReviewTab({ onTotal }: { onTotal: (n: number) => void }) {
  const [items, setItems] = useState<Validacion[] | null>(null);
  const cargar = useCallback(async () => {
    const d = await api.listar("MANUAL_REVIEW", 50);
    setItems(d.items);
    onTotal(d.total);
  }, [onTotal]);
  useEffect(() => { void cargar(); }, [cargar]);

  if (!items) return <p className="sub">Cargando…</p>;
  if (!items.length) return <p className="sub">No hay fotografías pendientes de revisión. 🎉</p>;
  return <>{items.map(v => <Tarjeta key={v.validation_id} v={v} onListo={cargar} />)}</>;
}
