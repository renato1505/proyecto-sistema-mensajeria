import base64
import sys
import unittest
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from routes.auth import (
    UsuarioAcceso,
    _destino_login_seguro,
    verificar_clave_usuario,
)
from services import avisos, email_client
from services.email_templates import correo_destinatario_html
from utils.texto import (
    normalizar_correo_operativo,
    normalizar_nombre_operativo,
    normalizar_nombre_remitente,
    normalizar_observacion_operativa,
    normalizar_orden_flete,
    normalizar_texto_operativo,
)
from utils.validaciones import normalizar_telefono_chile, normalizar_telefono_operativo, telefono_operativo_valido


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
        smtp.send_message.return_value = {}

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


class AuthCredentialTests(unittest.TestCase):
    def test_login_acepta_hash_y_rechaza_clave_legacy(self):
        from werkzeug.security import generate_password_hash

        hash_clave = generate_password_hash("clave-segura")

        self.assertTrue(verificar_clave_usuario("clave-segura", hash_clave))
        self.assertFalse(verificar_clave_usuario("otra", hash_clave))
        self.assertFalse(verificar_clave_usuario("legacy", "legacy"))
        self.assertFalse(verificar_clave_usuario("legacy", "otra"))

    def test_usuario_acceso_no_contiene_area_ni_rol(self):
        usuario = UsuarioAcceso(usuario="operador", clave_hash="hash", nombre="Operador")
        self.assertFalse(hasattr(usuario, "area"))
        self.assertFalse(hasattr(usuario, "rol"))


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

    def test_primer_nombre_usa_solo_nombre_inicial(self):
        self.assertEqual(avisos._primer_nombre("Consuelo Pino Fuentes"), "Consuelo")
        self.assertEqual(avisos._primer_nombre("", "Equipo"), "Equipo")

    def test_cancelar_avisos_lote_solo_toca_pendientes(self):
        pendiente = SimpleNamespace(e_aviso_funcionario_estado="pendiente")
        enviado = SimpleNamespace(e_aviso_funcionario_estado="enviado")
        vacio = SimpleNamespace(e_aviso_funcionario_estado=None)

        cantidad = avisos.cancelar_avisos_lote([pendiente, enviado, vacio])

        self.assertEqual(cantidad, 1)
        self.assertEqual(pendiente.e_aviso_funcionario_estado, "cancelado")
        self.assertEqual(enviado.e_aviso_funcionario_estado, "enviado")
        self.assertIsNone(vacio.e_aviso_funcionario_estado)


class EmailTemplatesTests(unittest.TestCase):
    def test_correo_destinatario_no_expone_rut(self):
        envio = SimpleNamespace(
            e_remitente="Sofia Larrea",
            e_destinatario="Cristobal Fernandez",
            e_orden_flete="272063587",
            e_direccion="Av. Principal 123",
            e_comuna="Providencia",
            e_region="Region Metropolitana",
            e_telefono_destinatario="931905658",
            e_observacion="Tienda Costanera",
            e_rut_destinatario="12345678-9",
        )

        html = correo_destinatario_html(envio)

        self.assertIn("Hola", html)
        self.assertIn("Sofia Larrea", html)
        self.assertIn("272063587", html)
        self.assertIn("https://www.starken.cl/seguimiento", html)
        self.assertNotIn("12345678-9", html)


class ValidacionesTests(unittest.TestCase):
    def test_normalizar_telefono_chile_acepta_formatos_copiados(self):
        self.assertEqual(normalizar_telefono_chile("+569 3190 5658"), "931905658")
        self.assertEqual(normalizar_telefono_chile("56 9 8508 9918"), "985089918")
        self.assertEqual(normalizar_telefono_chile("56946554638"), "946554638")

    def test_telefono_operativo_acepta_internacional_con_codigo(self):
        self.assertEqual(normalizar_telefono_operativo("+54 9 11 1234 5678"), "5491112345678")
        self.assertEqual(normalizar_telefono_operativo("+56 9 3190 5658"), "931905658")
        self.assertTrue(telefono_operativo_valido("+54 9 11 1234 5678"))
        self.assertTrue(telefono_operativo_valido("931905658"))
        self.assertFalse(telefono_operativo_valido("1234"))

    def test_normalizar_texto_operativo_quita_tildes(self):
        self.assertEqual(normalizar_texto_operativo("Región Metropolitana de Santiago"), "Region Metropolitana de Santiago")
        self.assertEqual(normalizar_texto_operativo("Sofía Larrea"), "Sofia Larrea")
        self.assertEqual(normalizar_texto_operativo("döp", upper=True), "DOP")

    def test_normalizar_nombre_operativo_usa_mayuscula_por_palabra(self):
        self.assertEqual(normalizar_nombre_operativo("soFIA lArrea"), "Sofia Larrea")
        self.assertEqual(normalizar_nombre_operativo("josé luis pérez"), "Jose Luis Perez")

    def test_normalizar_nombre_remitente_usa_nombre_corto(self):
        self.assertEqual(normalizar_nombre_remitente("Carolina Alejandra Jeria Ramirez"), "Carolina Jeria")
        self.assertEqual(normalizar_nombre_remitente("Carolina Jeria"), "Carolina Jeria")
        self.assertEqual(normalizar_nombre_remitente("Juan Carlos Perez"), "Juan Perez")
        self.assertEqual(normalizar_nombre_remitente("maria jose gonzalez soto"), "Maria Gonzalez")

    def test_normalizar_correo_operativo_deja_minusculas(self):
        self.assertEqual(normalizar_correo_operativo(" Persona.LOREAL@GMAIL.COM "), "persona.loreal@gmail.com")

    def test_normalizar_observacion_operativa_quita_puntuacion_h2h(self):
        self.assertEqual(
            normalizar_observacion_operativa("Tienda, horario; contacto. urgente"),
            "Tienda horario contacto urgente",
        )

    def test_normalizar_orden_flete_quita_decimal_excel(self):
        self.assertEqual(normalizar_orden_flete("272472119.0"), "272472119")
        self.assertEqual(normalizar_orden_flete(272472117.0), "272472117")
        self.assertEqual(normalizar_orden_flete("272472126"), "272472126")


class AuthTests(unittest.TestCase):
    def test_destino_login_seguro_solo_permite_rutas_internas(self):
        self.assertEqual(_destino_login_seguro("/historico"), "/historico")
        self.assertEqual(_destino_login_seguro("https://externo.example.com"), "/")
        self.assertEqual(_destino_login_seguro("//externo.example.com/ruta"), "/")
        self.assertEqual(_destino_login_seguro(""), "/")


if __name__ == "__main__":
    unittest.main()
