from sqlalchemy import inspect, text

from database.conexion import engine


def asegurar_columnas_operativas():
    inspector = inspect(engine)
    columnas_envios = {columna["name"] for columna in inspector.get_columns("envios")}
    columnas_destinatarios = {
        columna["name"] for columna in inspector.get_columns("destinatarios")
    }
    tablas = set(inspector.get_table_names())
    columnas_excepciones = (
        {columna["name"] for columna in inspector.get_columns("excepciones_envio")}
        if "excepciones_envio" in tablas
        else set()
    )
    columnas_movimientos = (
        {columna["name"] for columna in inspector.get_columns("movimientos_excepcion")}
        if "movimientos_excepcion" in tablas
        else set()
    )
    columnas_evidencias = (
        {columna["name"] for columna in inspector.get_columns("evidencias_excepcion")}
        if "evidencias_excepcion" in tablas
        else set()
    )
    columnas_usuarios = (
        {columna["name"] for columna in inspector.get_columns("usuarios_sistema")}
        if "usuarios_sistema" in tablas
        else set()
    )

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

    if "usuarios_sistema" in tablas:
        if "u_ultimo_acceso" not in columnas_usuarios:
            alteraciones.append(
                "ALTER TABLE usuarios_sistema ADD COLUMN IF NOT EXISTS u_ultimo_acceso TIMESTAMP"
            )

        if "u_ultimo_ip" not in columnas_usuarios:
            alteraciones.append(
                "ALTER TABLE usuarios_sistema ADD COLUMN IF NOT EXISTS u_ultimo_ip VARCHAR(80)"
            )

        if "u_debe_cambiar_clave" not in columnas_usuarios:
            alteraciones.append(
                "ALTER TABLE usuarios_sistema ADD COLUMN IF NOT EXISTS u_debe_cambiar_clave BOOLEAN DEFAULT FALSE NOT NULL"
            )

        if "u_rut" not in columnas_usuarios:
            alteraciones.append(
                "ALTER TABLE usuarios_sistema ADD COLUMN IF NOT EXISTS u_rut VARCHAR(20)"
            )

    if "solicitudes_recuperacion_clave" in tablas:
        columnas_recuperacion = {
            columna["name"] for columna in inspector.get_columns("solicitudes_recuperacion_clave")
        }
        if "sr_rut" not in columnas_recuperacion:
            alteraciones.append(
                "ALTER TABLE solicitudes_recuperacion_clave ADD COLUMN IF NOT EXISTS sr_rut VARCHAR(20)"
            )

    if "excepciones_envio" in tablas:
        if "x_contacto_starken" not in columnas_excepciones:
            alteraciones.append(
                "ALTER TABLE excepciones_envio ADD COLUMN IF NOT EXISTS x_contacto_starken VARCHAR(120)"
            )

        if "x_respuesta" not in columnas_excepciones:
            alteraciones.append(
                "ALTER TABLE excepciones_envio ADD COLUMN IF NOT EXISTS x_respuesta VARCHAR(1000)"
            )

        if "x_resultado_final" not in columnas_excepciones:
            alteraciones.append(
                "ALTER TABLE excepciones_envio ADD COLUMN IF NOT EXISTS x_resultado_final VARCHAR(80)"
            )

        if "x_resumen_cierre" not in columnas_excepciones:
            alteraciones.append(
                "ALTER TABLE excepciones_envio ADD COLUMN IF NOT EXISTS x_resumen_cierre VARCHAR(1500)"
            )

        if "x_of_retorno" not in columnas_excepciones:
            alteraciones.append(
                "ALTER TABLE excepciones_envio ADD COLUMN IF NOT EXISTS x_of_retorno VARCHAR(80)"
            )

        if "x_fecha_cierre" not in columnas_excepciones:
            alteraciones.append(
                "ALTER TABLE excepciones_envio ADD COLUMN IF NOT EXISTS x_fecha_cierre TIMESTAMP"
            )

        if "x_fecha_anulacion" not in columnas_excepciones:
            alteraciones.append(
                "ALTER TABLE excepciones_envio ADD COLUMN IF NOT EXISTS x_fecha_anulacion TIMESTAMP"
            )

        if "x_motivo_anulacion" not in columnas_excepciones:
            alteraciones.append(
                "ALTER TABLE excepciones_envio ADD COLUMN IF NOT EXISTS x_motivo_anulacion VARCHAR(500)"
            )

    if "movimientos_excepcion" in tablas:
        if "m_tipo" not in columnas_movimientos:
            alteraciones.append(
                "ALTER TABLE movimientos_excepcion ADD COLUMN IF NOT EXISTS m_tipo VARCHAR(80)"
            )

        if "m_detalle" not in columnas_movimientos:
            alteraciones.append(
                "ALTER TABLE movimientos_excepcion ADD COLUMN IF NOT EXISTS m_detalle VARCHAR(1500)"
            )

    if "evidencias_excepcion" in tablas:
        if "ev_nombre_original" not in columnas_evidencias:
            alteraciones.append(
                "ALTER TABLE evidencias_excepcion ADD COLUMN IF NOT EXISTS ev_nombre_original VARCHAR(255)"
            )

        if "ev_nombre_archivo" not in columnas_evidencias:
            alteraciones.append(
                "ALTER TABLE evidencias_excepcion ADD COLUMN IF NOT EXISTS ev_nombre_archivo VARCHAR(255)"
            )

        if "ev_descripcion" not in columnas_evidencias:
            alteraciones.append(
                "ALTER TABLE evidencias_excepcion ADD COLUMN IF NOT EXISTS ev_descripcion VARCHAR(500)"
            )

    if not alteraciones:
        return

    with engine.begin() as conexion:
        for consulta in alteraciones:
            conexion.execute(text(consulta))
