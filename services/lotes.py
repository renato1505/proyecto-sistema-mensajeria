from database.modelos import Envio
from services.starken import generar_csv_starken


def ids_envios_seleccionados(valores):
    if not valores:
        raise ValueError("Debes seleccionar al menos un envio para generar el lote.")
    try:
        ids = [int(valor) for valor in valores]
    except (TypeError, ValueError) as exc:
        raise ValueError("La seleccion contiene IDs de envio invalidos.") from exc
    if any(envio_id <= 0 for envio_id in ids):
        raise ValueError("La seleccion contiene IDs de envio invalidos.")
    if len(ids) != len(set(ids)):
        raise ValueError("La seleccion contiene IDs de envio duplicados.")
    return ids


def obtener_envios_seleccionados_para_lote(db, valores):
    ids = ids_envios_seleccionados(valores)
    envios = (
        db.query(Envio)
        .filter(Envio.id.in_(ids))
        .order_by(Envio.id.asc())
        .with_for_update()
        .all()
    )
    encontrados = {envio.id for envio in envios}
    if set(ids) - encontrados:
        raise ValueError(
            "Uno o mas envios seleccionados no existen. Recarga Pendientes e intenta nuevamente."
        )
    if any(envio.e_estado != "pendiente" or bool(envio.e_anulado) for envio in envios):
        raise ValueError(
            "Uno o mas envios seleccionados ya no estan pendientes. "
            "Recarga la pantalla antes de generar el lote."
        )
    if any(envio.e_tipo_envio == "Agencia" and not envio.e_codigo_agencia for envio in envios):
        raise ValueError(
            "Hay envios de agencia sin codigo. Editalos antes de generar el lote Starken."
        )
    return envios


def preparar_lote_starken(envios, fecha_actual, correo_destino="", estado_correo="descargado"):
    lote = fecha_actual.strftime("LOTE-%Y%m%d-%H%M%S")
    nombre_archivo, contenido_bytes = generar_csv_starken(envios, fecha_actual)
    for fila_excel, envio in enumerate(envios, start=2):
        envio.e_estado = "en_proceso"
        envio.e_lote = lote
        envio.e_fila_excel = fila_excel
        envio.e_fecha_exportacion = fecha_actual
        envio.e_nombre_archivo = nombre_archivo
        envio.e_correo_destino = correo_destino
        envio.e_fecha_envio_correo = None
        envio.e_estado_correo = estado_correo
    return {
        "lote": lote,
        "nombre_archivo": nombre_archivo,
        "contenido_bytes": contenido_bytes,
        "envios": envios,
    }


def obtener_lotes_en_proceso(db):
    """Devuelve los lotes activos junto al CSV Starken que origino cada lote."""
    filas = (
        db.query(Envio.e_lote, Envio.e_nombre_archivo)
        .filter(Envio.e_estado == "en_proceso", Envio.e_lote.isnot(None))
        .distinct()
        .order_by(Envio.e_lote.desc())
        .all()
    )

    return [
        {"lote": fila[0], "nombre_archivo": fila[1] or ""}
        for fila in filas
        if fila[0]
    ]


def buscar_lote_por_nombre_archivo(lotes, nombre_archivo):
    nombre = (nombre_archivo or "").strip().lower()

    if not nombre:
        return None

    for lote in lotes:
        if (lote["nombre_archivo"] or "").strip().lower() == nombre:
            return lote

    return None


def lote_coincide_con_archivo(db, lote, nombre_archivo):
    """Evita procesar una OF cuando el correo pertenece a otro CSV/lote."""
    nombre = (nombre_archivo or "").strip().lower()

    if not nombre:
        return True

    envio = (
        db.query(Envio)
        .filter(Envio.e_lote == lote, Envio.e_estado == "en_proceso")
        .first()
    )

    if not envio:
        return False

    return (envio.e_nombre_archivo or "").strip().lower() == nombre


def preparar_correos_of_para_lotes(correos, lotes, mostrar_todos=False):
    """Marca cada correo con su lote sugerido y oculta los ya procesados por defecto."""
    for correo in correos:
        correo.lote_sugerido = buscar_lote_por_nombre_archivo(
            lotes,
            correo.archivo_procesado,
        )

    if mostrar_todos:
        return correos, 0

    correos_con_lote = [correo for correo in correos if correo.lote_sugerido]
    return correos_con_lote, len(correos) - len(correos_con_lote)
