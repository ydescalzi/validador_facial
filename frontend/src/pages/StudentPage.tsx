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

type Paso = "subir" | "analizando" | "resultado";

const SI = ["Fondo blanco y liso", "Saco, blazer, camisa o blusa formal", "De frente, mirando a la cámara", "De los hombros hacia arriba"];
const NO = ["Polos, polerones o ropa deportiva", "Lentes, gorras o capuchas", "Selfies, filtros o fotos de pantalla", "Otras personas en la foto"];

export default function StudentPage() {
  const enlace = useMemo(leerParametros, []);
  const [paso, setPaso] = useState<Paso>("subir");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [resultado, setResultado] = useState<Validacion | null>(null);
  const [carnet, setCarnet] = useState<ReglasCarnet | null>(null);
  const [disponible, setDisponible] = useState(true);
  const [abierto, setAbierto] = useState(true);
  const abrir = useRef<(() => void) | null>(null);
  const arriba = useRef<HTMLDivElement>(null);
  const dialogo = useRef<HTMLDivElement>(null);
  const botonAbrir = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    api.reglas()
      .then(d => {
        const c = d.rules.carnet as unknown as ReglasCarnet | undefined;
        if (c?.enabled) setCarnet(c);
      })
      .catch(() => setDisponible(false));
  }, []);

  useEffect(() => {
    if (!abierto) return;
    const anterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialogo.current?.focus();
    const cerrarConEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAbierto(false);
    };
    window.addEventListener("keydown", cerrarConEscape);
    return () => {
      document.body.style.overflow = anterior;
      window.removeEventListener("keydown", cerrarConEscape);
    };
  }, [abierto]);

  useEffect(() => {
    if (!abierto) botonAbrir.current?.focus();
  }, [abierto]);

  async function validar() {
    if (!archivo) return;
    setError(""); setPaso("analizando");
    arriba.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    try {
      // En modo "generar" se reduce en el navegador (subida rápida desde el celular);
      // en modo "validar" el archivo se envía intacto para medir sus píxeles, peso y ppp.
      const foto = carnet?.mode === "validate" ? archivo : await reducirFoto(archivo, CONFIG.MAX_LADO_SUBIDA);
      const v = await api.validar(foto, enlace.codigo || undefined);
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
      {abierto ? (
        <div className="modal-fondo">
          <div className="modal-dialogo" role="dialog" aria-modal="true" aria-labelledby="titulo-modal"
               tabIndex={-1} ref={dialogo}>
            <header className="barra">
              <div className="marca">
                <img src="/logo-usmp.png" alt="Universidad de San Martín de Porres" />
                <span>Portal de verificación</span>
              </div>
              <div className="modal-barra-acciones">
                <small className="barra-sub">Estudiantes · Docentes</small>
                <button className="modal-cerrar" type="button" aria-label="Cerrar verificador"
                        onClick={() => setAbierto(false)}>×</button>
              </div>
            </header>

            <main className="estudiante" ref={arriba}>
              <section className="tarjeta">
                <div className="bienvenida">
                  <span className="bienvenida-etiqueta">CARNÉ UNIVERSITARIO · ESTUDIANTES Y DOCENTES</span>
                  <h1 id="titulo-modal">{enlace.nombre ? `Hola, ${enlace.nombre}` : "Sube tu foto para el carné"}</h1>
                  <p className="sub">Te acompañamos para que tu fotografía cumpla los requisitos. Súbela y recibe el resultado al instante.</p>
                </div>

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
                  <Resultado v={resultado} archivo={archivo} onReintentar={reintentar} onContinuar={continuar} />
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
                      <div className="subida-encabezado">
                        <span className="subida-icono" aria-hidden="true">01</span>
                        <div>
                          <h2>Tu fotografía</h2>
                          <p>Elige una imagen clara, de frente y con buena iluminación.</p>
                        </div>
                      </div>
                      <ZonaCarga archivo={archivo} abrirRef={abrir} deshabilitado={paso === "analizando"}
                                 maxMb={carnet?.mode === "validate" ? 5 : 15}
                                 onArchivo={f => { setArchivo(f); setError(""); }} onError={setError} />

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
              <p className="pie">Si tu foto necesita algún ajuste, podrás corregirla y volver a intentarlo.</p>
            </main>
          </div>
        </div>
      ) : (
        <main className="verificador-cerrado">
          <button ref={botonAbrir} className="btn grande" type="button" onClick={() => setAbierto(true)}>
            Abrir verificador de fotos
          </button>
        </main>
      )}
    </>
  );
}
