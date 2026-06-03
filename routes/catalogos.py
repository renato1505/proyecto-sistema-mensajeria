import logging

from flask import jsonify, request

from database.conexion import SessionLocal
from database.modelos import Comuna, Destinatario, Remitente
from utils.validaciones import (
    email_valido,
    normalizar_telefono_chile,
    rut_operativo_valido,
    telefono_chile_valido,
)


MAX_RESULTADOS_AUTOCOMPLETE = 10
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


def _validar_remitente(data):
    if not data["nombre"]:
        return "El nombre del remitente es obligatorio"

    if data["correo"] and not email_valido(data["correo"]):
        return "El correo del remitente no tiene un formato valido"

    return None


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


def _validar_destinatario(data):
    campos_obligatorios = [
        data["rut"],
        data["nombre"],
        data["direccion"],
        data["comuna"],
        data["region"],
        data["telefono"],
    ]

    if not all(campos_obligatorios):
        return "Todos los campos del destinatario son obligatorios"

    if not rut_operativo_valido(data["rut"]):
        return "Debes ingresar RUT del destinatario o 0 si no fue informado"

    if not telefono_chile_valido(data["telefono"]):
        return "El telefono debe tener 8 o 9 digitos"

    return None


def _serializar_comuna(comuna):
    return {
        "nombre": comuna.c_nombre,
        "region": comuna.c_region,
    }


def _serializar_remitente(remitente):
    return {
        "nombre": remitente.r_nombre,
        "correo": remitente.r_correo,
        "division": remitente.r_division,
        "centro_costo": remitente.r_centro_costo,
    }


def _serializar_destinatario(destinatario):
    return {
        "nombre": destinatario.d_nombre,
        "rut": destinatario.d_rut,
        "direccion": destinatario.d_direccion,
        "comuna": destinatario.d_comuna,
        "region": destinatario.d_region,
        "telefono": destinatario.d_telefono,
    }


def _buscar_destinatario_existente(db, data):
    if data["rut"] != "0":
        return db.query(Destinatario).filter(Destinatario.d_rut == data["rut"]).first()

    return (
        db.query(Destinatario)
        .filter(
            Destinatario.d_rut == "0",
            Destinatario.d_nombre == data["nombre"],
            Destinatario.d_direccion == data["direccion"],
            Destinatario.d_comuna == data["comuna"],
        )
        .first()
    )


def registrar_rutas_catalogos(app):
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
            return jsonify([_serializar_comuna(comuna) for comuna in resultados])
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
            return jsonify([_serializar_remitente(remitente) for remitente in resultados])
        finally:
            db.close()

    @app.route("/guardar_remitente", methods=["POST"])
    def guardar_remitente():
        data = _leer_form_remitente()
        error = _validar_remitente(data)

        if error:
            return _json_error(error)

        db = SessionLocal()
        try:
            existente = (
                db.query(Remitente)
                .filter(Remitente.r_nombre == data["nombre"])
                .first()
            )

            if existente:
                existente.r_correo = data["correo"]
                existente.r_division = data["division"]
                existente.r_centro_costo = data["centro_costo"]
                mensaje = "Remitente actualizado correctamente"
            else:
                nuevo_remitente = Remitente(
                    r_nombre=data["nombre"],
                    r_correo=data["correo"],
                    r_division=data["division"],
                    r_centro_costo=data["centro_costo"],
                )
                db.add(nuevo_remitente)
                mensaje = "Remitente guardado correctamente"

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
                _serializar_destinatario(destinatario)
                for destinatario in resultados
            ])
        finally:
            db.close()

    @app.route("/guardar_destinatario", methods=["POST"])
    def guardar_destinatario():
        data = _leer_form_destinatario()
        error = _validar_destinatario(data)

        if error:
            return _json_error(error)

        db = SessionLocal()
        try:
            existente = _buscar_destinatario_existente(db, data)

            if existente:
                existente.d_nombre = data["nombre"]
                existente.d_direccion = data["direccion"]
                existente.d_comuna = data["comuna"]
                existente.d_region = data["region"]
                existente.d_telefono = data["telefono"]
                mensaje = "Destinatario actualizado correctamente"
            else:
                nuevo_destinatario = Destinatario(
                    d_rut=data["rut"],
                    d_nombre=data["nombre"],
                    d_direccion=data["direccion"],
                    d_comuna=data["comuna"],
                    d_region=data["region"],
                    d_telefono=data["telefono"],
                )
                db.add(nuevo_destinatario)
                mensaje = "Destinatario guardado correctamente"

            db.commit()
            return jsonify({"ok": True, "mensaje": mensaje})
        except Exception:
            db.rollback()
            logger.exception("No se pudo guardar destinatario en catalogo")
            return _json_error("No se pudo guardar el destinatario", 500)
        finally:
            db.close()
