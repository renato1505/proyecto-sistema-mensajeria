import os
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash, generate_password_hash

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.conexion import SessionLocal, engine
from database.modelos import Base, UsuarioSistema
import scripts.reset_password as reset_password
from scripts.reset_password import CODIGO_ERROR, CODIGO_OK, CODIGO_VALIDACION, ejecutar_reset


class ResetPasswordTest(unittest.TestCase):
    USUARIO = "reset_v2"

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        db = SessionLocal()
        db.query(UsuarioSistema).filter(UsuarioSistema.u_usuario == self.USUARIO).delete()
        db.add(
            UsuarioSistema(
                u_usuario=self.USUARIO,
                u_nombre="Usuario Reset",
                u_rut="11111111-1",
                u_clave_hash=generate_password_hash("clave-anterior"),
                u_area="mensajeria",
                u_rol="usuario",
                u_activo=True,
                u_debe_cambiar_clave=False,
            )
        )
        db.commit()
        db.close()

    def tearDown(self):
        db = SessionLocal()
        db.query(UsuarioSistema).filter(UsuarioSistema.u_usuario == self.USUARIO).delete()
        db.commit()
        db.close()

    def _hash_actual(self):
        db = SessionLocal()
        try:
            return db.query(UsuarioSistema).filter(UsuarioSistema.u_usuario == self.USUARIO).first().u_clave_hash
        finally:
            db.close()

    def test_usuario_existente_se_actualiza(self):
        codigo = ejecutar_reset(self.USUARIO, "clave-nueva", "clave-nueva")
        self.assertEqual(codigo, CODIGO_OK)

    def test_usuario_inexistente_no_se_crea(self):
        codigo = ejecutar_reset("no-existe", "clave-nueva", "clave-nueva")
        self.assertEqual(codigo, CODIGO_VALIDACION)

    def test_nueva_clave_queda_hasheada(self):
        ejecutar_reset(self.USUARIO, "clave-nueva", "clave-nueva")
        hash_nuevo = self._hash_actual()
        self.assertNotEqual(hash_nuevo, "clave-nueva")
        self.assertTrue(check_password_hash(hash_nuevo, "clave-nueva"))

    def test_clave_anterior_deja_de_funcionar(self):
        ejecutar_reset(self.USUARIO, "clave-nueva", "clave-nueva")
        self.assertFalse(check_password_hash(self._hash_actual(), "clave-anterior"))

    def test_clave_nueva_funciona(self):
        ejecutar_reset(self.USUARIO, "clave-nueva", "clave-nueva")
        self.assertTrue(check_password_hash(self._hash_actual(), "clave-nueva"))

    def test_confirmacion_incorrecta_no_modifica_datos(self):
        hash_anterior = self._hash_actual()
        codigo = ejecutar_reset(self.USUARIO, "clave-nueva", "otra-clave")
        self.assertEqual(codigo, CODIGO_VALIDACION)
        self.assertEqual(self._hash_actual(), hash_anterior)

    def test_error_de_commit_produce_rollback(self):
        class DBConError:
            def __init__(self):
                self.rollback_ejecutado = False

            def query(self, *_args):
                return self

            def filter(self, *_args):
                return self

            def first(self):
                return type(
                    "Usuario",
                    (),
                    {
                        "u_clave_hash": generate_password_hash("anterior"),
                        "u_debe_cambiar_clave": False,
                        "u_fecha_actualizacion": None,
                    },
                )()

            def commit(self):
                raise RuntimeError("fallo simulado")

            def rollback(self):
                self.rollback_ejecutado = True

            def close(self):
                pass

        db = DBConError()
        with patch("scripts.reset_password.logger.exception") as registrar_error:
            codigo = ejecutar_reset(
                self.USUARIO,
                "clave-nueva",
                "clave-nueva",
                session_factory=lambda: db,
            )
        self.assertEqual(codigo, CODIGO_ERROR)
        self.assertTrue(db.rollback_ejecutado)
        registrar_error.assert_called_once()

    def test_destino_incorrecto_aborta_antes_de_solicitar_clave(self):
        with patch.object(reset_password, "DATABASE_URL", "sqlite:///qa_reset.db"), patch.object(
            reset_password.getpass, "getpass"
        ) as solicitar_clave, patch("builtins.print"):
            codigo = reset_password.main(
                ["--usuario", self.USUARIO, "--confirmar-destino", "otro-host/otra-base"]
            )
        self.assertEqual(codigo, CODIGO_VALIDACION)
        solicitar_clave.assert_not_called()


if __name__ == "__main__":
    unittest.main()
