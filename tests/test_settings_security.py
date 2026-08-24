import unittest

from config.settings import validar_configuracion_seguridad


class SettingsSecurityTest(unittest.TestCase):
    def test_produccion_exige_login(self):
        with self.assertRaisesRegex(RuntimeError, "LOGIN_REQUIRED"):
            validar_configuracion_seguridad(True, "secreto-seguro", False)

    def test_produccion_exige_secret_key_no_default(self):
        with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
            validar_configuracion_seguridad(True, "clave_local_solo_desarrollo", True)

    def test_desarrollo_permite_configuracion_local(self):
        validar_configuracion_seguridad(False, "clave_local_solo_desarrollo", False)


if __name__ == "__main__":
    unittest.main()
