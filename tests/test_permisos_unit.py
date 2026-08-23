import unittest

from services.permisos import permiso_para_ruta, usuario_puede


class PermisosUnitTest(unittest.TestCase):
    def test_admin_puede_acceder_a_todo(self):
        self.assertTrue(usuario_puede("administracion", "admin", "admin.panel"))
        self.assertTrue(usuario_puede("administracion", "admin", "historico.eliminar"))

    def test_mensajeria_tiene_permisos_operativos(self):
        self.assertTrue(usuario_puede("mensajeria", "usuario", "envios.crear"))
        self.assertTrue(usuario_puede("mensajeria", "usuario", "historico.ver"))
        self.assertFalse(usuario_puede("mensajeria", "usuario", "historico.anular"))
        self.assertFalse(usuario_puede("mensajeria", "usuario", "admin.panel"))

    def test_supervisor_mensajeria_tiene_acciones_criticas(self):
        self.assertTrue(usuario_puede("mensajeria", "supervisor", "historico.anular"))
        self.assertTrue(usuario_puede("mensajeria", "supervisor", "historico.eliminar"))

    def test_visita_mensajeria_solo_lectura(self):
        self.assertTrue(usuario_puede("mensajeria", "visita", "historico.ver"))
        self.assertFalse(usuario_puede("mensajeria", "visita", "envios.crear"))

    def test_areas_reservadas_no_heredan_mensajeria(self):
        self.assertFalse(usuario_puede("recepcion", "usuario", "envios.crear"))
        self.assertFalse(usuario_puede("seguridad", "usuario", "historico.ver"))

    def test_rutas_criticas_tienen_permiso(self):
        self.assertEqual(permiso_para_ruta("/admin"), "admin.panel")
        self.assertEqual(permiso_para_ruta("/crear_envio"), "envios.crear")
        self.assertEqual(permiso_para_ruta("/generar_excel"), "pendientes.gestionar")
        self.assertEqual(permiso_para_ruta("/cargar_of/LOTE-1"), "proceso.gestionar")
        self.assertEqual(permiso_para_ruta("/eliminar_historico_seleccionados"), "historico.eliminar")
        self.assertIsNone(permiso_para_ruta("/reportes", "GET"))
        self.assertEqual(permiso_para_ruta("/catalogos", "GET"), "catalogos.ver")
        self.assertEqual(permiso_para_ruta("/catalogos/remitentes/guardar", "POST"), "catalogos.gestionar")


if __name__ == "__main__":
    unittest.main()
