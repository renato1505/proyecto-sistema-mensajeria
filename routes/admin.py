from flask import render_template, request, session

from database.conexion import SessionLocal
from routes.admin_auditoria import registrar_rutas_admin_auditoria
from routes.admin_helpers import requiere_admin
from routes.admin_seguridad import registrar_rutas_admin_seguridad
from routes.admin_usuarios import registrar_rutas_admin_usuarios
from services.admin_context import construir_contexto_admin


def registrar_rutas_admin(app):
    @app.route("/admin")
    def admin_panel():
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        db = SessionLocal()
        try:
            return render_template("admin.html", **construir_contexto_admin(db, request.args, session))
        finally:
            db.close()

    registrar_rutas_admin_auditoria(app)
    registrar_rutas_admin_seguridad(app)
    registrar_rutas_admin_usuarios(app)
