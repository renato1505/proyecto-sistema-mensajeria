"""Entrada local y Gunicorn: contrato versionado obligatorio, sin auto-reparación."""
from aplicacion import crear_app
from config.settings import FLASK_DEBUG

app = crear_app()

if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG)
