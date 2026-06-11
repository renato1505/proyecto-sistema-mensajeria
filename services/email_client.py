import base64
import json
import smtplib
import urllib.error
import urllib.request
from email.utils import getaddresses

from config.settings import (
    BREVO_API_KEY,
    BREVO_API_URL,
    BREVO_SENDER_NAME,
    BREVO_SMTP_HOST,
    BREVO_SMTP_LOGIN,
    BREVO_SMTP_PASSWORD,
    BREVO_SMTP_PORT,
    CORREO_CLAVE_APP,
    CORREO_EMISOR,
    EMAIL_PROVIDER,
)


SMTP_HOST = "smtp.gmail.com"
SMTP_SSL_PORT = 465
SMTP_STARTTLS_PORT = 587
EMAIL_TIMEOUT_SECONDS = 8
EMAIL_PROVIDERS = {"smtp", "brevo", "brevo_smtp"}


def proveedor_correo_valido():
    return EMAIL_PROVIDER in EMAIL_PROVIDERS


def proveedor_correo_configurado():
    if not proveedor_correo_valido():
        return False

    if EMAIL_PROVIDER == "brevo":
        return bool(CORREO_EMISOR and BREVO_API_KEY)

    if EMAIL_PROVIDER == "brevo_smtp":
        return bool(CORREO_EMISOR and BREVO_SMTP_LOGIN and BREVO_SMTP_PASSWORD)

    return bool(CORREO_EMISOR and CORREO_CLAVE_APP)


def enviar_mensaje(msg):
    if not proveedor_correo_valido():
        raise RuntimeError(
            "EMAIL_PROVIDER debe ser 'smtp', 'brevo' o 'brevo_smtp'. "
            f"Valor actual: {EMAIL_PROVIDER or 'vacio'}"
        )

    if EMAIL_PROVIDER == "brevo":
        return _enviar_brevo(msg)

    if EMAIL_PROVIDER == "brevo_smtp":
        return _enviar_brevo_smtp(msg)

    return _enviar_smtp(msg)


def _enviar_smtp(msg):
    errores = []

    try:
        with smtplib.SMTP_SSL(
            SMTP_HOST,
            SMTP_SSL_PORT,
            timeout=EMAIL_TIMEOUT_SECONDS,
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
            timeout=EMAIL_TIMEOUT_SECONDS,
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


def _enviar_brevo_smtp(msg):
    if not BREVO_SMTP_LOGIN or not BREVO_SMTP_PASSWORD:
        raise RuntimeError("Faltan credenciales SMTP de Brevo.")

    with smtplib.SMTP(
        BREVO_SMTP_HOST,
        BREVO_SMTP_PORT,
        timeout=EMAIL_TIMEOUT_SECONDS,
    ) as servidor:
        servidor.ehlo()
        servidor.starttls()
        servidor.ehlo()
        servidor.login(BREVO_SMTP_LOGIN, BREVO_SMTP_PASSWORD)
        servidor.send_message(msg)


def _direcciones(cabecera):
    return [
        {"email": correo, "name": nombre}
        if nombre
        else {"email": correo}
        for nombre, correo in getaddresses([cabecera or ""])
        if correo
    ]


def _contenido(msg, tipo):
    parte = msg.get_body(preferencelist=(tipo,))
    if not parte:
        return ""
    contenido = parte.get_content()
    return contenido if isinstance(contenido, str) else str(contenido or "")


def _adjuntos(msg):
    adjuntos = []
    for parte in msg.iter_attachments():
        nombre = parte.get_filename()
        contenido = parte.get_payload(decode=True)
        if not nombre or contenido is None:
            continue

        adjuntos.append({
            "name": nombre,
            "content": base64.b64encode(contenido).decode("ascii"),
        })
    return adjuntos


def _payload_brevo(msg):
    destinatarios = _direcciones(msg.get("To"))
    if not destinatarios:
        raise RuntimeError("El correo no tiene destinatarios.")

    texto = _contenido(msg, "plain")
    html = _contenido(msg, "html")
    payload = {
        "sender": {
            "email": CORREO_EMISOR,
            "name": BREVO_SENDER_NAME,
        },
        "to": destinatarios,
        "subject": msg.get("Subject", "Portal Operativo"),
    }

    if html:
        payload["htmlContent"] = html
        payload["textContent"] = texto or "Correo generado por Portal Operativo."
    else:
        payload["textContent"] = texto or "Correo generado por Portal Operativo."

    adjuntos = _adjuntos(msg)
    if adjuntos:
        payload["attachment"] = adjuntos

    return payload


def _enviar_brevo(msg):
    if not BREVO_API_KEY:
        raise RuntimeError("Falta BREVO_API_KEY para enviar correos por Brevo.")

    data = json.dumps(_payload_brevo(msg)).encode("utf-8")
    request = urllib.request.Request(
        BREVO_API_URL,
        data=data,
        headers={
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=EMAIL_TIMEOUT_SECONDS) as response:
            if response.status >= 300:
                raise RuntimeError(f"Brevo respondio HTTP {response.status}.")
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Brevo respondio HTTP {exc.code}: {detalle}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"No se pudo conectar a Brevo: {exc.reason}") from exc
