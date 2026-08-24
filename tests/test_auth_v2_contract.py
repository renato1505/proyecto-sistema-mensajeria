import os
import re
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask
from werkzeug.security import check_password_hash, generate_password_hash

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import routes.auth as auth
from utils.csrf import obtener_csrf_token, validar_csrf


class _FakeQuery:
    def __init__(self, usuario):
        self.usuario = usuario

    def filter(self, *_args):
        return self

    def first(self):
        return self.usuario


class _FakeDB:
    def __init__(self, usuario):
        self.usuario = usuario
        self.commits = 0
        self.rollbacks = 0

    def query(self, *_args):
        return _FakeQuery(self.usuario)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


class AuthV2ContractTest(unittest.TestCase):
    def setUp(self):
        auth.INTENTOS_LOGIN.clear()
        self.app = Flask(__name__, template_folder="../templates")
        self.app.secret_key = "auth-v2-test"
        self.app.config.update(TESTING=True)

        @self.app.before_request
        def proteger_csrf():
            validar_csrf()

        @self.app.context_processor
        def csrf_context():
            return {"csrf_token": obtener_csrf_token}

        auth.registrar_rutas_auth(self.app)

        for indice, ruta in enumerate(
            ("/envios", "/en_proceso", "/historico", "/avisos", "/carga_masiva")
        ):
            self.app.add_url_rule(ruta, f"privada_{indice}", lambda: "OK")

        self.app.add_url_rule("/mutacion", "mutacion", lambda: "MUTADA", methods=["POST"])

        self.login_required = patch.object(auth, "LOGIN_REQUIRED", True)
        self.login_required.start()
        self.client = self.app.test_client()

    def tearDown(self):
        self.login_required.stop()
        auth.INTENTOS_LOGIN.clear()

    def _autenticar(self, **cambios):
        datos = {
            "usuario_autenticado": True,
            "usuario_nombre": "operador",
            "usuario_display": "Operador Mensajeria",
            "debe_cambiar_clave": False,
            "ultima_actividad": time.time(),
        }
        datos.update(cambios)
        with self.client.session_transaction() as sesion:
            sesion.update(datos)

    def _csrf_login(self):
        html = self.client.get("/login").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def test_usuario_no_autenticado_no_accede_a_envios(self):
        respuesta = self.client.get("/envios")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login", respuesta.location)

    def test_usuario_autenticado_accede_a_envios_sin_importar_area_rol(self):
        self._autenticar()
        self.assertEqual(self.client.get("/envios").status_code, 200)

    def test_usuario_autenticado_accede_a_en_proceso(self):
        self._autenticar()
        self.assertEqual(self.client.get("/en_proceso").status_code, 200)

    def test_usuario_autenticado_accede_a_historico(self):
        self._autenticar()
        self.assertEqual(self.client.get("/historico").status_code, 200)

    def test_usuario_autenticado_accede_a_avisos(self):
        self._autenticar()
        self.assertEqual(self.client.get("/avisos").status_code, 200)

    def test_usuario_autenticado_accede_a_carga_masiva(self):
        self._autenticar()
        self.assertEqual(self.client.get("/carga_masiva").status_code, 200)

    def test_timeout_de_sesion_sigue_funcionando(self):
        self._autenticar(ultima_actividad=time.time() - 7200)
        with patch.object(auth, "SESSION_TIMEOUT_MINUTES", 1):
            respuesta = self.client.get("/envios")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login", respuesta.location)
        with self.client.session_transaction() as sesion:
            self.assertNotIn("usuario_autenticado", sesion)

    def test_csrf_bloquea_post_sin_token(self):
        self._autenticar()
        self.assertEqual(self.client.post("/mutacion").status_code, 400)

    def test_bloqueo_por_intentos_fallidos_continua_funcionando(self):
        token = self._csrf_login()
        with patch.object(auth, "obtener_usuarios_configurados", return_value={}), patch.object(
            auth, "_registrar_evento_login"
        ):
            for _ in range(auth.MAX_INTENTOS_LOGIN):
                self.client.post(
                    "/login",
                    data={"csrf_token": token, "usuario": "operador", "clave": "incorrecta"},
                )
        bloqueo = auth.listar_bloqueos_login()[0]
        self.assertTrue(bloqueo["bloqueado"])
        self.assertEqual(bloqueo["intentos"], auth.MAX_INTENTOS_LOGIN)

    def test_login_valida_hash_werkzeug(self):
        token = self._csrf_login()
        usuario = auth.UsuarioAcceso(
            usuario="operador",
            clave_hash=generate_password_hash("secreto-seguro"),
            nombre="Operador",
        )
        with patch.object(auth, "obtener_usuarios_configurados", return_value={"operador": usuario}), patch.object(
            auth, "_actualizar_ultimo_acceso"
        ):
            respuesta = self.client.post(
                "/login",
                data={"csrf_token": token, "usuario": "operador", "clave": "secreto-seguro"},
            )
        self.assertEqual(respuesta.status_code, 302)
        with self.client.session_transaction() as sesion:
            self.assertTrue(sesion["usuario_autenticado"])

    def test_login_rechaza_credencial_legacy_en_texto_plano(self):
        token = self._csrf_login()
        usuario = auth.UsuarioAcceso(usuario="operador", clave_hash="texto-plano", nombre="Operador")
        with patch.object(auth, "obtener_usuarios_configurados", return_value={"operador": usuario}), patch.object(
            auth, "_registrar_evento_login"
        ):
            respuesta = self.client.post(
                "/login",
                data={"csrf_token": token, "usuario": "operador", "clave": "texto-plano"},
            )
        self.assertEqual(respuesta.status_code, 200)
        with self.client.session_transaction() as sesion:
            self.assertNotIn("usuario_autenticado", sesion)

    def test_login_falla_cerrado_si_bd_no_disponible(self):
        with patch.object(auth, "obtener_usuarios_configurados", side_effect=RuntimeError("BD no disponible")), patch.object(
            auth.logger, "exception"
        ) as registrar_error:
            respuesta = self.client.get("/login")
        self.assertEqual(respuesta.status_code, 503)
        registrar_error.assert_called_once()

    def test_ruta_recuperacion_legacy_no_existe(self):
        self.assertNotIn("/login/recuperar", {regla.rule for regla in self.app.url_map.iter_rules()})

    def test_cambio_de_clave_requiere_clave_actual(self):
        usuario = SimpleNamespace(
            u_clave_hash=generate_password_hash("actual-segura"),
            u_debe_cambiar_clave=True,
            u_fecha_actualizacion=None,
        )
        db = _FakeDB(usuario)
        self._autenticar(debe_cambiar_clave=True)
        with self.client.session_transaction() as sesion:
            token = "csrf-cambio-clave"
            sesion["_csrf_token"] = token
        with patch.object(auth, "SessionLocal", return_value=db), patch.object(auth, "registrar_accion"):
            respuesta = self.client.post(
                "/cambiar_clave",
                data={
                    "csrf_token": token,
                    "clave_actual": "incorrecta",
                    "clave": "nueva-segura",
                    "confirmar_clave": "nueva-segura",
                },
            )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(check_password_hash(usuario.u_clave_hash, "actual-segura"))
        self.assertEqual(db.commits, 0)

    def test_nueva_clave_se_almacena_como_hash(self):
        usuario = SimpleNamespace(
            u_clave_hash=generate_password_hash("actual-segura"),
            u_debe_cambiar_clave=True,
            u_fecha_actualizacion=None,
        )
        db = _FakeDB(usuario)
        self._autenticar(debe_cambiar_clave=True)
        with self.client.session_transaction() as sesion:
            token = "csrf-cambio-clave"
            sesion["_csrf_token"] = token
        with patch.object(auth, "SessionLocal", return_value=db), patch.object(auth, "registrar_accion"):
            respuesta = self.client.post(
                "/cambiar_clave",
                data={
                    "csrf_token": token,
                    "clave_actual": "actual-segura",
                    "clave": "nueva-segura",
                    "confirmar_clave": "nueva-segura",
                },
            )
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotEqual(usuario.u_clave_hash, "nueva-segura")
        self.assertTrue(check_password_hash(usuario.u_clave_hash, "nueva-segura"))
        self.assertEqual(db.commits, 1)


if __name__ == "__main__":
    unittest.main()
