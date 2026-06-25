from flask import flash, redirect, request

from routes.auth import usuario_es_admin


def requiere_admin():
    if usuario_es_admin():
        return None

    flash("No tienes permisos para acceder al administrador.", "danger")
    return redirect("/")


def confirmacion_usuario_valida(usuario, campo="confirmar_usuario"):
    confirmacion = request.form.get(campo, "").strip()
    return confirmacion == (usuario.u_usuario or "").strip()
