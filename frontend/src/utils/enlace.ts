import { CONFIG } from "../config";
import type { Validacion } from "../api/types";

/**
 * Integración con el sistema que enlaza a esta página.
 *   ?codigo=2026001         código del estudiante (se muestra fijo)
 *   ?nombre=Ana%20Pérez      nombre a mostrar (opcional)
 *   ?retorno=https://...     adónde volver cuando la foto sea aceptada
 */
export interface ParametrosEnlace {
  codigo: string;
  nombre: string;
  retorno: URL | null;
}

const CODIGO = /^[A-Za-z0-9_.-]{1,50}$/;

function origenPermitido(u: URL): boolean {
  return CONFIG.ORIGENES_PERMITIDOS.some(o => {
    try { return new URL(o).origin === u.origin; } catch { return false; }
  });
}

export function leerParametros(): ParametrosEnlace {
  const p = new URLSearchParams(window.location.search);
  const codigo = (p.get("codigo") ?? "").trim();
  let retorno: URL | null = null;
  try {
    const r = p.get("retorno");
    if (r) {
      const u = new URL(r);
      if ((u.protocol === "https:" || u.hostname === "localhost") && origenPermitido(u)) retorno = u;
    }
  } catch { /* URL inválida: se ignora */ }
  return {
    codigo: CODIGO.test(codigo) ? codigo : "",
    nombre: (p.get("nombre") ?? "").slice(0, 80),
    retorno,
  };
}

/** Avisa al sistema que abrió esta página (iframe o ventana emergente). */
export function notificarResultado(v: Validacion, retorno: URL | null) {
  const destino = window.parent !== window ? window.parent : window.opener as Window | null;
  if (!destino || !retorno) return;
  destino.postMessage({
    tipo: "validacion-foto-carnet",
    estado: v.status,                  // "APPROVED" | "REJECTED" | "MANUAL_REVIEW"
    validation_id: v.validation_id,
    codigo: v.student_code,
    motivos: v.rejection_reasons,
    foto_carnet: v.status === "APPROVED" ? v.carnet_photo : null,  // data:image/jpeg;base64,…
    comprobante: v.comprobante,        // verificar en GET /api/v1/photos/verify?comprobante=…
  }, retorno.origin);
}

/** URL a la que se vuelve al aceptar la foto. */
export function urlRetorno(v: Validacion, retorno: URL): string {
  const u = new URL(retorno.toString());
  u.searchParams.set("validation_id", v.validation_id);
  u.searchParams.set("estado", v.status);
  if (v.student_code) u.searchParams.set("codigo", v.student_code);
  if (v.comprobante) u.searchParams.set("comprobante", v.comprobante);
  return u.toString();
}
