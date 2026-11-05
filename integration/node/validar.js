// Node.js 18+ (fetch y FormData nativos). Ejemplo con Express + multer.
//   npm i express multer
const express = require("express");
const multer = require("multer");

const VALIDATOR_URL = process.env.PHOTO_VALIDATOR_URL || "http://127.0.0.1:8080";
const VALIDATOR_KEY = process.env.PHOTO_VALIDATOR_KEY;

async function validarFoto(buffer, mimetype, codigoEstudiante) {
  const fd = new FormData();
  fd.append("photo", new Blob([buffer], { type: mimetype }), "foto.jpg");
  fd.append("student_code", codigoEstudiante);
  const r = await fetch(`${VALIDATOR_URL}/api/v1/photos/validate`, {
    method: "POST", headers: { "X-API-Key": VALIDATOR_KEY }, body: fd,
  });
  const d = await r.json();
  if (r.status === 400) return { status: "REJECTED", rejection_reasons: [d.detail], recommendations: [] };
  if (!r.ok) throw new Error(`Validador respondió ${r.status}`);
  return d;
}

const app = express();
const upload = multer({ limits: { fileSize: 5 * 1024 * 1024 } });

app.post("/carnet/foto", upload.single("foto"), async (req, res) => {
  try {
    const r = await validarFoto(req.file.buffer, req.file.mimetype, req.body.codigo);
    // Guarda r.validation_id y r.status en tu base de datos aquí
    res.json({ estado: r.status, mensaje: r.message, motivos: r.rejection_reasons, recomendaciones: r.recommendations });
  } catch (e) {
    res.status(502).json({ error: "No se pudo validar la fotografía" });
  }
});

app.listen(3000, () => console.log("Plataforma en http://localhost:3000"));
module.exports = { validarFoto };
