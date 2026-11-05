import { useEffect, useRef, useState } from "react";

const TIPOS = ["image/jpeg", "image/png", "image/webp"];
const MAX_MB = 15; // el navegador la reduce antes de subirla (modo generar)

interface Props {
  archivo: File | null;
  onArchivo: (f: File) => void;
  onError: (msg: string) => void;
  abrirRef?: React.MutableRefObject<(() => void) | null>;
  deshabilitado?: boolean;
  maxMb?: number;
}

/** Vista previa 5:6 + botones "Tomar foto" (cámara del celular) y "Elegir de la galería". */
export function ZonaCarga({ archivo, onArchivo, onError, abrirRef, deshabilitado, maxMb = MAX_MB }: Props) {
  const galeria = useRef<HTMLInputElement>(null);
  const camara = useRef<HTMLInputElement>(null);
  const [arrastre, setArrastre] = useState(false);
  const [vista, setVista] = useState<string | null>(null);

  useEffect(() => {
    if (!archivo) { setVista(null); return; }
    const url = URL.createObjectURL(archivo);
    setVista(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);

  useEffect(() => {
    if (abrirRef) abrirRef.current = () => galeria.current?.click();
  }, [abrirRef]);

  function elegir(f?: File | null) {
    if (!f) return;
    if (!TIPOS.includes(f.type)) return onError("Formato no permitido. Usa una foto JPG, PNG o WEBP.");
    if (f.size > maxMb * 1024 * 1024) return onError(`La imagen supera los ${maxMb} MB.`);
    onArchivo(f);
  }

  const alCambiar = (e: React.ChangeEvent<HTMLInputElement>) => { elegir(e.target.files?.[0]); e.target.value = ""; };

  return (
    <div className="carga">
      <div
        className={`marco${arrastre ? " arrastre" : ""}${vista ? " con-foto" : ""}`}
        onClick={() => !deshabilitado && galeria.current?.click()}
        onDragEnter={e => { e.preventDefault(); setArrastre(true); }}
        onDragOver={e => { e.preventDefault(); setArrastre(true); }}
        onDragLeave={e => { e.preventDefault(); setArrastre(false); }}
        onDrop={e => { e.preventDefault(); setArrastre(false); if (!deshabilitado) elegir(e.dataTransfer.files[0]); }}
        role="button"
        tabIndex={0}
        aria-label="Elegir fotografía"
        onKeyDown={e => { if (e.key === "Enter" || e.key === " ") galeria.current?.click(); }}
      >
        {vista ? <img src={vista} alt="Vista previa de tu fotografía" /> : (
          <div className="marco-vacio">
            <svg viewBox="0 0 120 144" aria-hidden="true">
              <ellipse cx="60" cy="58" rx="22" ry="28" />
              <path d="M14 144c2-28 20-40 46-40s44 12 46 40z" />
            </svg>
            <span>Tu foto aparecerá aquí</span>
          </div>
        )}
        <div className="marco-guia" aria-hidden="true" />
      </div>

      <div className="carga-botones">
        <button type="button" className="btn" disabled={deshabilitado} onClick={() => camara.current?.click()}>
          📷 Tomar foto
        </button>
        <button type="button" className="btn sec" disabled={deshabilitado} onClick={() => galeria.current?.click()}>
          🖼️ {archivo ? "Elegir otra" : "Elegir de la galería"}
        </button>
      </div>
      <p className="meta centro">JPG, PNG o WEBP · también puedes arrastrar la foto aquí</p>

      <input ref={galeria} type="file" accept={TIPOS.join(",")} className="oculto" onChange={alCambiar} />
      <input ref={camara} type="file" accept="image/*" capture="user" className="oculto" onChange={alCambiar} />
    </div>
  );
}
