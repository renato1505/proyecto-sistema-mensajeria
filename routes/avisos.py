import logging

from flask import flash, redirect, render_template, request

from database.conexion import SessionLocal
from services.avisos import (
    cancelar_avisos_lote,
    correo_avisos_configurado,
    enviar_avisos_lote,
    obtener_envios_lote,
    obtener_lotes_con_avisos,
    preparar_resumen_avisos,
)


logger = logging.getLogger(__name__)


def registrar_rutas_avisos(app):
    @app.route("/avisos")
    def avisos_pendientes():
        db = SessionLocal()
        try:
            lotes = obtener_lotes_con_avisos(db)
            return render_template("avisos_pendientes.html", lotes=lotes)
        finally:
            db.close()

    @app.route("/avisos_lote/<lote>")
    def avisos_lote(lote):
        db = SessionLocal()
        try:
            envios = obtener_envios_lote(db, lote)
            if not envios:
                flash("No se encontraron envios para este lote.", "warning")
                return redirect("/en_proceso")

            resumen = preparar_resumen_avisos(envios)
            return render_template(
                "avisos_lote.html",
                lote=lote,
                resumen=resumen,
                correo_configurado=correo_avisos_configurado(),
            )
        finally:
            db.close()

    @app.route("/enviar_avisos_lote/<lote>", methods=["POST"])
    def enviar_avisos_lote_route(lote):
        correos = request.form.getlist("correos")
        db = SessionLocal()

        try:
            envios = obtener_envios_lote(db, lote)
            if not envios:
                flash("No se encontraron envios para este lote.", "warning")
                return redirect("/en_proceso")

            resultado = enviar_avisos_lote(lote, envios, correos)
            db.commit()
            flash(
                f"Avisos enviados a {resultado['funcionarios']} funcionario(s) "
                f"y {resultado['destinatarios']} destinatario(s).",
                "success",
            )
            return redirect("/historico")
        except Exception as e:
            logger.exception("No se pudieron enviar avisos del lote %s", lote)
            flash(f"No se pudieron enviar los avisos: {str(e)}", "danger")
            return redirect(f"/avisos_lote/{lote}")
        finally:
            db.close()

    @app.route("/cancelar_avisos_lote/<lote>", methods=["POST"])
    def cancelar_avisos_lote_route(lote):
        db = SessionLocal()
        try:
            envios = obtener_envios_lote(db, lote)
            if not envios:
                flash("No se encontraron envios para este lote.", "warning")
                return redirect("/avisos")

            cantidad = cancelar_avisos_lote(envios)
            db.commit()
            flash(
                f"Se cancelaron los avisos pendientes del lote {lote}. "
                f"Registros actualizados: {cantidad}.",
                "warning",
            )
            return redirect("/avisos")
        except Exception as e:
            db.rollback()
            logger.exception("No se pudieron cancelar avisos del lote %s", lote)
            flash(f"No se pudieron cancelar los avisos: {str(e)}", "danger")
            return redirect(f"/avisos_lote/{lote}")
        finally:
            db.close()
