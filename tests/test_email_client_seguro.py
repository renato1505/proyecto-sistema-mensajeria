import io
import json
import os
import smtplib
import unittest
import urllib.error
from email.message import EmailMessage
from unittest.mock import MagicMock, patch


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from services import email_client
from services.email_client import (
    ErrorCorreoConfirmado,
    ResultadoCorreoIncierto,
    ResultadoEmail,
)
from services.proveedor_avisos import enviar_correo_aviso, SolicitudCorreoAviso


class RespuestaHTTPFake:
    def __init__(self, status, datos):
        self.status = status
        self.datos = datos

    def read(self):
        return self.datos

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def mensaje():
    msg = EmailMessage()
    msg["From"] = "origen@example.com"
    msg["To"] = "destino@example.com"
    msg["Subject"] = "Prueba"
    msg.set_content("Contenido")
    return msg


def solicitud():
    return SolicitudCorreoAviso(
        aviso_id=1,
        envio_id=2,
        tipo="FUNCIONARIO",
        destinatario="snapshot@example.com",
        remitente_nombre="Ana Ejemplo",
        destinatario_nombre="Destino",
        orden_flete="OF-1",
        direccion="Direccion",
        comuna="Comuna",
        region="Region",
        telefono="12345678",
        observacion="",
    )


class BrevoSeguroTest(unittest.TestCase):
    def _http_error(self, status, datos):
        return urllib.error.HTTPError(
            "https://api.example.invalid/v3/smtp/email",
            status,
            "error",
            {},
            io.BytesIO(json.dumps(datos).encode("utf-8")),
        )

    def test_201_recupera_message_id_y_no_expone_api_key(self):
        respuesta = RespuestaHTTPFake(201, b'{"messageId":"brevo-123"}')
        with patch.object(email_client, "BREVO_API_KEY", "secreto-api"), patch.object(
            email_client.urllib.request, "urlopen", return_value=respuesta
        ) as abrir:
            resultado = email_client._enviar_brevo(mensaje())
        self.assertEqual(resultado, ResultadoEmail(True, "brevo", "brevo-123", 201))
        self.assertNotIn("secreto-api", repr(resultado))
        self.assertEqual(abrir.call_count, 1)

    def test_respuesta_exitosa_sin_message_id_o_json_invalido_es_incierta(self):
        for cuerpo in (b"{}", b"no-json"):
            with self.subTest(cuerpo=cuerpo), patch.object(
                email_client, "BREVO_API_KEY", "key"
            ), patch.object(
                email_client.urllib.request,
                "urlopen",
                return_value=RespuestaHTTPFake(201, cuerpo),
            ):
                with self.assertRaises(ResultadoCorreoIncierto) as contexto:
                    email_client._enviar_brevo(mensaje())
                self.assertEqual(contexto.exception.status_code, 201)

    def test_http_4xx_confirmados_y_5xx_inciertos(self):
        for status in (400, 401, 403, 429):
            with self.subTest(status=status), patch.object(
                email_client, "BREVO_API_KEY", "key"
            ), patch.object(
                email_client.urllib.request,
                "urlopen",
                side_effect=self._http_error(status, {"code": "invalid", "message": "rechazado"}),
            ):
                with self.assertRaises(ErrorCorreoConfirmado) as contexto:
                    email_client._enviar_brevo(mensaje())
                self.assertEqual(contexto.exception.status_code, status)
                self.assertEqual(contexto.exception.codigo_proveedor, "invalid")

        for status in (500, 502, 503):
            with self.subTest(status=status), patch.object(
                email_client, "BREVO_API_KEY", "key"
            ), patch.object(
                email_client.urllib.request,
                "urlopen",
                side_effect=self._http_error(status, {"message": "servidor"}),
            ):
                with self.assertRaises(ResultadoCorreoIncierto) as contexto:
                    email_client._enviar_brevo(mensaje())
                self.assertEqual(contexto.exception.status_code, status)

    def test_timeout_y_conexion_interrumpida_son_inciertos(self):
        errores = [TimeoutError("timeout"), urllib.error.URLError("conexion cortada")]
        for error in errores:
            with self.subTest(error=type(error).__name__), patch.object(
                email_client, "BREVO_API_KEY", "key"
            ), patch.object(email_client.urllib.request, "urlopen", side_effect=error):
                with self.assertRaises(ResultadoCorreoIncierto):
                    email_client._enviar_brevo(mensaje())

    def test_error_sanitiza_secretos_y_no_incluye_api_key(self):
        error = self._http_error(400, {
            "code": "invalid_parameter",
            "message": "token=abc123 https://usuario:clave@example.invalid fallo",
        })
        with patch.object(email_client, "BREVO_API_KEY", "api-super-secreta"), patch.object(
            email_client.urllib.request, "urlopen", side_effect=error
        ):
            with self.assertRaises(ErrorCorreoConfirmado) as contexto:
                email_client._enviar_brevo(mensaje())
        detalle = str(contexto.exception)
        self.assertNotIn("abc123", detalle)
        self.assertNotIn("usuario:clave", detalle)
        self.assertNotIn("api-super-secreta", detalle)


class SMTPSeguroTest(unittest.TestCase):
    def _contexto(self):
        contexto = MagicMock()
        servidor = contexto.__enter__.return_value
        servidor.send_message.return_value = {}
        return contexto, servidor

    def test_aceptacion_devuelve_resultado_sin_message_id(self):
        contexto, servidor = self._contexto()
        with patch.object(email_client.smtplib, "SMTP_SSL", return_value=contexto):
            resultado = email_client._enviar_smtp(mensaje())
        self.assertEqual(resultado, ResultadoEmail(True, "smtp", None, None))
        servidor.send_message.assert_called_once()

    def test_destinatarios_rechazados_es_error_confirmado(self):
        contexto, servidor = self._contexto()
        servidor.send_message.side_effect = smtplib.SMTPRecipientsRefused({
            "destino@example.com": (550, b"rejected")
        })
        with patch.object(email_client.smtplib, "SMTP_SSL", return_value=contexto):
            with self.assertRaises(ErrorCorreoConfirmado):
                email_client._enviar_smtp(mensaje())

    def test_autenticacion_rechazada_no_inicia_fallback(self):
        contexto, servidor = self._contexto()
        servidor.login.side_effect = smtplib.SMTPAuthenticationError(535, b"denied")
        with patch.object(email_client.smtplib, "SMTP_SSL", return_value=contexto), patch.object(
            email_client.smtplib, "SMTP"
        ) as starttls:
            with self.assertRaises(ErrorCorreoConfirmado):
                email_client._enviar_smtp(mensaje())
        starttls.assert_not_called()

    def test_fallo_previo_permite_fallback_starttls(self):
        segundo, servidor = self._contexto()
        with patch.object(
            email_client.smtplib, "SMTP_SSL", side_effect=OSError("sin conexion SSL")
        ), patch.object(email_client.smtplib, "SMTP", return_value=segundo) as starttls:
            resultado = email_client._enviar_smtp(mensaje())
        self.assertTrue(resultado.aceptado)
        starttls.assert_called_once()
        servidor.send_message.assert_called_once()

    def test_fallo_durante_send_es_incierto_y_no_hace_fallback(self):
        contexto, servidor = self._contexto()
        servidor.send_message.side_effect = ConnectionResetError("corte posterior")
        with patch.object(email_client.smtplib, "SMTP_SSL", return_value=contexto), patch.object(
            email_client.smtplib, "SMTP"
        ) as starttls:
            with self.assertRaises(ResultadoCorreoIncierto):
                email_client._enviar_smtp(mensaje())
        starttls.assert_not_called()


class AdaptadorV2SeguroTest(unittest.TestCase):
    def test_propaga_message_id_y_excepciones_tipadas_sin_regex(self):
        with patch(
            "services.proveedor_avisos.enviar_mensaje",
            return_value=ResultadoEmail(True, "brevo", "id-real", 201),
        ):
            self.assertEqual(enviar_correo_aviso(solicitud()).message_id, "id-real")

        with patch(
            "services.proveedor_avisos.enviar_mensaje",
            side_effect=ErrorCorreoConfirmado("rechazo", "brevo", 400),
        ):
            resultado = enviar_correo_aviso(solicitud())
            self.assertFalse(resultado.aceptado)
            self.assertFalse(resultado.resultado_incierto)

        with patch(
            "services.proveedor_avisos.enviar_mensaje",
            side_effect=ResultadoCorreoIncierto("timeout", "brevo"),
        ):
            resultado = enviar_correo_aviso(solicitud())
            self.assertTrue(resultado.resultado_incierto)


if __name__ == "__main__":
    unittest.main()
