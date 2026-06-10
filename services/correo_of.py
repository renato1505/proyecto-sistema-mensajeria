import imaplib
import re
from dataclasses import dataclass
from email import message_from_bytes
from email.header import decode_header
from email.utils import parsedate_to_datetime
from html import unescape

from config.settings import (
    CORREO_CLAVE_APP,
    CORREO_EMISOR,
    OF_CORREO_FILTRO_REMITENTE,
    OF_CORREO_FILTRO_TEXTO,
    OF_IMAP_HOST,
    OF_IMAP_PORT,
)


EXTENSIONES_OF = (".xlsx", ".xls")


@dataclass
class AdjuntoOF:
    indice: int
    nombre: str
    tamano: int


@dataclass
class CorreoOF:
    uid: str
    asunto: str
    remitente: str
    fecha: object
    archivo_procesado: str
    adjuntos: list[AdjuntoOF]


def correo_of_configurado():
    return bool(CORREO_EMISOR and CORREO_CLAVE_APP and OF_IMAP_HOST and OF_IMAP_PORT)


def _decodificar_header(valor):
    if not valor:
        return ""

    partes = []
    for contenido, encoding in decode_header(valor):
        if isinstance(contenido, bytes):
            partes.append(contenido.decode(encoding or "utf-8", errors="replace"))
        else:
            partes.append(contenido)

    return "".join(partes).strip()


def _abrir_buzon():
    if not correo_of_configurado():
        raise RuntimeError("Faltan credenciales IMAP para revisar el correo OF.")

    cliente = imaplib.IMAP4_SSL(OF_IMAP_HOST, OF_IMAP_PORT)
    cliente.login(CORREO_EMISOR, CORREO_CLAVE_APP)
    cliente.select("INBOX", readonly=True)
    return cliente


def _cumple_filtros(asunto, remitente):
    filtro_remitente = OF_CORREO_FILTRO_REMITENTE.strip().lower()
    filtro_texto = OF_CORREO_FILTRO_TEXTO.strip().lower()

    if filtro_remitente and filtro_remitente not in remitente.lower():
        return False

    if filtro_texto and filtro_texto not in asunto.lower():
        return False

    return True


def _extraer_adjuntos_of(mensaje):
    adjuntos = []
    indice = 0

    for parte in mensaje.walk():
        if parte.get_content_disposition() != "attachment":
            continue

        nombre = _decodificar_header(parte.get_filename())
        if not nombre.lower().endswith(EXTENSIONES_OF):
            continue

        contenido = parte.get_payload(decode=True) or b""
        adjuntos.append(AdjuntoOF(indice=indice, nombre=nombre, tamano=len(contenido)))
        indice += 1

    return adjuntos


def _decodificar_parte_texto(parte):
    contenido = parte.get_payload(decode=True)
    if not contenido:
        return ""

    charset = parte.get_content_charset() or "utf-8"
    return contenido.decode(charset, errors="replace")


def _extraer_texto_mensaje(mensaje):
    textos = []

    for parte in mensaje.walk():
        if parte.get_content_disposition() == "attachment":
            continue

        content_type = parte.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue

        texto = _decodificar_parte_texto(parte)

        if content_type == "text/html":
            texto = re.sub(r"<br\s*/?>", "\n", texto, flags=re.IGNORECASE)
            texto = re.sub(r"<[^>]+>", " ", texto)
            texto = unescape(texto)

        textos.append(texto)

    return "\n".join(textos)


def extraer_archivo_procesado(texto):
    """Obtiene el CSV que Starken declara como procesado en el cuerpo del correo."""
    if not texto:
        return ""

    patrones = [
        r"Archivo\s+procesado\s*:\s*([^\s\r\n]+\.csv)",
        r"archivo\s+procesado\s*:\s*([^\s\r\n]+\.csv)",
        r"([A-Za-z0-9_.-]+\.csv)",
    ]

    for patron in patrones:
        match = re.search(patron, texto, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().strip(".,;")

    return ""


def buscar_correos_of(limite=10):
    """Busca respuestas OF recientes sin marcar correos ni modificar la bandeja."""
    cliente = _abrir_buzon()
    correos = []

    try:
        estado, data = cliente.uid("search", None, "ALL")
        if estado != "OK" or not data or not data[0]:
            return []

        uids = data[0].split()[-max(limite * 3, limite):]

        for uid_bytes in reversed(uids):
            uid = uid_bytes.decode("ascii", errors="ignore")
            estado, mensaje_data = cliente.uid("fetch", uid, "(RFC822)")
            if estado != "OK" or not mensaje_data:
                continue

            raw = mensaje_data[0][1]
            mensaje = message_from_bytes(raw)
            asunto = _decodificar_header(mensaje.get("Subject"))
            remitente = _decodificar_header(mensaje.get("From"))

            if not _cumple_filtros(asunto, remitente):
                continue

            adjuntos = _extraer_adjuntos_of(mensaje)
            if not adjuntos:
                continue

            archivo_procesado = extraer_archivo_procesado(_extraer_texto_mensaje(mensaje))

            fecha_raw = mensaje.get("Date")
            try:
                fecha = parsedate_to_datetime(fecha_raw) if fecha_raw else None
            except (TypeError, ValueError):
                fecha = None

            correos.append(CorreoOF(
                uid=uid,
                asunto=asunto or "Sin asunto",
                remitente=remitente or "Sin remitente",
                fecha=fecha,
                archivo_procesado=archivo_procesado,
                adjuntos=adjuntos,
            ))

            if len(correos) >= limite:
                break
    finally:
        cliente.close()
        cliente.logout()

    return correos


def descargar_adjunto_of(uid, indice_adjunto):
    """Descarga un adjunto OF y devuelve tambien el CSV procesado informado por Starken."""
    cliente = _abrir_buzon()

    try:
        estado, mensaje_data = cliente.uid("fetch", str(uid), "(RFC822)")
        if estado != "OK" or not mensaje_data:
            raise RuntimeError("No se pudo leer el correo seleccionado.")

        mensaje = message_from_bytes(mensaje_data[0][1])
        archivo_procesado = extraer_archivo_procesado(_extraer_texto_mensaje(mensaje))
        adjunto_actual = 0

        for parte in mensaje.walk():
            if parte.get_content_disposition() != "attachment":
                continue

            nombre = _decodificar_header(parte.get_filename())
            if not nombre.lower().endswith(EXTENSIONES_OF):
                continue

            if adjunto_actual == int(indice_adjunto):
                return nombre, parte.get_payload(decode=True) or b"", archivo_procesado

            adjunto_actual += 1
    finally:
        cliente.close()
        cliente.logout()

    raise RuntimeError("No se encontro el adjunto OF seleccionado.")
