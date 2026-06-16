import hmac
import time
from urllib.parse import urlsplit

from flask import flash, redirect, render_template, request, session, url_for

from config.settings import (
    APP_ACCESS_PASSWORD,
    APP_USERS,
    LOGIN_REQUIRED,
    SESSION_TIMEOUT_MINUTES,
)


USUARIOS_POR_DEFECTO = ["mensajeria", "recepcion", "seguridad"]


def login_habilitado():
    return LOGIN_REQUIRED


def usuario_autenticado():
    if not LOGIN_REQUIRED:
        return True

    return bool(session.get("usuario_autenticado"))


def obtener_usuarios_configurados():
    usuarios = {}

    for item in (APP_USERS or "").split(";"):
        item = item.strip()
        if not item or ":" not in item:
            continue

        usuario, clave = item.split(":", 1)
        usuario = usuario.strip().lower()
        clave = clave.strip()

        if usuario and clave:
            usuarios[usuario] = clave

    if not usuarios and APP_ACCESS_PASSWORD:
        usuarios["mensajeria"] = APP_ACCESS_PASSWORD

    return usuarios


def nombres_usuarios_login():
    usuarios = obtener_usuarios_configurados()
    if usuarios:
        return list(usuarios.keys())

    return USUARIOS_POR_DEFECTO


def _destino_login_seguro(destino):
    destino = (destino or "").strip()
    if not destino:
        return "/"

    partes = urlsplit(destino)
    if partes.scheme or partes.netloc or not destino.startswith("/"):
        return "/"

    return destino


def _sesion_expirada():
    ultima_actividad = session.get("ultima_actividad")
    if not ultima_actividad:
        return False

    segundos_limite = max(1, SESSION_TIMEOUT_MINUTES) * 60
    return time.time() - float(ultima_actividad) > segundos_limite


def registrar_rutas_auth(app):
    @app.before_request
    def proteger_acceso():
        if not LOGIN_REQUIRED:
            return

        rutas_publicas = {"login", "static"}
        if request.endpoint in rutas_publicas:
            return

        if not session.get("usuario_autenticado"):
            return redirect(url_for("login", next=request.path))

        if _sesion_expirada():
            session.clear()
            flash("Sesion expirada por inactividad.", "info")
            return redirect(url_for("login", next=request.path))

        session["ultima_actividad"] = time.time()

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not LOGIN_REQUIRED:
            return redirect("/")

        usuarios = obtener_usuarios_configurados()

        if request.method == "POST":
            usuario = request.form.get("usuario", "").strip().lower()
            clave = request.form.get("clave", "")
            clave_esperada = usuarios.get(usuario, "")

            if clave_esperada and hmac.compare_digest(clave, clave_esperada):
                session.permanent = True
                session["usuario_autenticado"] = True
                session["usuario_nombre"] = usuario
                session["ultima_actividad"] = time.time()
                flash("Acceso iniciado correctamente.", "success")
                return redirect(_destino_login_seguro(request.args.get("next")))

            flash("Usuario o clave incorrectos.", "danger")

        if not usuarios:
            flash("Los usuarios de acceso no estan configurados.", "danger")

        return render_template("login.html", usuarios=nombres_usuarios_login())

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("Sesion cerrada correctamente.", "info")
        return redirect("/login" if LOGIN_REQUIRED else "/")
