import io
import logging

from flask import flash, redirect, render_template, request, send_file, session

from database.conexion import SessionLocal
from database.modelos import Envio
from services.avisos import (
    correo_avisos_configurado,
    enviar_respaldo_mensajeria,
    marcar_avisos_pendientes_lote,
    obtener_envios_lote,
)
from services.correo import (
    correo_starken_configurado,
    enviar_archivo_starken,
    obtener_correo_destino_starken,
)
from services.correo_of import (
    buscar_correos_of,
    correo_of_configurado,
    descargar_adjunto_of,
)
from services.lotes import (
    lote_coincide_con_archivo,
    obtener_lotes_en_proceso,
    preparar_correos_of_para_lotes,
)
from services.of_processor import OFProcessingError, procesar_archivo_of
from services.starken import generar_csv_starken, guardar_respaldo_lote
from utils.fechas import ahora_chile


logger = logging.getLogger(__name__)


def _ids_envios_seleccionados(valores):
    if not valores:
        raise ValueError("Debes seleccionar al menos un envio para generar el lote.")

    try:
        ids = [int(valor) for valor in valores]
    except (TypeError, ValueError) as exc:
        raise ValueError("La seleccion contiene IDs de envio invalidos.") from exc

    if any(envio_id <= 0 for envio_id in ids):
        raise ValueError("La seleccion contiene IDs de envio invalidos.")
    if len(ids) != len(set(ids)):
        raise ValueError("La seleccion contiene IDs de envio duplicados.")

    return ids


def _obtener_envios_seleccionados_para_lote(db, valores):
    ids = _ids_envios_seleccionados(valores)
    envios = (
        db.query(Envio)
        .filter(Envio.id.in_(ids))
        .order_by(Envio.id.asc())
        .with_for_update()
        .all()
    )

    encontrados = {envio.id for envio in envios}
    inexistentes = sorted(set(ids) - encontrados)
    if inexistentes:
        raise ValueError(
            "Uno o mas envios seleccionados no existen. Recarga Pendientes e intenta nuevamente."
        )

    no_disponibles = [
        envio.id
        for envio in envios
        if envio.e_estado != "pendiente" or bool(envio.e_anulado)
    ]
    if no_disponibles:
        raise ValueError(
            "Uno o mas envios seleccionados ya no estan pendientes. "
            "Recarga la pantalla antes de generar el lote."
        )

    return envios


def _responsable_actual():
    return (
        session.get("usuario_display")
        or session.get("usuario_nombre")
        or "Usuario no identificado"
    )


def _enviar_respaldo_post_of(db, lote, resultado):
    """Despues de procesar OF, activa avisos y envia respaldo interno a Mensajeria."""
    if resultado.get("total_ok", 0) <= 0:
        return

    marcar_avisos_pendientes_lote(db, lote)

    if not correo_avisos_configurado():
        flash(
            "La OF fue procesada, pero no se pudo enviar respaldo a Mensajeria: "
            "faltan credenciales de correo.",
            "danger",
        )
        return

    envios = obtener_envios_lote(db, lote)
    try:
        enviar_respaldo_mensajeria(lote, envios, _responsable_actual())
        flash("Respaldo completo del lote enviado a Mensajeria.", "success")
    except Exception as e:
        logger.exception("No se pudo enviar respaldo automatico del lote %s", lote)
        flash(
            f"La OF fue procesada, pero no se pudo enviar el respaldo a Mensajeria: {str(e)}",
            "danger",
        )


def _redirect_post_of(lote, resultado):
    if resultado.get("total_ok", 0) > 0:
        return redirect(f"/of_exito/{lote}")

    return redirect("/en_proceso")


def _resumen_of_lote(db, lote):
    envios = (
        db.query(Envio)
        .filter(Envio.e_lote == lote)
        .order_by(Envio.e_fila_excel.asc(), Envio.id.asc())
        .all()
    )
    envios_ok = [envio for envio in envios if envio.e_resultado_of == "OK" and envio.e_orden_flete]
    envios_error = [envio for envio in envios if envio.e_resultado_of == "ERROR"]
    ofs = [envio.e_orden_flete for envio in envios_ok]

    return {
        "lote": lote,
        "total": len(envios),
        "total_ok": len(envios_ok),
        "total_error": len(envios_error),
        "primera_of": ofs[0] if ofs else "",
        "ultima_of": ofs[-1] if ofs else "",
        "envios_ok": envios_ok,
        "envios_error": envios_error,
    }


def registrar_rutas_starken_lotes(app):
    @app.route("/of_exito/<lote>")
    def of_exito(lote):
        db = SessionLocal()
        try:
            resumen = _resumen_of_lote(db, lote)
            if not resumen["total"]:
                flash("No se encontro informacion del lote procesado.", "warning")
                return redirect("/en_proceso")

            return render_template("of_exito.html", resumen=resumen)
        finally:
            db.close()

    @app.route("/generar_excel", methods=["POST"])
    def generar_excel():
        # Bloquea y valida exclusivamente las filas elegidas antes de crear el lote.
        db = SessionLocal()
        accion = request.form.get("accion", "descargar").strip()

        try:
            envios_pendientes = _obtener_envios_seleccionados_para_lote(
                db,
                request.form.getlist("envio_ids"),
            )
        except ValueError as exc:
            db.rollback()
            db.close()
            flash(str(exc), "danger")
            return redirect("/envios")

        agencias_sin_codigo = [
            envio for envio in envios_pendientes
            if envio.e_tipo_envio == "Agencia" and not envio.e_codigo_agencia
        ]

        if agencias_sin_codigo:
            db.close()
            flash(
                "Hay envios de agencia sin codigo. Editalos antes de generar el lote Starken.",
                "danger",
            )
            return redirect("/envios")

        if accion == "enviar" and not correo_starken_configurado():
            db.close()
            flash("Faltan credenciales de correo en .env. No se genero ningun lote.", "danger")
            return redirect("/envios")

        fecha_actual = ahora_chile()
        lote = fecha_actual.strftime("LOTE-%Y%m%d-%H%M%S")
        nombre_archivo, contenido_bytes = generar_csv_starken(envios_pendientes, fecha_actual)

        fila_excel = 2
        for envio in envios_pendientes:
            envio.e_estado = "en_proceso"
            envio.e_lote = lote
            envio.e_fila_excel = fila_excel
            envio.e_fecha_exportacion = fecha_actual
            envio.e_nombre_archivo = nombre_archivo
            envio.e_correo_destino = obtener_correo_destino_starken()
            envio.e_fecha_envio_correo = None
            envio.e_estado_correo = "pendiente" if accion == "enviar" else "descargado"
            fila_excel += 1

        try:
            guardar_respaldo_lote(nombre_archivo, contenido_bytes)
        except Exception as e:
            logger.exception("No se pudo guardar respaldo temporal de lote Starken")
            flash(
                "No se pudo guardar una copia temporal del CSV, "
                "pero el lote continuara porque el respaldo critico esta en la base/correo.",
                "warning",
            )

        db.commit()

        if accion == "descargar":
            db.close()
            return send_file(
                io.BytesIO(contenido_bytes),
                as_attachment=True,
                download_name=nombre_archivo,
                mimetype="text/csv",
            )

        try:
            enviar_archivo_starken(nombre_archivo, contenido_bytes, lote)
        except Exception as e:
            db.rollback()
            logger.exception("No se pudo enviar correo Starken para lote %s", lote)

            for envio in envios_pendientes:
                envio_db = db.query(Envio).filter(Envio.id == envio.id).first()
                if envio_db:
                    envio_db.e_estado_correo = "error"

            db.commit()
            flash(f"No se pudo enviar el correo del lote {lote}: {str(e)}", "danger")
            return redirect("/en_proceso")
        else:
            fecha_envio = ahora_chile()
            for envio in envios_pendientes:
                envio.e_fecha_envio_correo = fecha_envio
                envio.e_estado_correo = "enviado"

            db.commit()
            flash(f"Archivo enviado correctamente por correo. Lote: {lote}", "success")
            return redirect("/en_proceso")
        finally:
            db.close()

    @app.route("/cargar_of/<lote>", methods=["POST"])
    def cargar_of(lote):
        db = SessionLocal()
        archivo = request.files.get("archivo_of")

        if not archivo or archivo.filename == "":
            db.close()
            flash("Debes seleccionar un archivo Excel OF", "danger")
            return redirect("/en_proceso")

        try:
            resultado = procesar_archivo_of(db, lote, archivo, archivo.filename)
            flash(resultado["mensaje"], "success")
            _enviar_respaldo_post_of(db, lote, resultado)
            return _redirect_post_of(lote, resultado)
        except OFProcessingError as e:
            db.rollback()
            flash(str(e), "danger")
            return redirect("/en_proceso")
        except Exception as e:
            db.rollback()
            logger.exception("Error al procesar archivo OF para lote %s", lote)
            flash(f"Error al procesar el archivo OF: {str(e)}", "danger")
            return redirect("/en_proceso")
        finally:
            db.close()

    @app.route("/of_correo")
    def of_correo():
        db = SessionLocal()
        try:
            lotes = obtener_lotes_en_proceso(db)
        finally:
            db.close()

        correos = []
        correos_ocultos = 0
        busqueda_realizada = request.args.get("buscar") == "1"
        mostrar_todos = request.args.get("mostrar_todos") == "1"

        if busqueda_realizada:
            if not correo_of_configurado():
                flash("Faltan credenciales IMAP para revisar el correo OF.", "danger")
            else:
                try:
                    correos = buscar_correos_of(limite=10)
                    correos, correos_ocultos = preparar_correos_of_para_lotes(
                        correos,
                        lotes,
                        mostrar_todos,
                    )

                    if not correos:
                        if correos_ocultos:
                            flash(
                                "Solo se encontraron correos OF sin lote activo asociado. "
                                "Probablemente ya fueron procesados.",
                                "warning",
                            )
                        else:
                            flash("No se encontraron correos con adjuntos OF Excel.", "warning")
                except Exception as e:
                    logger.exception("No se pudo revisar el correo OF")
                    flash(f"No se pudo revisar el correo: {str(e)}", "danger")

        return render_template(
            "of_correo.html",
            lotes=lotes,
            correos=correos,
            correos_ocultos=correos_ocultos,
            busqueda_realizada=busqueda_realizada,
            mostrar_todos=mostrar_todos,
            correo_configurado=correo_of_configurado(),
        )

    @app.route("/procesar_of_correo", methods=["POST"])
    def procesar_of_correo():
        lote = request.form.get("lote", "").strip()
        uid = request.form.get("uid", "").strip()
        indice_adjunto = request.form.get("indice_adjunto", "").strip()

        if not lote or not uid or indice_adjunto == "":
            flash("Debes seleccionar lote y archivo OF del correo.", "danger")
            return redirect("/of_correo?buscar=1")

        db = SessionLocal()

        try:
            nombre_archivo, contenido, archivo_procesado = descargar_adjunto_of(uid, indice_adjunto)

            if not lote_coincide_con_archivo(db, lote, archivo_procesado):
                flash(
                    "El correo OF indica un archivo procesado distinto al lote seleccionado. "
                    "No se proceso nada.",
                    "danger",
                )
                return redirect("/of_correo?buscar=1")

            archivo = io.BytesIO(contenido)
            resultado = procesar_archivo_of(db, lote, archivo, nombre_archivo)
            flash(f"{resultado['mensaje']} Archivo tomado desde correo: {nombre_archivo}", "success")
            _enviar_respaldo_post_of(db, lote, resultado)
            return _redirect_post_of(lote, resultado)
        except OFProcessingError as e:
            db.rollback()
            flash(str(e), "danger")
            return redirect("/of_correo?buscar=1")
        except Exception as e:
            db.rollback()
            logger.exception("No se pudo procesar OF desde correo para lote %s", lote)
            flash(f"No se pudo procesar el OF desde correo: {str(e)}", "danger")
            return redirect("/of_correo?buscar=1")
        finally:
            db.close()

    @app.route("/cancelar_lote/<lote>", methods=["POST"])
    def cancelar_lote(lote):
        db = SessionLocal()

        envios_lote = (
            db.query(Envio)
            .filter(Envio.e_lote == lote, Envio.e_estado == "en_proceso")
            .all()
        )

        if not envios_lote:
            db.close()
            flash("No se encontro el lote o ya no esta en proceso", "warning")
            return redirect("/en_proceso")

        for envio in envios_lote:
            envio.e_estado = "pendiente"
            envio.e_lote = None
            envio.e_fila_excel = None
            envio.e_fecha_exportacion = None
            envio.e_resultado_of = None
            envio.e_detalle_of = None
            envio.e_orden_flete = None
            envio.e_estado_correo = None

        db.commit()
        db.close()

        flash("Lote cancelado correctamente. Los envios volvieron a pendientes", "warning")
        return redirect("/en_proceso")
