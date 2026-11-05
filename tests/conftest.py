import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="pv_test_")
os.environ.update({
    "PERSIST": "1",
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
    "STORAGE_DIR": f"{_tmp}/storage",
    "API_KEYS": "clave-test",
    "JWT_SECRET": "secreto-test",
    "ADMIN_USERNAME": "admin",
    "PUBLIC_UI": "1",
    "RATE_LIMIT_PER_MINUTE": "1000",
    # Los tests no descargan modelos de Hugging Face (rápidos y sin internet).
    "ENABLE_YOLOS": "0", "ENABLE_FASHIONCLIP": "0", "ENABLE_MEDIAPIPE": "0", "ENABLE_SEGFORMER": "0",
    "HF_HUB_OFFLINE": "1",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password  # noqa: E402

os.environ["ADMIN_PASSWORD_HASH"] = hash_password("clave-admin")
from app.core.config import settings  # noqa: E402

settings.admin_password_hash = os.environ["ADMIN_PASSWORD_HASH"]
