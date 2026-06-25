from flask import flash, redirect, request, session

from database.conexion import SessionLocal
from database.modelos import SolicitudRecuperacionClave, UsuarioSistema
from routes.admin_helpers import requiere_admin
from routes.auth import actualizar_politica_login, desbloquear_login
from services.auditoria import registrar_accion
from services.recuperacion import (
    generar_clave_temporal,
    rechazar_solicitud,
    resolver_solicitud_con_clave,
)
from services.usuarios import cambiar_clave_usuario


def registrar_rutas_admin_seguridad(app):
    @app.route("/admin/seguridad/desbloquear", methods=["POST"])
    def admin_desbloquear_login():
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        clave_bloqueo = request.form.get("clave_bloqueo", "").strip()

        db = SessionLocal()
        try:
            liberado = desbloquear_login(clave_bloqueo)
            registrar_accion(
                db,
                "desbloquear_login",
                "seguridad",
                clave_bloqueo,
                "Bloqueo liberado por administrador." if liberado else "No existia bloqueo activo.",
            )
            db.commit()
            if liberado:
                flash("Bloqueo de acceso liberado correctamente.", "success")
            else:
                flash("No habia un bloqueo activo para liberar.", "info")
        except Exception:
            db.rollback()
            flash("No se pudo liberar el bloqueo de acceso.", "danger")
        finally:
            db.close()

        return redirect("/admin?tab=seguridad")

    @app.route("/admin/seguridad/politica", methods=["POST"])
    def admin_actualizar_politica_login():
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        max_intentos = request.form.get("max_intentos", "")
        bloqueo_minutos = request.form.get("bloqueo_minutos", "")

        db = SessionLocal()
        try:
            actualizar_politica_login(max_intentos, bloqueo_minutos)
            registrar_accion(
                db,
                "actualizar_politica_login",
                "seguridad",
                "",
                f"Intentos: {max_intentos}. Duracion: {bloqueo_minutos} min.",
            )
            db.commit()
            flash("Politica de acceso actualizada para el servidor actual.", "success")
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "warning")
        except Exception:
            db.rollback()
            flash("No se pudo actualizar la politica de acceso.", "danger")
        finally:
            db.close()

        return redirect("/admin?tab=seguridad")

    @app.route("/admin/recuperacion/<int:solicitud_id>/rechazar", methods=["POST"])
    def admin_rechazar_solicitud_recuperacion(solicitud_id):
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        admin_usuario = session.get("usuario_nombre") or "admin"

        db = SessionLocal()
        try:
            solicitud = db.query(SolicitudRecuperacionClave).filter(SolicitudRecuperacionClave.id == solicitud_id).first()
            if not solicitud:
                flash("No se encontro la solicitud de recuperacion.", "warning")
                return redirect("/admin?tab=seguridad")

            if solicitud.sr_estado == "resuelta":
                flash("La solicitud ya fue resuelta.", "info")
                return redirect("/admin?tab=seguridad")

            rechazar_solicitud(solicitud, admin_usuario)
            registrar_accion(
                db,
                "rechazar_solicitud_recuperacion",
                "recuperacion",
                solicitud.id,
                f"Usuario: {solicitud.sr_usuario}. RUT validado: {solicitud.sr_rut or 'sin registro'}.",
            )
            db.commit()
            flash("Solicitud rechazada y retirada de pendientes.", "success")
        except Exception:
            db.rollback()
            flash("No se pudo actualizar la solicitud.", "danger")
        finally:
            db.close()

        return redirect("/admin?tab=seguridad")

    @app.route("/admin/recuperacion/<int:solicitud_id>/generar_clave", methods=["POST"])
    def admin_generar_clave_recuperacion(solicitud_id):
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        admin_usuario = session.get("usuario_nombre") or "admin"

        db = SessionLocal()
        try:
            solicitud = db.query(SolicitudRecuperacionClave).filter(SolicitudRecuperacionClave.id == solicitud_id).first()
            if not solicitud:
                flash("No se encontro la solicitud de recuperacion.", "warning")
                return redirect("/admin?tab=seguridad")

            if solicitud.sr_estado == "resuelta":
                flash("La solicitud ya fue resuelta.", "info")
                return redirect("/admin?tab=seguridad")

            usuario = db.query(UsuarioSistema).filter(UsuarioSistema.u_usuario == solicitud.sr_usuario).first()
            if not usuario:
                flash("No existe un usuario con ese nombre. Revisa la solicitud manualmente.", "warning")
                return redirect("/admin?tab=seguridad")

            clave_temporal = generar_clave_temporal()
            cambiar_clave_usuario(usuario, clave_temporal)
            resolver_solicitud_con_clave(solicitud, admin_usuario)
            registrar_accion(
                db,
                "generar_clave_recuperacion",
                "usuario",
                usuario.u_usuario,
                f"Solicitud: {solicitud.id}. RUT validado: {solicitud.sr_rut or 'sin registro'}.",
            )
            db.commit()
            flash(
                f"Clave temporal generada para {usuario.u_usuario}: {clave_temporal}. Entregala por canal interno seguro.",
                "success",
            )
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "warning")
        except Exception:
            db.rollback()
            flash("No se pudo generar la clave temporal.", "danger")
        finally:
            db.close()

        return redirect("/admin?tab=seguridad")
