import unittest

from services.recuperacion import enmascarar_correo, generar_clave_temporal
from utils.validaciones import clave_rut_usuario, normalizar_rut_usuario


class RecuperacionClaveTest(unittest.TestCase):
    def test_generar_clave_temporal_es_segura_para_entrega_manual(self):
        clave = generar_clave_temporal()

        self.assertGreaterEqual(len(clave), 8)
        self.assertNotIn(" ", clave)
        self.assertNotIn("O", clave)
        self.assertNotIn("I", clave)

    def test_enmascarar_correo_oculta_usuario_y_mantiene_dominio(self):
        self.assertEqual(enmascarar_correo("renato@example.com"), "re***@example.com")

    def test_normaliza_rut_para_comparacion_de_recuperacion(self):
        self.assertEqual(normalizar_rut_usuario("12.345.678-5"), "12345678-5")
        self.assertEqual(clave_rut_usuario("12.345.678-5"), clave_rut_usuario("123456785"))


if __name__ == "__main__":
    unittest.main()
