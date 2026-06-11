import smtplib

from config.settings import CORREO_CLAVE_APP, CORREO_EMISOR


SMTP_HOST = "smtp.gmail.com"
SMTP_SSL_PORT = 465
SMTP_STARTTLS_PORT = 587
SMTP_TIMEOUT_SECONDS = 8


def enviar_mensaje_smtp(msg):
    """Envia correos Gmail con timeout y fallback para entornos cloud."""
    errores = []

    try:
        with smtplib.SMTP_SSL(
            SMTP_HOST,
            SMTP_SSL_PORT,
            timeout=SMTP_TIMEOUT_SECONDS,
        ) as servidor:
            servidor.login(CORREO_EMISOR, CORREO_CLAVE_APP)
            servidor.send_message(msg)
            return
    except Exception as exc:
        errores.append(f"SSL {SMTP_SSL_PORT}: {exc}")

    try:
        with smtplib.SMTP(
            SMTP_HOST,
            SMTP_STARTTLS_PORT,
            timeout=SMTP_TIMEOUT_SECONDS,
        ) as servidor:
            servidor.ehlo()
            servidor.starttls()
            servidor.ehlo()
            servidor.login(CORREO_EMISOR, CORREO_CLAVE_APP)
            servidor.send_message(msg)
            return
    except Exception as exc:
        errores.append(f"STARTTLS {SMTP_STARTTLS_PORT}: {exc}")

    raise RuntimeError("No se pudo conectar a Gmail SMTP. " + " | ".join(errores))
