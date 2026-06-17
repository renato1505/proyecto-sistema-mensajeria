import logging

from database.conexion import SessionLocal
from database.modelos import Comuna, Destinatario, Envio, Remitente
from utils.texto import (
    normalizar_nombre_operativo,
    normalizar_orden_flete,
    normalizar_texto_operativo,
)


logger = logging.getLogger(__name__)


def _normalizar_envio(envio):
    cambios = 0
    nombres = {
        "e_remitente": normalizar_nombre_operativo(envio.e_remitente),
        "e_destinatario": normalizar_nombre_operativo(envio.e_destinatario),
    }
    otros = {
        "e_division": normalizar_texto_operativo(envio.e_division),
        "e_direccion": normalizar_texto_operativo(envio.e_direccion),
        "e_comuna": normalizar_texto_operativo(envio.e_comuna),
        "e_region": normalizar_texto_operativo(envio.e_region),
        "e_observacion": normalizar_texto_operativo(envio.e_observacion),
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
    nombre = normalizar_nombre_operativo(remitente.r_nombre)
    division = normalizar_texto_operativo(remitente.r_division, upper=True)

    if remitente.r_nombre != nombre:
        remitente.r_nombre = nombre
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
        "d_direccion": normalizar_texto_operativo(destinatario.d_direccion),
        "d_comuna": normalizar_texto_operativo(destinatario.d_comuna),
        "d_region": normalizar_texto_operativo(destinatario.d_region),
        "d_observacion": normalizar_texto_operativo(destinatario.d_observacion),
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


def normalizar_datos_operativos():
    db = SessionLocal()
    try:
        cambios = 0

        for envio in db.query(Envio).all():
            cambios += _normalizar_envio(envio)

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
