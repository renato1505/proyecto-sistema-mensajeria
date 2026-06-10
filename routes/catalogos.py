import logging
from math import ceil
from urllib.parse import urlencode

from flask import flash, redirect, render_template, request

from database.conexion import SessionLocal
from database.modelos import Destinatario, Remitente
from services.catalogos_operativos import (
    OPCIONES_PER_PAGE_CATALOGOS,
    divisiones_disponibles,
    guardar_destinatario_catalogo,
    guardar_remitente_catalogo,
    query_destinatarios_filtrados,
    query_remitentes_filtrados,
    validar_destinatario,
    validar_remitente,
)
from utils.validaciones import normalizar_telefono_chile


logger = logging.getLogger(__name__)


def _leer_form_remitente():
    return {
        "nombre": request.form.get("remitente", "").strip(),
        "correo": request.form.get("correo_remitente", "").strip(),
        "division": request.form.get("division", "").strip(),
        "centro_costo": request.form.get("centro_costo", "").strip(),
    }


def _leer_form_destinatario():
    return {
        "rut": request.form.get("rut_destinatario", "").strip(),
        "nombre": request.form.get("destinatario", "").strip(),
        "direccion": request.form.get("direccion", "").strip(),
        "comuna": request.form.get("comuna", "").strip(),
        "region": request.form.get("region", "").strip(),
        "telefono": normalizar_telefono_chile(
            request.form.get("telefono_destinatario", "").strip()
        ),
    }


def _leer_filtros_catalogos(args):
    return {
        "tab": args.get("tab", "remitentes").strip() or "remitentes",
        "r_nombre": args.get("r_nombre", "").strip(),
        "r_division": args.get("r_division", "").strip(),
        "r_centro_costo": args.get("r_centro_costo", "").strip(),
        "d_nombre": args.get("d_nombre", "").strip(),
        "d_rut": args.get("d_rut", "").strip(),
        "d_direccion": args.get("d_direccion", "").strip(),
        "d_comuna": args.get("d_comuna", "").strip(),
    }


def _leer_paginacion_catalogos(args):
    try:
        page = int(args.get("page", "1"))
    except ValueError:
        page = 1

    try:
        per_page = int(args.get("per_page", "25"))
    except ValueError:
        per_page = 25

    if page < 1:
        page = 1

    if per_page not in OPCIONES_PER_PAGE_CATALOGOS:
        per_page = 25

    return page, per_page


def _url_catalogos_filtros(filtros, page, per_page):
    params = {
        "tab": filtros["tab"],
        "r_nombre": filtros["r_nombre"],
        "r_division": filtros["r_division"],
        "r_centro_costo": filtros["r_centro_costo"],
        "d_nombre": filtros["d_nombre"],
        "d_rut": filtros["d_rut"],
        "d_direccion": filtros["d_direccion"],
        "d_comuna": filtros["d_comuna"],
        "page": page,
        "per_page": per_page,
    }
    return "/catalogos?" + urlencode(params)


def _url_catalogos(tab):
    return f"/catalogos?tab={tab}"


def _pagination(filtros, total_activo, page, per_page):
    total_paginas = max(ceil(total_activo / per_page), 1)

    if page > total_paginas:
        page = total_paginas

    offset = (page - 1) * per_page
    return {
        "page": page,
        "per_page": per_page,
        "offset": offset,
        "total_paginas": total_paginas,
        "total_activo": total_activo,
        "pagina_inicio": offset + 1 if total_activo else 0,
        "pagina_fin": min(offset + per_page, total_activo),
        "tiene_anterior": page > 1,
        "tiene_siguiente": page < total_paginas,
        "url_anterior": _url_catalogos_filtros(filtros, page - 1, per_page),
        "url_siguiente": _url_catalogos_filtros(filtros, page + 1, per_page),
        "url_primera": _url_catalogos_filtros(filtros, 1, per_page),
        "url_ultima": _url_catalogos_filtros(filtros, total_paginas, per_page),
        "opciones_per_page": OPCIONES_PER_PAGE_CATALOGOS,
    }


def registrar_rutas_catalogos(app):
    @app.route("/catalogos")
    def catalogos():
        filtros = _leer_filtros_catalogos(request.args)
        page, per_page = _leer_paginacion_catalogos(request.args)
        db = SessionLocal()
        try:
            query_remitentes = query_remitentes_filtrados(db, filtros)
            query_destinatarios = query_destinatarios_filtrados(db, filtros)

            total_remitentes = query_remitentes.count()
            total_destinatarios = query_destinatarios.count()
            total_activo = total_destinatarios if filtros["tab"] == "destinatarios" else total_remitentes
            pagination = _pagination(filtros, total_activo, page, per_page)

            remitentes = (
                query_remitentes
                .order_by(Remitente.r_nombre.asc())
                .offset(pagination["offset"] if filtros["tab"] == "remitentes" else 0)
                .limit(per_page)
                .all()
            )
            destinatarios = (
                query_destinatarios
                .order_by(Destinatario.d_nombre.asc())
                .offset(pagination["offset"] if filtros["tab"] == "destinatarios" else 0)
                .limit(per_page)
                .all()
            )

            return render_template(
                "catalogos.html",
                filtros=filtros,
                remitentes=remitentes,
                destinatarios=destinatarios,
                total_remitentes=total_remitentes,
                total_destinatarios=total_destinatarios,
                divisiones=divisiones_disponibles(db),
                pagination=pagination,
            )
        finally:
            db.close()

    @app.route("/catalogos/remitentes/guardar", methods=["POST"])
    def guardar_remitente_admin():
        data = _leer_form_remitente()
        error = validar_remitente(data)

        if error:
            flash(error, "danger")
            return redirect(_url_catalogos("remitentes"))

        remitente_id = request.form.get("catalogo_id", "").strip()
        remitente_id = int(remitente_id) if remitente_id.isdigit() else None

        db = SessionLocal()
        try:
            ok, mensaje = guardar_remitente_catalogo(db, data, remitente_id)
            if not ok:
                flash(mensaje, "warning")
                return redirect(_url_catalogos("remitentes"))

            db.commit()
            flash(mensaje, "success")
            return redirect(_url_catalogos("remitentes"))
        except Exception:
            db.rollback()
            logger.exception("No se pudo guardar remitente desde catalogos")
            flash("No se pudo guardar el remitente.", "danger")
            return redirect(_url_catalogos("remitentes"))
        finally:
            db.close()

    @app.route("/catalogos/remitentes/<int:remitente_id>/eliminar", methods=["POST"])
    def eliminar_remitente_admin(remitente_id):
        db = SessionLocal()
        try:
            remitente = db.query(Remitente).filter(Remitente.id == remitente_id).first()
            if not remitente:
                flash("No se encontro el remitente solicitado.", "warning")
                return redirect(_url_catalogos("remitentes"))

            db.delete(remitente)
            db.commit()
            flash("Remitente eliminado del catalogo.", "warning")
            return redirect(_url_catalogos("remitentes"))
        except Exception:
            db.rollback()
            logger.exception("No se pudo eliminar remitente desde catalogos")
            flash("No se pudo eliminar el remitente.", "danger")
            return redirect(_url_catalogos("remitentes"))
        finally:
            db.close()

    @app.route("/catalogos/destinatarios/guardar", methods=["POST"])
    def guardar_destinatario_admin():
        data = _leer_form_destinatario()
        error = validar_destinatario(data)

        if error:
            flash(error, "danger")
            return redirect(_url_catalogos("destinatarios"))

        destinatario_id = request.form.get("catalogo_id", "").strip()
        destinatario_id = int(destinatario_id) if destinatario_id.isdigit() else None

        db = SessionLocal()
        try:
            ok, mensaje = guardar_destinatario_catalogo(db, data, destinatario_id)
            if not ok:
                flash(mensaje, "warning")
                return redirect(_url_catalogos("destinatarios"))

            db.commit()
            flash(mensaje, "success")
            return redirect(_url_catalogos("destinatarios"))
        except Exception:
            db.rollback()
            logger.exception("No se pudo guardar destinatario desde catalogos")
            flash("No se pudo guardar el destinatario.", "danger")
            return redirect(_url_catalogos("destinatarios"))
        finally:
            db.close()

    @app.route("/catalogos/destinatarios/<int:destinatario_id>/eliminar", methods=["POST"])
    def eliminar_destinatario_admin(destinatario_id):
        db = SessionLocal()
        try:
            destinatario = (
                db.query(Destinatario)
                .filter(Destinatario.id == destinatario_id)
                .first()
            )
            if not destinatario:
                flash("No se encontro el destinatario solicitado.", "warning")
                return redirect(_url_catalogos("destinatarios"))

            db.delete(destinatario)
            db.commit()
            flash("Destinatario eliminado del catalogo.", "warning")
            return redirect(_url_catalogos("destinatarios"))
        except Exception:
            db.rollback()
            logger.exception("No se pudo eliminar destinatario desde catalogos")
            flash("No se pudo eliminar el destinatario.", "danger")
            return redirect(_url_catalogos("destinatarios"))
        finally:
            db.close()
