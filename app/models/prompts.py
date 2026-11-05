"""
Frases que FashionCLIP compara con la foto (zero-shot).

IMPORTANTE: si cambias estas frases, vuelve a ejecutar
    python scripts/exportar_onnx.py
porque sus embeddings se precalculan durante la exportación.

Reglas: misma estructura en buenas y malas, neutras en género, sin negaciones.
"""

TORSO_FORMAL = [
    "a person wearing a suit jacket over a dress shirt",
    "a person wearing a blazer over a collared shirt",
    "a person wearing a buttoned collared dress shirt",
    "a person wearing a formal blouse with a collar",
    "a person wearing a shirt and tie",
]

TORSO_INFORMAL = [
    "a person wearing a crew neck t-shirt",
    "a person wearing a colored cotton t-shirt",
    "a person wearing a polo shirt",
    "a person wearing a hoodie or sweatshirt",
    "a person wearing a tank top",
    "a person wearing a sports jersey or tracksuit",
]

# clave → frase (el orden se conserva)
FACE = {
    "bare": "a close-up photo of a face with bare eyes and uncovered hair",
    "eyeglasses": "a close-up photo of a face wearing clear prescription eyeglasses",
    "sunglasses": "a close-up photo of a face wearing dark sunglasses",
    "hat": "a close-up photo of a face wearing a baseball cap or hat",
    "headphones": "a close-up photo of a face wearing headphones",
    "face_mask": "a close-up photo of a face wearing a medical face mask",
}
