from sqlalchemy import func

from database.modelos import Comuna, Destinatario, Remitente
from utils.validaciones import (
    centro_costo_valido,
    email_valido,
    nombre_persona_valido,
    rut_operativo_valido,
    telefono_chile_valido,
)


MAX_RESULTADOS_AUTOCOMPLETE = 10
OPCIONES_PER_PAGE_CATALOGOS = [25, 50, 100]


def validar_remitente(data):
    if not data["nombre"]:
        return "El nombre del remitente es obligatorio"

    if not nombre_persona_valido(data["nombre"]):
        return "El nombre del remitente solo debe contener letras y espacios"

    if not data["correo"]:
        return "El correo del remitente es obligatorio"

    if not email_valido(data["correo"]):
        return "El correo del remitente no tiene un formato valido"

    if not data["division"]:
        return "La division del remitente es obligatoria"

    if not centro_costo_valido(data["centro_costo"]):
        return "El centro de costo del remitente debe contener solo numeros"

    return None


def validar_destinatario(data):
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

    if not nombre_persona_valido(data["nombre"]):
        return "El nombre del destinatario solo debe contener letras y espacios"

    if not rut_operativo_valido(data["rut"]):
        return "Debes ingresar RUT del destinatario o 0 si no fue informado"

    if not telefono_chile_valido(data["telefono"]):
        return "El telefono debe tener 8 o 9 digitos"

    return None


def serializar_comuna(comuna):
    return {
        "nombre": comuna.c_nombre,
        "region": comuna.c_region,
    }


def serializar_remitente(remitente):
    return {
        "nombre": remitente.r_nombre,
        "correo": remitente.r_correo,
        "division": remitente.r_division,
        "centro_costo": remitente.r_centro_costo,
    }


def serializar_destinatario(destinatario):
    return {
        "nombre": destinatario.d_nombre,
        "rut": destinatario.d_rut,
        "direccion": destinatario.d_direccion,
        "comuna": destinatario.d_comuna,
        "region": destinatario.d_region,
        "telefono": destinatario.d_telefono,
    }


def buscar_destinatario_existente(db, data):
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


def query_remitentes_filtrados(db, filtros):
    query = db.query(Remitente)

    if filtros["r_nombre"]:
        query = query.filter(Remitente.r_nombre.ilike(f"%{filtros['r_nombre']}%"))

    if filtros["r_division"]:
        query = query.filter(Remitente.r_division == filtros["r_division"])

    if filtros["r_centro_costo"]:
        query = query.filter(Remitente.r_centro_costo.ilike(f"%{filtros['r_centro_costo']}%"))

    return query


def query_destinatarios_filtrados(db, filtros):
    query = db.query(Destinatario)

    if filtros["d_nombre"]:
        query = query.filter(Destinatario.d_nombre.ilike(f"%{filtros['d_nombre']}%"))

    if filtros["d_rut"]:
        query = query.filter(Destinatario.d_rut.ilike(f"%{filtros['d_rut']}%"))

    if filtros["d_direccion"]:
        query = query.filter(Destinatario.d_direccion.ilike(f"%{filtros['d_direccion']}%"))

    if filtros["d_comuna"]:
        query = query.filter(Destinatario.d_comuna.ilike(f"%{filtros['d_comuna']}%"))

    return query


def divisiones_disponibles(db):
    resultados = (
        db.query(Remitente.r_division)
        .filter(Remitente.r_division.isnot(None), Remitente.r_division != "")
        .distinct()
        .order_by(Remitente.r_division.asc())
        .all()
    )
    return [item[0] for item in resultados if item[0]]


def guardar_remitente_catalogo(db, data, remitente_id=None):
    if remitente_id:
        remitente = db.query(Remitente).filter(Remitente.id == remitente_id).first()
        if not remitente:
            return False, "No se encontro el remitente solicitado"
    else:
        remitente = (
            db.query(Remitente)
            .filter(func.lower(Remitente.r_nombre) == data["nombre"].lower())
            .first()
        )

    if remitente:
        remitente.r_nombre = data["nombre"]
        remitente.r_correo = data["correo"]
        remitente.r_division = data["division"]
        remitente.r_centro_costo = data["centro_costo"]
        return True, "Remitente actualizado correctamente"

    db.add(Remitente(
        r_nombre=data["nombre"],
        r_correo=data["correo"],
        r_division=data["division"],
        r_centro_costo=data["centro_costo"],
    ))
    return True, "Remitente creado correctamente"


def guardar_destinatario_catalogo(db, data, destinatario_id=None):
    if destinatario_id:
        destinatario = (
            db.query(Destinatario)
            .filter(Destinatario.id == destinatario_id)
            .first()
        )
        if not destinatario:
            return False, "No se encontro el destinatario solicitado"
    else:
        destinatario = buscar_destinatario_existente(db, data)

    if destinatario:
        destinatario.d_rut = data["rut"]
        destinatario.d_nombre = data["nombre"]
        destinatario.d_direccion = data["direccion"]
        destinatario.d_comuna = data["comuna"]
        destinatario.d_region = data["region"]
        destinatario.d_telefono = data["telefono"]
        return True, "Destinatario actualizado correctamente"

    db.add(Destinatario(
        d_rut=data["rut"],
        d_nombre=data["nombre"],
        d_direccion=data["direccion"],
        d_comuna=data["comuna"],
        d_region=data["region"],
        d_telefono=data["telefono"],
    ))
    return True, "Destinatario creado correctamente"
