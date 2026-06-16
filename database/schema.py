from sqlalchemy import inspect, text

from database.conexion import engine


def asegurar_columnas_operativas():
    inspector = inspect(engine)
    columnas_envios = {columna["name"] for columna in inspector.get_columns("envios")}
    columnas_destinatarios = {
        columna["name"] for columna in inspector.get_columns("destinatarios")
    }

    alteraciones = []

    if "e_aviso_funcionario_estado" not in columnas_envios:
        alteraciones.append(
            "ALTER TABLE envios ADD COLUMN IF NOT EXISTS e_aviso_funcionario_estado VARCHAR(50)"
        )

    if "e_fecha_aviso_funcionario" not in columnas_envios:
        alteraciones.append(
            "ALTER TABLE envios ADD COLUMN IF NOT EXISTS e_fecha_aviso_funcionario TIMESTAMP"
        )

    if "e_correo_destinatario" not in columnas_envios:
        alteraciones.append(
            "ALTER TABLE envios ADD COLUMN IF NOT EXISTS e_correo_destinatario VARCHAR(255)"
        )

    if "e_observacion" not in columnas_envios:
        alteraciones.append(
            "ALTER TABLE envios ADD COLUMN IF NOT EXISTS e_observacion VARCHAR(500)"
        )

    if "e_anulado" not in columnas_envios:
        alteraciones.append(
            "ALTER TABLE envios ADD COLUMN IF NOT EXISTS e_anulado BOOLEAN DEFAULT FALSE NOT NULL"
        )

    if "e_fecha_anulacion" not in columnas_envios:
        alteraciones.append(
            "ALTER TABLE envios ADD COLUMN IF NOT EXISTS e_fecha_anulacion TIMESTAMP"
        )

    if "e_motivo_anulacion" not in columnas_envios:
        alteraciones.append(
            "ALTER TABLE envios ADD COLUMN IF NOT EXISTS e_motivo_anulacion VARCHAR(500)"
        )

    if "d_correo" not in columnas_destinatarios:
        alteraciones.append(
            "ALTER TABLE destinatarios ADD COLUMN IF NOT EXISTS d_correo VARCHAR(255)"
        )

    if "d_observacion" not in columnas_destinatarios:
        alteraciones.append(
            "ALTER TABLE destinatarios ADD COLUMN IF NOT EXISTS d_observacion VARCHAR(500)"
        )

    if not alteraciones:
        return

    with engine.begin() as conexion:
        for consulta in alteraciones:
            conexion.execute(text(consulta))
