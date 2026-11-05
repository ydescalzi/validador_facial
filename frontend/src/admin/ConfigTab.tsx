import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Reglas, ValorRegla } from "../api/types";

const GRUPOS: Record<string, string> = {
  decision: "Decisión", carnet: "Formato de carné", resolution: "Resolución", face: "Rostro y encuadre", orientation: "Orientación", eyes: "Ojos",
  quality: "Calidad de imagen", background: "Fondo", clothing: "Vestimenta", accessories: "Accesorios",
  weights: "Pesos del puntaje",
};

const ETIQUETAS: Record<string, string> = {
  enabled: "Criterio activo", min_width: "Ancho mínimo (px)", min_height: "Alto mínimo (px)",
  require_portrait: "Exigir foto vertical", min_confidence: "Confianza mínima del detector",
  secondary_face_ratio: "Tamaño para contar otra persona", size_min: "Tamaño mínimo del rostro",
  size_max: "Tamaño máximo del rostro", center_tolerance: "Tolerancia de centrado",
  top_margin_min: "Margen superior mínimo", shoulders_space_min: "Espacio mínimo para hombros",
  max_roll_deg: "Inclinación lateral máx. (°)", max_yaw_deg: "Giro lateral máx. (°)",
  max_pitch_deg: "Inclinación vertical máx. (°)", yunet_max_roll_deg: "Inclinación máx. YuNet (°)",
  yunet_max_yaw_ratio: "Giro máx. YuNet (proporción)", max_blink_score: "Máx. ojos cerrados (0-1)",
  sharpness_min: "Nitidez mínima", brightness_min: "Brillo mínimo (0-255)", brightness_max: "Brillo máximo (0-255)",
  contrast_min: "Contraste mínimo", saturated_max_pct: "Máx. píxeles saturados (0-1)",
  uniformity_min: "Uniformidad mínima (0-1)", yolos_min_score: "Confianza mínima YOLOS",
  yolos_strong_score: "Confianza YOLOS 'muy segura'", formal_items: "Prendas formales (YOLOS)",
  informal_items: "Prendas informales (YOLOS)", neutral_items: "Prendas neutras (YOLOS)",
  clip_formal_min: "FashionCLIP: formal si ≥", clip_informal_max: "FashionCLIP: informal si ≤",
  clip_strong_formal: "FashionCLIP: formal muy seguro ≥", clip_strong_informal: "FashionCLIP: informal muy seguro ≤",
  sunglasses: "Lentes de sol", hat: "Gorra / sombrero", hood: "Capucha", headphones: "Audífonos",
  face_mask: "Mascarilla", head_covering: "Prenda en la cabeza", eyeglasses: "Lentes con medida",
  clip_min_prob: "Probabilidad mínima FashionCLIP",
  mode: "Modo", width: "Ancho exacto (px)", height: "Alto exacto (px)", max_kb: "Peso máximo (KB)",
  min_kb: "Peso mínimo (KB, 0 = sin mínimo)", dpi: "Resolución (ppp)", only_jpg: "Solo JPG",
  face_height_ratio: "Alto del rostro en la foto (0-1)", top_space_ratio: "Espacio sobre la frente (0-1)",
  require_white: "Exigir fondo blanco", max_saturation: "Máx. saturación del fondo (0-255)",
  carnet_format: "Formato de carné",
  uncertain_as: "Si la IA no está segura",
};

const POLITICAS = [["reject", "Rechazar"], ["manual_review", "Revisión manual"], ["allow", "Permitir"]] as const;
const DUDA = [["reject", "Rechazar y pedir otra foto"], ["manual_review", "Enviar a revisión manual"]] as const;
const MODOS = [["generate", "Generar automáticamente el archivo de carné"], ["validate", "Exigir que el archivo ya cumpla las medidas"]] as const;

function Campo({ nombre, valor, onCambio }: { nombre: string; valor: ValorRegla; onCambio: (v: ValorRegla) => void }) {
  const et = ETIQUETAS[nombre] ?? nombre;
  if (typeof valor === "boolean") {
    return <label><input type="checkbox" checked={valor} onChange={e => onCambio(e.target.checked)} /> {et}</label>;
  }
  if (typeof valor === "string") {
    return (
      <label>{et}
        <select value={valor} onChange={e => onCambio(e.target.value)}>
          {(nombre === "mode" ? MODOS : nombre === "uncertain_as" ? DUDA : POLITICAS).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
      </label>
    );
  }
  if (Array.isArray(valor)) {
    return (
      <label>{et} (separadas por ;)
        <input type="text" value={valor.join("; ")}
               onChange={e => onCambio(e.target.value.split(";").map(x => x.trim()).filter(Boolean))} />
      </label>
    );
  }
  return (
    <label>{et}
      <input type="number" step="any" value={Number.isNaN(valor) ? "" : valor}
             onChange={e => onCambio(e.target.valueAsNumber)} />
    </label>
  );
}

export default function ConfigTab() {
  const [version, setVersion] = useState(0);
  const [reglas, setReglas] = useState<Reglas | null>(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const cargar = () => api.reglas().then(d => { setVersion(d.version); setReglas(d.rules); });
  useEffect(() => { void cargar(); }, []);

  function cambiar(grupo: string, clave: string, valor: ValorRegla) {
    setReglas(r => r && { ...r, [grupo]: { ...r[grupo], [clave]: valor } });
    setMsg("");
  }

  async function guardar() {
    if (!reglas) return;
    setError(""); setMsg("");
    try {
      const d = await api.guardarReglas(reglas);
      setVersion(d.version); setReglas(d.rules); setMsg(`Guardado. Versión ${d.version}.`);
    } catch (e) { setError(e instanceof Error ? e.message : "Error"); }
  }

  async function restablecer() {
    await api.restablecerReglas();
    await cargar();
    setMsg("Valores por defecto restablecidos.");
  }

  if (!reglas) return <p className="sub">Cargando…</p>;
  return (
    <>
      <p className="sub">Versión activa de reglas: {version}. Los cambios se aplican a las siguientes validaciones y quedan auditados.</p>
      {Object.entries(reglas).map(([g, obj]) => (
        <div className="grupo" key={g}>
          <h3>{GRUPOS[g] ?? g}</h3>
          <div className="campos">
            {Object.entries(obj).map(([k, v]) => <Campo key={k} nombre={k} valor={v} onCambio={x => cambiar(g, k, x)} />)}
          </div>
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button className="btn" onClick={guardar}>Guardar cambios</button>
        <button className="btn sec" onClick={restablecer}>Restablecer valores por defecto</button>
        {msg && <span className="meta">{msg}</span>}
      </div>
      {error && <div className="error">{error}</div>}
    </>
  );
}
