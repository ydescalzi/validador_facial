/**
 * ============================================================================
 *  CONFIGURACIÓN DEL FRONTEND — este es el único archivo que debes editar.
 * ============================================================================
 */
export const CONFIG = {
  /** Nombre que se muestra en la cabecera. */
  INSTITUCION: "Universidad",

  /**
   * Dirección del backend (Python).
   *   ""  → usa el mismo dominio. En Vercel, el archivo vercel.json reenvía /api al
   *         backend (recomendado: no necesitas configurar CORS).
   *   "https://mi-backend.ejemplo.com" → llama directo al backend (debes agregar el
   *         dominio de Vercel en CORS_ORIGINS del backend).
   */
  API_URL: "",

  /**
   * Sistemas que pueden enlazar a esta página y recibir el resultado.
   * El otro sistema abre:  https://tu-app.vercel.app/?codigo=2026001&retorno=https://sistema.edu.pe/carnet
   * Solo se redirige (y se envía postMessage) a orígenes de esta lista.
   * Ejemplo: ["https://intranet.miuniversidad.edu.pe"]
   */
  ORIGENES_PERMITIDOS: [] as string[],

  /** Lado mayor (px) al que se reduce la foto en el celular antes de subirla (más rápido). */
  MAX_LADO_SUBIDA: 1600,
};
