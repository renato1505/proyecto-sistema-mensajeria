import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"


def _load_env_file():
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        value = value.strip().strip('"').strip("'")

        os.environ.setdefault(key, value)


_load_env_file()


DATABASE_URL = os.getenv("DATABASE_URL", "")
SECRET_KEY = os.getenv("SECRET_KEY", "clave_local_solo_desarrollo")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0").strip() == "1"
LOGIN_REQUIRED = os.getenv("LOGIN_REQUIRED", "0").strip() == "1"
APP_ACCESS_PASSWORD = os.getenv("APP_ACCESS_PASSWORD", "")
APP_USERS = os.getenv("APP_USERS", "")
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

CORREO_EMISOR = os.getenv("CORREO_EMISOR", "")
CORREO_CLAVE_APP = os.getenv("CORREO_CLAVE_APP", "")
CORREO_DESTINO_STARKEN = os.getenv("CORREO_DESTINO_STARKEN", "")
CORREO_RESPALDO_MENSAJERIA = os.getenv(
    "CORREO_RESPALDO_MENSAJERIA",
    "mensajeria.alcantara@loreal.com",
)
EMAIL_PROVIDER = (os.getenv("EMAIL_PROVIDER") or "smtp").strip().lower()
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "Portal Operativo")
BREVO_API_URL = os.getenv("BREVO_API_URL", "https://api.brevo.com/v3/smtp/email")
BREVO_SMTP_HOST = os.getenv("BREVO_SMTP_HOST", "smtp-relay.brevo.com")
BREVO_SMTP_PORT = int(os.getenv("BREVO_SMTP_PORT", "587"))
BREVO_SMTP_LOGIN = os.getenv("BREVO_SMTP_LOGIN", "")
BREVO_SMTP_PASSWORD = os.getenv("BREVO_SMTP_PASSWORD", "")

OF_IMAP_HOST = os.getenv("OF_IMAP_HOST", "imap.gmail.com")
OF_IMAP_PORT = int(os.getenv("OF_IMAP_PORT", "993"))
OF_CORREO_FILTRO_REMITENTE = os.getenv("OF_CORREO_FILTRO_REMITENTE", "")
OF_CORREO_FILTRO_TEXTO = os.getenv("OF_CORREO_FILTRO_TEXTO", "")

CLAVE_ELIMINACION_HISTORICO = os.getenv("CLAVE_ELIMINACION_HISTORICO", "")

RESPALDOS_LOTES_DIR = os.getenv(
    "RESPALDOS_LOTES_DIR",
    str(BASE_DIR / "respaldos_lotes"),
)

LOGS_DIR = os.getenv("LOGS_DIR", str(BASE_DIR / "logs"))
