"""Snapshot explícito del contrato V2 consolidado en 20261025_06.

No se deriva de metadata al validar ni de la cabeza de Alembic. Cambiar este
contrato exige revisar compatibilidad y cobertura para la versión desplegada.
"""
REVISIONES_V2 = (
    "20260826_01", "20260828_02", "20260828_03",
    "20260829_04", "20260829_05", "20261025_06",
)

COLUMNAS_V2 = (
    ('remitentes', ('id', 'r_nombre', 'r_correo', 'r_division', 'r_centro_costo')),
    ('destinatarios', ('id', 'd_nombre', 'd_rut', 'd_direccion', 'd_comuna', 'd_region', 'd_telefono', 'd_correo', 'd_observacion')),
    ('comunas', ('id', 'c_nombre', 'c_region')),
    ('areas_operativas', ('id', 'ar_codigo', 'ar_nombre', 'ar_activa', 'ar_fecha_creacion')),
    ('usuarios_sistema', ('id', 'u_usuario', 'u_nombre', 'u_rut', 'u_clave_hash', 'u_area', 'u_rol', 'u_activo', 'u_debe_cambiar_clave', 'u_ultimo_acceso', 'u_ultimo_ip', 'u_fecha_creacion', 'u_fecha_actualizacion')),
    ('puntos_retiro', ('id', 'pr_codigo', 'pr_nombre', 'pr_es_local', 'pr_incluir_metricas_locales', 'pr_activo', 'pr_fecha_creacion')),
    ('envios', ('id', 'e_remitente', 'e_correo_remitente', 'e_division', 'e_centro_costo', 'e_destinatario', 'e_rut_destinatario', 'e_direccion', 'e_comuna', 'e_region', 'e_telefono_destinatario', 'e_correo_destinatario', 'e_observacion', 'e_tipo_envio', 'e_codigo_agencia', 'e_bultos', 'e_kilos', 'e_estado', 'e_orden_flete', 'e_lote', 'e_fila_excel', 'e_resultado_of', 'e_detalle_of', 'e_fecha_exportacion', 'e_fecha_of', 'e_punto_retiro_id', 'e_nombre_archivo', 'e_correo_destino', 'e_fecha_envio_correo', 'e_estado_correo', 'e_aviso_funcionario_estado', 'e_fecha_aviso_funcionario', 'e_anulado', 'e_fecha_anulacion', 'e_motivo_anulacion', 'e_fecha_creacion')),
    ('avisos_envio', ('id', 'envio_id', 'av_tipo', 'av_correo_snapshot', 'av_estado', 'av_intentos', 'av_fecha_creacion', 'av_fecha_procesamiento', 'av_fecha_envio', 'av_ultimo_error', 'av_clave_idempotencia', 'av_message_id')),
    ('retiros_starken', ('id', 'rs_codigo', 'punto_retiro_id', 'rs_fecha_retiro', 'rs_fecha_confirmacion', 'rs_responsable', 'rs_observacion', 'rs_anulado', 'rs_fecha_anulacion', 'rs_motivo_anulacion')),
    ('retiro_envios', ('id', 'retiro_id', 'envio_id', 're_bultos_snapshot', 're_fecha_asociacion', 're_vigente')),
    ('excepciones_envio', ('id', 'envio_id', 'x_estado', 'x_tipo', 'x_prioridad', 'x_contacto_starken', 'x_detalle', 'x_indicacion', 'x_respuesta', 'x_resultado_final', 'x_resumen_cierre', 'x_of_retorno', 'x_fecha_anulacion', 'x_motivo_anulacion', 'x_fecha_creacion', 'x_fecha_actualizacion', 'x_fecha_cierre')),
    ('movimientos_excepcion', ('id', 'reporte_id', 'm_tipo', 'm_detalle', 'm_fecha')),
    ('evidencias_excepcion', ('id', 'reporte_id', 'ev_nombre_original', 'ev_nombre_archivo', 'ev_descripcion', 'ev_fecha')),
    ('auditoria', ('id', 'a_fecha', 'a_usuario', 'a_accion', 'a_entidad', 'a_entidad_id', 'a_detalle')),
    ('solicitudes_recuperacion_clave', ('id', 'sr_usuario', 'sr_correo', 'sr_correo_enmascarado', 'sr_rut', 'sr_ip', 'sr_estado', 'sr_nota', 'sr_clave_temporal_generada', 'sr_fecha_creacion', 'sr_fecha_revision', 'sr_revisado_por')),
    ('intentos_of', ('id', 'envio_id', 'io_secuencia', 'io_transportista', 'io_lote', 'io_fila', 'io_archivo', 'io_fecha_creacion', 'io_estado', 'io_anterior_id')),
    ('registros_of', ('id', 'intento_id', 'envio_id', 'ro_transportista', 'ro_numero', 'ro_fecha_registro', 'ro_origen')),
    ('conciliaciones_h2h', ('id', 'intento_id', 'envio_id', 'ch_resultado_original', 'ch_detalle_original', 'ch_estado', 'ch_fecha_creacion', 'ch_fecha_deteccion', 'ch_fecha_verificacion', 'ch_operador', 'ch_metodo', 'ch_observacion', 'ch_referencia', 'ch_registro_of_id', 'ch_intento_sucesor_id')),
    ('movimientos_envio', ('id', 'envio_id', 'intento_id', 'me_tipo', 'me_fecha', 'me_actor', 'me_detalle', 'me_clave_idempotencia')),
)

UNICOS_V2 = (
    ('areas_operativas', ('ar_codigo',)),
    ('usuarios_sistema', ('u_usuario',)),
    ('puntos_retiro', ('pr_codigo',)),
    ('avisos_envio', ('envio_id', 'av_tipo')),
    ('avisos_envio', ('av_clave_idempotencia',)),
    ('retiros_starken', ('rs_codigo',)),
    ('intentos_of', ('envio_id', 'io_secuencia')),
    ('intentos_of', ('id', 'envio_id')),
    ('intentos_of', ('id', 'envio_id', 'io_transportista')),
    ('intentos_of', ('id', 'envio_id', 'io_anterior_id')),
    ('intentos_of', ('io_anterior_id',)),
    ('registros_of', ('intento_id',)),
    ('registros_of', ('ro_transportista', 'ro_numero')),
    ('registros_of', ('id', 'intento_id', 'envio_id')),
    ('conciliaciones_h2h', ('intento_id',)),
    ('conciliaciones_h2h', ('ch_intento_sucesor_id',)),
    ('movimientos_envio', ('me_clave_idempotencia',)),
)

FKS_V2 = (
    ('envios', ('e_punto_retiro_id',), 'puntos_retiro', ('id',)),
    ('avisos_envio', ('envio_id',), 'envios', ('id',)),
    ('retiros_starken', ('punto_retiro_id',), 'puntos_retiro', ('id',)),
    ('retiro_envios', ('retiro_id',), 'retiros_starken', ('id',)),
    ('retiro_envios', ('envio_id',), 'envios', ('id',)),
    ('intentos_of', ('io_anterior_id', 'envio_id'), 'intentos_of', ('id', 'envio_id')),
    ('intentos_of', ('envio_id',), 'envios', ('id',)),
    ('registros_of', ('intento_id', 'envio_id', 'ro_transportista'), 'intentos_of', ('id', 'envio_id', 'io_transportista')),
    ('registros_of', ('envio_id',), 'envios', ('id',)),
    ('conciliaciones_h2h', ('intento_id', 'envio_id'), 'intentos_of', ('id', 'envio_id')),
    ('conciliaciones_h2h', ('ch_intento_sucesor_id', 'envio_id', 'intento_id'), 'intentos_of', ('id', 'envio_id', 'io_anterior_id')),
    ('conciliaciones_h2h', ('ch_registro_of_id', 'intento_id', 'envio_id'), 'registros_of', ('id', 'intento_id', 'envio_id')),
    ('conciliaciones_h2h', ('envio_id',), 'envios', ('id',)),
    ('movimientos_envio', ('intento_id', 'envio_id'), 'intentos_of', ('id', 'envio_id')),
    ('movimientos_envio', ('envio_id',), 'envios', ('id',)),
)

INDICES_PARCIALES_V2 = (
    ("retiro_envios", "uq_retiro_envios_envio_vigente", ("envio_id",),
     ("re_vigente IS TRUE", "re_vigente = 1", "re_vigente IS 1")),
    ("intentos_of", "uq_intentos_of_envio_abierto", ("envio_id",),
     ("io_estado IN ('ABIERTO', 'EN_VERIFICACION')",
      "io_estado = ANY (ARRAY['ABIERTO', 'EN_VERIFICACION'])")),
)

# Subconjunto deliberado: no se afirma equivalencia general de expresiones SQL.
CHECKS_V2 = (
    ("retiro_envios", "ck_retiro_envios_bultos_snapshot_positivo", "re_bultos_snapshot >= 1"),
    ("intentos_of", "ck_intentos_of_secuencia_positiva", "io_secuencia >= 1"),
    ("avisos_envio", "ck_avisos_envio_intentos_no_negativo", "av_intentos >= 0"),
)
