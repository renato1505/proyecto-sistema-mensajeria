import logging
import math
from datetime import datetime

from flask import flash, redirect, render_template, request, session, url_for

from database.conexion import SessionLocal
from database.modelos import RetiroEnvio
from services.retiros import (
    RetiroConcurrenciaError,
    RetiroValidacionError,
    confirmar_retiro,
    obtener_envios_elegibles,
)
from utils.fechas import ahora_chile


logger = logging.getLogger(__name__)
FILAS_POR_PAGINA = 25


def _entero_positivo(valor, predeterminado=1):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return predeterminado
    return numero if numero > 0 else predeterminado


def _coincide_busqueda(envio, termino):
    if not termino:
        return True
    texto = " ".join(
        (
            str(envio.orden_flete or ""),
            str(envio.remitente or ""),
            str(envio.destinatario or ""),
        )
    ).casefold()
    return termino.casefold() in texto


def _responsable_actual():
    return session.get("usuario_display") or session.get("usuario_nombre") or None


def _parsear_fecha_retiro(valor):
    try:
        return datetime.fromisoformat(str(valor or "").strip())
    except (TypeError, ValueError):
        raise RetiroValidacionError("Debes indicar una fecha y hora efectiva valida") from None


def registrar_rutas_retiros(app):
    @app.get("/operacion/retiros")
    def ver_retiros_listos():
        db = SessionLocal()
        try:
            elegibles = obtener_envios_elegibles(db)
        finally:
            db.close()

        busqueda = request.args.get("q", "").strip()
        filtrados = [envio for envio in elegibles if _coincide_busqueda(envio, busqueda)]
        total_paginas = math.ceil(len(filtrados) / FILAS_POR_PAGINA) if filtrados else 0
        pagina = _entero_positivo(request.args.get("pagina"))
        if total_paginas:
            pagina = min(pagina, total_paginas)
        inicio = (pagina - 1) * FILAS_POR_PAGINA

        return render_template(
            "retiros_listos.html",
            envios=filtrados[inicio:inicio + FILAS_POR_PAGINA],
            busqueda=busqueda,
            pagina=pagina,
            total_paginas=total_paginas,
            total_filtrados=len(filtrados),
            total_bultos=sum(envio.bultos for envio in filtrados),
            todos_elegibles=[{"id": envio.envio_id, "bultos": envio.bultos} for envio in elegibles],
            elegibles_filtrados=[
                {"id": envio.envio_id, "bultos": envio.bultos} for envio in filtrados
            ],
            fecha_retiro_default=ahora_chile().strftime("%Y-%m-%dT%H:%M"),
            responsable=_responsable_actual(),
        )

    @app.post("/operacion/retiros/confirmar")
    def confirmar_retiro_operativo():
        db = SessionLocal()
        try:
            retiro = confirmar_retiro(
                db,
                request.form.getlist("envio_ids"),
                _parsear_fecha_retiro(request.form.get("fecha_retiro")),
                responsable=_responsable_actual(),
                observacion=request.form.get("observacion"),
            )
            snapshots = (
                db.query(RetiroEnvio.re_bultos_snapshot)
                .filter(RetiroEnvio.retiro_id == retiro.id)
                .all()
            )
            cantidad = len(snapshots)
            bultos = sum(valor for (valor,) in snapshots)
            flash(
                f"Retiro {retiro.rs_codigo} registrado. "
                f"{cantidad} envios \u00b7 {bultos} bultos.",
                "success",
            )
        except RetiroConcurrenciaError:
            flash(
                "No se pudo registrar el retiro porque uno o mas envios ya fueron "
                "retirados o dejaron de ser elegibles. La lista fue actualizada.",
                "warning",
            )
        except RetiroValidacionError as exc:
            flash(str(exc), "warning")
        except Exception:
            logger.exception("Error inesperado al confirmar un retiro Starken")
            flash("No se pudo registrar el retiro por un error inesperado.", "danger")
        finally:
            db.close()

        return redirect(url_for("ver_retiros_listos"))
