/**
 * Reduce la foto en el navegador antes de subirla (fotos de celular de 4–12 MB → ~0,5 MB).
 * Solo se usa en modo "generate": en modo "validate" el archivo debe llegar intacto.
 * Respeta la orientación EXIF y no aplica filtros.
 */
export async function reducirFoto(archivo: File, maxLado: number): Promise<Blob> {
  if (!("createImageBitmap" in window)) return archivo;
  let bmp: ImageBitmap;
  try {
    bmp = await createImageBitmap(archivo, { imageOrientation: "from-image" });
  } catch {
    return archivo;
  }
  const escala = Math.min(1, maxLado / Math.max(bmp.width, bmp.height));
  if (escala === 1 && archivo.size < 2 * 1024 * 1024 && archivo.type === "image/jpeg") {
    bmp.close();
    return archivo;
  }
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bmp.width * escala);
  canvas.height = Math.round(bmp.height * escala);
  const ctx = canvas.getContext("2d");
  if (!ctx) { bmp.close(); return archivo; }
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height);
  bmp.close();
  const blob = await new Promise<Blob | null>(res => canvas.toBlob(res, "image/jpeg", 0.92));
  return blob ?? archivo;
}
