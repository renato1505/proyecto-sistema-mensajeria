from flask import flash, redirect, render_template, request

from database.conexion import SessionLocal
from database.modelos import Envio
from utils.texto import (
    normalizar_correo_operativo,
    normalizar_nombre_operativo,
    normalizar_nombre_remitente,
    normalizar_observacion_operativa,
    normalizar_texto_operativo,
)
from utils.validaciones import (
    email_valido,
    normalizar_telefono_chile,
    rut_operativo_valido,
    telefono_chile_valido,
)


def _leer_form_envio():
    return {
        "remitente": normalizar_nombre_remitente(request.form.get("remitente", "").strip()),
        "correo_remitente": normalizar_correo_operativo(request.form.get("correo_remitente", "").strip()),
        "division": normalizar_texto_operativo(request.form.get("division", "").strip(), upper=True),
        "centro_costo": request.form.get("centro_costo", "").strip(),
        "destinatario": normalizar_nombre_operativo(request.form.get("destinatario", "").strip()),
        "rut_destinatario": request.form.get("rut_destinatario", "").strip(),
        "direccion": normalizar_texto_operativo(request.form.get("direccion", "").strip()),
        "comuna": normalizar_texto_operativo(request.form.get("comuna", "").strip()),
        "region": normalizar_texto_operativo(request.form.get("region", "").strip()),
        "telefono_destinatario": normalizar_telefono_chile(
            request.form.get("telefono_destinatario", "").strip()
        ),
        "correo_destinatario": normalizar_correo_operativo(request.form.get("correo_destinatario", "").strip()),
        "observacion": normalizar_observacion_operativa(request.form.get("observacion", "").strip()),
        "tipo_envio": request.form.get("tipo_envio", "").strip(),
        "codigo_agencia": request.form.get("codigo_agencia", "").strip(),
        "bultos": request.form.get("bultos", "").strip(),
        "kilos": request.form.get("kilos", "").strip(),
    }


def _validar_form_envio(data):
    campos_obligatorios = [
        data["remitente"],
        data["correo_remitente"],
        data["division"],
        data["centro_costo"],
        data["destinatario"],
        data["rut_destinatario"],
        data["direccion"],
        data["comuna"],
        data["region"],
        data["telefono_destinatario"],
        data["tipo_envio"],
        data["bultos"],
        data["kilos"],
    ]

    if not all(campos_obligatorios):
        return None, None, "Todos los campos obligatorios deben estar completos"

    if not email_valido(data["correo_remitente"]):
        return None, None, "El correo del remitente no tiene un formato valido"

    if not rut_operativo_valido(data["rut_destinatario"]):
        return None, None, "Debes ingresar RUT del destinatario o 0 si no fue informado"

    if not telefono_chile_valido(data["telefono_destinatario"]):
        return None, None, "El telefono debe tener 8 o 9 digitos"

    if data["correo_destinatario"] and not email_valido(data["correo_destinatario"]):
        return None, None, "El correo del destinatario no tiene un formato valido"

    if data["tipo_envio"] == "Agencia":
        if not data["codigo_agencia"]:
            return None, None, "Debes ingresar el codigo de agencia"

        if not data["codigo_agencia"].isdigit():
            return None, None, "El codigo de agencia debe contener solo numeros"

        if len(data["codigo_agencia"]) > 5:
            return None, None, "El codigo de agencia no puede superar 5 digitos"

    try:
        bultos_int = int(data["bultos"])
        kilos_int = int(data["kilos"])
    except ValueError:
        return None, None, "Bultos y kilos deben ser numericos"

    if bultos_int < 1 or kilos_int < 1:
        return None, None, "Bultos y kilos deben ser mayores a 0"

    if bultos_int > 9999 or kilos_int > 9999:
        return None, None, "Bultos y kilos no pueden superar 9999"

    return bultos_int, kilos_int, None


def _aplicar_data_envio(envio, data, bultos_int, kilos_int):
    envio.e_remitente = data["remitente"]
    envio.e_correo_remitente = data["correo_remitente"]
    envio.e_division = data["division"]
    envio.e_centro_costo = data["centro_costo"]
    envio.e_destinatario = data["destinatario"]
    envio.e_rut_destinatario = data["rut_destinatario"]
    envio.e_direccion = data["direccion"]
    envio.e_comuna = data["comuna"]
    envio.e_region = data["region"]
    envio.e_telefono_destinatario = data["telefono_destinatario"]
    envio.e_correo_destinatario = data["correo_destinatario"]
    envio.e_observacion = data["observacion"]
    envio.e_tipo_envio = data["tipo_envio"]
    envio.e_codigo_agencia = data["codigo_agencia"]
    envio.e_bultos = bultos_int
    envio.e_kilos = kilos_int


def _guardar_envio_desde_form(envio):
    data = _leer_form_envio()
    bultos_int, kilos_int, error = _validar_form_envio(data)

    if error:
        return error

    _aplicar_data_envio(envio, data, bultos_int, kilos_int)
    return None


def registrar_rutas_envios(app):
    @app.route("/nuevo_envio", methods=["GET", "POST"])
    def nuevo_envio():
        if request.method == "POST":
            db = SessionLocal()
            nuevo = Envio(e_estado="pendiente")
            error = _guardar_envio_desde_form(nuevo)

            if error:
                db.close()
                flash(error, "danger")
                return redirect("/nuevo_envio")

            db.add(nuevo)
            db.commit()
            db.close()

            flash("Envio registrado correctamente", "success")
            return redirect("/nuevo_envio")

        return render_template("nuevo_envio.html")

    @app.route("/eliminar_envio/<int:id>", methods=["POST"])
    def eliminar_envio(id):
        db = SessionLocal()
        envio = db.query(Envio).filter(Envio.id == id).first()

        if envio:
            db.delete(envio)
            db.commit()
            flash("Envio eliminado correctamente", "danger")

        db.close()
        return redirect("/envios")

    @app.route("/editar_envio/<int:id>", methods=["GET", "POST"])
    def editar_envio(id):
        db = SessionLocal()
        envio = db.query(Envio).filter(Envio.id == id).first()

        if not envio:
            db.close()
            flash("El envio no existe", "danger")
            return redirect("/envios")

        if request.method == "POST":
            error = _guardar_envio_desde_form(envio)

            if error:
                db.close()
                flash(error, "danger")
                return redirect(f"/editar_envio/{id}")

            db.commit()
            db.close()

            flash("Envio editado correctamente", "warning")
            return redirect("/envios")

        db.close()
        return render_template("editar_envio.html", envio=envio)
