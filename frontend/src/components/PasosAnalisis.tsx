import { useEffect, useState } from "react";

const PASOS = [
  "Revisando el archivo y la calidad de imagen",
  "Detectando el rostro y su orientación",
  "Analizando la vestimenta y accesorios",
  "Aplicando los requisitos de la universidad",
];

/** Indicador visual mientras el backend analiza la foto. */
export function PasosAnalisis({ activo }: { activo: boolean }) {
  const [actual, setActual] = useState(0);

  useEffect(() => {
    if (!activo) { setActual(0); return; }
    const t = setInterval(() => setActual(i => Math.min(i + 1, PASOS.length - 1)), 900);
    return () => clearInterval(t);
  }, [activo]);

  if (!activo) return null;
  return (
    <div className="analisis activo" aria-live="polite">
      {PASOS.map((p, i) => (
        <div key={p} className={`paso${i < actual ? " hecho" : i === actual ? " actual" : ""}`}>
          <span className="punto" />{p}
        </div>
      ))}
    </div>
  );
}
