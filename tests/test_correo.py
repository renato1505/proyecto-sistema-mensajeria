import sys
from email.message import EmailMessage
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from config.settings import CORREO_CLAVE_APP, CORREO_DESTINO_STARKEN, CORREO_EMISOR
from services.smtp_client import enviar_mensaje_smtp


def enviar_prueba():
    if not CORREO_EMISOR or not CORREO_CLAVE_APP or not CORREO_DESTINO_STARKEN:
        raise RuntimeError("Faltan credenciales de correo en el archivo .env")

    msg = EmailMessage()
    msg["Subject"] = "Prueba de envio - Portal Operativo"
    msg["From"] = CORREO_EMISOR
    msg["To"] = CORREO_DESTINO_STARKEN

    msg.set_content(
        "Hola,\n\n"
        "Este es un correo de prueba enviado desde el Portal Operativo.\n\n"
        "Si recibiste este mensaje, la conexion con Gmail funciona correctamente.\n\n"
        "Saludos."
    )

    enviar_mensaje_smtp(msg)

    print("Correo enviado correctamente.")

if __name__ == "__main__":
    if "--confirmar" not in sys.argv:
        print("Esta prueba envia un correo real.")
        print("Ejecuta: python tests\\test_correo.py --confirmar")
        raise SystemExit(1)

    enviar_prueba()
