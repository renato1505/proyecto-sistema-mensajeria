"""Construcción de Flask con validación previa de esquema, sin reparaciones."""
from datetime import timedelta
import logging

from flask import Flask, session

from config.logging_config import configurar_logging
from config.settings import BASE_DIR, ES_PRODUCCION, SECRET_KEY, SESSION_TIMEOUT_MINUTES
from database.conexion import engine
from database.validacion_esquema import CONTRATO_V2, contrato_fixture_sqlite, validar_esquema
from routes.auth import login_habilitado, registrar_rutas_auth
from routes.avisos import registrar_rutas_avisos
from routes.carga_masiva import registrar_rutas_carga_masiva
from routes.catalogos import registrar_rutas_catalogos
from routes.catalogos_ajax import registrar_rutas_catalogos_ajax
from routes.configuracion import registrar_rutas_configuracion
from routes.envios import registrar_rutas_envios
from routes.historico import registrar_rutas_historico
from routes.historico_ajax import registrar_rutas_historico_ajax
from routes.paginas import registrar_rutas_paginas
from routes.retiros import registrar_rutas_retiros
from routes.starken_lotes import registrar_rutas_starken_lotes
from utils.csrf import obtener_csrf_token, validar_csrf


class ArranqueIncompatible(RuntimeError):
    """La aplicación no debe atender solicitudes con este esquema."""


def crear_app(*, contrato=CONTRATO_V2):
    app = Flask("main", root_path=str(BASE_DIR))
    app.secret_key = SECRET_KEY
    app.permanent_session_lifetime = timedelta(minutes=max(1, SESSION_TIMEOUT_MINUTES))
    configurar_logging()
    app.logger.setLevel(logging.INFO)

    def rechazar(estado, detalle):
        mensaje = f"Arranque rechazado [{estado}]: {detalle}"
        app.logger.error(mensaje)
        raise ArranqueIncompatible(mensaje) from None

    # main:app usa siempre CONTRATO_V2. La excepción requiere una llamada Python
    # explícita y el contrato exacto de fixture; no se selecciona desde APP_ENV,
    # variables de entorno, un fallo de validación o una revisión ausente.
    if contrato != CONTRATO_V2:
        if (contrato != contrato_fixture_sqlite() or ES_PRODUCCION
                or engine.dialect.name != "sqlite"
                or engine.url.database not in (None, "", ":memory:")):
            rechazar("CONTRATO_NO_PERMITIDO",
                     "El contrato de fixture solo admite SQLite en memoria fuera de producción.")

    resultado = validar_esquema(engine, contrato)
    if not resultado.compatible:
        detalle = " ".join(h.mensaje for h in resultado.hallazgos)
        rechazar(resultado.estado, detalle)

    @app.before_request
    def proteger_formularios_post():
        validar_csrf()

    @app.context_processor
    def inyectar_csrf_token():
        return {"csrf_token": obtener_csrf_token}

    @app.context_processor
    def inyectar_estado_auth():
        return {
            "login_habilitado": login_habilitado(),
            "usuario_actual": session.get("usuario_nombre", ""),
            "usuario_display": session.get("usuario_display", session.get("usuario_nombre", "")),
        }

    registrar_rutas_auth(app)
    registrar_rutas_configuracion(app)
    registrar_rutas_paginas(app)
    registrar_rutas_retiros(app)
    registrar_rutas_envios(app)
    registrar_rutas_catalogos(app)
    registrar_rutas_catalogos_ajax(app)
    registrar_rutas_avisos(app)
    registrar_rutas_carga_masiva(app)
    registrar_rutas_historico(app)
    registrar_rutas_historico_ajax(app)
    registrar_rutas_starken_lotes(app)
    app.logger.info("Portal Operativo iniciado")
    return app
