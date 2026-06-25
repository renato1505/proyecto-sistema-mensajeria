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
from utils.texto import (
    clave_texto_operativo,
    normalizar_correo_operativo,
    normalizar_nombre_operativo,
    normalizar_nombre_remitente,
    normalizar_observacion_operativa,
    normalizar_texto_operativo,
)
from utils.validaciones import normalizar_telefono_operativo


logger = logging.getLogger(__name__)


def _json_error(mensaje, status_code=400):
    response = jsonify({"ok": False, "mensaje": mensaje})
    response.status_code = status_code
    return response


def _deduplicar_items(items, clave_fn):
    vistos = set()
    resultado = []

    for item in items:
        clave = clave_fn(item)
        if clave in vistos:
            continue
        vistos.add(clave)
        resultado.append(item)

    return resultado


def _leer_form_remitente():
    return {
        "nombre": normalizar_nombre_remitente(request.form.get("remitente", "").strip()),
        "correo": normalizar_correo_operativo(request.form.get("correo_remitente", "").strip()),
        "division": normalizar_texto_operativo(request.form.get("division", "").strip(), upper=True),
        "centro_costo": request.form.get("centro_costo", "").strip(),
    }


def _leer_form_destinatario():
    telefono_codigo_pais = request.form.get("telefono_codigo_pais", "56").strip()
    return {
        "rut": request.form.get("rut_destinatario", "").strip(),
        "nombre": normalizar_nombre_operativo(request.form.get("destinatario", "").strip()),
        "direccion": normalizar_texto_operativo(request.form.get("direccion", "").strip()),
        "comuna": normalizar_texto_operativo(request.form.get("comuna", "").strip()),
        "region": normalizar_texto_operativo(request.form.get("region", "").strip()),
        "telefono_codigo_pais": telefono_codigo_pais,
        "telefono": normalizar_telefono_operativo(
            request.form.get("telefono_destinatario", "").strip(),
            telefono_codigo_pais,
        ),
        "correo": normalizar_correo_operativo(request.form.get("correo_destinatario", "").strip()),
        "observacion": normalizar_observacion_operativa(request.form.get("observacion", "").strip()),
    }


def registrar_rutas_catalogos_ajax(app):
    @app.route("/buscar_comunas")
    def buscar_comunas():
        termino = normalizar_texto_operativo(request.args.get("q", "").strip())

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
            items = [serializar_comuna(comuna) for comuna in resultados]
            items = _deduplicar_items(
                items,
                lambda item: (
                    clave_texto_operativo(item["nombre"]),
                    clave_texto_operativo(item["region"]),
                ),
            )
            return jsonify(items)
        finally:
            db.close()

    @app.route("/buscar_remitentes")
    def buscar_remitentes():
        termino = normalizar_texto_operativo(request.args.get("q", "").strip())

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
            items = [serializar_remitente(remitente) for remitente in resultados]
            items = _deduplicar_items(
                items,
                lambda item: (
                    clave_texto_operativo(item["nombre"]),
                    item["correo"].strip().lower(),
                    clave_texto_operativo(item["division"]),
                    item["centro_costo"].strip(),
                ),
            )
            return jsonify(items)
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
        termino = normalizar_texto_operativo(request.args.get("q", "").strip())

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
            items = [
                serializar_destinatario(destinatario)
                for destinatario in resultados
            ]
            items = _deduplicar_items(
                items,
                lambda item: (
                    item["rut"].strip(),
                    clave_texto_operativo(item["nombre"]),
                    clave_texto_operativo(item["direccion"]),
                    clave_texto_operativo(item["comuna"]),
                ),
            )
            return jsonify(items)
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
