import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LOGIN_REQUIRED"] = "1"

from main import app
import routes.auth as auth


class OperacionV2UXTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.login_required = patch.object(auth, "LOGIN_REQUIRED", True)
        cls.login_required.start()
        app.config.update(TESTING=True)

    @classmethod
    def tearDownClass(cls):
        cls.login_required.stop()

    def setUp(self):
        self.client = app.test_client()

    def _autenticar(self):
        with self.client.session_transaction() as sesion:
            sesion.update(
                {
                    "usuario_autenticado": True,
                    "usuario_nombre": "operador_v2",
                    "usuario_display": "Operador Mensajeria",
                    "debe_cambiar_clave": False,
                    "ultima_actividad": time.time(),
                }
            )

    def test_inicio_requiere_login(self):
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login", respuesta.location)

    def test_inicio_operacional_responde_y_expone_acciones_principales(self):
        self._autenticar()
        respuesta = self.client.get("/")
        html = respuesta.get_data(as_text=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('href="/nuevo_envio"', html)
        self.assertIn('href="/carga_masiva"', html)
        self.assertIn('href="/operacion"', html)

    def test_operacion_responde_y_agrupa_superficies_existentes(self):
        self._autenticar()
        respuesta = self.client.get("/operacion")
        html = respuesta.get_data(as_text=True)

        self.assertEqual(respuesta.status_code, 200)
        for ruta in ("/nuevo_envio", "/carga_masiva", "/envios", "/en_proceso", "/of_correo", "/avisos", "/operacion/retiros"):
            with self.subTest(ruta=ruta):
                self.assertIn(f'href="{ruta}"', html)

    def test_navegacion_primaria_es_reducida_y_configuracion_sigue_disponible(self):
        self._autenticar()
        html = self.client.get("/").get_data(as_text=True)

        self.assertIn('href="/"', html)
        self.assertIn('href="/operacion"', html)
        self.assertIn('href="/historico"', html)
        self.assertIn('href="/configuracion"', html)
        self.assertNotIn('href="/admin', html)
        self.assertNotIn('href="/reportes', html)
        navegacion = html.split('<nav class="app-nav">', 1)[1].split("</nav>", 1)[0]
        self.assertNotIn('href="/envios"', navegacion)
        self.assertNotIn('href="/en_proceso"', navegacion)
        self.assertNotIn('href="/catalogos"', navegacion)
        self.assertNotIn('href="/avisos"', navegacion)

    def test_sidebar_y_menu_movil_tienen_estructura_accesible(self):
        self._autenticar()
        html = self.client.get("/").get_data(as_text=True)

        self.assertIn('id="appSidebar"', html)
        self.assertIn('aria-label="Navegacion principal"', html)
        self.assertIn('id="sidebarToggle"', html)
        self.assertIn('aria-controls="appSidebar"', html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('id="sidebarBackdrop"', html)
        self.assertIn('class="sidebar-config ', html)
        self.assertIn('action="/logout"', html)

    def test_pendientes_conserva_controles_de_lote_parcial(self):
        html = (Path(__file__).resolve().parent.parent / "templates" / "envios.html").read_text(encoding="utf-8")

        self.assertIn('id="abrirGenerarLote"', html)
        self.assertIn('id="formGenerarCsv"', html)
        self.assertIn('action="/generar_excel"', html)
        self.assertIn('id="seleccionarTodosVisibles"', html)
        self.assertIn('id="limpiarSeleccion"', html)
        self.assertIn('id="seleccionCantidad"', html)

    def test_rutas_core_heredadas_continuan_disponibles(self):
        self._autenticar()
        for ruta in ("/crear_envio", "/nuevo_envio", "/carga_masiva", "/envios", "/en_proceso", "/of_correo", "/avisos", "/historico", "/catalogos", "/operacion/retiros"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 200)

    def test_nuevo_envio_conserva_campos_y_tipos_sin_preview_referencial(self):
        self._autenticar()
        respuesta = self.client.get("/nuevo_envio")
        html = respuesta.get_data(as_text=True)

        self.assertEqual(respuesta.status_code, 200)
        for campo in ("tipo_envio", "codigo_agencia", "remitente", "destinatario", "rut_destinatario", "bultos", "kilos"):
            with self.subTest(campo=campo):
                self.assertIn(f'name="{campo}"', html)
        self.assertIn('value="Domicilio"', html)
        self.assertIn('value="Agencia"', html)
        self.assertNotIn("Etiqueta referencial", html)
        self.assertNotIn("PREVISUALIZACION DE LA ETIQUETA", html)
        self.assertNotIn("preview_tipo_envio", html)
        self.assertNotIn("Registro operativo", html)
        self.assertEqual(html.count("42315-7"), 1)
        self.assertIn('class="account-field"', html)
        self.assertIn('class="btn btn-primary btn-sm px-4">Guardar envio', html)

    def test_lotes_presentan_resumen_compacto_y_selector_of_accesible(self):
        html = (Path(__file__).resolve().parent.parent / "templates" / "en_proceso.html").read_text(encoding="utf-8")

        self.assertIn('class="lote-summary"', html)
        self.assertIn('class="of-summary"', html)
        self.assertIn('class="summary-item"', html)
        self.assertNotIn('&middot;', html)
        self.assertIn('class="file-upload-control"', html)
        self.assertIn('class="file-upload-trigger"', html)
        self.assertIn('Ningún archivo seleccionado', html)
        self.assertIn('class="file-upload-input"', html)
        self.assertIn('aria-describedby="archivo-of-nombre-{{ loop.index }} archivo-of-ayuda-{{ loop.index }}"', html)
        self.assertIn('name="archivo_of"', html)
        self.assertIn('accept=".xlsx,.xls"', html)

        javascript = (Path(__file__).resolve().parent.parent / "static" / "js" / "en_proceso.js").read_text(encoding="utf-8")
        self.assertIn('input.files[0].name', javascript)

    def test_historico_separa_acciones_y_conserva_etiquetas_accesibles(self):
        html = (Path(__file__).resolve().parent.parent / "templates" / "historico.html").read_text(encoding="utf-8")

        self.assertIn('class="historico-action-group" aria-label="Exportacion y consulta"', html)
        self.assertIn('class="historico-action-group destructive" aria-label="Acciones destructivas"', html)
        for etiqueta in ("Exportar Excel", "Descargar seleccionados", "Anular seleccionados", "Eliminar seleccionados", "Eliminar filtrados"):
            with self.subTest(etiqueta=etiqueta):
                self.assertIn(f'aria-label="{etiqueta}"', html)


if __name__ == "__main__":
    unittest.main()
