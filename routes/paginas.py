import io
import logging
import os
import re
from datetime import datetime
from urllib.parse import urlencode

import pandas as pd
from flask import flash, jsonify, redirect, render_template, request, send_file
from sqlalchemy import func

from config.settings import CLAVE_ELIMINACION_HISTORICO
from database.conexion import SessionLocal
from database.modelos import Envio
from services.estado_sistema import obtener_estado_sistema


logger = logging.getLogger(__name__)


def construir_url_historico(mes, of="", destinatario="", remitente="", fecha="", fecha_desde="", fecha_hasta=""):
    params = {
        "mes": mes,
        "of": of,
        "destinatario": destinatario,
        "remitente": remitente,
        "fecha": fecha,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
    }
    return "/historico?" + urlencode(params)


def limpiar_nombre_archivo(texto):
    texto = str(texto or "").strip()
    texto = re.sub(r"[^A-Za-z0-9_.-]+", "_", texto)
    return texto[:80] or "archivo"


def construir_query_historico(
    db,
    mes_seleccionado,
    filtro_of,
    filtro_destinatario,
    filtro_remitente,
    filtro_fecha,
    fecha_desde,
    fecha_hasta,
):
    if not mes_seleccionado:
        mes_seleccionado = datetime.now().strftime("%Y-%m")

    try:
        mes_obj = datetime.strptime(mes_seleccionado, "%Y-%m")
    except ValueError:
        mes_obj = datetime.now()

    query = db.query(Envio).filter(Envio.e_estado == "historico")

    if not fecha_desde and not fecha_hasta and not filtro_fecha:
        query = query.filter(
            func.extract("year", Envio.e_fecha_creacion) == mes_obj.year,
            func.extract("month", Envio.e_fecha_creacion) == mes_obj.month,
        )

    if filtro_of:
        query = query.filter(Envio.e_orden_flete.ilike(f"%{filtro_of}%"))

    if filtro_destinatario:
        query = query.filter(Envio.e_destinatario.ilike(f"%{filtro_destinatario}%"))

    if filtro_remitente:
        query = query.filter(Envio.e_remitente.ilike(f"%{filtro_remitente}%"))

    if filtro_fecha:
        try:
            fecha_obj = datetime.strptime(filtro_fecha, "%Y-%m-%d").date()
            query = query.filter(func.date(Envio.e_fecha_creacion) == fecha_obj)
        except ValueError:
            pass

    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, "%Y-%m-%d")
            query = query.filter(Envio.e_fecha_creacion >= fecha_desde_obj)
        except ValueError:
            pass

    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, "%Y-%m-%d")
            fecha_hasta_obj = fecha_hasta_obj.replace(hour=23, minute=59, second=59)
            query = query.filter(Envio.e_fecha_creacion <= fecha_hasta_obj)
        except ValueError:
            pass

    return query


def convertir_envios_a_dataframe(envios):
    data = []

    for envio in envios:
        data.append({
            "Fecha": envio.e_fecha_creacion.strftime("%d/%m/%Y %H:%M") if envio.e_fecha_creacion else "",
            "Remitente": envio.e_remitente,
            "Correo remitente": envio.e_correo_remitente,
            "División": envio.e_division,
            "Centro de costo": envio.e_centro_costo,
            "Destinatario": envio.e_destinatario,
            "RUT destinatario": envio.e_rut_destinatario,
            "Dirección": envio.e_direccion,
            "Comuna": envio.e_comuna,
            "Región": envio.e_region,
            "Teléfono": envio.e_telefono_destinatario,
            "Tipo envío": envio.e_tipo_envio,
            "Código agencia": envio.e_codigo_agencia if envio.e_tipo_envio == "Agencia" else "No aplica",
            "Bultos": envio.e_bultos,
            "Kilos": envio.e_kilos,
            "Orden de flete": envio.e_orden_flete,
        })

    return pd.DataFrame(data)


def guardar_respaldo_historico(envios):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(base_dir)
    carpeta_respaldos = os.path.join(project_dir, "respaldos_historico")

    os.makedirs(carpeta_respaldos, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nombre_archivo = f"respaldo_historico_{timestamp}.xlsx"
    ruta_archivo = os.path.join(carpeta_respaldos, nombre_archivo)

    df = convertir_envios_a_dataframe(envios)

    with pd.ExcelWriter(ruta_archivo, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Historico")

    return nombre_archivo, ruta_archivo


def _leer_filtros(args):
    return {
        "mes": args.get("mes", "").strip(),
        "of": args.get("of", "").strip(),
        "destinatario": args.get("destinatario", "").strip(),
        "remitente": args.get("remitente", "").strip(),
        "fecha": args.get("fecha", "").strip(),
        "fecha_desde": args.get("fecha_desde", "").strip(),
        "fecha_hasta": args.get("fecha_hasta", "").strip(),
    }


def _query_desde_filtros(db, filtros):
    mes = filtros["mes"] or datetime.now().strftime("%Y-%m")
    return construir_query_historico(
        db,
        mes,
        filtros["of"],
        filtros["destinatario"],
        filtros["remitente"],
        filtros["fecha"],
        filtros["fecha_desde"],
        filtros["fecha_hasta"],
    )


def registrar_rutas_paginas(app):
    @app.route("/")
    def inicio():
        estado = obtener_estado_sistema()
        return render_template("index.html", estado=estado)

    @app.route("/estado_sistema")
    def estado_sistema():
        estado = obtener_estado_sistema()
        return render_template("estado_sistema.html", estado=estado)

    @app.route("/envios")
    def ver_envio():
        db = SessionLocal()
        envios = db.query(Envio).filter(Envio.e_estado == "pendiente").all()
        db.close()
        return render_template("envios.html", envios=envios)

    @app.route("/en_proceso")
    def ver_en_proceso():
        db = SessionLocal()

        envios_en_proceso = (
            db.query(Envio)
            .filter(Envio.e_estado == "en_proceso")
            .order_by(Envio.e_fecha_exportacion.desc(), Envio.e_fila_excel.asc())
            .all()
        )

        lotes_dict = {}

        for envio in envios_en_proceso:
            lote = envio.e_lote or "SIN_LOTE"

            if lote not in lotes_dict:
                lotes_dict[lote] = {
                    "lote": lote,
                    "fecha_exportacion": envio.e_fecha_exportacion,
                    "envios": [],
                }

            lotes_dict[lote]["envios"].append(envio)

        lotes = list(lotes_dict.values())

        for lote in lotes:
            lote["cantidad_envios"] = len(lote["envios"])
            resultados = [e.e_resultado_of for e in lote["envios"] if e.e_resultado_of]

            if not resultados:
                lote["estado_general"] = "Esperando OF"
            elif any(r == "ERROR" for r in resultados):
                if len(resultados) < lote["cantidad_envios"]:
                    lote["estado_general"] = "Procesado parcialmente"
                else:
                    lote["estado_general"] = "Con errores"
            elif all(r == "OK" for r in resultados):
                lote["estado_general"] = "Completado"
            else:
                lote["estado_general"] = "Procesado parcialmente"

        db.close()
        return render_template("en_proceso.html", lotes=lotes)

    @app.route("/historico")
    def ver_historico():
        db = SessionLocal()

        meses_es = {
            1: "Enero",
            2: "Febrero",
            3: "Marzo",
            4: "Abril",
            5: "Mayo",
            6: "Junio",
            7: "Julio",
            8: "Agosto",
            9: "Septiembre",
            10: "Octubre",
            11: "Noviembre",
            12: "Diciembre",
        }

        filtros = _leer_filtros(request.args)
        if not filtros["mes"]:
            filtros["mes"] = datetime.now().strftime("%Y-%m")

        query = _query_desde_filtros(db, filtros)
        envios = query.order_by(Envio.e_fecha_creacion.desc()).all()

        registros_historicos = (
            db.query(Envio)
            .filter(Envio.e_estado == "historico")
            .order_by(Envio.e_fecha_creacion.desc())
            .all()
        )

        meses_disponibles = []
        meses_vistos = set()

        for envio in registros_historicos:
            if envio.e_fecha_creacion:
                clave = envio.e_fecha_creacion.strftime("%Y-%m")
                nombre = f"{meses_es[envio.e_fecha_creacion.month]} {envio.e_fecha_creacion.year}"

                if clave not in meses_vistos:
                    meses_disponibles.append({"valor": clave, "nombre": nombre})
                    meses_vistos.add(clave)

        total_registros = len(envios)
        total_bultos = sum(envio.e_bultos or 0 for envio in envios)
        total_domicilio = sum(1 for envio in envios if envio.e_tipo_envio == "Domicilio")
        total_agencia = sum(1 for envio in envios if envio.e_tipo_envio == "Agencia")

        db.close()

        return render_template(
            "historico.html",
            envios=envios,
            mes_seleccionado=filtros["mes"],
            meses_disponibles=meses_disponibles,
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
        )

    @app.route("/exportar_historico")
    def exportar_historico():
        db = SessionLocal()

        filtros = _leer_filtros(request.args)
        if not filtros["mes"]:
            filtros["mes"] = datetime.now().strftime("%Y-%m")

        query = _query_desde_filtros(db, filtros)
        envios = query.order_by(Envio.e_fecha_creacion.desc()).all()
        df = convertir_envios_a_dataframe(envios)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Historico")

        output.seek(0)
        db.close()

        nombre_archivo = f"historico_filtrado_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

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
            flash("No se encontró el envío histórico solicitado.", "warning")
            return redirect("/historico")

        df = convertir_envios_a_dataframe([envio])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Detalle")

        output.seek(0)
        db.close()

        of_texto = limpiar_nombre_archivo(envio.e_orden_flete if envio.e_orden_flete else f"envio_{envio.id}")
        nombre_archivo = f"detalle_{of_texto}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.route("/descargar_historico_seleccionados", methods=["POST"])
    def descargar_historico_seleccionados():
        db = SessionLocal()

        ids = request.form.getlist("envio_ids")

        if not ids:
            db.close()
            flash("Debes seleccionar al menos un registro para descargar.", "warning")
            return redirect("/historico")

        ids_validos = []
        for valor in ids:
            try:
                ids_validos.append(int(valor))
            except ValueError:
                pass

        envios = (
            db.query(Envio)
            .filter(Envio.id.in_(ids_validos), Envio.e_estado == "historico")
            .order_by(Envio.e_fecha_creacion.desc())
            .all()
        )

        if not envios:
            db.close()
            flash("No se encontraron registros válidos para descargar.", "warning")
            return redirect("/historico")

        df = convertir_envios_a_dataframe(envios)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Seleccionados")

        output.seek(0)
        db.close()

        nombre_archivo = f"historico_seleccionados_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.route("/eliminar_historico", methods=["POST"])
    def eliminar_historico():
        db = SessionLocal()

        clave = request.form.get("clave", "").strip()
        filtros = _leer_filtros(request.form)

        if not CLAVE_ELIMINACION_HISTORICO:
            db.close()
            flash("La clave de eliminación histórica no está configurada en .env.", "danger")
            return redirect("/historico")

        if clave != CLAVE_ELIMINACION_HISTORICO:
            db.close()
            flash("Contraseña incorrecta. No se eliminó ningún registro.", "danger")
            return redirect(construir_url_historico(
                filtros["mes"],
                filtros["of"],
                filtros["destinatario"],
                filtros["remitente"],
                filtros["fecha"],
                filtros["fecha_desde"],
                filtros["fecha_hasta"],
            ))

        if not filtros["mes"]:
            filtros["mes"] = datetime.now().strftime("%Y-%m")

        query = _query_desde_filtros(db, filtros)
        envios_a_eliminar = query.all()

        if not envios_a_eliminar:
            db.close()
            flash("No hay registros para eliminar con esos filtros.", "warning")
            return redirect(construir_url_historico(
                filtros["mes"],
                filtros["of"],
                filtros["destinatario"],
                filtros["remitente"],
                filtros["fecha"],
                filtros["fecha_desde"],
                filtros["fecha_hasta"],
            ))

        try:
            nombre_respaldo, ruta_respaldo = guardar_respaldo_historico(envios_a_eliminar)
            cantidad = len(envios_a_eliminar)

            for envio in envios_a_eliminar:
                db.delete(envio)

            db.commit()
        except Exception:
            db.rollback()
            db.close()
            logger.exception("No se pudo eliminar historico con respaldo previo")
            flash("No se pudo eliminar el historico. Revisa el log del sistema.", "danger")
            return redirect(construir_url_historico(
                filtros["mes"],
                filtros["of"],
                filtros["destinatario"],
                filtros["remitente"],
                filtros["fecha"],
                filtros["fecha_desde"],
                filtros["fecha_hasta"],
            ))

        db.close()

        flash(
            f"Se eliminaron {cantidad} registro(s) del histórico. "
            f"Respaldo guardado en 'respaldos_historico/{nombre_respaldo}'",
            "warning",
        )
        return redirect(construir_url_historico(filtros["mes"]))

    @app.route("/buscar_of_historico")
    def buscar_of_historico():
        q = request.args.get("q", "").strip()

        if len(q) < 1:
            return jsonify([])

        db = SessionLocal()
        resultados = (
            db.query(Envio.e_orden_flete)
            .filter(
                Envio.e_estado == "historico",
                Envio.e_orden_flete.isnot(None),
                Envio.e_orden_flete.ilike(f"%{q}%"),
            )
            .distinct()
            .limit(8)
            .all()
        )
        db.close()

        return jsonify([r[0] for r in resultados if r[0]])

    @app.route("/buscar_destinatarios_historico")
    def buscar_destinatarios_historico():
        q = request.args.get("q", "").strip()

        if len(q) < 2:
            return jsonify([])

        db = SessionLocal()
        resultados = (
            db.query(Envio.e_destinatario)
            .filter(
                Envio.e_estado == "historico",
                Envio.e_destinatario.ilike(f"%{q}%"),
            )
            .distinct()
            .limit(8)
            .all()
        )
        db.close()

        return jsonify([r[0] for r in resultados if r[0]])

    @app.route("/buscar_remitentes_historico")
    def buscar_remitentes_historico():
        q = request.args.get("q", "").strip()

        if len(q) < 2:
            return jsonify([])

        db = SessionLocal()
        resultados = (
            db.query(Envio.e_remitente)
            .filter(
                Envio.e_estado == "historico",
                Envio.e_remitente.ilike(f"%{q}%"),
            )
            .distinct()
            .limit(8)
            .all()
        )
        db.close()

        return jsonify([r[0] for r in resultados if r[0]])
