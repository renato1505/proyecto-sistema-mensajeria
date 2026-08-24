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


SECRET_KEY_DESARROLLO = "clave_local_solo_desarrollo"


def _entorno_productivo():
    entorno = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "").strip().lower()
    en_render = os.getenv("RENDER", "").strip().lower() == "true"
    return en_render or entorno in {"production", "produccion", "prod"}


def validar_configuracion_seguridad(es_produccion, secret_key, login_required):
    if not es_produccion:
        return
    if not secret_key or secret_key == SECRET_KEY_DESARROLLO:
        raise RuntimeError("SECRET_KEY debe configurarse con un valor seguro en produccion.")
    if not login_required:
        raise RuntimeError("LOGIN_REQUIRED debe estar activado en produccion.")


DATABASE_URL = os.getenv("DATABASE_URL", "")
ES_PRODUCCION = _entorno_productivo()
SECRET_KEY = os.getenv("SECRET_KEY", "") or SECRET_KEY_DESARROLLO
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0").strip() == "1"
LOGIN_REQUIRED = os.getenv("LOGIN_REQUIRED", "0").strip() == "1"
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

validar_configuracion_seguridad(ES_PRODUCCION, SECRET_KEY, LOGIN_REQUIRED)

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
