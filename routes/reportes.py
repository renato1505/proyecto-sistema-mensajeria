import logging
import os
from datetime import timedelta
from io import BytesIO

from flask import flash, jsonify, redirect, render_template, request, send_file, session

from database.conexion import SessionLocal
from database.modelos import Envio, EvidenciaExcepcion, ExcepcionEnvio, MovimientoExcepcion, UsuarioSistema
from services.auditoria import registrar_accion
from services.evidencias_reportes import guardar_archivo_evidencia, validar_archivo_evidencia
from services.reportes import (
    ESTADOS_ACTIVOS,
    ESTADOS_CERRADOS,
    ESTADOS_EXCEPCION,
    RESULTADOS_CIERRE,
    TIPOS_EXCEPCION,
    TIPOS_MOVIMIENTO,
    actualizar_reporte,
    agrupar_reportes_por_remitente,
    anular_reporte,
    buscar_reporte_vigente_por_envio,
    buscar_envio_reportable,
    cerrar_reporte,
    crear_evidencia,
    crear_movimiento,
    crear_reporte,
    evidencias_por_reporte,
    leer_filtros_reportes,
    metricas_reportes,
    movimientos_por_reporte,
    query_reportes,
)
from services.reportes_pdf import generar_pdf_reporte
from services.reportes_respaldo import enviar_respaldo_eliminacion_reporte
from utils.fechas import ahora_chile
from utils.texto import normalizar_orden_flete, normalizar_texto_operativo


logger = logging.getLogger(__name__)


def _autor_pdf_actual(db):
    usuario_codigo = (session.get("usuario_nombre") or "").strip()
    if usuario_codigo:
        usuario = db.query(UsuarioSistema).filter(UsuarioSistema.u_usuario == usuario_codigo).first()
        if usuario and usuario.u_nombre:
            return usuario.u_nombre
        return session.get("usuario_display") or usuario_codigo
    if session.get("usuario_display"):
        return session.get("usuario_display")
    return "Equipo de Operaciones L'Oreal Mensajeria"


def _url_actual_reportes():
    url_actual = request.full_path
    return url_actual[:-1] if url_actual.endswith("?") else url_actual


def _redirect_reportes(default="/reportes"):
    destino = request.form.get("return_url", "").strip()
    if destino.startswith("/reportes"):
        return redirect(destino)
    return redirect(default)


def _leer_form_reporte():
    return {
        "envio_id": request.form.get("envio_id", "").strip(),
        "orden_flete": request.form.get("orden_flete", "").strip(),
        "estado": request.form.get("estado", "abierto").strip().lower(),
        "tipo": request.form.get("tipo", "").strip(),
        "contacto_starken": "",
        "detalle": normalizar_texto_operativo(request.form.get("detalle", "").strip()),
        "indicacion": normalizar_texto_operativo(request.form.get("indicacion", "").strip()),
        "respuesta": normalizar_texto_operativo(request.form.get("respuesta", "").strip()),
    }


def _validar_reporte(data):
    if not data["tipo"] or data["tipo"] not in TIPOS_EXCEPCION:
        return "Debes seleccionar un tipo de reporte valido."

    if not data["detalle"]:
        return "Debes ingresar el detalle del problema."

    if not data["indicacion"]:
        return "Debes registrar la indicacion o accion a seguir."

    return None


def registrar_rutas_reportes(app):
    @app.route("/buscar_reportes_sugerencias")
    def buscar_reportes_sugerencias():
        termino = normalizar_texto_operativo(request.args.get("q", "").strip())
        if len(termino) < 1:
            return jsonify([])

        like = f"%{termino}%"
        db = SessionLocal()
        try:
            filas = (
                db.query(Envio.e_orden_flete, Envio.e_destinatario)
                .join(ExcepcionEnvio, ExcepcionEnvio.envio_id == Envio.id)
                .filter(
                    (Envio.e_orden_flete.ilike(like))
                    | (Envio.e_destinatario.ilike(like))
                )
                .order_by(ExcepcionEnvio.x_fecha_actualizacion.desc())
                .limit(20)
                .all()
            )
        finally:
            db.close()

        sugerencias = []
        vistos = set()
        for orden_flete, destinatario in filas:
            for valor in (orden_flete, destinatario):
                valor = (valor or "").strip()
                clave = valor.casefold()
                if valor and clave not in vistos:
                    sugerencias.append(valor)
                    vistos.add(clave)

        return jsonify(sugerencias[:10])

    @app.route("/reportes")
    def reportes():
        filtros = leer_filtros_reportes(request.args)
        envio_id = request.args.get("envio_id", "").strip()
        envio_id_int = int(envio_id) if envio_id.isdigit() else None

        db = SessionLocal()
        try:
            envio_preseleccionado = buscar_envio_reportable(db, envio_id=envio_id_int)
            reportes_data = query_reportes(db, filtros).all()
            reporte_ids = [reporte.id for reporte, _envio in reportes_data]
            movimientos = movimientos_por_reporte(db, reporte_ids)
            evidencias = evidencias_por_reporte(db, reporte_ids)
            metricas = metricas_reportes(db)
            reportes_agrupados = agrupar_reportes_por_remitente(reportes_data)
            fecha_alerta_seguimiento = ahora_chile() - timedelta(days=3)
            return render_template(
                "reportes.html",
                filtros=filtros,
                reportes=reportes_data,
                reportes_agrupados=reportes_agrupados,
                movimientos=movimientos,
                evidencias=evidencias,
                metricas=metricas,
                envio_preseleccionado=envio_preseleccionado,
                estados=ESTADOS_EXCEPCION,
                estados_activos=ESTADOS_ACTIVOS,
                tipos=TIPOS_EXCEPCION,
                tipos_movimiento=TIPOS_MOVIMIENTO,
                resultados_cierre=RESULTADOS_CIERRE,
                url_actual=_url_actual_reportes(),
                fecha_alerta_seguimiento=fecha_alerta_seguimiento,
            )
        finally:
            db.close()

    @app.route("/reportes/<int:reporte_id>/evidencia", methods=["POST"])
    def agregar_evidencia_route(reporte_id):
        archivo = request.files.get("evidencia")
        descripcion = normalizar_texto_operativo(request.form.get("descripcion_evidencia", "").strip())
        error_archivo = validar_archivo_evidencia(archivo, request.content_length)
        if error_archivo:
            flash(error_archivo, "warning")
            return _redirect_reportes()

        db = SessionLocal()
        try:
            reporte = db.query(ExcepcionEnvio).filter(ExcepcionEnvio.id == reporte_id).first()
            if not reporte:
                flash("No se encontro el reporte solicitado.", "warning")
                return _redirect_reportes()

            if reporte.x_estado in ESTADOS_CERRADOS:
                flash("No se puede agregar evidencia a un reporte cerrado.", "warning")
                return _redirect_reportes()

            nombre_archivo = guardar_archivo_evidencia(
                archivo,
                reporte_id,
                os.path.join("static", "uploads", "reportes"),
            )

            evidencia, movimiento = crear_evidencia(
                reporte,
                archivo.filename,
                nombre_archivo,
                descripcion,
            )
            db.add(evidencia)
            db.add(movimiento)
            if reporte.x_estado == "abierto":
                reporte.x_estado = "en seguimiento"
            registrar_accion(
                db,
                "agregar_evidencia_reporte",
                "reporte",
                reporte.id,
                f"Archivo: {archivo.filename}. Descripcion: {descripcion}",
            )
            db.commit()
            flash("Evidencia agregada correctamente.", "success")
            return _redirect_reportes()
        except Exception:
            db.rollback()
            logger.exception("No se pudo agregar evidencia al reporte %s", reporte_id)
            flash("No se pudo agregar la evidencia.", "danger")
            return _redirect_reportes()
        finally:
            db.close()

    @app.route("/reportes/<int:reporte_id>/pdf")
    def descargar_reporte_pdf(reporte_id):
        db = SessionLocal()
        try:
            fila = (
                db.query(ExcepcionEnvio, Envio)
                .join(Envio, ExcepcionEnvio.envio_id == Envio.id)
                .filter(ExcepcionEnvio.id == reporte_id)
                .first()
            )
            if not fila:
                flash("No se encontro el reporte solicitado.", "warning")
                return redirect("/reportes")

            reporte, envio = fila
            movimientos = movimientos_por_reporte(db, [reporte.id]).get(reporte.id, [])
            evidencias = evidencias_por_reporte(db, [reporte.id]).get(reporte.id, [])
            pdf = generar_pdf_reporte(reporte, envio, movimientos, evidencias, _autor_pdf_actual(db))
            nombre = f"reporte_excepcion_OF_{envio.e_orden_flete or reporte.id}.pdf"
            return send_file(
                BytesIO(pdf),
                as_attachment=True,
                download_name=nombre,
                mimetype="application/pdf",
            )
        finally:
            db.close()

    @app.route("/reportes/crear", methods=["POST"])
    def crear_reporte_route():
        data = _leer_form_reporte()
        error = _validar_reporte(data)

        if error:
            flash(error, "warning")
            return redirect("/reportes")

        envio_id = int(data["envio_id"]) if data["envio_id"].isdigit() else None
        db = SessionLocal()
        try:
            envio = buscar_envio_reportable(db, envio_id=envio_id, orden_flete=data["orden_flete"])
            if not envio:
                flash("No se encontro una OF historica valida para crear el reporte.", "warning")
                return redirect("/reportes")

            reporte_vigente = buscar_reporte_vigente_por_envio(db, envio.id)
            if reporte_vigente:
                flash(
                    "Esta OF ya tiene un reporte vigente. Se abrio el caso existente.",
                    "info",
                )
                return redirect(f"/reportes?estado=todos#reporte-{reporte_vigente.id}")

            reporte = crear_reporte(envio, data)
            db.add(reporte)
            db.flush()
            db.add(crear_movimiento(
                reporte,
                "Informacion Starken",
                f"{data['detalle']}\n\nIndicacion inicial: {data['indicacion']}",
            ))
            registrar_accion(
                db,
                "crear_reporte",
                "reporte",
                reporte.id,
                f"OF: {envio.e_orden_flete}. Tipo: {data['tipo']}",
            )
            db.commit()
            flash("Reporte creado correctamente.", "success")
            return redirect(f"/reportes#reporte-{reporte.id}")
        except Exception:
            db.rollback()
            logger.exception("No se pudo crear reporte de excepcion")
            flash("No se pudo crear el reporte.", "danger")
            return redirect("/reportes")
        finally:
            db.close()

    @app.route("/reportes/<int:reporte_id>/movimiento", methods=["POST"])
    def agregar_movimiento_route(reporte_id):
        tipo = request.form.get("tipo_movimiento", "Nota interna").strip()
        detalle = normalizar_texto_operativo(request.form.get("detalle_movimiento", "").strip())

        if not detalle:
            flash("Debes ingresar el detalle del movimiento.", "warning")
            return _redirect_reportes()

        db = SessionLocal()
        try:
            reporte = db.query(ExcepcionEnvio).filter(ExcepcionEnvio.id == reporte_id).first()
            if not reporte:
                flash("No se encontro el reporte solicitado.", "warning")
                return _redirect_reportes()

            if reporte.x_estado in ESTADOS_CERRADOS:
                flash("No se puede agregar movimientos a un reporte cerrado.", "warning")
                return _redirect_reportes()

            db.add(crear_movimiento(reporte, tipo, detalle))
            if reporte.x_estado == "abierto":
                reporte.x_estado = "en seguimiento"
            registrar_accion(
                db,
                "agregar_movimiento_reporte",
                "reporte",
                reporte.id,
                f"Tipo: {tipo}. Detalle: {detalle[:500]}",
            )
            db.commit()
            flash("Movimiento agregado correctamente.", "success")
            return _redirect_reportes()
        except Exception:
            db.rollback()
            logger.exception("No se pudo agregar movimiento al reporte %s", reporte_id)
            flash("No se pudo agregar el movimiento.", "danger")
            return _redirect_reportes()
        finally:
            db.close()

    @app.route("/reportes/<int:reporte_id>/cerrar", methods=["POST"])
    def cerrar_reporte_route(reporte_id):
        data = {
            "resultado_final": request.form.get("resultado_final", "").strip(),
            "of_retorno": normalizar_orden_flete(request.form.get("of_retorno", "").strip()),
            "resumen_cierre": normalizar_texto_operativo(request.form.get("resumen_cierre", "").strip()),
        }

        if not data["resumen_cierre"]:
            flash("Debes ingresar un resumen de cierre.", "warning")
            return _redirect_reportes()

        db = SessionLocal()
        try:
            reporte = db.query(ExcepcionEnvio).filter(ExcepcionEnvio.id == reporte_id).first()
            if not reporte:
                flash("No se encontro el reporte solicitado.", "warning")
                return _redirect_reportes()

            if reporte.x_estado in ESTADOS_CERRADOS:
                flash("Este reporte ya esta cerrado.", "info")
                return _redirect_reportes()

            db.add(cerrar_reporte(reporte, data))
            registrar_accion(
                db,
                "cerrar_reporte",
                "reporte",
                reporte.id,
                f"Resultado: {data['resultado_final']}. OF retorno: {data['of_retorno'] or 'No aplica'}",
            )
            db.commit()
            flash("Reporte cerrado correctamente.", "success")
            return redirect(f"/reportes?estado=todos#reporte-{reporte_id}")
        except Exception:
            db.rollback()
            logger.exception("No se pudo cerrar reporte %s", reporte_id)
            flash("No se pudo cerrar el reporte.", "danger")
            return _redirect_reportes()
        finally:
            db.close()

    @app.route("/reportes/<int:reporte_id>/anular", methods=["POST"])
    def anular_reporte_route(reporte_id):
        motivo = normalizar_texto_operativo(request.form.get("motivo_anulacion", "").strip())
        if not motivo:
            flash("Debes indicar el motivo de anulacion.", "warning")
            return _redirect_reportes()

        db = SessionLocal()
        try:
            reporte = db.query(ExcepcionEnvio).filter(ExcepcionEnvio.id == reporte_id).first()
            if not reporte:
                flash("No se encontro el reporte solicitado.", "warning")
                return _redirect_reportes()

            if reporte.x_estado == "anulado":
                flash("Este reporte ya esta anulado.", "info")
                return _redirect_reportes()

            responsable = _autor_pdf_actual(db)
            db.add(anular_reporte(reporte, motivo))
            registrar_accion(
                db,
                "anular_reporte",
                "reporte",
                reporte.id,
                f"Responsable: {responsable}. Motivo: {motivo}",
            )
            db.commit()
            flash("Reporte anulado correctamente.", "success")
            return redirect(f"/reportes?estado=todos#reporte-{reporte_id}")
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "warning")
            return _redirect_reportes()
        except Exception:
            db.rollback()
            logger.exception("No se pudo anular reporte %s", reporte_id)
            flash("No se pudo anular el reporte.", "danger")
            return _redirect_reportes()
        finally:
            db.close()

    @app.route("/reportes/<int:reporte_id>/eliminar", methods=["POST"])
    def eliminar_reporte_route(reporte_id):
        motivo = normalizar_texto_operativo(request.form.get("motivo_eliminacion", "").strip())
        if not motivo:
            flash("Debes indicar el motivo de eliminacion.", "warning")
            return _redirect_reportes()

        db = SessionLocal()
        try:
            fila = (
                db.query(ExcepcionEnvio, Envio)
                .join(Envio, ExcepcionEnvio.envio_id == Envio.id)
                .filter(ExcepcionEnvio.id == reporte_id)
                .first()
            )
            if not fila:
                flash("No se encontro el reporte solicitado.", "warning")
                return _redirect_reportes()

            reporte, envio = fila
            responsable = _autor_pdf_actual(db)
            movimientos = movimientos_por_reporte(db, [reporte.id]).get(reporte.id, [])
            evidencias = evidencias_por_reporte(db, [reporte.id]).get(reporte.id, [])
            pdf = generar_pdf_reporte(reporte, envio, movimientos, evidencias, responsable)
            enviar_respaldo_eliminacion_reporte(reporte, envio, pdf, motivo, responsable)

            db.query(EvidenciaExcepcion).filter(EvidenciaExcepcion.reporte_id == reporte.id).delete()
            db.query(MovimientoExcepcion).filter(MovimientoExcepcion.reporte_id == reporte.id).delete()
            registrar_accion(
                db,
                "eliminar_reporte",
                "reporte",
                reporte.id,
                f"OF: {envio.e_orden_flete}. Responsable: {responsable}. Motivo: {motivo}",
            )
            db.delete(reporte)
            db.commit()
            flash("Reporte eliminado y respaldado correctamente.", "success")
            return redirect("/reportes?estado=todos")
        except Exception:
            db.rollback()
            logger.exception("No se pudo eliminar reporte %s", reporte_id)
            flash("No se pudo eliminar el reporte. Revisa la configuracion de correo de respaldo.", "danger")
            return _redirect_reportes()
        finally:
            db.close()

    @app.route("/reportes/<int:reporte_id>/actualizar", methods=["POST"])
    def actualizar_reporte_route(reporte_id):
        data = _leer_form_reporte()
        error = _validar_reporte(data)

        if error:
            flash(error, "warning")
            return _redirect_reportes()

        if data["estado"] in ESTADOS_CERRADOS:
            flash("Para cerrar un reporte debes usar la accion Cerrar caso y registrar el resumen.", "warning")
            return _redirect_reportes()

        db = SessionLocal()
        try:
            reporte = db.query(ExcepcionEnvio).filter(ExcepcionEnvio.id == reporte_id).first()
            if not reporte:
                flash("No se encontro el reporte solicitado.", "warning")
                return _redirect_reportes()

            if reporte.x_estado in ESTADOS_CERRADOS:
                flash("No se puede editar un reporte cerrado.", "warning")
                return _redirect_reportes()

            actualizar_reporte(reporte, data)
            registrar_accion(
                db,
                "actualizar_reporte",
                "reporte",
                reporte.id,
                f"Estado: {data['estado']}. Tipo: {data['tipo']}",
            )
            db.commit()
            flash("Reporte actualizado correctamente.", "success")
            return _redirect_reportes()
        except Exception:
            db.rollback()
            logger.exception("No se pudo actualizar reporte %s", reporte_id)
            flash("No se pudo actualizar el reporte.", "danger")
            return _redirect_reportes()
        finally:
            db.close()
