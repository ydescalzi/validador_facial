import { useEffect, useState } from "react";
import { api, fecha } from "../api/client";
import type { Auditoria } from "../api/types";

export default function AuditTab() {
  const [filas, setFilas] = useState<Auditoria[] | null>(null);
  useEffect(() => { void api.auditoria().then(setFilas); }, []);
  if (!filas) return <p className="sub">Cargando…</p>;
  return (
    <div className="tabla-scroll">
      <table>
        <thead><tr><th>Fecha</th><th>Actor</th><th>Acción</th><th>Objetivo</th><th>IP</th><th>Detalle</th></tr></thead>
        <tbody>
          {filas.map((a, i) => (
            <tr key={i}>
              <td>{fecha(a.time)}</td><td>{a.actor}</td><td>{a.action}</td><td>{a.target ?? ""}</td>
              <td>{a.ip ?? ""}</td><td><small>{a.details ? JSON.stringify(a.details) : ""}</small></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
