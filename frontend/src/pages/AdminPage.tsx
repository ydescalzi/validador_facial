import { useCallback, useState } from "react";
import { api, sesion } from "../api/client";
import AuditTab from "../admin/AuditTab";
import ConfigTab from "../admin/ConfigTab";
import ModelsTab from "../admin/ModelsTab";
import ReviewTab from "../admin/ReviewTab";
import StatsTab from "../admin/StatsTab";
import ValidationsTab from "../admin/ValidationsTab";

const PESTANAS = [
  ["revision", "Revisión manual"], ["validaciones", "Validaciones"], ["estadisticas", "Estadísticas"],
  ["config", "Configuración"], ["auditoria", "Auditoría"], ["modelos", "Estado de modelos"],
] as const;
type Pestana = (typeof PESTANAS)[number][0];

function Login({ onEntrar }: { onEntrar: () => void }) {
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState("");

  async function entrar() {
    setError("");
    try {
      const r = await api.login(usuario, clave);
      sesion.set(r.access_token);
      onEntrar();
    } catch (e) { setError(e instanceof Error ? e.message : "Error"); }
  }

  return (
    <section className="tarjeta" style={{ maxWidth: 420, margin: "40px auto" }}>
      <h1>Iniciar sesión</h1>
      <p className="sub">Acceso para personal autorizado.</p>
      <label className="campo" htmlFor="usuario">Usuario</label>
      <input id="usuario" type="text" autoComplete="username" value={usuario} onChange={e => setUsuario(e.target.value)} />
      <label className="campo" htmlFor="clave">Contraseña</label>
      <input id="clave" type="password" autoComplete="current-password" value={clave}
             onChange={e => setClave(e.target.value)} onKeyDown={e => { if (e.key === "Enter") void entrar(); }} />
      <button className="btn bloque" onClick={entrar}>Entrar</button>
      {error && <div className="error">{error}</div>}
    </section>
  );
}

export default function AdminPage() {
  const [logueado, setLogueado] = useState(Boolean(sesion.get()));
  const [pestana, setPestana] = useState<Pestana>("revision");
  const [pendientes, setPendientes] = useState(0);
  const onTotal = useCallback((n: number) => setPendientes(n), []);

  function salir() { sesion.clear(); setLogueado(false); }

  return (
    <>
      <header className="barra">
        <div className="marca"><span className="logo">U</span> Validación de fotografías <small>· Panel administrativo</small></div>
        {logueado && <button className="btn sec peq" onClick={salir}>Cerrar sesión</button>}
      </header>
      <main>
        {!logueado ? <Login onEntrar={() => setLogueado(true)} /> : (
          <section className="tarjeta">
            <nav className="tabs">
              {PESTANAS.map(([k, t]) => (
                <button key={k} className={k === pestana ? "activo" : ""} onClick={() => setPestana(k)}>
                  {t}{k === "revision" && <span className="n">{pendientes}</span>}
                </button>
              ))}
            </nav>
            <ErrorDeSesion onExpirada={salir}>
              {pestana === "revision" && <ReviewTab onTotal={onTotal} />}
              {pestana === "validaciones" && <ValidationsTab />}
              {pestana === "estadisticas" && <StatsTab />}
              {pestana === "config" && <ConfigTab />}
              {pestana === "auditoria" && <AuditTab />}
              {pestana === "modelos" && <ModelsTab />}
            </ErrorDeSesion>
          </section>
        )}
      </main>
    </>
  );
}

/** Si una llamada devuelve 401 (sesión expirada), vuelve al login. */
function ErrorDeSesion({ children, onExpirada }: { children: React.ReactNode; onExpirada: () => void }) {
  if (typeof window !== "undefined") {
    window.onunhandledrejection = ev => {
      const r = ev.reason as { status?: number } | undefined;
      if (r?.status === 401) { ev.preventDefault(); onExpirada(); }
    };
  }
  return <>{children}</>;
}
