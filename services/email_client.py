import base64
import json
import re
import smtplib
import urllib.error
import urllib.request
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ResultadoEmail:
    aceptado: bool
    transporte: str
    message_id: str | None = None
    status_code: int | None = None


def _sanitizar_detalle(valor):
    texto = " ".join(str(valor or "Error de correo").split())
    reemplazos = (
        (r"(?i)(api[-_ ]?key|authorization|token|password|secret)\s*[:=]\s*\S+", r"\1=[REDACTADO]"),
        (r"(?i)(https?://)[^/@\s]+:[^/@\s]+@", r"\1[REDACTADO]@"),
    )
    for patron, reemplazo in reemplazos:
        texto = re.sub(patron, reemplazo, texto)
    return texto[:1500]


class ErrorClienteCorreo(RuntimeError):
    def __init__(self, mensaje, transporte, status_code=None, codigo_proveedor=None):
        self.transporte = transporte
        self.status_code = status_code
        self.codigo_proveedor = _sanitizar_detalle(codigo_proveedor) if codigo_proveedor else None
        self.mensaje_sanitizado = _sanitizar_detalle(mensaje)
        super().__init__(self.mensaje_sanitizado)


class ErrorCorreoConfirmado(ErrorClienteCorreo):
    """El proveedor no acepto el mensaje; puede evaluarse un reintento explicito."""


class ResultadoCorreoIncierto(ErrorClienteCorreo):
    """No puede demostrarse si el proveedor acepto el mensaje; no debe reintentarse."""


class _FalloSMTPPrevio(Exception):
    pass


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
        raise ErrorCorreoConfirmado(
            "EMAIL_PROVIDER debe ser 'smtp', 'brevo' o 'brevo_smtp'. "
            f"Valor actual: {EMAIL_PROVIDER or 'vacio'}",
            EMAIL_PROVIDER or "desconocido",
        )

    if EMAIL_PROVIDER == "brevo":
        return _enviar_brevo(msg)

    if EMAIL_PROVIDER == "brevo_smtp":
        return _enviar_brevo_smtp(msg)

    return _enviar_smtp(msg)


def _enviar_smtp(msg):
    try:
        return _intento_smtp(
            lambda: smtplib.SMTP_SSL(SMTP_HOST, SMTP_SSL_PORT, timeout=EMAIL_TIMEOUT_SECONDS),
            msg,
            "smtp",
            usar_starttls=False,
        )
    except _FalloSMTPPrevio as primer_error:
        detalle_primero = _sanitizar_detalle(primer_error)

    try:
        return _intento_smtp(
            lambda: smtplib.SMTP(SMTP_HOST, SMTP_STARTTLS_PORT, timeout=EMAIL_TIMEOUT_SECONDS),
            msg,
            "smtp",
            usar_starttls=True,
        )
    except _FalloSMTPPrevio as segundo_error:
        raise ErrorCorreoConfirmado(
            f"No se pudo iniciar SMTP: SSL {detalle_primero}; STARTTLS {_sanitizar_detalle(segundo_error)}",
            "smtp",
        ) from segundo_error


def _enviar_brevo_smtp(msg):
    if not BREVO_SMTP_LOGIN or not BREVO_SMTP_PASSWORD:
        raise ErrorCorreoConfirmado("Faltan credenciales SMTP de Brevo.", "brevo_smtp")
    try:
        return _intento_smtp(
            lambda: smtplib.SMTP(
                BREVO_SMTP_HOST,
                BREVO_SMTP_PORT,
                timeout=EMAIL_TIMEOUT_SECONDS,
            ),
            msg,
            "brevo_smtp",
            usar_starttls=True,
            usuario=BREVO_SMTP_LOGIN,
            clave=BREVO_SMTP_PASSWORD,
        )
    except _FalloSMTPPrevio as exc:
        raise ErrorCorreoConfirmado(
            f"No se pudo iniciar SMTP de Brevo: {_sanitizar_detalle(exc)}",
            "brevo_smtp",
        ) from exc


def _destinatarios_mensaje(msg):
    return {
        correo.lower()
        for cabecera in ("To", "Cc", "Bcc")
        for _nombre, correo in getaddresses([msg.get(cabecera, "")])
        if correo
    }


def _intento_smtp(crear_cliente, msg, transporte, usar_starttls, usuario=None, clave=None):
    contexto = None
    servidor = None
    try:
        contexto = crear_cliente()
        servidor = contexto.__enter__()
        if usar_starttls:
            servidor.ehlo()
            servidor.starttls()
            servidor.ehlo()
        servidor.login(usuario or CORREO_EMISOR, clave or CORREO_CLAVE_APP)
    except smtplib.SMTPAuthenticationError as exc:
        _cerrar_smtp(contexto, exc)
        raise ErrorCorreoConfirmado("Autenticacion SMTP rechazada", transporte) from exc
    except Exception as exc:
        _cerrar_smtp(contexto, exc)
        raise _FalloSMTPPrevio(_sanitizar_detalle(exc)) from exc

    try:
        rechazados = servidor.send_message(msg) or {}
    except smtplib.SMTPRecipientsRefused as exc:
        _cerrar_smtp(contexto, exc)
        raise ErrorCorreoConfirmado("Todos los destinatarios SMTP fueron rechazados", transporte) from exc
    except smtplib.SMTPDataError as exc:
        _cerrar_smtp(contexto, exc)
        raise ErrorCorreoConfirmado(
            f"SMTP rechazo el contenido con codigo {exc.smtp_code}",
            transporte,
            status_code=exc.smtp_code,
        ) from exc
    except Exception as exc:
        _cerrar_smtp(contexto, exc)
        raise ResultadoCorreoIncierto(
            f"La conexion SMTP se interrumpio durante el envio: {_sanitizar_detalle(exc)}",
            transporte,
        ) from exc

    # send_message ya recibio una respuesta SMTP final. Un fallo al cerrar no
    # justifica repetir un mensaje que el servidor pudo haber aceptado.
    _cerrar_smtp(contexto, None)
    if rechazados:
        destinos = _destinatarios_mensaje(msg)
        rechazados_normalizados = {str(correo).lower() for correo in rechazados}
        if destinos and destinos.issubset(rechazados_normalizados):
            raise ErrorCorreoConfirmado("Todos los destinatarios SMTP fueron rechazados", transporte)
        raise ResultadoCorreoIncierto(
            "SMTP acepto parcialmente el mensaje y rechazo uno o mas destinatarios",
            transporte,
        )
    return ResultadoEmail(aceptado=True, transporte=transporte, message_id=None)


def _cerrar_smtp(contexto, error):
    if contexto is None:
        return
    try:
        contexto.__exit__(type(error) if error else None, error, getattr(error, "__traceback__", None))
    except Exception:
        # Si send_message termino, el cierre no invalida su respuesta final.
        pass


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
        raise ErrorCorreoConfirmado("Falta BREVO_API_KEY para enviar correos por Brevo.", "brevo")

    try:
        data = json.dumps(_payload_brevo(msg)).encode("utf-8")
    except ErrorClienteCorreo:
        raise
    except Exception as exc:
        raise ErrorCorreoConfirmado(
            f"No se pudo construir la solicitud Brevo: {_sanitizar_detalle(exc)}",
            "brevo",
        ) from exc
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
            status = response.status
            try:
                cuerpo = response.read().decode("utf-8")
                respuesta = json.loads(cuerpo)
            except Exception as exc:
                raise ResultadoCorreoIncierto(
                    "Brevo respondio con contenido no interpretable despues de procesar la solicitud",
                    "brevo",
                    status_code=status,
                ) from exc
            message_id = respuesta.get("messageId") if isinstance(respuesta, dict) else None
            if status != 201 or not message_id:
                raise ResultadoCorreoIncierto(
                    "Brevo respondio exitosamente sin un messageId valido",
                    "brevo",
                    status_code=status,
                )
            return ResultadoEmail(
                aceptado=True,
                transporte="brevo",
                message_id=str(message_id)[:255],
                status_code=status,
            )
    except urllib.error.HTTPError as exc:
        detalle, codigo = _detalle_error_brevo(exc)
        clase = ErrorCorreoConfirmado if exc.code in {400, 401, 403, 404, 422, 429} else ResultadoCorreoIncierto
        raise clase(
            f"Brevo respondio HTTP {exc.code}: {detalle}",
            "brevo",
            status_code=exc.code,
            codigo_proveedor=codigo,
        ) from exc
    except urllib.error.URLError as exc:
        raise ResultadoCorreoIncierto(
            f"No se pudo confirmar la respuesta de Brevo: {_sanitizar_detalle(exc.reason)}",
            "brevo",
        ) from exc
    except TimeoutError as exc:
        raise ResultadoCorreoIncierto("Timeout esperando respuesta de Brevo", "brevo") from exc


def _detalle_error_brevo(exc):
    try:
        cuerpo = exc.read().decode("utf-8", errors="replace")
    finally:
        exc.close()
    try:
        datos = json.loads(cuerpo)
    except (TypeError, ValueError):
        return _sanitizar_detalle(cuerpo), None
    if not isinstance(datos, dict):
        return "Respuesta de error no estructurada", None
    return _sanitizar_detalle(datos.get("message") or "Solicitud rechazada"), datos.get("code")
