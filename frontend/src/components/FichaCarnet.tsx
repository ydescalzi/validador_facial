import type { ReglasCarnet } from "../api/types";

/** Ficha técnica del formato de carné, con una silueta a escala 5:6. */
export function FichaCarnet({ r }: { r: ReglasCarnet }) {
  const items = [
    { k: "Medidas", v: `${r.width} × ${r.height} px` },
    { k: "Formato", v: r.only_jpg ? "JPG" : "JPG / PNG" },
    { k: "Peso", v: r.min_kb ? `${r.min_kb}–${r.max_kb} KB` : `máx. ${r.max_kb} KB` },
    { k: "Resolución", v: `${r.dpi} ppp` },
    { k: "Fondo", v: "Blanco liso" },
    { k: "Encuadre", v: "Hombros hacia arriba" },
  ];
  return (
    <div className="ficha">
      <div className="ficha-silueta" style={{ aspectRatio: `${r.width} / ${r.height}` }} aria-hidden="true">
        <svg viewBox="0 0 120 144">
          <rect width="120" height="144" fill="#fff" />
          <ellipse cx="60" cy="58" rx="22" ry="28" fill="var(--borde)" />
          <path d="M14 144c2-28 20-40 46-40s44 12 46 40z" fill="var(--borde)" />
          <line x1="0" y1="14" x2="120" y2="14" className="guia-linea" />
          <line x1="60" y1="0" x2="60" y2="144" className="guia-linea" />
        </svg>
        <span className="ficha-cota ancho">{r.width}px</span>
        <span className="ficha-cota alto">{r.height}px</span>
      </div>
      <div>
        <h3 className="ficha-titulo">Formato de foto para carné</h3>
        <dl className="ficha-datos">
          {items.map(i => (
            <div key={i.k}><dt>{i.k}</dt><dd>{i.v}</dd></div>
          ))}
        </dl>
        <p className="meta" style={{ marginTop: 8 }}>
          {r.mode === "generate"
            ? "Sube una foto nítida; si cumple los requisitos, generamos tu archivo con estas medidas exactas."
            : "Tu archivo ya debe tener estas medidas exactas."}
        </p>
      </div>
    </div>
  );
}
