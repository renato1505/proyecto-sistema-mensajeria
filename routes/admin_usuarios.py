from flask import flash, redirect, request, session

from database.conexion import SessionLocal
from database.modelos import AreaOperativa, UsuarioSistema
from routes.admin_helpers import confirmacion_usuario_valida, requiere_admin
from services.auditoria import registrar_accion
from services.usuarios import (
    asegurar_area,
    actualizar_area,
    actualizar_usuario,
    cambiar_clave_usuario,
    cambiar_estado_usuario,
    crear_usuario,
    eliminar_area,
    es_ultimo_admin_activo,
)


def registrar_rutas_admin_usuarios(app):
    @app.route("/admin/areas", methods=["POST"])
    def admin_crear_area():
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        nombre = request.form.get("nombre", "").strip()

        db = SessionLocal()
        try:
            area = asegurar_area(db, nombre, nombre)
            registrar_accion(db, "crear_area", "area", area.ar_codigo, f"Nombre: {area.ar_nombre}")
            db.commit()
            flash("Area guardada correctamente.", "success")
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "warning")
        except Exception:
            db.rollback()
            flash("No se pudo guardar el area.", "danger")
        finally:
            db.close()

        return redirect("/admin?tab=usuarios")

    @app.route("/admin/areas/<int:area_id>/editar", methods=["POST"])
    def admin_editar_area(area_id):
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        nombre = request.form.get("nombre", "").strip()

        db = SessionLocal()
        try:
            area = db.query(AreaOperativa).filter(AreaOperativa.id == area_id).first()
            if not area:
                flash("No se encontro el area.", "warning")
                return redirect("/admin?tab=usuarios")

            nombre_anterior = area.ar_nombre
            actualizar_area(area, nombre)
            registrar_accion(
                db,
                "editar_area",
                "area",
                area.ar_codigo,
                f"Nombre anterior: {nombre_anterior}. Nombre nuevo: {area.ar_nombre}.",
            )
            db.commit()
            flash("Area actualizada correctamente.", "success")
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "warning")
        except Exception:
            db.rollback()
            flash("No se pudo actualizar el area.", "danger")
        finally:
            db.close()

        return redirect("/admin?tab=usuarios")

    @app.route("/admin/areas/<int:area_id>/eliminar", methods=["POST"])
    def admin_eliminar_area(area_id):
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        db = SessionLocal()
        try:
            area = db.query(AreaOperativa).filter(AreaOperativa.id == area_id).first()
            if not area:
                flash("No se encontro el area.", "warning")
                return redirect("/admin?tab=usuarios")

            codigo = area.ar_codigo
            nombre = area.ar_nombre
            eliminar_area(db, area)
            registrar_accion(db, "eliminar_area", "area", codigo, f"Nombre: {nombre}.")
            db.commit()
            flash("Area eliminada correctamente.", "success")
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "warning")
        except Exception:
            db.rollback()
            flash("No se pudo eliminar el area.", "danger")
        finally:
            db.close()

        return redirect("/admin?tab=usuarios")

    @app.route("/admin/usuarios", methods=["POST"])
    def admin_crear_usuario():
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        data = {
            "usuario": request.form.get("usuario", "").strip(),
            "nombre": request.form.get("nombre", "").strip(),
            "rut": request.form.get("rut", "").strip(),
            "clave": request.form.get("clave", ""),
            "area": request.form.get("area", "").strip(),
            "rol": request.form.get("rol", "usuario").strip(),
        }

        db = SessionLocal()
        try:
            asegurar_area(db, data["area"])
            usuario = crear_usuario(
                db,
                data["usuario"],
                data["nombre"],
                data["rut"],
                data["clave"],
                data["area"],
                data["rol"],
            )
            registrar_accion(
                db,
                "crear_usuario",
                "usuario",
                usuario.u_usuario,
                f"Area: {usuario.u_area}. Rol: {usuario.u_rol}",
            )
            db.commit()
            flash("Usuario creado correctamente.", "success")
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "warning")
        except Exception:
            db.rollback()
            flash("No se pudo crear el usuario.", "danger")
        finally:
            db.close()

        return redirect("/admin?tab=usuarios")

    @app.route("/admin/usuarios/<int:usuario_id>/editar", methods=["POST"])
    def admin_editar_usuario(usuario_id):
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        data = {
            "nombre": request.form.get("nombre", "").strip(),
            "rut": request.form.get("rut", "").strip(),
            "area": request.form.get("area", "").strip(),
            "rol": request.form.get("rol", "usuario").strip(),
        }

        db = SessionLocal()
        try:
            usuario = db.query(UsuarioSistema).filter(UsuarioSistema.id == usuario_id).first()
            if not usuario:
                flash("No se encontro el usuario.", "warning")
                return redirect("/admin?tab=usuarios")

            if es_ultimo_admin_activo(db, usuario) and data["rol"] != "admin":
                flash("No puedes quitar el rol admin al ultimo administrador activo.", "warning")
                return redirect("/admin?tab=usuarios")

            if usuario.u_usuario == session.get("usuario_nombre") and usuario.u_rol == "admin" and data["rol"] != "admin":
                flash("No puedes quitar tu propio rol admin mientras tienes la sesion activa.", "warning")
                return redirect("/admin?tab=usuarios")

            if usuario.u_rol == "admin" and data["rol"] != "admin" and not confirmacion_usuario_valida(usuario, "confirmar_cambio_rol"):
                flash("Para quitar el rol admin debes escribir el usuario exacto.", "warning")
                return redirect("/admin?tab=usuarios")

            asegurar_area(db, data["area"])
            actualizar_usuario(usuario, data["nombre"], data["rut"], data["area"], data["rol"])
            registrar_accion(
                db,
                "editar_usuario",
                "usuario",
                usuario.u_usuario,
                f"Area: {usuario.u_area}. Rol: {usuario.u_rol}",
            )
            db.commit()
            flash("Usuario actualizado correctamente.", "success")
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "warning")
        except Exception:
            db.rollback()
            flash("No se pudo actualizar el usuario.", "danger")
        finally:
            db.close()

        return redirect("/admin?tab=usuarios")

    @app.route("/admin/usuarios/<int:usuario_id>/clave", methods=["POST"])
    def admin_cambiar_clave_usuario(usuario_id):
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        clave = request.form.get("clave", "")

        db = SessionLocal()
        try:
            usuario = db.query(UsuarioSistema).filter(UsuarioSistema.id == usuario_id).first()
            if not usuario:
                flash("No se encontro el usuario.", "warning")
                return redirect("/admin?tab=usuarios")

            cambiar_clave_usuario(usuario, clave)
            registrar_accion(db, "cambiar_clave_usuario", "usuario", usuario.u_usuario, "Clave actualizada por administrador.")
            db.commit()
            flash("Clave actualizada correctamente.", "success")
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "warning")
        except Exception:
            db.rollback()
            flash("No se pudo actualizar la clave.", "danger")
        finally:
            db.close()

        return redirect("/admin?tab=usuarios")

    @app.route("/admin/usuarios/<int:usuario_id>/eliminar", methods=["POST"])
    def admin_eliminar_usuario(usuario_id):
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        db = SessionLocal()
        try:
            usuario = db.query(UsuarioSistema).filter(UsuarioSistema.id == usuario_id).first()
            if not usuario:
                flash("No se encontro el usuario.", "warning")
                return redirect("/admin?tab=usuarios")

            if usuario.u_usuario == session.get("usuario_nombre"):
                flash("No puedes eliminar tu propio usuario mientras tienes la sesion activa.", "warning")
                return redirect("/admin?tab=usuarios")

            if es_ultimo_admin_activo(db, usuario):
                flash("No puedes eliminar el ultimo administrador activo.", "warning")
                return redirect("/admin?tab=usuarios")

            if not confirmacion_usuario_valida(usuario):
                flash("Para eliminar debes escribir el usuario exacto.", "warning")
                return redirect("/admin?tab=usuarios")

            usuario_codigo = usuario.u_usuario
            registrar_accion(
                db,
                "eliminar_usuario",
                "usuario",
                usuario_codigo,
                f"Nombre: {usuario.u_nombre}. Area: {usuario.u_area}. Rol: {usuario.u_rol}",
            )
            db.delete(usuario)
            db.commit()
            flash("Usuario eliminado correctamente.", "success")
        except Exception:
            db.rollback()
            flash("No se pudo eliminar el usuario.", "danger")
        finally:
            db.close()

        return redirect("/admin?tab=usuarios")

    @app.route("/admin/usuarios/<int:usuario_id>/estado", methods=["POST"])
    def admin_cambiar_estado_usuario(usuario_id):
        bloqueo = requiere_admin()
        if bloqueo:
            return bloqueo

        db = SessionLocal()
        try:
            usuario = db.query(UsuarioSistema).filter(UsuarioSistema.id == usuario_id).first()
            if not usuario:
                flash("No se encontro el usuario.", "warning")
                return redirect("/admin?tab=usuarios")

            if es_ultimo_admin_activo(db, usuario):
                flash("No puedes desactivar el ultimo administrador activo.", "warning")
                return redirect("/admin?tab=usuarios")

            if usuario.u_usuario == session.get("usuario_nombre") and usuario.u_activo:
                flash("No puedes desactivar tu propio usuario mientras tienes la sesion activa.", "warning")
                return redirect("/admin?tab=usuarios")

            if usuario.u_rol == "admin" and usuario.u_activo and not confirmacion_usuario_valida(usuario):
                flash("Para desactivar un admin debes escribir el usuario exacto.", "warning")
                return redirect("/admin?tab=usuarios")

            cambiar_estado_usuario(usuario)
            registrar_accion(db, "cambiar_estado_usuario", "usuario", usuario.u_usuario, f"Activo: {usuario.u_activo}")
            db.commit()
            flash("Estado de usuario actualizado.", "success")
        except Exception:
            db.rollback()
            flash("No se pudo actualizar el usuario.", "danger")
        finally:
            db.close()

        return redirect("/admin?tab=usuarios")
