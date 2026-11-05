import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { ReglasCarnet, Validacion } from "../api/types";
import { CONFIG } from "../config";
import { FichaCarnet } from "../components/FichaCarnet";
import { PasosAnalisis } from "../components/PasosAnalisis";
import { Resultado } from "../components/Resultado";
import { ZonaCarga } from "../components/ZonaCarga";
import { leerParametros, notificarResultado, urlRetorno } from "../utils/enlace";
import { reducirFoto } from "../utils/imagen";

const CODIGO = /^[A-Za-z0-9_.-]{1,50}$/;
type Paso = "subir" | "analizando" | "resultado";

const SI = ["Fondo blanco y liso", "Saco, blazer, camisa o blusa formal", "De frente, mirando a la cámara", "De los hombros hacia arriba"];
const NO = ["Polos, polerones o ropa deportiva", "Lentes, gorras o capuchas", "Selfies, filtros o fotos de pantalla", "Otras personas en la foto"];

export default function StudentPage() {
  const enlace = useMemo(leerParametros, []);
  const [paso, setPaso] = useState<Paso>("subir");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [codigo, setCodigo] = useState(enlace.codigo);
  const [error, setError] = useState("");
  const [resultado, setResultado] = useState<Validacion | null>(null);
  const [carnet, setCarnet] = useState<ReglasCarnet | null>(null);
  const [disponible, setDisponible] = useState(true);
  const abrir = useRef<(() => void) | null>(null);
  const arriba = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.reglas()
      .then(d => {
        const c = d.rules.carnet as unknown as ReglasCarnet | undefined;
        if (c?.enabled) setCarnet(c);
      })
      .catch(() => setDisponible(false));
  }, []);

  async function validar() {
    if (!archivo) return;
    const cod = codigo.trim();
    if (cod && !CODIGO.test(cod)) { setError("Código de estudiante inválido."); return; }
    setError(""); setPaso("analizando");
    arriba.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    try {
      // En modo "generar" se reduce en el navegador (subida rápida desde el celular);
      // en modo "validar" el archivo se envía intacto para medir sus píxeles, peso y ppp.
      const foto = carnet?.mode === "validate" ? archivo : await reducirFoto(archivo, CONFIG.MAX_LADO_SUBIDA);
      const v = await api.validar(foto, cod || undefined);
      setResultado(v);
      setPaso("resultado");
      notificarResultado(v, enlace.retorno);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo validar la fotografía.");
      setPaso("subir");
    }
  }

  function reintentar() {
    setResultado(null); setArchivo(null); setError(""); setPaso("subir");
    arriba.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    setTimeout(() => abrir.current?.(), 150);
  }

  const continuar = enlace.retorno && resultado?.status === "APPROVED"
    ? () => { window.location.href = urlRetorno(resultado, enlace.retorno!); }
    : undefined;

  const pasoN = paso === "subir" ? (archivo ? 2 : 1) : 3;

  return (
    <>
      <header className="barra">
        <div className="marca"><span className="logo">{CONFIG.INSTITUCION.charAt(0)}</span>{CONFIG.INSTITUCION}</div>
        <small className="barra-sub">Foto para carné</small>
      </header>

      <main className="estudiante" ref={arriba}>
        <section className="tarjeta">
          <h1>{enlace.nombre ? `Hola, ${enlace.nombre}` : "Sube tu foto para el carné"}</h1>
          <p className="sub">Revisamos tu foto al instante. Si cumple los requisitos, queda aceptada.</p>

          <ol className="pasos" aria-label="Progreso">
            {["Requisitos", "Tu foto", "Resultado"].map((t, i) => (
              <li key={t} className={i + 1 < pasoN ? "hecho" : i + 1 === pasoN ? "actual" : ""}>
                <span>{i + 1 < pasoN ? "✓" : i + 1}</span>{t}
              </li>
            ))}
          </ol>

          {!disponible && (
            <div className="caja motivos" role="alert">
              <h4>Servicio no disponible</h4>
              <p style={{ margin: 0 }}>No pudimos conectar con el validador. Inténtalo en unos minutos.</p>
            </div>
          )}

          {paso === "resultado" && resultado ? (
            <Resultado v={resultado} onReintentar={reintentar} onContinuar={continuar} />
          ) : (
            <div className="rejilla">
              <div className="col-requisitos">
                {carnet && <FichaCarnet r={carnet} />}
                <div className="si-no">
                  <div className="si">
                    <h3>Sí</h3>
                    <ul>{SI.map(x => <li key={x}>{x}</li>)}</ul>
                  </div>
                  <div className="no">
                    <h3>No</h3>
                    <ul>{NO.map(x => <li key={x}>{x}</li>)}</ul>
                  </div>
                </div>
              </div>

              <div className="col-subida">
                <ZonaCarga archivo={archivo} abrirRef={abrir} deshabilitado={paso === "analizando"}
                           maxMb={carnet?.mode === "validate" ? 5 : 15}
                           onArchivo={f => { setArchivo(f); setError(""); }} onError={setError} />

                {enlace.codigo ? (
                  <p className="codigo-fijo">Código de estudiante: <b>{enlace.codigo}</b></p>
                ) : (
                  <>
                    <label className="campo" htmlFor="codigo">Código de estudiante</label>
                    <input id="codigo" type="text" inputMode="numeric" maxLength={50} autoComplete="off"
                           placeholder="Ej. 2026001234" value={codigo} onChange={e => setCodigo(e.target.value)} />
                  </>
                )}

                <button className="btn bloque grande" disabled={!archivo || paso === "analizando" || !disponible}
                        onClick={validar}>
                  {paso === "analizando" ? "Revisando tu foto…" : "Validar mi foto"}
                </button>
                <PasosAnalisis activo={paso === "analizando"} />
                {error && <div className="error" role="alert">{error}</div>}
              </div>
            </div>
          )}
        </section>
        <p className="pie">Tu foto se usa solo para verificar los requisitos del carné.</p>
      </main>
    </>
  );
}
