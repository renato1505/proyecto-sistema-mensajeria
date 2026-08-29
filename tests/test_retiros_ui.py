import os
import time
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask, redirect, request, session
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database.modelos import Base, Envio, PuntoRetiro, RetiroEnvio, RetiroStarken
from routes import retiros as retiros_routes
from services.retiros import RetiroConcurrenciaError, RetiroValidacionError
from utils.csrf import obtener_csrf_token, validar_csrf
from utils.fechas import ahora_chile


PROJECT_DIR = Path(__file__).resolve().parent.parent


class RetirosUITest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def activar_fk(dbapi_connection, _connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.local = PuntoRetiro(
            pr_codigo="MENSAJERIA_LOCAL",
            pr_nombre="Mensajeria local",
            pr_es_local=True,
            pr_incluir_metricas_locales=True,
            pr_activo=True,
        )
        self.academia = PuntoRetiro(
            pr_codigo="ACADEMIA",
            pr_nombre="Academia",
            pr_es_local=False,
            pr_incluir_metricas_locales=False,
            pr_activo=True,
        )
        self.db.add_all([self.local, self.academia])
        self.db.commit()

        self.app = Flask(
            __name__,
            template_folder=str(PROJECT_DIR / "templates"),
            static_folder=str(PROJECT_DIR / "static"),
        )
        self.app.secret_key = "retiros-ui-test"
        self.app.config.update(TESTING=True)

        @self.app.before_request
        def proteger_y_validar():
            validar_csrf()
            if request.endpoint not in {"login", "static"} and not session.get("usuario_autenticado"):
                return redirect("/login")

        @self.app.get("/login")
        def login():
            return "login"

        @self.app.context_processor
        def contexto_base():
            return {
                "csrf_token": obtener_csrf_token,
                "login_habilitado": True,
                "usuario_actual": session.get("usuario_nombre", ""),
                "usuario_display": session.get("usuario_display", ""),
            }

        retiros_routes.registrar_rutas_retiros(self.app)
        self.session_patch = patch.object(retiros_routes, "SessionLocal", self.Session)
        self.session_patch.start()
        self.client = self.app.test_client()

    def tearDown(self):
        self.session_patch.stop()
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _autenticar(self):
        with self.client.session_transaction() as sesion:
            sesion.update(
                {
                    "usuario_autenticado": True,
                    "usuario_nombre": "operador_v2",
                    "usuario_display": "Operador Mensajeria",
                    "ultima_actividad": time.time(),
                    "_csrf_token": "csrf-retiro",
                }
            )

    def _envio(self, nombre, **cambios):
        datos = {
            "e_remitente": f"Remitente {nombre}",
            "e_destinatario": f"Destino {nombre}",
            "e_direccion": "Direccion QA",
            "e_comuna": "Santiago",
            "e_tipo_envio": "Domicilio",
            "e_bultos": 2,
            "e_kilos": 1,
            "e_estado": "historico",
            "e_orden_flete": f"OF-{nombre}",
            "e_fecha_of": ahora_chile() - timedelta(hours=2),
            "e_punto_retiro_id": self.local.id,
            "e_anulado": False,
        }
        datos.update(cambios)
        envio = Envio(**datos)
        self.db.add(envio)
        self.db.flush()
        return envio

    def _post_confirmar(self, ids, **datos):
        formulario = {
            "csrf_token": "csrf-retiro",
            "envio_ids": [str(envio_id) for envio_id in ids],
            "fecha_retiro": (ahora_chile() - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M"),
            "observacion": "Retiro QA",
        }
        formulario.update(datos)
        return self.client.post("/operacion/retiros/confirmar", data=formulario, follow_redirects=True)

    def test_get_requiere_login_y_responde_autenticado(self):
        self.assertEqual(self.client.get("/operacion/retiros").status_code, 302)
        self._autenticar()
        respuesta = self.client.get("/operacion/retiros")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Listos para retiro", respuesta.get_data(as_text=True))

    def test_muestra_solo_elegibles_y_total_bultos(self):
        visible = self._envio("VISIBLE", e_bultos=7)
        self._envio("LEGACY", e_fecha_of=None)
        self._envio("ACADEMIA", e_punto_retiro_id=self.academia.id)
        retirado = self._envio("RETIRADO")
        retiro = RetiroStarken(
            rs_codigo="RET-QA-EXISTENTE",
            punto_retiro_id=self.local.id,
            rs_fecha_retiro=ahora_chile() - timedelta(hours=1),
            rs_fecha_confirmacion=ahora_chile(),
        )
        self.db.add(retiro)
        self.db.flush()
        self.db.add(RetiroEnvio(
            retiro_id=retiro.id,
            envio_id=retirado.id,
            re_bultos_snapshot=2,
            re_fecha_asociacion=ahora_chile(),
        ))
        self.db.commit()
        self._autenticar()

        html = self.client.get("/operacion/retiros").get_data(as_text=True)
        self.assertIn(visible.e_orden_flete, html)
        self.assertIn("1 env&iacute;o &middot; 7 bultos", html)
        self.assertNotIn("OF-LEGACY", html)
        self.assertNotIn("OF-ACADEMIA", html)
        self.assertNotIn("OF-RETIRADO", html)

    def test_busqueda_combina_of_remitente_y_destinatario(self):
        self._envio("BASE", e_orden_flete="90001234", e_remitente="Ana Buscar", e_destinatario="Tienda Norte")
        self._envio("OTRO", e_orden_flete="80009999", e_remitente="Juan", e_destinatario="Tienda Sur")
        self.db.commit()
        self._autenticar()

        for termino, esperado, ausente in (
            ("90001234", "Tienda Norte", "Tienda Sur"),
            ("ana buscar", "90001234", "80009999"),
            ("tienda sur", "80009999", "90001234"),
        ):
            with self.subTest(termino=termino):
                html = self.client.get("/operacion/retiros", query_string={"q": termino}).get_data(as_text=True)
                self.assertIn(esperado, html)
                self.assertNotIn(ausente, html)

    def test_pagina_en_25_y_publica_seleccion_global_del_filtro(self):
        for indice in range(30):
            self._envio(f"VOLUMEN-{indice:02d}", e_bultos=3)
        self.db.commit()
        self._autenticar()
        html_1 = self.client.get("/operacion/retiros").get_data(as_text=True)
        html_2 = self.client.get("/operacion/retiros?pagina=2").get_data(as_text=True)
        self.assertEqual(html_1.count('class="form-check-input retiro-checkbox"'), 25)
        self.assertEqual(html_2.count('class="form-check-input retiro-checkbox"'), 5)
        self.assertIn("Seleccionar todos los 30 resultados", html_1)
        self.assertIn("P&aacute;gina 1 de 2", html_1)

    def test_seleccion_vacia_y_csrf_son_rechazados(self):
        self._autenticar()
        sin_csrf = self.client.post("/operacion/retiros/confirmar", data={})
        self.assertEqual(sin_csrf.status_code, 400)
        respuesta = self._post_confirmar([])
        self.assertIn("Debes seleccionar al menos un envio", respuesta.get_data(as_text=True))
        self.assertEqual(self.db.query(RetiroStarken).count(), 0)

    def test_confirmacion_individual_recibe_fecha_y_responsable_de_sesion(self):
        envio = self._envio("INDIVIDUAL", e_bultos=4)
        self.db.commit()
        self._autenticar()
        fecha = (ahora_chile() - timedelta(minutes=8)).replace(second=0, microsecond=0)

        with patch.object(retiros_routes, "confirmar_retiro", return_value=SimpleNamespace(id=999, rs_codigo="RET-TEST")) as confirmar:
            respuesta = self._post_confirmar(
                [envio.id],
                fecha_retiro=fecha.strftime("%Y-%m-%dT%H:%M"),
                responsable="Responsable manipulado",
            )

        self.assertEqual(respuesta.status_code, 200)
        args, kwargs = confirmar.call_args
        self.assertEqual(args[1], [str(envio.id)])
        self.assertEqual(args[2], fecha)
        self.assertEqual(kwargs["responsable"], "Operador Mensajeria")

    def test_confirmacion_multiple_persiste_total_y_actualiza_cola(self):
        primero = self._envio("PRIMERO", e_bultos=3)
        segundo = self._envio("SEGUNDO", e_bultos=6)
        tercero = self._envio("NO-SELECCIONADO", e_bultos=2)
        self.db.commit()
        ids = [primero.id, segundo.id]
        self._autenticar()

        respuesta = self._post_confirmar(ids)
        html = respuesta.get_data(as_text=True)
        self.assertEqual(self.db.query(RetiroStarken).count(), 1)
        asociaciones = self.db.query(RetiroEnvio).all()
        self.assertEqual({item.envio_id for item in asociaciones}, set(ids))
        self.assertEqual(sum(item.re_bultos_snapshot for item in asociaciones), 9)
        self.assertIn("2 envios \u00b7 9 bultos", html)
        self.assertNotIn("OF-PRIMERO", html)
        self.assertNotIn("OF-SEGUNDO", html)
        self.assertIn(tercero.e_orden_flete, html)

    def test_errores_de_dominio_y_concurrencia_son_comprensibles(self):
        envio = self._envio("ERROR")
        self.db.commit()
        self._autenticar()
        casos = (
            (RetiroValidacionError("Seleccion no elegible"), "Seleccion no elegible"),
            (RetiroConcurrenciaError("colision"), "ya fueron retirados o dejaron de ser elegibles"),
        )
        for error, mensaje in casos:
            with self.subTest(error=type(error).__name__), patch.object(
                retiros_routes, "confirmar_retiro", side_effect=error
            ):
                html = self._post_confirmar([envio.id]).get_data(as_text=True)
                self.assertIn(mensaje, html)
        self.assertEqual(self.db.query(RetiroStarken).count(), 0)

    def test_estado_vacio_explica_cuando_aparecen_envios(self):
        self._autenticar()
        html = self.client.get("/operacion/retiros").get_data(as_text=True)
        self.assertIn("No hay env&iacute;os listos para retiro", html)
        self.assertIn("una OF procesada correctamente", html)

    def test_template_conserva_accesibilidad_y_seleccion_multipagina(self):
        template = (PROJECT_DIR / "templates" / "retiros_listos.html").read_text(encoding="utf-8")
        javascript = (PROJECT_DIR / "static" / "js" / "retiros.js").read_text(encoding="utf-8")
        self.assertIn('aria-label="Seleccionar OF', template)
        self.assertIn('aria-labelledby="confirmarRetiroTitulo"', template)
        self.assertIn('type="datetime-local"', template)
        self.assertIn('name="csrf_token"', template)
        self.assertIn("sessionStorage", javascript)
        self.assertIn("filtrados.forEach", javascript)
        self.assertIn('input.name = "envio_ids"', javascript)


if __name__ == "__main__":
    unittest.main()
