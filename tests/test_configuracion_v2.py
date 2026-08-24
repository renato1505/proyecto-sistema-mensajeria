import os
import time
import unittest
from datetime import datetime
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LOGIN_REQUIRED"] = "1"

from database.conexion import SessionLocal
from database.modelos import UsuarioSistema
from main import app
import routes.auth as auth


class ConfiguracionV2Test(unittest.TestCase):
    USUARIO = "operador_config_v2"

    @classmethod
    def setUpClass(cls):
        cls.login_required = patch.object(auth, "LOGIN_REQUIRED", True)
        cls.login_required.start()
        app.config.update(TESTING=True)

    @classmethod
    def tearDownClass(cls):
        cls.login_required.stop()

    def setUp(self):
        db = SessionLocal()
        db.query(UsuarioSistema).filter(UsuarioSistema.u_usuario == self.USUARIO).delete()
        db.add(
            UsuarioSistema(
                u_usuario=self.USUARIO,
                u_nombre="Operador Configuracion",
                u_rut="11111111-1",
                u_clave_hash="hash-no-utilizado",
                u_area="recepcion",
                u_rol="visita",
                u_activo=True,
                u_debe_cambiar_clave=False,
                u_ultimo_acceso=datetime(2026, 8, 22, 10, 30),
                u_ultimo_ip="192.0.2.25",
            )
        )
        db.commit()
        db.close()
        self.client = app.test_client()

    def tearDown(self):
        db = SessionLocal()
        db.query(UsuarioSistema).filter(UsuarioSistema.u_usuario == self.USUARIO).delete()
        db.commit()
        db.close()

    def _autenticar(self):
        with self.client.session_transaction() as sesion:
            sesion.update(
                {
                    "usuario_autenticado": True,
                    "usuario_nombre": self.USUARIO,
                    "usuario_display": "Nombre heredado de sesion",
                    "debe_cambiar_clave": False,
                    "ultima_actividad": time.time(),
                }
            )

    def test_configuracion_requiere_login(self):
        respuesta = self.client.get("/configuracion")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login", respuesta.location)

    def test_usuario_autenticado_puede_ver_configuracion(self):
        self._autenticar()
        respuesta = self.client.get("/configuracion")
        self.assertEqual(respuesta.status_code, 200)

    def test_configuracion_muestra_datos_del_usuario_actual(self):
        self._autenticar()
        html = self.client.get("/configuracion").get_data(as_text=True)

        self.assertIn(self.USUARIO, html)
        self.assertIn("Operador Configuracion", html)
        self.assertIn("22/08/2026 10:30", html)
        self.assertIn("192.0.2.25", html)
        self.assertNotIn("recepcion", html.lower())
        self.assertNotIn("visita", html.lower())

    def test_admin_y_rutas_empresariales_dejan_de_registrarse(self):
        reglas_admin = [regla.rule for regla in app.url_map.iter_rules() if regla.rule.startswith("/admin")]
        self.assertEqual(reglas_admin, [])
        self._autenticar()
        self.assertEqual(self.client.get("/admin").status_code, 404)

    def test_core_mensajeria_sigue_accesible(self):
        self._autenticar()
        for ruta in ("/envios", "/en_proceso", "/historico", "/avisos", "/carga_masiva"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 200)


if __name__ == "__main__":
    unittest.main()
