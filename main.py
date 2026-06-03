from flask import Flask
from config.logging_config import configurar_logging
from config.settings import FLASK_DEBUG, SECRET_KEY
from database.conexion import engine
from database.modelos import Base
from routes.paginas import registrar_rutas_paginas
from routes.envios import registrar_rutas_envios
from routes.catalogos import registrar_rutas_catalogos
from utils.csrf import obtener_csrf_token, validar_csrf

app = Flask(__name__)
app.secret_key = SECRET_KEY
configurar_logging(app)


@app.before_request
def proteger_formularios_post():
    validar_csrf()


@app.context_processor
def inyectar_csrf_token():
    return {"csrf_token": obtener_csrf_token}

Base.metadata.create_all(bind=engine)

registrar_rutas_paginas(app)
registrar_rutas_envios(app)
registrar_rutas_catalogos(app)

if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG)
