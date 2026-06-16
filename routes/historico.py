import io
import logging
from math import ceil

import pandas as pd
from flask import flash, redirect, render_template, request, send_file
from sqlalchemy import func

from config.settings import CLAVE_ELIMINACION_HISTORICO
from database.conexion import SessionLocal
from database.modelos import Envio
from services.historico import (
    OPCIONES_PER_PAGE_HISTORICO,
    construir_url_historico,
    convertir_envios_a_dataframe,
    enviar_respaldo_eliminacion_historico,
    leer_filtros_historico,
    leer_paginacion_historico,
    limpiar_nombre_archivo,
    meses_disponibles,
    query_desde_filtros,
    url_desde_filtros,
)
from utils.fechas import ahora_chile, timestamp_archivo_chile


logger = logging.getLogger(__name__)


def _leer_ids_seleccionados():
    ids_validos = []
    for valor in request.form.getlist("envio_ids"):
        try:
            ids_validos.append(int(valor))
        except ValueError:
            pass
    return ids_validos


def _pagination(filtros, total_registros, page, per_page, cantidad_pagina):
    total_paginas = max(ceil(total_registros / per_page), 1)

    if page > total_paginas:
        page = total_paginas

    offset = (page - 1) * per_page
    return {
        "page": page,
        "per_page": per_page,
        "offset": offset,
        "total_paginas": total_paginas,
        "total_registros": total_registros,
        "pagina_inicio": offset + 1 if total_registros else 0,
        "pagina_fin": min(offset + cantidad_pagina, total_registros),
        "tiene_anterior": page > 1,
        "tiene_siguiente": page < total_paginas,
        "url_anterior": url_desde_filtros(filtros, page - 1, per_page),
        "url_siguiente": url_desde_filtros(filtros, page + 1, per_page),
        "url_primera": url_desde_filtros(filtros, 1, per_page),
        "url_ultima": url_desde_filtros(filtros, total_paginas, per_page),
        "opciones_per_page": OPCIONES_PER_PAGE_HISTORICO,
    }


def _excel_response(df, nombre_archivo, sheet_name):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)

    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def registrar_rutas_historico(app):
    @app.route("/historico")
    def ver_historico():
        db = SessionLocal()
        filtros = leer_filtros_historico(request.args)
        if not filtros["mes"]:
            filtros["mes"] = "todos"

        page, per_page = leer_paginacion_historico(request.args)
        query = query_desde_filtros(db, filtros)
        total_registros = query.count()
        total_paginas = max(ceil(total_registros / per_page), 1)
        page = min(page, total_paginas)
        offset = (page - 1) * per_page

        envios = (
            query
            .order_by(Envio.e_fecha_creacion.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        pagination = _pagination(filtros, total_registros, page, per_page, len(envios))

        registros_historicos = (
            db.query(Envio)
            .filter(Envio.e_estado == "historico")
            .order_by(Envio.e_fecha_creacion.desc())
            .all()
        )

        total_bultos = query.with_entities(func.coalesce(func.sum(Envio.e_bultos), 0)).scalar()
        total_domicilio = query.filter(Envio.e_tipo_envio == "Domicilio").count()
        total_agencia = query.filter(Envio.e_tipo_envio == "Agencia").count()
        meses = meses_disponibles(registros_historicos)
        db.close()

        return render_template(
            "historico.html",
            envios=envios,
            mes_seleccionado=filtros["mes"],
            meses_disponibles=meses,
            total_registros=total_registros,
            total_bultos=total_bultos,
            total_domicilio=total_domicilio,
            total_agencia=total_agencia,
            filtro_of=filtros["of"],
            filtro_destinatario=filtros["destinatario"],
            filtro_remitente=filtros["remitente"],
            filtro_fecha=filtros["fecha"],
            fecha_desde=filtros["fecha_desde"],
            fecha_hasta=filtros["fecha_hasta"],
            estado_of=filtros["estado_of"],
            pagination=pagination,
        )

    @app.route("/exportar_historico")
    def exportar_historico():
        db = SessionLocal()
        filtros = leer_filtros_historico(request.args)
        if not filtros["mes"]:
            filtros["mes"] = "todos"

        query = query_desde_filtros(db, filtros)
        envios = query.order_by(Envio.e_fecha_creacion.desc()).all()
        df = convertir_envios_a_dataframe(envios)
        db.close()

        nombre_archivo = f"historico_filtrado_{timestamp_archivo_chile()}.xlsx"
        return _excel_response(df, nombre_archivo, "Historico")

    @app.route("/descargar_envio_historico/<int:envio_id>")
    def descargar_envio_historico(envio_id):
        db = SessionLocal()
        envio = (
            db.query(Envio)
            .filter(Envio.id == envio_id, Envio.e_estado == "historico")
            .first()
        )

        if not envio:
            db.close()
            flash("No se encontro el envio historico solicitado.", "warning")
            return redirect("/historico")

        df = convertir_envios_a_dataframe([envio])
        of_texto = limpiar_nombre_archivo(envio.e_orden_flete if envio.e_orden_flete else f"envio_{envio.id}")
        db.close()

        nombre_archivo = f"detalle_{of_texto}_{timestamp_archivo_chile()}.xlsx"
        return _excel_response(df, nombre_archivo, "Detalle")

    @app.route("/descargar_historico_seleccionados", methods=["POST"])
    def descargar_historico_seleccionados():
        ids_validos = _leer_ids_seleccionados()

        if not ids_validos:
            flash("Debes seleccionar al menos un registro para descargar.", "warning")
            return redirect("/historico")

        db = SessionLocal()
        envios = (
            db.query(Envio)
            .filter(Envio.id.in_(ids_validos), Envio.e_estado == "historico")
            .order_by(Envio.e_fecha_creacion.desc())
            .all()
        )

        if not envios:
            db.close()
            flash("No se encontraron registros validos para descargar.", "warning")
            return redirect("/historico")

        df = convertir_envios_a_dataframe(envios)
        db.close()

        nombre_archivo = f"historico_seleccionados_{timestamp_archivo_chile()}.xlsx"
        return _excel_response(df, nombre_archivo, "Seleccionados")

    @app.route("/anular_historico_seleccionados", methods=["POST"])
    def anular_historico_seleccionados():
        ids_validos = _leer_ids_seleccionados()
        motivo = request.form.get("motivo_anulacion", "").strip()

        if not ids_validos:
            flash("Debes seleccionar al menos un registro para anular.", "warning")
            return redirect("/historico")

        if not motivo:
            flash("Debes indicar un motivo de anulacion.", "warning")
            return redirect("/historico")

        db = SessionLocal()
        envios = (
            db.query(Envio)
            .filter(Envio.id.in_(ids_validos), Envio.e_estado == "historico")
            .all()
        )

        if not envios:
            db.close()
            flash("No se encontraron registros validos para anular.", "warning")
            return redirect("/historico")

        fecha_anulacion = ahora_chile()
        cantidad = 0
        for envio in envios:
            if envio.e_anulado:
                continue
            envio.e_anulado = True
            envio.e_fecha_anulacion = fecha_anulacion
            envio.e_motivo_anulacion = motivo[:500]
            cantidad += 1

        db.commit()
        db.close()

        if cantidad:
            flash(f"Se marcaron {cantidad} registro(s) como anulados.", "success")
        else:
            flash("Los registros seleccionados ya estaban anulados.", "info")
        return redirect("/historico")

    @app.route("/eliminar_historico_seleccionados", methods=["POST"])
    def eliminar_historico_seleccionados():
        ids_validos = _leer_ids_seleccionados()
        clave = request.form.get("clave", "").strip()

        if not ids_validos:
            flash("Debes seleccionar al menos un registro para eliminar.", "warning")
            return redirect("/historico")

        if not CLAVE_ELIMINACION_HISTORICO:
            flash("La clave de eliminacion historica no esta configurada en .env.", "danger")
            return redirect("/historico")

        if clave != CLAVE_ELIMINACION_HISTORICO:
            flash("Contrasena incorrecta. No se elimino ningun registro.", "danger")
            return redirect("/historico")

        db = SessionLocal()
        envios_a_eliminar = (
            db.query(Envio)
            .filter(Envio.id.in_(ids_validos), Envio.e_estado == "historico")
            .all()
        )

        if not envios_a_eliminar:
            db.close()
            flash("No se encontraron registros validos para eliminar.", "warning")
            return redirect("/historico")

        try:
            cantidad = len(envios_a_eliminar)
            filtros = {"seleccionados": ", ".join(str(item) for item in ids_validos)}
            nombre_respaldo, destinatarios_respaldo = enviar_respaldo_eliminacion_historico(
                envios_a_eliminar,
                filtros,
            )

            for envio in envios_a_eliminar:
                db.delete(envio)

            db.commit()
        except Exception:
            db.rollback()
            db.close()
            logger.exception("No se pudo eliminar historico seleccionado con respaldo por correo")
            flash(
                "No se elimino el historico seleccionado porque no se pudo enviar el respaldo por correo.",
                "danger",
            )
            return redirect("/historico")

        db.close()
        flash(
            f"Se eliminaron {cantidad} registro(s) seleccionados. "
            f"Respaldo '{nombre_respaldo}' enviado a {', '.join(destinatarios_respaldo)}.",
            "warning",
        )
        return redirect("/historico")

    @app.route("/eliminar_historico", methods=["POST"])
    def eliminar_historico():
        db = SessionLocal()
        clave = request.form.get("clave", "").strip()
        filtros = leer_filtros_historico(request.form)

        if not CLAVE_ELIMINACION_HISTORICO:
            db.close()
            flash("La clave de eliminacion historica no esta configurada en .env.", "danger")
            return redirect("/historico")

        if clave != CLAVE_ELIMINACION_HISTORICO:
            db.close()
            flash("Contrasena incorrecta. No se elimino ningun registro.", "danger")
            return redirect(url_desde_filtros(filtros))

        if not filtros["mes"]:
            filtros["mes"] = "todos"

        query = query_desde_filtros(db, filtros)
        envios_a_eliminar = query.all()

        if not envios_a_eliminar:
            db.close()
            flash("No hay registros para eliminar con esos filtros.", "warning")
            return redirect(url_desde_filtros(filtros))

        # En cloud, el respaldo critico debe salir por correo antes de borrar.
        try:
            cantidad = len(envios_a_eliminar)
            nombre_respaldo, destinatarios_respaldo = enviar_respaldo_eliminacion_historico(
                envios_a_eliminar,
                filtros,
            )

            for envio in envios_a_eliminar:
                db.delete(envio)

            db.commit()
        except Exception:
            db.rollback()
            db.close()
            logger.exception("No se pudo eliminar historico con respaldo por correo")
            flash(
                "No se elimino el historico porque no se pudo enviar el respaldo por correo.",
                "danger",
            )
            return redirect(url_desde_filtros(filtros))

        db.close()
        flash(
            f"Se eliminaron {cantidad} registro(s) del historico. "
            f"Respaldo '{nombre_respaldo}' enviado a {', '.join(destinatarios_respaldo)}.",
            "warning",
        )
        return redirect(construir_url_historico(filtros["mes"]))
