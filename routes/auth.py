import logging
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from config.settings import LOGIN_REQUIRED, SESSION_TIMEOUT_MINUTES
from database.conexion import SessionLocal
from database.modelos import UsuarioSistema
from services.auditoria import registrar_accion
from utils.fechas import ahora_chile


logger = logging.getLogger(__name__)
INTENTOS_LOGIN = {}
MAX_INTENTOS_LOGIN = 5
BLOQUEO_LOGIN_SEGUNDOS = 10 * 60


@dataclass(frozen=True)
class UsuarioAcceso:
    usuario: str
    clave_hash: str
    nombre: str = ""
    debe_cambiar_clave: bool = False


def login_habilitado():
    return LOGIN_REQUIRED


def usuario_autenticado():
    if not LOGIN_REQUIRED:
        return True

    return bool(session.get("usuario_autenticado"))


def _usuarios_desde_bd():
    usuarios = {}
    db = SessionLocal()
    try:
        filas = (
            db.query(UsuarioSistema)
            .filter(UsuarioSistema.u_activo.is_(True))
            .order_by(UsuarioSistema.u_usuario.asc())
            .all()
        )
        for fila in filas:
            if not _clave_es_hash(fila.u_clave_hash):
                logger.warning(
                    "Usuario activo '%s' tiene una clave sin hash Werkzeug reconocido; requiere reset externo.",
                    fila.u_usuario,
                )
            usuarios[fila.u_usuario] = UsuarioAcceso(
                usuario=fila.u_usuario,
                clave_hash=fila.u_clave_hash,
                nombre=fila.u_nombre,
                debe_cambiar_clave=bool(fila.u_debe_cambiar_clave),
            )
    finally:
        db.close()

    return usuarios


def obtener_usuarios_configurados():
    return _usuarios_desde_bd()


def _clave_intentos_login(usuario):
    ip = _ip_cliente()
    return f"{ip}:{usuario}"


def _ip_cliente():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "local").split(",")[0].strip()


def _segundos_bloqueo_restantes(clave_intentos):
    datos = INTENTOS_LOGIN.get(clave_intentos)
    if not datos:
        return 0

    bloqueado_hasta = datos.get("bloqueado_hasta", 0)
    if not bloqueado_hasta:
        return 0

    restante = int(bloqueado_hasta - time.time())
    if restante <= 0:
        INTENTOS_LOGIN.pop(clave_intentos, None)
        return 0

    return restante


def _registrar_intento_fallido(clave_intentos):
    datos = INTENTOS_LOGIN.setdefault(clave_intentos, {"intentos": 0, "bloqueado_hasta": 0})
    datos["intentos"] += 1
    if datos["intentos"] >= MAX_INTENTOS_LOGIN:
        datos["bloqueado_hasta"] = time.time() + BLOQUEO_LOGIN_SEGUNDOS
        return True
    return False


def _limpiar_intentos_login(clave_intentos):
    INTENTOS_LOGIN.pop(clave_intentos, None)


def _registrar_evento_login(usuario, accion, detalle):
    db = SessionLocal()
    try:
        registrar_accion(db, accion, "login", usuario or "sin_usuario", detalle, usuario=usuario or "sistema")
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _actualizar_ultimo_acceso(usuario):
    db = SessionLocal()
    try:
        fila = db.query(UsuarioSistema).filter(UsuarioSistema.u_usuario == usuario).first()
        if fila:
            fila.u_ultimo_acceso = ahora_chile()
            fila.u_ultimo_ip = _ip_cliente()
            fila.u_fecha_actualizacion = ahora_chile()
        registrar_accion(
            db,
            "login_exitoso",
            "login",
            usuario,
            f"Acceso correcto desde IP {_ip_cliente()}.",
            usuario=usuario,
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def listar_bloqueos_login():
    bloqueos = []
    for clave, datos in list(INTENTOS_LOGIN.items()):
        restante = _segundos_bloqueo_restantes(clave)
        if clave not in INTENTOS_LOGIN:
            continue

        ip, usuario = clave.rsplit(":", 1) if ":" in clave else ("", clave)
        bloqueos.append(
            {
                "clave": clave,
                "ip": ip,
                "usuario": usuario,
                "intentos": int(datos.get("intentos", 0)),
                "bloqueado": bool(restante),
                "restante": restante,
                "restante_minutos": max(1, restante // 60) if restante else 0,
            }
        )

    return sorted(bloqueos, key=lambda item: (not item["bloqueado"], item["usuario"], item["ip"]))


def _clave_es_hash(valor):
    return str(valor or "").startswith(("pbkdf2:", "scrypt:"))


def verificar_clave_usuario(clave_ingresada, clave_configurada):
    if not clave_configurada or not _clave_es_hash(clave_configurada):
        return False

    try:
        return check_password_hash(clave_configurada, clave_ingresada)
    except ValueError:
        return False


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

        if session.get("debe_cambiar_clave") and request.endpoint not in {"cambiar_clave_obligatoria", "logout"}:
            return redirect(url_for("cambiar_clave_obligatoria"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not LOGIN_REQUIRED:
            return redirect("/")

        try:
            usuarios = obtener_usuarios_configurados()
        except Exception:
            logger.exception("No se pudo consultar usuarios_sistema durante el login.")
            flash("El servicio de acceso no esta disponible temporalmente.", "danger")
            return render_template("login.html"), 503

        if request.method == "POST":
            usuario = request.form.get("usuario", "").strip().lower()
            clave = request.form.get("clave", "")
            usuario_configurado = usuarios.get(usuario)
            clave_esperada = usuario_configurado.clave_hash if usuario_configurado else ""
            clave_intentos = _clave_intentos_login(usuario)
            bloqueo_restante = _segundos_bloqueo_restantes(clave_intentos)

            if bloqueo_restante:
                minutos = max(1, bloqueo_restante // 60)
                _registrar_evento_login(
                    usuario,
                    "login_bloqueado",
                    f"Intento bloqueado desde IP {_ip_cliente()}. Restan {minutos} minuto(s).",
                )
                flash(f"Acceso bloqueado temporalmente. Intenta nuevamente en {minutos} minuto(s).", "danger")
                return render_template("login.html")

            if verificar_clave_usuario(clave, clave_esperada):
                session.clear()
                session.permanent = True
                session["usuario_autenticado"] = True
                session["usuario_nombre"] = usuario
                session["usuario_display"] = usuario_configurado.nombre or usuario
                session["debe_cambiar_clave"] = bool(usuario_configurado.debe_cambiar_clave)
                session["ultima_actividad"] = time.time()
                _limpiar_intentos_login(clave_intentos)
                _actualizar_ultimo_acceso(usuario)
                flash("Acceso iniciado correctamente.", "success")
                if usuario_configurado.debe_cambiar_clave:
                    return redirect(url_for("cambiar_clave_obligatoria"))
                return redirect(_destino_login_seguro(request.args.get("next")))

            bloqueo_activado = _registrar_intento_fallido(clave_intentos)
            if bloqueo_activado:
                _registrar_evento_login(
                    usuario,
                    "login_bloqueado",
                    f"Bloqueo activado desde IP {_ip_cliente()} tras {MAX_INTENTOS_LOGIN} intento(s).",
                )
                flash(
                    f"Acceso bloqueado temporalmente por {max(1, BLOQUEO_LOGIN_SEGUNDOS // 60)} minuto(s).",
                    "danger",
                )
                return render_template("login.html")

            _registrar_evento_login(
                usuario,
                "login_fallido",
                f"Credenciales incorrectas desde IP {_ip_cliente()}.",
            )
            flash("Usuario o clave incorrectos.", "danger")

        if not usuarios:
            flash("Los usuarios de acceso no estan configurados.", "danger")

        return render_template("login.html")

    @app.route("/cambiar_clave", methods=["GET", "POST"])
    def cambiar_clave_obligatoria():
        if not session.get("usuario_autenticado"):
            return redirect(url_for("login", next=request.path))

        usuario = session.get("usuario_nombre", "")

        if request.method == "POST":
            clave_actual = request.form.get("clave_actual", "")
            clave = request.form.get("clave", "")
            confirmar = request.form.get("confirmar_clave", "")

            if clave != confirmar:
                flash("Las claves ingresadas no coinciden.", "danger")
                return render_template("cambiar_clave.html")

            db = SessionLocal()
            try:
                usuario_db = db.query(UsuarioSistema).filter(UsuarioSistema.u_usuario == usuario).first()
                if not usuario_db:
                    flash("No se encontro el usuario en la base de datos.", "danger")
                    return render_template("cambiar_clave.html")

                if not verificar_clave_usuario(clave_actual, usuario_db.u_clave_hash):
                    flash("La clave actual no es correcta.", "danger")
                    return render_template("cambiar_clave.html")

                if verificar_clave_usuario(clave, usuario_db.u_clave_hash):
                    flash("La nueva clave debe ser distinta a la clave actual.", "warning")
                    return render_template("cambiar_clave.html")

                from services.usuarios import cambiar_clave_propia

                cambiar_clave_propia(usuario_db, clave)
                registrar_accion(
                    db,
                    "cambiar_clave_propia",
                    "usuario",
                    usuario,
                    "Clave temporal reemplazada por el usuario.",
                    usuario=usuario,
                )
                db.commit()
                session["debe_cambiar_clave"] = False
                flash("Clave actualizada correctamente.", "success")
                return redirect("/")
            except ValueError as exc:
                db.rollback()
                flash(str(exc), "warning")
            except Exception:
                db.rollback()
                flash("No se pudo actualizar la clave.", "danger")
            finally:
                db.close()

        return render_template("cambiar_clave.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("Sesion cerrada correctamente.", "info")
        return redirect("/login" if LOGIN_REQUIRED else "/")
