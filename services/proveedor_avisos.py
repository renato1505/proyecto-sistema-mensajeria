from dataclasses import dataclass
from email.message import EmailMessage

from config.settings import CORREO_EMISOR
from database.modelos import AVISO_TIPO_DESTINATARIO, AVISO_TIPO_FUNCIONARIO
from services.email_client import (
    ErrorCorreoConfirmado,
    ResultadoCorreoIncierto,
    enviar_mensaje,
)


@dataclass(frozen=True)
class ResultadoEnvioCorreo:
    aceptado: bool
    message_id: str | None = None
    error: str | None = None
    resultado_incierto: bool = False

    @classmethod
    def exito(cls, message_id=None):
        return cls(aceptado=True, message_id=message_id)

    @classmethod
    def error_confirmado(cls, error):
        return cls(aceptado=False, error=error)

    @classmethod
    def incierto(cls, error):
        return cls(aceptado=False, error=error, resultado_incierto=True)


@dataclass(frozen=True)
class SolicitudCorreoAviso:
    aviso_id: int
    envio_id: int
    tipo: str
    destinatario: str
    remitente_nombre: str
    destinatario_nombre: str
    orden_flete: str
    direccion: str
    comuna: str
    region: str
    telefono: str
    observacion: str


class ProveedorCorreoFake:
    """Proveedor determinista para pruebas y demo; nunca accede a la red."""

    def __init__(self, resultados=None):
        self.resultados = dict(resultados or {})
        self.invocaciones = []

    def __call__(self, solicitud):
        self.invocaciones.append(solicitud)
        resultado = self.resultados.get(solicitud.aviso_id)
        return resultado or ResultadoEnvioCorreo.exito(f"fake-{solicitud.aviso_id}")


def _mensaje_destinatario(solicitud):
    mensaje = EmailMessage()
    mensaje["Subject"] = "L'Oreal Mensajeria - envio en curso"
    mensaje["From"] = CORREO_EMISOR
    mensaje["To"] = solicitud.destinatario
    mensaje.set_content(
        "Te informamos que Mensajeria L'Oreal gestiono un envio a tu nombre mediante Starken.\n\n"
        f"Remitente: {solicitud.remitente_nombre}\n"
        f"Orden de flete: {solicitud.orden_flete}\n"
        f"Direccion de entrega: {solicitud.direccion}\n"
        f"Comuna / Region: {solicitud.comuna} / {solicitud.region or 'No informada'}\n"
        f"Telefono registrado: {solicitud.telefono or 'No informado'}\n"
        f"Observacion: {solicitud.observacion or 'Sin observacion'}\n\n"
        "Puedes revisar el seguimiento en Starken: https://www.starken.cl/seguimiento\n\n"
        "Equipo de Mensajeria\nL'Oreal\n"
    )
    return mensaje


def _mensaje_funcionario(solicitud):
    primer_nombre = (solicitud.remitente_nombre or "Funcionario").strip().split()[0]
    mensaje = EmailMessage()
    mensaje["Subject"] = "Tu envio Starken ya fue procesado"
    mensaje["From"] = CORREO_EMISOR
    mensaje["To"] = solicitud.destinatario
    mensaje.set_content(
        f"Hola {primer_nombre},\n\n"
        "Tu envio fue procesado por Mensajeria y ya cuenta con orden de flete.\n\n"
        f"Orden de flete: {solicitud.orden_flete}\n"
        f"Destinatario: {solicitud.destinatario_nombre}\n"
        f"Comuna: {solicitud.comuna}\n\n"
        "Saludos,\nEquipo de Mensajeria\nL'Oreal\n"
    )
    return mensaje


def enviar_correo_aviso(solicitud):
    """Adaptador productivo. La aceptacion es del proveedor, no entrega final."""
    if solicitud.tipo == AVISO_TIPO_FUNCIONARIO:
        mensaje = _mensaje_funcionario(solicitud)
    elif solicitud.tipo == AVISO_TIPO_DESTINATARIO:
        mensaje = _mensaje_destinatario(solicitud)
    else:
        return ResultadoEnvioCorreo.error_confirmado("Tipo de aviso no soportado")

    try:
        respuesta = enviar_mensaje(mensaje)
    except ErrorCorreoConfirmado as exc:
        return ResultadoEnvioCorreo.error_confirmado(exc.mensaje_sanitizado)
    except ResultadoCorreoIncierto as exc:
        return ResultadoEnvioCorreo.incierto(exc.mensaje_sanitizado)
    except Exception as exc:
        return ResultadoEnvioCorreo.incierto(str(exc))

    return ResultadoEnvioCorreo.exito(respuesta.message_id)
