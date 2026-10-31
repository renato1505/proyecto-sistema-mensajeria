import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from tests.entorno_aislado import preparar_entorno_pruebas

preparar_entorno_pruebas()

import re
import unittest

from tests.fixtures_app import obtener_app_aislada

app = obtener_app_aislada()
import routes.auth as auth


class LoginSeguridadTest(unittest.TestCase):
    def tearDown(self):
        auth.INTENTOS_LOGIN.clear()

    def test_bloquea_en_el_quinto_intento_fallido(self):
        client = app.test_client()
        auth.INTENTOS_LOGIN.clear()

        login_page = client.get("/login").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', login_page).group(1)

        for _ in range(auth.MAX_INTENTOS_LOGIN):
            client.post(
                "/login",
                data={
                    "csrf_token": token,
                    "usuario": "usuario_bloqueo_test",
                    "clave": "incorrecta",
                },
            )

        bloqueos = auth.listar_bloqueos_login()
        self.assertEqual(len(bloqueos), 1)
        self.assertTrue(bloqueos[0]["bloqueado"])
        self.assertEqual(bloqueos[0]["intentos"], auth.MAX_INTENTOS_LOGIN)


if __name__ == "__main__":
    unittest.main()
