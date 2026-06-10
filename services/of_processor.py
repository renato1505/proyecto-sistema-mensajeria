import pandas as pd

from database.modelos import Envio


class OFProcessingError(Exception):
    pass


def _leer_excel_of(archivo, nombre_archivo):
    nombre = (nombre_archivo or "").lower()

    if nombre.endswith(".xls"):
        return pd.read_excel(archivo, engine="xlrd")

    return pd.read_excel(archivo, engine="openpyxl")


def _normalizar_columnas(df):
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


def _validar_columnas(df):
    columnas_requeridas = ["estado", "fila", "orden flete", "detalle"]

    for columna in columnas_requeridas:
        if columna not in df.columns:
            raise OFProcessingError(f"Falta la columna requerida: {columna}")


def procesar_archivo_of(db, lote, archivo, nombre_archivo):
    """Valida y aplica un archivo OF, ya sea subido manualmente o tomado del correo."""
    df = _normalizar_columnas(_leer_excel_of(archivo, nombre_archivo))
    _validar_columnas(df)

    envios_lote = (
        db.query(Envio)
        .filter(Envio.e_lote == lote, Envio.e_estado == "en_proceso")
        .all()
    )

    if not envios_lote:
        raise OFProcessingError("No se encontraron envios en proceso para este lote")

    df_validas = df[df["fila"].notna()].copy()
    cantidad_filas_archivo = len(df_validas)
    cantidad_envios_lote = len(envios_lote)

    if cantidad_filas_archivo != cantidad_envios_lote:
        raise OFProcessingError(
            f"La cantidad de filas del archivo OF ({cantidad_filas_archivo}) "
            f"no coincide con la cantidad de envios del lote ({cantidad_envios_lote}). "
            "No se proceso nada."
        )

    # La columna "fila" es el enlace con el CSV enviado a Starken.
    # Si hay filas duplicadas o invalidas, es mas seguro abortar todo el lote.
    filas_archivo = []
    for valor in df_validas["fila"].tolist():
        try:
            filas_archivo.append(int(valor))
        except (ValueError, TypeError):
            raise OFProcessingError("El archivo OF contiene una fila invalida en la columna 'fila'")

    if len(filas_archivo) != len(set(filas_archivo)):
        raise OFProcessingError("El archivo OF tiene filas repetidas. No se proceso nada.")

    ofs_archivo = []
    for _, fila in df_validas.iterrows():
        estado = str(fila.get("estado", "")).strip().upper()
        orden_flete = fila.get("orden flete")

        if estado == "OK" and not pd.isna(orden_flete):
            orden_texto = str(orden_flete).strip()
            if orden_texto:
                ofs_archivo.append(orden_texto)

    if len(ofs_archivo) != len(set(ofs_archivo)):
        raise OFProcessingError(
            "El archivo OF contiene ordenes de flete duplicadas. No se proceso nada."
        )

    # Una orden de flete no puede quedar asociada a dos lotes distintos.
    if ofs_archivo:
        ofs_existentes = (
            db.query(Envio)
            .filter(Envio.e_orden_flete.in_(ofs_archivo), Envio.e_lote != lote)
            .all()
        )

        if ofs_existentes:
            repetidas = sorted({e.e_orden_flete for e in ofs_existentes if e.e_orden_flete})
            raise OFProcessingError(
                "Ya existen ordenes de flete registradas en el sistema: "
                f"{', '.join(repetidas)}. No se proceso nada."
            )

    total_ok = 0
    total_error = 0
    total_sin_match = 0

    for _, fila in df_validas.iterrows():
        estado = str(fila.get("estado", "")).strip().upper()
        fila_excel = fila.get("fila")
        orden_flete = fila.get("orden flete")
        detalle = fila.get("detalle")

        try:
            fila_excel = int(fila_excel)
        except (ValueError, TypeError):
            continue

        envio = (
            db.query(Envio)
            .filter(
                Envio.e_lote == lote,
                Envio.e_fila_excel == fila_excel,
                Envio.e_estado == "en_proceso",
            )
            .first()
        )

        if not envio:
            total_sin_match += 1
            continue

        detalle_texto = "" if pd.isna(detalle) else str(detalle).strip()
        orden_texto = "" if pd.isna(orden_flete) else str(orden_flete).strip()

        envio.e_resultado_of = estado
        envio.e_detalle_of = detalle_texto

        if estado == "OK":
            envio.e_orden_flete = orden_texto
            envio.e_estado = "historico"
            total_ok += 1
        else:
            envio.e_orden_flete = None
            envio.e_estado = "en_proceso"
            total_error += 1

    db.commit()

    return {
        "total_ok": total_ok,
        "total_error": total_error,
        "total_sin_match": total_sin_match,
        "mensaje": (
            f"Archivo OF procesado correctamente. OK: {total_ok} | "
            f"ERROR: {total_error} | Sin coincidencia: {total_sin_match}"
        ),
    }
