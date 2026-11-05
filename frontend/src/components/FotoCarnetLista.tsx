import type { Validacion } from "../api/types";

/** Tarjeta con la foto de carné generada y el botón de descarga. */
export function FotoCarnetLista({ v }: { v: Validacion }) {
  if (!v.carnet_photo || !v.carnet) return null;
  const c = v.carnet;
  const nombre = `carnet_${v.student_code || v.validation_id}.jpg`;
  return (
    <div className="carnet-listo">
      <div className="carnet-tarjeta">
        <div className="carnet-banda">CARNÉ UNIVERSITARIO</div>
        <img src={v.carnet_photo} width={c.width} height={c.height} alt="Tu foto para el carné" />
      </div>
      <div className="carnet-info">
        <h3>Tu foto de carné está lista</h3>
        <p className="sub">La recortamos y ajustamos al formato oficial. Descárgala y úsala en tu trámite.</p>
        <div className="chips">
          <span className="chip-dato">{c.width} × {c.height} px</span>
          <span className="chip-dato">{c.format === "JPEG" ? "JPG" : c.format}</span>
          <span className="chip-dato">{c.kb} KB</span>
          <span className="chip-dato">{c.dpi} ppp</span>
        </div>
        <a className="btn ok" href={v.carnet_photo} download={nombre}>⬇ Descargar foto ({nombre})</a>
      </div>
    </div>
  );
}
