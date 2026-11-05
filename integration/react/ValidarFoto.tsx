// Componente React + TypeScript para incrustar en TU plataforma.
// Envía la foto a TU backend (Laravel/Node), que llama a la API con la API key.
// No pongas la API key en el navegador.
import { useEffect, useState } from "react";

interface Respuesta {
  estado: "APPROVED" | "REJECTED" | "MANUAL_REVIEW";
  mensaje: string;
  motivos: string[];
  recomendaciones: string[];
}

export default function ValidarFoto({ endpoint = "/carnet/foto" }: { endpoint?: string }) {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [vista, setVista] = useState<string | null>(null);
  const [res, setRes] = useState<Respuesta | null>(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    if (!archivo) return;
    const u = URL.createObjectURL(archivo);
    setVista(u);
    return () => URL.revokeObjectURL(u);
  }, [archivo]);

  async function enviar() {
    if (!archivo) return;
    setCargando(true);
    const fd = new FormData();
    fd.append("foto", archivo);
    const r = await fetch(endpoint, { method: "POST", body: fd, credentials: "include" });
    setRes((await r.json()) as Respuesta);
    setCargando(false);
  }

  return (
    <div>
      <input type="file" accept="image/jpeg,image/png,image/webp"
             onChange={e => setArchivo(e.target.files?.[0] ?? null)} />
      {vista && <img src={vista} alt="Vista previa" style={{ maxWidth: 240 }} />}
      <button disabled={!archivo || cargando} onClick={enviar}>{cargando ? "Analizando…" : "Validar fotografía"}</button>
      {res && (
        <div>
          <h3>{res.mensaje}</h3>
          {res.motivos.length > 0 && <ul>{res.motivos.map(m => <li key={m}>{m}</li>)}</ul>}
          {res.recomendaciones.length > 0 && <p>{res.recomendaciones.join(" ")}</p>}
        </div>
      )}
    </div>
  );
}
