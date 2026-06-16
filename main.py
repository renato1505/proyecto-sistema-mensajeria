from datetime import timedelta

from flask import Flask, session
from config.logging_config import configurar_logging
from config.settings import FLASK_DEBUG, SECRET_KEY, SESSION_TIMEOUT_MINUTES
from database.conexion import engine
from database.modelos import Base
from database.schema import asegurar_columnas_operativas
from database.conexion import SessionLocal
from routes.paginas import registrar_rutas_paginas
from routes.auth import registrar_rutas_auth, login_habilitado
from routes.envios import registrar_rutas_envios
from routes.catalogos import registrar_rutas_catalogos
from routes.catalogos_ajax import registrar_rutas_catalogos_ajax
from routes.avisos import registrar_rutas_avisos
from routes.carga_masiva import registrar_rutas_carga_masiva
from routes.historico import registrar_rutas_historico
from routes.historico_ajax import registrar_rutas_historico_ajax
from routes.starken_lotes import registrar_rutas_starken_lotes
from services.avisos import contar_lotes_avisos_pendientes
from database.modelos import Envio
from utils.csrf import obtener_csrf_token, validar_csrf

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=max(1, SESSION_TIMEOUT_MINUTES))
configurar_logging(app)


@app.before_request
def proteger_formularios_post():
    validar_csrf()


@app.context_processor
def inyectar_csrf_token():
    return {"csrf_token": obtener_csrf_token}


@app.context_processor
def inyectar_contador_avisos():
    db = SessionLocal()
    try:
        return {
            "avisos_pendientes_count": contar_lotes_avisos_pendientes(db),
            "pendientes_count": db.query(Envio).filter(Envio.e_estado == "pendiente").count(),
            "en_proceso_count": db.query(Envio).filter(Envio.e_estado == "en_proceso").count(),
        }
    except Exception:
        return {
            "avisos_pendientes_count": 0,
            "pendientes_count": 0,
            "en_proceso_count": 0,
        }
    finally:
        db.close()

@app.context_processor
def inyectar_estado_auth():
    return {
        "login_habilitado": login_habilitado(),
        "usuario_actual": session.get("usuario_nombre", ""),
    }

Base.metadata.create_all(bind=engine)
asegurar_columnas_operativas()

registrar_rutas_auth(app)
registrar_rutas_paginas(app)
registrar_rutas_envios(app)
registrar_rutas_catalogos(app)
registrar_rutas_catalogos_ajax(app)
registrar_rutas_avisos(app)
registrar_rutas_carga_masiva(app)
registrar_rutas_historico(app)
registrar_rutas_historico_ajax(app)
registrar_rutas_starken_lotes(app)

if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG)
