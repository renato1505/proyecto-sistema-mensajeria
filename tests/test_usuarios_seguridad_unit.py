import unittest
from types import SimpleNamespace

from services.usuarios import salud_usuario


class UsuariosSeguridadUnitTest(unittest.TestCase):
    def test_salud_usuario_ok(self):
        usuario = SimpleNamespace(
            u_activo=True,
            u_debe_cambiar_clave=False,
            u_ultimo_acceso="2026-06-23",
            u_rol="usuario",
        )

        salud = salud_usuario(usuario)

        self.assertEqual(salud["nivel"], "ok")
        self.assertEqual(salud["etiquetas"][0]["texto"], "OK")

    def test_salud_usuario_clave_temporal_sin_acceso(self):
        usuario = SimpleNamespace(
            u_activo=True,
            u_debe_cambiar_clave=True,
            u_ultimo_acceso=None,
            u_rol="usuario",
        )

        salud = salud_usuario(usuario)
        textos = {item["texto"] for item in salud["etiquetas"]}

        self.assertEqual(salud["nivel"], "warning")
        self.assertIn("Clave temporal", textos)
        self.assertIn("Sin ultimo acceso", textos)

    def test_salud_usuario_inactivo_domina(self):
        usuario = SimpleNamespace(
            u_activo=False,
            u_debe_cambiar_clave=True,
            u_ultimo_acceso=None,
            u_rol="admin",
        )

        salud = salud_usuario(usuario)
        textos = {item["texto"] for item in salud["etiquetas"]}

        self.assertEqual(salud["nivel"], "danger")
        self.assertIn("Inactivo", textos)
        self.assertIn("Admin", textos)


if __name__ == "__main__":
    unittest.main()
