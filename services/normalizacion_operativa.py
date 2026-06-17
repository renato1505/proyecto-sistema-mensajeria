import logging

from database.conexion import SessionLocal
from database.modelos import Comuna, Destinatario, Envio, Remitente
from utils.texto import (
    normalizar_correo_operativo,
    normalizar_nombre_operativo,
    normalizar_nombre_remitente,
    normalizar_observacion_operativa,
    normalizar_orden_flete,
    normalizar_texto_operativo,
)


logger = logging.getLogger(__name__)


def _normalizar_envio(envio, remitentes_por_correo=None):
    cambios = 0
    correo_remitente = normalizar_correo_operativo(envio.e_correo_remitente)
    correo_destinatario = normalizar_correo_operativo(envio.e_correo_destinatario)
    remitente = normalizar_nombre_remitente(envio.e_remitente)

    if correo_remitente and remitentes_por_correo:
        remitente = remitentes_por_correo.get(correo_remitente, remitente)

    nombres = {
        "e_remitente": remitente,
        "e_destinatario": normalizar_nombre_operativo(envio.e_destinatario),
    }
    otros = {
        "e_correo_remitente": correo_remitente,
        "e_correo_destinatario": correo_destinatario,
        "e_division": normalizar_texto_operativo(envio.e_division),
        "e_direccion": normalizar_texto_operativo(envio.e_direccion),
        "e_comuna": normalizar_texto_operativo(envio.e_comuna),
        "e_region": normalizar_texto_operativo(envio.e_region),
        "e_observacion": normalizar_observacion_operativa(envio.e_observacion),
    }

    for campo, nuevo in {**nombres, **otros}.items():
        valor = getattr(envio, campo)
        if valor != nuevo:
            setattr(envio, campo, nuevo)
            cambios += 1

    nuevo_of = normalizar_orden_flete(envio.e_orden_flete)
    if envio.e_orden_flete != nuevo_of:
        envio.e_orden_flete = nuevo_of
        cambios += 1

    return cambios


def _normalizar_remitente(remitente):
    cambios = 0
    nombre = normalizar_nombre_remitente(remitente.r_nombre)
    correo = normalizar_correo_operativo(remitente.r_correo)
    division = normalizar_texto_operativo(remitente.r_division, upper=True)

    if remitente.r_nombre != nombre:
        remitente.r_nombre = nombre
        cambios += 1

    if remitente.r_correo != correo:
        remitente.r_correo = correo
        cambios += 1

    if remitente.r_division != division:
        remitente.r_division = division
        cambios += 1

    return cambios


def _normalizar_destinatario(destinatario):
    cambios = 0
    nombres = {
        "d_nombre": normalizar_nombre_operativo(destinatario.d_nombre),
    }
    otros = {
        "d_correo": normalizar_correo_operativo(destinatario.d_correo),
        "d_direccion": normalizar_texto_operativo(destinatario.d_direccion),
        "d_comuna": normalizar_texto_operativo(destinatario.d_comuna),
        "d_region": normalizar_texto_operativo(destinatario.d_region),
        "d_observacion": normalizar_observacion_operativa(destinatario.d_observacion),
    }

    for campo, nuevo in {**nombres, **otros}.items():
        valor = getattr(destinatario, campo)
        if valor != nuevo:
            setattr(destinatario, campo, nuevo)
            cambios += 1

    return cambios


def _normalizar_comuna(comuna):
    cambios = 0
    nombre = normalizar_texto_operativo(comuna.c_nombre)
    region = normalizar_texto_operativo(comuna.c_region)

    if comuna.c_nombre != nombre:
        comuna.c_nombre = nombre
        cambios += 1

    if comuna.c_region != region:
        comuna.c_region = region
        cambios += 1

    return cambios


def _unificar_remitentes_por_correo(db):
    cambios = 0
    principales = {}

    remitentes = db.query(Remitente).order_by(Remitente.id.asc()).all()
    for remitente in remitentes:
        cambios += _normalizar_remitente(remitente)
        correo = normalizar_correo_operativo(remitente.r_correo)
        if not correo:
            continue

        if correo not in principales:
            principales[correo] = remitente
            continue

        principal = principales[correo]
        if not principal.r_centro_costo and remitente.r_centro_costo:
            principal.r_centro_costo = remitente.r_centro_costo
            cambios += 1
        if not principal.r_division and remitente.r_division:
            principal.r_division = remitente.r_division
            cambios += 1

        db.delete(remitente)
        cambios += 1

    return cambios, {
        correo: normalizar_nombre_remitente(remitente.r_nombre)
        for correo, remitente in principales.items()
    }


def normalizar_datos_operativos():
    db = SessionLocal()
    try:
        cambios = 0

        cambios_remitentes, remitentes_por_correo = _unificar_remitentes_por_correo(db)
        cambios += cambios_remitentes

        for envio in db.query(Envio).all():
            cambios += _normalizar_envio(envio, remitentes_por_correo)

        # Segunda pasada para remitentes creados o modificados durante el arranque.
        for remitente in db.query(Remitente).all():
            cambios += _normalizar_remitente(remitente)

        for destinatario in db.query(Destinatario).all():
            cambios += _normalizar_destinatario(destinatario)

        for comuna in db.query(Comuna).all():
            cambios += _normalizar_comuna(comuna)

        if cambios:
            db.commit()
            logger.info("Normalizacion operativa aplicada: %s cambio(s)", cambios)
        else:
            db.rollback()
    except Exception:
        db.rollback()
        logger.exception("No se pudo completar la normalizacion operativa")
    finally:
        db.close()
