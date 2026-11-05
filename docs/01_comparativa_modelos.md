# Fase 1 — Comparativa técnica de modelos preentrenados

Fecha de la investigación: 2026-11-05. Datos tomados de los repositorios y
fichas oficiales (enlaces al final). Lo que **no** figura en la ficha oficial
se indica como "no publicado" o "aprox." — no se inventan métricas.

## A. Vestimenta

| | YOLOS Fashionpedia | FashionCLIP | SegFormer B2 Clothes | SCHP |
|---|---|---|---|---|
| **Id exacto** | `valentinafeve/yolos-fashionpedia` | `patrickjohncyh/fashion-clip` | `mattmdjaga/segformer_b2_clothes` | `PeikeLi/Self-Correction-Human-Parsing` (GitHub) |
| **Tarea** | Detección de objetos (cajas) | Clasificación zero-shot imagen↔texto | Segmentación semántica (píxeles) | Segmentación de partes humanas |
| **Arquitectura** | YOLOS (ViT detector) afinado en Fashionpedia | CLIP ViT-B/32 afinado con >800K productos Farfetch | SegFormer, base `nvidia/mit-b2` | ResNet-101 + A-CE2P |
| **Clases** | 46: *shirt/blouse, top/t-shirt/sweatshirt, sweater, cardigan, jacket, vest, coat, dress, tie, hood, collar, lapel, neckline, glasses, hat, headband/head covering*, pants, etc. | Abiertas (las define el texto) | 18 (ATR): background, hat, hair, sunglasses, upper-clothes, skirt, pants, dress, belt, face, arms, legs, bag, scarf… | LIP 20 / ATR 18 / Pascal 7 |
| **Licencia** | MIT (ficha HF) | MIT | "other" (ficha HF) + dataset ATR | MIT (código); pesos en Google Drive |
| **Tamaño** | aprox. 120 MB (YOLOS-small) | aprox. 600 MB | aprox. 110 MB | aprox. 260 MB |
| **Hardware** | CPU OK (≈0,3–1 s/foto aprox.), GPU opcional | CPU OK | CPU OK | Requiere GPU + compilar `inplace_abn` (CUDA) |
| **Descarga** | `transformers` (`from_pretrained`) | `transformers` | `transformers` | Manual, Google Drive |
| **Métricas oficiales** | No publicadas en la ficha | No publicadas en la ficha | No publicadas en la ficha | mIoU: LIP 59,36 %, ATR 82,29 %, Pascal 71,46 % |
| **FastAPI** | Sí | Sí | Sí | Difícil (Python 3.6 / conda / CUDA) |
| **Limitaciones** | Entrenado con fotos de moda, no de carnet; no distingue lentes de sol de lentes normales | Sesgo hacia fotos de producto con fondo blanco; los datos asocian prendas a géneros; el autor indica que no fue creado para despliegue en producción | No distingue tipos de prenda superior (polo vs. camisa = "upper-clothes"); licencia no estándar | Pesos fuera de HF, dependencias antiguas |

**Seleccionados:** YOLOS Fashionpedia (detecta *cuello, solapa, corbata, saco,
camisa, polo, capucha*) **+** FashionCLIP (juicio global formal/informal sobre
el recorte del torso). Las dos evidencias se combinan en el motor de reglas; si
se contradicen o la confianza es baja, la foto va a **revisión manual**.

**Opcional (desactivado por defecto):** SegFormer B2 Clothes, para separar
persona y fondo, y para detectar lentes de sol y sombrero. Está desactivado por
su licencia "other": revisa sus términos antes de activarlo.

**Descartado:** SCHP. Sus pesos están en Google Drive, necesita compilar CUDA y
usa un entorno de Python 3.6. No es viable para un microservicio en CPU.

## B. Detección facial

| | YuNet (OpenCV Zoo) | MediaPipe Face Landmarker | RetinaFace / SCRFD (InsightFace) |
|---|---|---|---|
| **Id / archivo** | `face_detection_yunet_2023mar.onnx` | `face_landmarker.task` (float16) | `buffalo_l`, `scrfd_*` |
| **Tarea** | Detección de rostros + 5 puntos (ojos, nariz, comisuras) | BlazeFace + 478 puntos 3D + 52 blendshapes + matriz de pose | Detección de rostros + 5 puntos |
| **Licencia** | MIT | Código Apache 2.0; fichas de modelo publicadas por Google | Código MIT, **modelos solo para investigación no comercial** |
| **Tamaño** | 232 KB (verificado) | aprox. 3,6 MB | 3–16 MB |
| **Hardware** | CPU, milisegundos | CPU, milisegundos | CPU/GPU |
| **Precisión oficial** | WIDER Face val: 0,834 / 0,824 / 0,708 AP (easy/medium/hard) | Ver ficha de modelo de Google | Ver repositorio |
| **Descarga** | `media.githubusercontent.com/.../opencv_zoo` | `storage.googleapis.com/mediapipe-models/...` | `pip install insightface` |
| **Uso en Python** | `cv2.FaceDetectorYN` (incluido en OpenCV ≥ 4.8) | `pip install mediapipe` (Tasks API) | `insightface` + `onnxruntime` |

**Seleccionados:**
- **YuNet** como detector principal. Se encarga de contar rostros, centrado, tamaño e inclinación (roll y yaw estimados con los 5 puntos).
- **MediaPipe Face Landmarker** como segunda opinión. Da la pose 3D (yaw, pitch y roll) a partir de la matriz de transformación, y los ojos abiertos con `eyeBlinkLeft/Right`.

**Descartados:** RetinaFace y SCRFD de InsightFace, porque su licencia de modelos no permite uso fuera de la investigación no comercial. Esto aplica a una plataforma universitaria en producción.

## C. Calidad de imagen (OpenCV, sin IA)
Resolución, proporción, nitidez (varianza del Laplaciano), iluminación (media de
luminancia en el rostro), contraste (desviación estándar), sobre/subexposición
(porcentaje de píxeles saturados) y fondo (tono y uniformidad de los bordes, o de
la máscara de fondo si SegFormer está activo).

## Fuentes
- https://huggingface.co/valentinafeve/yolos-fashionpedia
- https://huggingface.co/patrickjohncyh/fashion-clip
- https://huggingface.co/mattmdjaga/segformer_b2_clothes
- https://github.com/PeikeLi/Self-Correction-Human-Parsing
- https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker
- https://github.com/deepinsight/insightface (licencia de modelos)
