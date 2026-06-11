from email.message import EmailMessage
from config.settings import CORREO_CLAVE_APP, CORREO_DESTINO_STARKEN, CORREO_EMISOR
from services.smtp_client import enviar_mensaje_smtp


def obtener_correo_destino_starken():
    return CORREO_DESTINO_STARKEN


def correo_starken_configurado():
    return bool(CORREO_EMISOR and CORREO_CLAVE_APP and CORREO_DESTINO_STARKEN)


def enviar_archivo_starken(nombre_archivo, contenido_bytes, lote):
    if not correo_starken_configurado():
        raise RuntimeError("Faltan credenciales de correo en el archivo .env")

    msg = EmailMessage()
    msg["Subject"] = f"Carga Starken - {lote}"
    msg["From"] = CORREO_EMISOR
    msg["To"] = CORREO_DESTINO_STARKEN

    msg.set_content(
        f"Se adjunta archivo Starken correspondiente al lote {lote}.\n\n"
    )

    msg.add_attachment(
        contenido_bytes,
        maintype="text",
        subtype="csv",
        filename=nombre_archivo
    )

    enviar_mensaje_smtp(msg)
