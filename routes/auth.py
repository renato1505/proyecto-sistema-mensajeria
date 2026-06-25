import hmac
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from config.settings import (
    APP_ACCESS_PASSWORD,
    APP_USERS,
    LOGIN_REQUIRED,
    SESSION_TIMEOUT_MINUTES,
)
from database.conexion import SessionLocal
from database.modelos import UsuarioSistema
from services.auditoria import registrar_accion
from services.permisos import permiso_para_ruta, usuario_puede
from services.recuperacion import crear_solicitud_recuperacion
from utils.fechas import ahora_chile
from utils.validaciones import clave_rut_usuario, normalizar_rut_usuario


USUARIOS_POR_DEFECTO = ["mensajeria", "recepcion", "seguridad"]
AREA_POR_DEFECTO = "mensajeria"
INTENTOS_LOGIN = {}
MAX_INTENTOS_LOGIN = 5
BLOQUEO_LOGIN_SEGUNDOS = 10 * 60


@dataclass(frozen=True)
class UsuarioAcceso:
    usuario: str
    clave: str
    area: str = AREA_POR_DEFECTO
    rol: str = "usuario"
    nombre: str = ""
    debe_cambiar_clave: bool = False


def login_habilitado():
    return LOGIN_REQUIRED


def usuario_autenticado():
    if not LOGIN_REQUIRED:
        return True

    return bool(session.get("usuario_autenticado"))


def usuario_es_admin():
    if not LOGIN_REQUIRED:
        return True

    return session.get("usuario_rol") == "admin"


def usuario_tiene_permiso(permiso):
    if not LOGIN_REQUIRED:
        return True
    return usuario_puede(session.get("usuario_area"), session.get("usuario_rol"), permiso)


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
            usuarios[fila.u_usuario] = UsuarioAcceso(
                usuario=fila.u_usuario,
                clave=fila.u_clave_hash,
                area=fila.u_area,
                rol=fila.u_rol,
                nombre=fila.u_nombre,
                debe_cambiar_clave=bool(fila.u_debe_cambiar_clave),
            )
    except Exception:
        usuarios = {}
    finally:
        db.close()

    return usuarios


def obtener_usuarios_configurados():
    usuarios = _usuarios_desde_bd()

    for item in (APP_USERS or "").split(";"):
        item = item.strip()
        if not item:
            continue

        if "|" in item:
            partes = item.split("|", 3)
            if len(partes) == 4:
                usuario, area, rol, clave = partes
            elif len(partes) == 3:
                usuario, area, clave = partes
                rol = "usuario"
            else:
                continue
        elif ":" in item:
            usuario, clave = item.split(":", 1)
            area = AREA_POR_DEFECTO
            rol = "usuario"
        else:
            continue

        usuario = usuario.strip().lower()
        area = (area or AREA_POR_DEFECTO).strip().lower()
        rol = (rol or "usuario").strip().lower()
        if rol not in {"visita", "usuario", "supervisor", "admin"}:
            rol = "usuario"
        clave = clave.strip()

        if usuario and clave and usuario not in usuarios:
            usuarios[usuario] = UsuarioAcceso(usuario=usuario, clave=clave, area=area, rol=rol, nombre=usuario)

    if not usuarios and APP_ACCESS_PASSWORD:
        usuarios["mensajeria"] = UsuarioAcceso(
            usuario="mensajeria",
            clave=APP_ACCESS_PASSWORD,
            area=AREA_POR_DEFECTO,
            rol="usuario",
            nombre="mensajeria",
        )

    return usuarios


def etiqueta_area(area):
    etiquetas = {
        "mensajeria": "Mensajeria",
        "recepcion": "Recepcion",
        "seguridad": "Seguridad",
        "administracion": "Administracion",
        "admin": "Admin",
    }
    return etiquetas.get((area or "").strip().lower(), (area or AREA_POR_DEFECTO).title())


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


def _registrar_permiso_denegado(permiso):
    usuario = session.get("usuario_nombre") or "sistema"
    db = SessionLocal()
    try:
        registrar_accion(
            db,
            "permiso_denegado",
            "seguridad",
            permiso,
            f"Ruta: {request.path}. Metodo: {request.method}.",
            usuario=usuario,
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _registrar_solicitud_recuperacion(usuario, rut):
    usuario = (usuario or "").strip().lower()
    rut = normalizar_rut_usuario(rut)

    db = SessionLocal()
    try:
        usuario_db = db.query(UsuarioSistema).filter(UsuarioSistema.u_usuario == usuario).first()
        if not usuario_db or clave_rut_usuario(usuario_db.u_rut) != clave_rut_usuario(rut):
            registrar_accion(
                db,
                "solicitud_recuperacion_rechazada",
                "usuario",
                usuario or "sin_usuario",
                f"RUT no coincide o usuario inexistente. IP: {_ip_cliente()}.",
                usuario=usuario or "sistema",
            )
            db.commit()
            return False

        crear_solicitud_recuperacion(db, usuario, "", _ip_cliente(), rut)
        registrar_accion(
            db,
            "solicitud_recuperacion",
            "usuario",
            usuario or "sin_usuario",
            f"Solicitud de cambio de clave validada con RUT. IP: {_ip_cliente()}.",
            usuario=usuario or "sistema",
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
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


def bloqueos_por_usuario():
    resumen = {}
    for bloqueo in listar_bloqueos_login():
        usuario = (bloqueo.get("usuario") or "").strip().lower()
        if not usuario:
            continue
        resumen.setdefault(usuario, {"intentos": 0, "bloqueado": False})
        resumen[usuario]["intentos"] = max(resumen[usuario]["intentos"], bloqueo.get("intentos", 0))
        resumen[usuario]["bloqueado"] = resumen[usuario]["bloqueado"] or bool(bloqueo.get("bloqueado"))
    return resumen


def desbloquear_login(clave_intentos):
    clave_intentos = (clave_intentos or "").strip()
    if not clave_intentos:
        return False
    return INTENTOS_LOGIN.pop(clave_intentos, None) is not None


def metricas_seguridad_login():
    bloqueos = listar_bloqueos_login()
    return {
        "intentos": len(bloqueos),
        "bloqueos": sum(1 for item in bloqueos if item["bloqueado"]),
        "max_intentos": MAX_INTENTOS_LOGIN,
        "bloqueo_minutos": max(1, BLOQUEO_LOGIN_SEGUNDOS // 60),
    }


def actualizar_politica_login(max_intentos, bloqueo_minutos):
    global MAX_INTENTOS_LOGIN, BLOQUEO_LOGIN_SEGUNDOS

    try:
        max_intentos = int(max_intentos)
        bloqueo_minutos = int(bloqueo_minutos)
    except (TypeError, ValueError):
        raise ValueError("La politica debe usar numeros validos.")

    if max_intentos < 3 or max_intentos > 10:
        raise ValueError("Los intentos deben estar entre 3 y 10.")
    if bloqueo_minutos < 1 or bloqueo_minutos > 120:
        raise ValueError("La duracion debe estar entre 1 y 120 minutos.")

    MAX_INTENTOS_LOGIN = max_intentos
    BLOQUEO_LOGIN_SEGUNDOS = bloqueo_minutos * 60


def _clave_es_hash(valor):
    return str(valor or "").startswith(("pbkdf2:", "scrypt:"))


def verificar_clave_usuario(clave_ingresada, clave_configurada):
    if not clave_configurada:
        return False

    if _clave_es_hash(clave_configurada):
        try:
            return check_password_hash(clave_configurada, clave_ingresada)
        except ValueError:
            return False

    return hmac.compare_digest(clave_ingresada, clave_configurada)


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

        rutas_publicas = {"login", "solicitar_recuperacion", "static"}
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

        permiso = permiso_para_ruta(request.path, request.method)
        if permiso and not usuario_tiene_permiso(permiso):
            _registrar_permiso_denegado(permiso)
            flash("No tienes permisos para acceder a esa seccion.", "danger")
            if usuario_es_admin():
                return redirect("/admin")
            return redirect("/")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not LOGIN_REQUIRED:
            return redirect("/")

        usuarios = obtener_usuarios_configurados()

        if request.method == "POST":
            usuario = request.form.get("usuario", "").strip().lower()
            clave = request.form.get("clave", "")
            usuario_configurado = usuarios.get(usuario)
            clave_esperada = usuario_configurado.clave if usuario_configurado else ""
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
                return render_template("login.html", usuarios_login=nombres_usuarios_login())

            if verificar_clave_usuario(clave, clave_esperada):
                session.clear()
                session.permanent = True
                session["usuario_autenticado"] = True
                session["usuario_nombre"] = usuario
                session["usuario_area"] = usuario_configurado.area
                session["usuario_area_base"] = usuario_configurado.area
                session["usuario_rol"] = usuario_configurado.rol
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
                return render_template("login.html", usuarios_login=nombres_usuarios_login())

            _registrar_evento_login(
                usuario,
                "login_fallido",
                f"Credenciales incorrectas desde IP {_ip_cliente()}.",
            )
            flash("Usuario o clave incorrectos.", "danger")

        if not usuarios:
            flash("Los usuarios de acceso no estan configurados.", "danger")

        return render_template("login.html", usuarios_login=nombres_usuarios_login())

    @app.route("/cambiar_clave", methods=["GET", "POST"])
    def cambiar_clave_obligatoria():
        if not session.get("usuario_autenticado"):
            return redirect(url_for("login", next=request.path))

        usuario = session.get("usuario_nombre", "")

        if request.method == "POST":
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

                if verificar_clave_usuario(clave, usuario_db.u_clave_hash):
                    flash("La nueva clave debe ser distinta a la clave temporal.", "warning")
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

    @app.route("/login/recuperar", methods=["POST"])
    def solicitar_recuperacion():
        usuario = request.form.get("usuario_recuperacion", "").strip().lower()
        rut = request.form.get("rut_recuperacion", "").strip()

        if not usuario or not rut:
            flash("Completa usuario y RUT para solicitar soporte.", "warning")
            return redirect(url_for("login"))

        if not _registrar_solicitud_recuperacion(usuario, rut):
            flash("No se pudo validar la solicitud. Revisa usuario y RUT o contacta al administrador.", "danger")
            return redirect(url_for("login"))

        flash("Solicitud registrada. El administrador podra generar una clave temporal.", "info")
        return redirect(url_for("login"))

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("Sesion cerrada correctamente.", "info")
        return redirect("/login" if LOGIN_REQUIRED else "/")
