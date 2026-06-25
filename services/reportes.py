from sqlalchemy import func, or_
from database.modelos import Envio, EvidenciaExcepcion, ExcepcionEnvio, MovimientoExcepcion
from utils.fechas import ahora_chile
from utils.texto import normalizar_texto_operativo


ESTADOS_EXCEPCION = [
    "abierto",
    "en seguimiento",
    "esperando starken",
    "resuelto",
    "cerrado",
    "anulado",
]

TIPOS_EXCEPCION = [
    "No entregado",
    "Robo o extravio",
    "Devuelve a origen",
    "Cambio de direccion",
    "Reintento de entrega",
    "Demora en entrega",
    "Otro",
]

TIPOS_MOVIMIENTO = [
    "Informacion Starken",
    "Indicacion enviada",
    "Respuesta recibida",
    "Recepcion en origen",
    "Nota interna",
]

RESULTADOS_CIERRE = [
    "Devuelto a origen",
    "Entregado",
    "Reenviado",
    "Extraviado",
    "Cerrado sin gestion adicional",
]

ESTADOS_CERRADOS = {"resuelto", "cerrado", "anulado"}
ESTADOS_ACTIVOS = [estado for estado in ESTADOS_EXCEPCION if estado not in ESTADOS_CERRADOS]


def leer_filtros_reportes(args):
    return {
        "estado": (args.get("estado") or "todos").strip().lower(),
        "q": normalizar_texto_operativo(args.get("q", "").strip()),
    }


def agrupar_reportes_por_remitente(reportes_data):
    grupos = []
    indice = {}

    for reporte, envio in reportes_data:
        remitente = envio.e_remitente or "Sin remitente"
        clave = remitente.casefold()

        if clave not in indice:
            indice[clave] = {
                "remitente": remitente,
                "total": 0,
                "abiertos": 0,
                "casos": [],
            }
            grupos.append(indice[clave])

        grupo = indice[clave]
        grupo["total"] += 1
        if reporte.x_estado not in ESTADOS_CERRADOS:
            grupo["abiertos"] += 1
        grupo["casos"].append({"reporte": reporte, "envio": envio})

    return grupos


def buscar_envio_reportable(db, envio_id=None, orden_flete=""):
    query = db.query(Envio).filter(Envio.e_estado == "historico")

    if envio_id:
        return query.filter(Envio.id == envio_id).first()

    orden_flete = str(orden_flete or "").strip()
    if orden_flete:
        return query.filter(Envio.e_orden_flete == orden_flete).first()

    return None


def buscar_reporte_vigente_por_envio(db, envio_id):
    return (
        db.query(ExcepcionEnvio)
        .filter(
            ExcepcionEnvio.envio_id == envio_id,
            ~ExcepcionEnvio.x_estado.in_(ESTADOS_CERRADOS),
        )
        .order_by(ExcepcionEnvio.x_fecha_actualizacion.desc(), ExcepcionEnvio.id.desc())
        .first()
    )


def query_reportes(db, filtros):
    query = (
        db.query(ExcepcionEnvio, Envio)
        .join(Envio, ExcepcionEnvio.envio_id == Envio.id)
    )

    estado = filtros["estado"]
    if estado == "abiertos":
        query = query.filter(~ExcepcionEnvio.x_estado.in_(ESTADOS_CERRADOS))
    elif estado == "cerrados":
        query = query.filter(ExcepcionEnvio.x_estado.in_(ESTADOS_CERRADOS))
    elif estado in ESTADOS_EXCEPCION:
        query = query.filter(ExcepcionEnvio.x_estado == estado)

    termino = filtros["q"]
    if termino:
        like = f"%{termino}%"
        query = query.filter(or_(
            Envio.e_orden_flete.ilike(like),
            Envio.e_destinatario.ilike(like),
        ))

    return query.order_by(
        ExcepcionEnvio.x_fecha_actualizacion.desc(),
        ExcepcionEnvio.id.desc(),
    )


def movimientos_por_reporte(db, reporte_ids):
    if not reporte_ids:
        return {}

    movimientos = (
        db.query(MovimientoExcepcion)
        .filter(MovimientoExcepcion.reporte_id.in_(reporte_ids))
        .order_by(MovimientoExcepcion.m_fecha.asc(), MovimientoExcepcion.id.asc())
        .all()
    )

    resultado = {reporte_id: [] for reporte_id in reporte_ids}
    for movimiento in movimientos:
        resultado.setdefault(movimiento.reporte_id, []).append(movimiento)

    return resultado


def evidencias_por_reporte(db, reporte_ids):
    if not reporte_ids:
        return {}

    evidencias = (
        db.query(EvidenciaExcepcion)
        .filter(EvidenciaExcepcion.reporte_id.in_(reporte_ids))
        .order_by(EvidenciaExcepcion.ev_fecha.desc(), EvidenciaExcepcion.id.desc())
        .all()
    )

    resultado = {reporte_id: [] for reporte_id in reporte_ids}
    for evidencia in evidencias:
        resultado.setdefault(evidencia.reporte_id, []).append(evidencia)

    return resultado


def estado_reportes_por_envio(db, envio_ids):
    if not envio_ids:
        return {}

    reportes = (
        db.query(ExcepcionEnvio)
        .filter(ExcepcionEnvio.envio_id.in_(envio_ids))
        .order_by(ExcepcionEnvio.x_fecha_actualizacion.desc(), ExcepcionEnvio.id.desc())
        .all()
    )

    resultado = {}
    for reporte in reportes:
        if reporte.envio_id in resultado:
            continue
        resultado[reporte.envio_id] = {
            "id": reporte.id,
            "estado": reporte.x_estado,
            "abierto": reporte.x_estado not in ESTADOS_CERRADOS,
            "of_retorno": reporte.x_of_retorno,
        }

    return resultado


def metricas_reportes(db):
    total = db.query(ExcepcionEnvio).count()
    abiertos = (
        db.query(ExcepcionEnvio)
        .filter(~ExcepcionEnvio.x_estado.in_(ESTADOS_CERRADOS))
        .count()
    )
    en_seguimiento = (
        db.query(ExcepcionEnvio)
        .filter(ExcepcionEnvio.x_estado == "en seguimiento")
        .count()
    )
    por_estado = dict(
        db.query(ExcepcionEnvio.x_estado, func.count(ExcepcionEnvio.id))
        .group_by(ExcepcionEnvio.x_estado)
        .all()
    )

    return {
        "total": total,
        "abiertos": abiertos,
        "en_seguimiento": en_seguimiento,
        "resueltos": por_estado.get("resuelto", 0) + por_estado.get("cerrado", 0),
    }


def contar_reportes_abiertos(db):
    return (
        db.query(ExcepcionEnvio)
        .filter(~ExcepcionEnvio.x_estado.in_(ESTADOS_CERRADOS))
        .count()
    )


def crear_reporte(envio, data):
    ahora = ahora_chile()
    estado = data.get("estado") if data.get("estado") in ESTADOS_EXCEPCION else "abierto"

    return ExcepcionEnvio(
        envio_id=envio.id,
        x_estado=estado,
        x_tipo=data["tipo"],
        x_prioridad="normal",
        x_contacto_starken=data.get("contacto_starken", ""),
        x_detalle=data.get("detalle", ""),
        x_indicacion=data.get("indicacion", ""),
        x_respuesta=data.get("respuesta", ""),
        x_fecha_creacion=ahora,
        x_fecha_actualizacion=ahora,
        x_fecha_cierre=ahora if estado in ESTADOS_CERRADOS else None,
    )


def crear_movimiento(reporte, tipo, detalle):
    tipo = tipo if tipo in TIPOS_MOVIMIENTO else "Nota interna"
    movimiento = MovimientoExcepcion(
        reporte_id=reporte.id,
        m_tipo=tipo,
        m_detalle=detalle,
        m_fecha=ahora_chile(),
    )
    reporte.x_fecha_actualizacion = movimiento.m_fecha
    return movimiento


def crear_evidencia(reporte, nombre_original, nombre_archivo, descripcion=""):
    ahora = ahora_chile()
    evidencia = EvidenciaExcepcion(
        reporte_id=reporte.id,
        ev_nombre_original=nombre_original,
        ev_nombre_archivo=nombre_archivo,
        ev_descripcion=descripcion,
        ev_fecha=ahora,
    )
    reporte.x_fecha_actualizacion = ahora
    movimiento = MovimientoExcepcion(
        reporte_id=reporte.id,
        m_tipo="Evidencia adjunta",
        m_detalle=(
            f"Archivo: {nombre_original}"
            + (f"\nDescripcion: {descripcion}" if descripcion else "")
        ),
        m_fecha=ahora,
    )
    return evidencia, movimiento


def actualizar_reporte(reporte, data):
    estado_anterior = reporte.x_estado
    estado = data.get("estado") if data.get("estado") in ESTADOS_EXCEPCION else reporte.x_estado

    reporte.x_estado = estado
    reporte.x_tipo = data["tipo"]
    reporte.x_prioridad = "normal"
    reporte.x_contacto_starken = data.get("contacto_starken", "")
    reporte.x_detalle = data.get("detalle", "")
    reporte.x_indicacion = data.get("indicacion", "")
    reporte.x_respuesta = data.get("respuesta", "")
    reporte.x_fecha_actualizacion = ahora_chile()

    if estado in ESTADOS_CERRADOS and estado_anterior not in ESTADOS_CERRADOS:
        reporte.x_fecha_cierre = ahora_chile()
    elif estado not in ESTADOS_CERRADOS:
        reporte.x_fecha_cierre = None


def cerrar_reporte(reporte, data):
    ahora = ahora_chile()
    resultado = data.get("resultado_final") if data.get("resultado_final") in RESULTADOS_CIERRE else "Cerrado sin gestion adicional"

    reporte.x_estado = "resuelto"
    reporte.x_resultado_final = resultado
    reporte.x_resumen_cierre = data.get("resumen_cierre", "")
    reporte.x_of_retorno = data.get("of_retorno", "")
    reporte.x_fecha_actualizacion = ahora
    reporte.x_fecha_cierre = ahora

    detalle = (
        f"Resultado final: {resultado}\n"
        f"OF retorno: {reporte.x_of_retorno or 'No aplica'}\n"
        f"Resumen: {reporte.x_resumen_cierre}"
    )
    return MovimientoExcepcion(
        reporte_id=reporte.id,
        m_tipo="Cierre de caso",
        m_detalle=detalle,
        m_fecha=ahora,
    )


def anular_reporte(reporte, motivo):
    motivo = normalizar_texto_operativo(motivo or "")
    if not motivo:
        raise ValueError("Debes indicar el motivo de anulacion.")

    ahora = ahora_chile()
    reporte.x_estado = "anulado"
    reporte.x_motivo_anulacion = motivo
    reporte.x_fecha_anulacion = ahora
    reporte.x_fecha_actualizacion = ahora
    reporte.x_fecha_cierre = ahora

    return MovimientoExcepcion(
        reporte_id=reporte.id,
        m_tipo="Reporte anulado",
        m_detalle=f"Motivo: {motivo}",
        m_fecha=ahora,
    )
