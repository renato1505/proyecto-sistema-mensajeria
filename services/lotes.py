from database.modelos import Envio


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
