import logging

from flask import jsonify, request

from database.conexion import SessionLocal
from database.modelos import Comuna, Destinatario, Remitente
from services.catalogos_operativos import (
    MAX_RESULTADOS_AUTOCOMPLETE,
    buscar_destinatario_existente,
    guardar_destinatario_catalogo,
    guardar_remitente_catalogo,
    serializar_comuna,
    serializar_destinatario,
    serializar_remitente,
    validar_destinatario,
    validar_remitente,
)
from utils.validaciones import normalizar_telefono_chile


logger = logging.getLogger(__name__)


def _json_error(mensaje, status_code=400):
    response = jsonify({"ok": False, "mensaje": mensaje})
    response.status_code = status_code
    return response


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
        "correo": request.form.get("correo_destinatario", "").strip(),
        "observacion": request.form.get("observacion", "").strip(),
    }


def registrar_rutas_catalogos_ajax(app):
    @app.route("/buscar_comunas")
    def buscar_comunas():
        termino = request.args.get("q", "").strip()

        if len(termino) < 2:
            return jsonify([])

        db = SessionLocal()
        try:
            resultados = (
                db.query(Comuna)
                .filter(Comuna.c_nombre.ilike(f"%{termino}%"))
                .order_by(Comuna.c_nombre.asc())
                .limit(MAX_RESULTADOS_AUTOCOMPLETE)
                .all()
            )
            return jsonify([serializar_comuna(comuna) for comuna in resultados])
        finally:
            db.close()

    @app.route("/buscar_remitentes")
    def buscar_remitentes():
        termino = request.args.get("q", "").strip()

        if len(termino) < 2:
            return jsonify([])

        db = SessionLocal()
        try:
            resultados = (
                db.query(Remitente)
                .filter(Remitente.r_nombre.ilike(f"%{termino}%"))
                .order_by(Remitente.r_nombre.asc())
                .limit(MAX_RESULTADOS_AUTOCOMPLETE)
                .all()
            )
            return jsonify([serializar_remitente(remitente) for remitente in resultados])
        finally:
            db.close()

    @app.route("/guardar_remitente", methods=["POST"])
    def guardar_remitente():
        data = _leer_form_remitente()
        error = validar_remitente(data)

        if error:
            return _json_error(error)

        db = SessionLocal()
        try:
            ok, mensaje = guardar_remitente_catalogo(db, data)
            if not ok:
                return _json_error(mensaje)

            db.commit()
            return jsonify({"ok": True, "mensaje": mensaje})
        except Exception:
            db.rollback()
            logger.exception("No se pudo guardar remitente en catalogo")
            return _json_error("No se pudo guardar el remitente", 500)
        finally:
            db.close()

    @app.route("/buscar_destinatarios")
    def buscar_destinatarios():
        termino = request.args.get("q", "").strip()

        if len(termino) < 2:
            return jsonify([])

        db = SessionLocal()
        try:
            resultados = (
                db.query(Destinatario)
                .filter(Destinatario.d_nombre.ilike(f"%{termino}%"))
                .order_by(Destinatario.d_nombre.asc())
                .limit(MAX_RESULTADOS_AUTOCOMPLETE)
                .all()
            )
            return jsonify([
                serializar_destinatario(destinatario)
                for destinatario in resultados
            ])
        finally:
            db.close()

    @app.route("/guardar_destinatario", methods=["POST"])
    def guardar_destinatario():
        data = _leer_form_destinatario()
        error = validar_destinatario(data)

        if error:
            return _json_error(error)

        db = SessionLocal()
        try:
            existente = buscar_destinatario_existente(db, data)
            ok, mensaje = guardar_destinatario_catalogo(
                db,
                data,
                existente.id if existente else None,
            )
            if not ok:
                return _json_error(mensaje)

            db.commit()
            return jsonify({"ok": True, "mensaje": mensaje})
        except Exception:
            db.rollback()
            logger.exception("No se pudo guardar destinatario en catalogo")
            return _json_error("No se pudo guardar el destinatario", 500)
        finally:
            db.close()
