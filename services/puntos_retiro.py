from database.modelos import PuntoRetiro


PUNTO_MENSAJERIA_LOCAL = "MENSAJERIA_LOCAL"
PUNTO_ACADEMIA = "ACADEMIA"
MARCADOR_ACADEMIA_LEGACY = "ACM"


def codigo_punto_retiro_para_centro_costo(centro_costo):
    marcador = str(centro_costo or "").strip().upper()
    if marcador == MARCADOR_ACADEMIA_LEGACY:
        return PUNTO_ACADEMIA
    return PUNTO_MENSAJERIA_LOCAL


def asignar_punto_retiro_nuevo_envio(db, envio):
    codigo = codigo_punto_retiro_para_centro_costo(envio.e_centro_costo)
    punto = (
        db.query(PuntoRetiro)
        .filter(PuntoRetiro.pr_codigo == codigo, PuntoRetiro.pr_activo.is_(True))
        .one_or_none()
    )
    if punto is None:
        raise RuntimeError(f"No existe el punto de retiro activo requerido: {codigo}")
    envio.e_punto_retiro_id = punto.id
    return punto
