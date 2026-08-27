import os
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from routes.carga_masiva import aplicar_cambio_masivo_carga
from services.carga_masiva import validar_registros_carga_masiva


class ConsultaVacia:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def all(self):
        return []


class BaseVacia:
    def query(self, *args, **kwargs):
        return ConsultaVacia()


def registros_base():
    return [
        {"numero": "2", "rut_destinatario": "", "tipo_envio": "", "kilos": ""},
        {"numero": "3", "rut_destinatario": "11111111-1", "tipo_envio": "Domicilio", "kilos": "4"},
        {"numero": "4", "rut_destinatario": "", "tipo_envio": "", "kilos": ""},
    ]


class CambiosMasivosCargaV2Test(unittest.TestCase):
    def test_aplica_rut_cero_solo_al_subconjunto(self):
        originales = registros_base()
        resultado = aplicar_cambio_masivo_carga(originales, [0, 2], "rut_destinatario", "0")

        self.assertEqual([fila["rut_destinatario"] for fila in resultado], ["0", "11111111-1", "0"])
        self.assertEqual(originales[0]["rut_destinatario"], "")

    def test_aplica_domicilio_solo_al_subconjunto(self):
        resultado = aplicar_cambio_masivo_carga(registros_base(), [0], "tipo_envio", "Domicilio")
        self.assertEqual([fila["tipo_envio"] for fila in resultado], ["Domicilio", "Domicilio", ""])

    def test_aplica_agencia_solo_al_subconjunto(self):
        resultado = aplicar_cambio_masivo_carga(registros_base(), [2], "tipo_envio", "Agencia")
        self.assertEqual([fila["tipo_envio"] for fila in resultado], ["", "Domicilio", "Agencia"])

    def test_aplica_kilos_solo_al_subconjunto(self):
        resultado = aplicar_cambio_masivo_carga(registros_base(), [0, 2], "kilos", "7")
        self.assertEqual([fila["kilos"] for fila in resultado], ["7", "4", "7"])

    def test_rechaza_seleccion_vacia_indices_inexistentes_y_duplicados(self):
        casos = [
            ([], "Selecciona"),
            ([8], "inexistentes"),
            ([0, 0], "duplicadas"),
        ]
        for indices, mensaje in casos:
            with self.subTest(indices=indices), self.assertRaisesRegex(ValueError, mensaje):
                aplicar_cambio_masivo_carga(registros_base(), indices, "rut_destinatario", "0")

    def test_rechaza_campo_arbitrario(self):
        with self.assertRaisesRegex(ValueError, "Campo"):
            aplicar_cambio_masivo_carga(registros_base(), [0], "estado", "historico")

    def test_rechaza_valores_invalidos(self):
        casos = [
            ("rut_destinatario", "123", "RUT"),
            ("tipo_envio", "Sucursal", "Tipo"),
            ("kilos", "2.5", "entero"),
            ("kilos", "0", "entre"),
        ]
        for campo, valor, mensaje in casos:
            with self.subTest(campo=campo, valor=valor), self.assertRaisesRegex(ValueError, mensaje):
                aplicar_cambio_masivo_carga(registros_base(), [0], campo, valor)

    def test_agencia_continua_marcada_para_completar_codigo(self):
        registro = {
            "numero": "2",
            "remitente": "Operador Demo",
            "correo_remitente": "operador@example.com",
            "centro_costo": "100",
            "division": "DPGP",
            "destinatario": "Destino Real",
            "rut_destinatario": "0",
            "direccion": "Calle Uno 123",
            "region": "Metropolitana",
            "comuna": "Santiago",
            "telefono_destinatario": "912345678",
            "correo_destinatario": "destino@example.com",
            "tipo_envio": "Agencia",
            "bultos": "1",
            "kilos": "2",
            "observacion": "",
        }
        with (
            patch("services.carga_masiva._obtener_catalogo_comunas", return_value=(
                {"Metropolitana": ["Santiago"]},
                {"santiago": "Metropolitana"},
            )),
            patch("services.carga_masiva._remitente_desde_correo", return_value=(
                "Operador Demo", "operador@example.com"
            )),
        ):
            resultado = validar_registros_carga_masiva([registro], BaseVacia())

        self.assertTrue(any(
            "Requiere completar codigo de agencia" in aviso
            for aviso in resultado["filas"][0]["advertencias"]
        ))
        self.assertEqual(resultado["filas"][0]["estado"], "advertencia")

    def test_ux_conserva_revalidacion_y_edicion_individual(self):
        raiz = Path(__file__).resolve().parent.parent
        html = (raiz / "templates" / "carga_masiva.html").read_text(encoding="utf-8")
        javascript = (raiz / "static" / "js" / "carga_masiva.js").read_text(encoding="utf-8")

        self.assertIn('action="/revalidar_carga_masiva"', html)
        self.assertIn('form.action = "/aplicar_cambio_masivo_carga"', javascript)
        self.assertIn('name="filas_seleccionadas"', html)
        self.assertIn('name="filas-{{ idx }}-rut_destinatario"', html)
        self.assertIn('name="filas-{{ idx }}-tipo_envio"', html)
        self.assertIn('name="filas-{{ idx }}-kilos"', html)
        for filtro in ("todos", "revision", "rut", "tipo", "kilos"):
            self.assertIn(f'data-review-filter="{filtro}"', html)


if __name__ == "__main__":
    unittest.main()
