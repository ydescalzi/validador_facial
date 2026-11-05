// Tipos que reflejan los esquemas de la API Python (app/schemas/validation.py)

export type Estado = "APPROVED" | "REJECTED" | "MANUAL_REVIEW";
export type EstadoCriterio = "PASS" | "FAIL" | "REVIEW" | "NOT_EVALUATED";

export interface Criterio {
  key: string;
  label: string;
  status: EstadoCriterio;
  message: string;
  recommendation: string;
  values: Record<string, unknown>;
}

export interface Validacion {
  success: boolean;
  validation_id: string;
  access_token: string | null;
  student_code: string | null;
  status: Estado;
  message: string;
  score: number;
  results: Record<string, string | boolean | null>;
  criteria: Criterio[];
  rejection_reasons: string[];
  review_reasons: string[];
  recommendations: string[];
  scores: Record<string, unknown>;
  models_used: string[];
  timings_ms: Record<string, number>;
  rules_version: number;
  created_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_comment: string | null;
  has_image?: boolean;
  carnet: InfoCarnet | null;
  /** data:image/jpeg;base64,… — solo cuando la foto fue APROBADA (modo generate) */
  carnet_photo: string | null;
  /** Resultado firmado: el otro sistema lo verifica en /api/v1/photos/verify */
  comprobante: string | null;
}

export interface InfoCarnet {
  mode: "generate" | "validate";
  generated?: boolean;
  width?: number;
  height?: number;
  kb?: number;
  dpi?: number | null;
  format?: string;
}

export interface ReglasCarnet {
  enabled: boolean;
  mode: "generate" | "validate";
  width: number;
  height: number;
  max_kb: number;
  min_kb: number;
  dpi: number;
  only_jpg: boolean;
}

export type ValorRegla = number | boolean | string | string[];
export type Reglas = Record<string, Record<string, ValorRegla>>;

export interface Estadisticas {
  period_days: number;
  total: number;
  by_status: Partial<Record<Estado, number>>;
  approval_rate: number | null;
  top_rejection_reasons: [string, number][];
  criteria: Record<string, { label: string } & Record<EstadoCriterio, number>>;
  human_reviews: { auto: Estado; final: Estado; count: number }[];
  processing_ms: { median: number; p95: number } | null;
}

export interface EstadoModelo {
  name: string;
  loaded: boolean;
  enabled: boolean;
  error?: string;
  load_seconds?: number;
}

export interface Salud {
  status: "ok" | "degraded";
  detail: string | null;
  database: string;
  persist: boolean;
  models: Record<string, EstadoModelo>;
}

export interface Auditoria {
  time: string;
  actor: string;
  action: string;
  target: string | null;
  ip: string | null;
  details: Record<string, unknown> | null;
}

export const TITULO_ESTADO: Record<Estado, string> = {
  APPROVED: "Fotografía aprobada",
  REJECTED: "Fotografía rechazada",
  MANUAL_REVIEW: "En revisión manual",
};

export const ESTADO_CORTO: Record<Estado, string> = {
  APPROVED: "Aprobada",
  REJECTED: "Rechazada",
  MANUAL_REVIEW: "Revisión manual",
};
