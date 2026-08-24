from flask import render_template, session

from database.conexion import SessionLocal
from services.usuarios import obtener_usuario_por_nombre


def registrar_rutas_configuracion(app):
    @app.route("/configuracion")
    def configuracion():
        usuario = session.get("usuario_nombre", "")
        db = SessionLocal()
        try:
            usuario_db = obtener_usuario_por_nombre(db, usuario) if usuario else None
            cuenta = {
                "usuario": usuario or "No disponible",
                "nombre": (
                    usuario_db.u_nombre
                    if usuario_db
                    else session.get("usuario_display") or usuario or "No disponible"
                ),
                "ultimo_acceso": usuario_db.u_ultimo_acceso if usuario_db else None,
                "ultima_ip": usuario_db.u_ultimo_ip if usuario_db else None,
            }
            return render_template("configuracion.html", cuenta=cuenta)
        finally:
            db.close()
