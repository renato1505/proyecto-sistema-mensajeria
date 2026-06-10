from sqlalchemy import inspect, text

from database.conexion import engine


def asegurar_columnas_operativas():
    inspector = inspect(engine)
    columnas = {columna["name"] for columna in inspector.get_columns("envios")}

    alteraciones = []

    if "e_aviso_funcionario_estado" not in columnas:
        alteraciones.append(
            "ALTER TABLE envios ADD COLUMN IF NOT EXISTS e_aviso_funcionario_estado VARCHAR(50)"
        )

    if "e_fecha_aviso_funcionario" not in columnas:
        alteraciones.append(
            "ALTER TABLE envios ADD COLUMN IF NOT EXISTS e_fecha_aviso_funcionario TIMESTAMP"
        )

    if not alteraciones:
        return

    with engine.begin() as conexion:
        for consulta in alteraciones:
            conexion.execute(text(consulta))
