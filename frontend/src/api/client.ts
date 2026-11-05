import { CONFIG } from "../config";
import type { Auditoria, Estadisticas, Reglas, Salud, Validacion } from "./types";

const BASE = CONFIG.API_URL.replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const TOKEN_KEY = "pv_jwt";

export const sesion = {
  get: (): string | null => {
    try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set: (t: string) => { try { sessionStorage.setItem(TOKEN_KEY, t); } catch { /* sin almacenamiento */ } },
  clear: () => { try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* sin almacenamiento */ } },
};

async function pedir<T>(url: string, opciones: RequestInit = {}, admin = false): Promise<T> {
  const headers = new Headers(opciones.headers);
  const token = sesion.get();
  if (admin && token) headers.set("Authorization", `Bearer ${token}`);
  let r: Response;
  try {
    r = await fetch(BASE + url, { ...opciones, headers });
  } catch {
    throw new ApiError(0, "No hay conexión con el servidor. Revisa tu internet e inténtalo de nuevo.");
  }
  if (!r.ok) {
    let detalle = r.status === 429 ? "Demasiados intentos. Espera un minuto y vuelve a intentarlo."
      : r.status >= 500 ? "El servicio no está disponible en este momento. Inténtalo en unos minutos."
      : `Error ${r.status}`;
    try { detalle = (await r.json()).detail ?? detalle; } catch { /* respuesta sin JSON */ }
    throw new ApiError(r.status, typeof detalle === "string" ? detalle : JSON.stringify(detalle));
  }
  const tipo = r.headers.get("content-type") ?? "";
  return (tipo.includes("json") ? r.json() : r.blob()) as Promise<T>;
}

const json = (cuerpo: unknown): RequestInit => ({
  body: JSON.stringify(cuerpo),
  headers: { "Content-Type": "application/json" },
});

export const api = {
  // --- estudiante ---
  validar(foto: Blob, codigo?: string): Promise<Validacion> {
    const fd = new FormData();
    fd.append("photo", foto, "foto.jpg");
    if (codigo) fd.append("student_code", codigo);
    return pedir("/api/v1/photos/validate", { method: "POST", body: fd });
  },
  validacion: (id: string, token: string) =>
    pedir<Validacion>(`/api/v1/photos/validation/${encodeURIComponent(id)}?token=${encodeURIComponent(token)}`),
  reglas: () => pedir<{ version: number; rules: Reglas }>("/api/v1/photos/rules"),
  salud: () => pedir<Salud>("/api/v1/health"),

  // --- administración ---
  login: (username: string, password: string) =>
    pedir<{ access_token: string }>("/api/v1/auth/login", { method: "POST", ...json({ username, password }) }),
  listar: (estado = "", limite = 100) =>
    pedir<{ total: number; items: Validacion[] }>(
      `/api/v1/admin/validations?limit=${limite}${estado ? `&status=${estado}` : ""}`, {}, true),
  imagen: (id: string) => pedir<Blob>(`/api/v1/admin/validations/${encodeURIComponent(id)}/image`, {}, true),
  revisar: (id: string, decision: "APPROVED" | "REJECTED", comment: string | null, reasons: string[]) =>
    pedir<Validacion>(`/api/v1/admin/reviews/${encodeURIComponent(id)}`,
      { method: "POST", ...json({ decision, comment, reasons }) }, true),
  estadisticas: (dias = 30) => pedir<Estadisticas>(`/api/v1/admin/stats?days=${dias}`, {}, true),
  guardarReglas: (cambios: Reglas) =>
    pedir<{ version: number; rules: Reglas }>("/api/v1/photos/rules", { method: "PUT", ...json(cambios) }, true),
  restablecerReglas: () => pedir<{ version: number }>("/api/v1/photos/rules/reset", { method: "POST" }, true),
  auditoria: (limite = 200) => pedir<Auditoria[]>(`/api/v1/admin/audit?limit=${limite}`, {}, true),
};

export const fecha = (iso: string) => new Date(iso.endsWith("Z") ? iso : `${iso}Z`).toLocaleString();
