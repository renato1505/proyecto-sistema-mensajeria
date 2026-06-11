import base64
import sys
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import MagicMock, patch


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from routes.auth import _destino_login_seguro
from services import avisos, email_client


class EmailClientTests(unittest.TestCase):
    def test_payload_brevo_incluye_destinatarios_contenido_y_adjunto(self):
        msg = EmailMessage()
        msg["Subject"] = "Prueba Brevo"
        msg["From"] = "portal@example.com"
        msg["To"] = "Usuario Uno <uno@example.com>, dos@example.com"
        msg.set_content("Texto simple")
        msg.add_alternative("<p>Texto html</p>", subtype="html")
        msg.add_attachment(
            b"contenido",
            maintype="text",
            subtype="csv",
            filename="lote.csv",
        )

        with patch.object(email_client, "CORREO_EMISOR", "portal@example.com"), patch.object(
            email_client,
            "BREVO_SENDER_NAME",
            "Portal Operativo",
        ):
            payload = email_client._payload_brevo(msg)

        self.assertEqual(payload["sender"]["email"], "portal@example.com")
        self.assertEqual(payload["to"][0], {"email": "uno@example.com", "name": "Usuario Uno"})
        self.assertEqual(payload["to"][1], {"email": "dos@example.com"})
        self.assertEqual(payload["subject"], "Prueba Brevo")
        self.assertIn("htmlContent", payload)
        self.assertEqual(payload["attachment"][0]["name"], "lote.csv")
        self.assertEqual(payload["attachment"][0]["content"], base64.b64encode(b"contenido").decode("ascii"))

    def test_proveedor_brevo_configurado_requiere_api_key_y_emisor(self):
        with patch.object(email_client, "EMAIL_PROVIDER", "brevo"), patch.object(
            email_client,
            "CORREO_EMISOR",
            "portal@example.com",
        ), patch.object(email_client, "BREVO_API_KEY", "key"):
            self.assertTrue(email_client.proveedor_correo_configurado())

        with patch.object(email_client, "EMAIL_PROVIDER", "brevo"), patch.object(
            email_client,
            "CORREO_EMISOR",
            "portal@example.com",
        ), patch.object(email_client, "BREVO_API_KEY", ""):
            self.assertFalse(email_client.proveedor_correo_configurado())

    def test_proveedor_brevo_smtp_configurado_requiere_credenciales_smtp(self):
        with patch.object(email_client, "EMAIL_PROVIDER", "brevo_smtp"), patch.object(
            email_client,
            "CORREO_EMISOR",
            "portal@example.com",
        ), patch.object(email_client, "BREVO_SMTP_LOGIN", "login"), patch.object(
            email_client,
            "BREVO_SMTP_PASSWORD",
            "password",
        ):
            self.assertTrue(email_client.proveedor_correo_configurado())

        with patch.object(email_client, "EMAIL_PROVIDER", "brevo_smtp"), patch.object(
            email_client,
            "CORREO_EMISOR",
            "portal@example.com",
        ), patch.object(email_client, "BREVO_SMTP_LOGIN", "login"), patch.object(
            email_client,
            "BREVO_SMTP_PASSWORD",
            "",
        ):
            self.assertFalse(email_client.proveedor_correo_configurado())

    def test_enviar_brevo_smtp_usa_relay_transaccional(self):
        msg = EmailMessage()
        msg["To"] = "destino@example.com"
        msg.set_content("Hola")

        smtp = MagicMock()
        smtp.__enter__.return_value = smtp

        with patch.object(email_client, "BREVO_SMTP_HOST", "smtp-relay.brevo.com"), patch.object(
            email_client,
            "BREVO_SMTP_PORT",
            587,
        ), patch.object(email_client, "BREVO_SMTP_LOGIN", "login"), patch.object(
            email_client,
            "BREVO_SMTP_PASSWORD",
            "password",
        ), patch.object(email_client.smtplib, "SMTP", return_value=smtp) as smtp_cls:
            email_client._enviar_brevo_smtp(msg)

        smtp_cls.assert_called_once_with("smtp-relay.brevo.com", 587, timeout=email_client.EMAIL_TIMEOUT_SECONDS)
        smtp.login.assert_called_once_with("login", "password")
        smtp.send_message.assert_called_once_with(msg)

    def test_proveedor_invalido_no_queda_configurado(self):
        msg = EmailMessage()
        msg["To"] = "destino@example.com"
        msg.set_content("Hola")

        with patch.object(email_client, "EMAIL_PROVIDER", "otro"):
            self.assertFalse(email_client.proveedor_correo_configurado())
            with self.assertRaisesRegex(RuntimeError, "EMAIL_PROVIDER"):
                email_client.enviar_mensaje(msg)


class AvisosTests(unittest.TestCase):
    def test_enviar_correo_usa_emisor_configurado(self):
        mensajes = []

        with patch.object(avisos, "CORREO_EMISOR", "portal@example.com"), patch.object(
            avisos,
            "enviar_mensaje",
            lambda msg: mensajes.append(msg),
        ):
            avisos._enviar_correo(
                "destino@example.com",
                "Asunto",
                "Cuerpo",
                "detalle.xlsx",
                b"excel",
            )

        self.assertEqual(len(mensajes), 1)
        self.assertEqual(mensajes[0]["From"], "portal@example.com")
        self.assertEqual(mensajes[0]["To"], "destino@example.com")


class AuthTests(unittest.TestCase):
    def test_destino_login_seguro_solo_permite_rutas_internas(self):
        self.assertEqual(_destino_login_seguro("/historico"), "/historico")
        self.assertEqual(_destino_login_seguro("https://externo.example.com"), "/")
        self.assertEqual(_destino_login_seguro("//externo.example.com/ruta"), "/")
        self.assertEqual(_destino_login_seguro(""), "/")


if __name__ == "__main__":
    unittest.main()
