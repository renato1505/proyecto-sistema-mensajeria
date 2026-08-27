"""Baseline del esquema actual previo a Retiro Starken.

Revision ID: 20260826_01
Revises:
Create Date: 2026-08-26

Esta revision crea una base vacia. Una base productiva existente debe auditarse
y, si coincide, marcarse con ``alembic stamp 20260826_01`` sin ejecutar upgrade.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260826_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _crear_indices(tabla, especificaciones):
    for nombre, columnas, unico in especificaciones:
        op.create_index(nombre, tabla, columnas, unique=unico)


def upgrade() -> None:
    op.create_table(
        "areas_operativas",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("ar_codigo", sa.String(80), nullable=False),
        sa.Column("ar_nombre", sa.String(120), nullable=False),
        sa.Column("ar_activa", sa.Boolean(), nullable=False),
        sa.Column("ar_fecha_creacion", sa.DateTime(), nullable=True),
    )
    _crear_indices("areas_operativas", [
        ("ix_areas_operativas_id", ["id"], False),
        ("ix_areas_operativas_ar_codigo", ["ar_codigo"], True),
        ("ix_areas_operativas_ar_activa", ["ar_activa"], False),
        ("ix_areas_operativas_ar_fecha_creacion", ["ar_fecha_creacion"], False),
    ])

    op.create_table(
        "auditoria",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("a_fecha", sa.DateTime(), nullable=True),
        sa.Column("a_usuario", sa.String(120), nullable=False),
        sa.Column("a_accion", sa.String(120), nullable=False),
        sa.Column("a_entidad", sa.String(80), nullable=False),
        sa.Column("a_entidad_id", sa.String(80), nullable=True),
        sa.Column("a_detalle", sa.String(1500), nullable=True),
    )
    _crear_indices("auditoria", [
        ("ix_auditoria_id", ["id"], False),
        ("ix_auditoria_a_fecha", ["a_fecha"], False),
        ("ix_auditoria_a_usuario", ["a_usuario"], False),
        ("ix_auditoria_a_accion", ["a_accion"], False),
        ("ix_auditoria_a_entidad", ["a_entidad"], False),
    ])

    op.create_table(
        "comunas",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("c_nombre", sa.String(), nullable=False),
        sa.Column("c_region", sa.String(), nullable=False),
    )
    _crear_indices("comunas", [
        ("ix_comunas_id", ["id"], False),
        ("ix_comunas_c_nombre", ["c_nombre"], False),
    ])

    op.create_table(
        "destinatarios",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("d_nombre", sa.String(), nullable=False),
        sa.Column("d_rut", sa.String(), nullable=False),
        sa.Column("d_direccion", sa.String(), nullable=True),
        sa.Column("d_comuna", sa.String(), nullable=True),
        sa.Column("d_region", sa.String(), nullable=True),
        sa.Column("d_telefono", sa.String(), nullable=True),
        sa.Column("d_correo", sa.String(), nullable=True),
        sa.Column("d_observacion", sa.String(), nullable=True),
    )
    _crear_indices("destinatarios", [
        ("ix_destinatarios_id", ["id"], False),
        ("ix_destinatarios_d_nombre", ["d_nombre"], False),
    ])

    op.create_table(
        "envios",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("e_remitente", sa.String(), nullable=False),
        sa.Column("e_correo_remitente", sa.String(), nullable=True),
        sa.Column("e_division", sa.String(), nullable=True),
        sa.Column("e_centro_costo", sa.String(), nullable=True),
        sa.Column("e_destinatario", sa.String(), nullable=False),
        sa.Column("e_rut_destinatario", sa.String(), nullable=True),
        sa.Column("e_direccion", sa.String(), nullable=False),
        sa.Column("e_comuna", sa.String(), nullable=False),
        sa.Column("e_region", sa.String(), nullable=True),
        sa.Column("e_telefono_destinatario", sa.String(), nullable=True),
        sa.Column("e_correo_destinatario", sa.String(), nullable=True),
        sa.Column("e_observacion", sa.String(), nullable=True),
        sa.Column("e_tipo_envio", sa.String(), nullable=False),
        sa.Column("e_codigo_agencia", sa.String(), nullable=True),
        sa.Column("e_bultos", sa.Integer(), nullable=False),
        sa.Column("e_kilos", sa.Integer(), nullable=False),
        sa.Column("e_estado", sa.String(), nullable=True),
        sa.Column("e_orden_flete", sa.String(), nullable=True),
        sa.Column("e_lote", sa.String(), nullable=True),
        sa.Column("e_fila_excel", sa.Integer(), nullable=True),
        sa.Column("e_resultado_of", sa.String(), nullable=True),
        sa.Column("e_detalle_of", sa.String(), nullable=True),
        sa.Column("e_fecha_exportacion", sa.DateTime(), nullable=True),
        sa.Column("e_nombre_archivo", sa.String(255), nullable=True),
        sa.Column("e_correo_destino", sa.String(255), nullable=True),
        sa.Column("e_fecha_envio_correo", sa.DateTime(), nullable=True),
        sa.Column("e_estado_correo", sa.String(50), nullable=True),
        sa.Column("e_aviso_funcionario_estado", sa.String(50), nullable=True),
        sa.Column("e_fecha_aviso_funcionario", sa.DateTime(), nullable=True),
        sa.Column("e_anulado", sa.Boolean(), nullable=False),
        sa.Column("e_fecha_anulacion", sa.DateTime(), nullable=True),
        sa.Column("e_motivo_anulacion", sa.String(500), nullable=True),
        sa.Column("e_fecha_creacion", sa.DateTime(), nullable=True),
    )
    _crear_indices("envios", [
        ("ix_envios_id", ["id"], False),
        ("ix_envios_e_estado", ["e_estado"], False),
        ("ix_envios_e_orden_flete", ["e_orden_flete"], False),
        ("ix_envios_e_lote", ["e_lote"], False),
        ("ix_envios_e_aviso_funcionario_estado", ["e_aviso_funcionario_estado"], False),
        ("ix_envios_e_anulado", ["e_anulado"], False),
        ("ix_envios_e_fecha_creacion", ["e_fecha_creacion"], False),
    ])

    op.create_table(
        "evidencias_excepcion",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("reporte_id", sa.Integer(), nullable=False),
        sa.Column("ev_nombre_original", sa.String(255), nullable=False),
        sa.Column("ev_nombre_archivo", sa.String(255), nullable=False),
        sa.Column("ev_descripcion", sa.String(500), nullable=True),
        sa.Column("ev_fecha", sa.DateTime(), nullable=True),
    )
    _crear_indices("evidencias_excepcion", [
        ("ix_evidencias_excepcion_id", ["id"], False),
        ("ix_evidencias_excepcion_reporte_id", ["reporte_id"], False),
        ("ix_evidencias_excepcion_ev_fecha", ["ev_fecha"], False),
    ])

    op.create_table(
        "excepciones_envio",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("envio_id", sa.Integer(), nullable=False),
        sa.Column("x_estado", sa.String(50), nullable=False),
        sa.Column("x_tipo", sa.String(80), nullable=False),
        sa.Column("x_prioridad", sa.String(30), nullable=False),
        sa.Column("x_contacto_starken", sa.String(120), nullable=True),
        sa.Column("x_detalle", sa.String(1000), nullable=True),
        sa.Column("x_indicacion", sa.String(1000), nullable=True),
        sa.Column("x_respuesta", sa.String(1000), nullable=True),
        sa.Column("x_resultado_final", sa.String(80), nullable=True),
        sa.Column("x_resumen_cierre", sa.String(1500), nullable=True),
        sa.Column("x_of_retorno", sa.String(80), nullable=True),
        sa.Column("x_fecha_anulacion", sa.DateTime(), nullable=True),
        sa.Column("x_motivo_anulacion", sa.String(500), nullable=True),
        sa.Column("x_fecha_creacion", sa.DateTime(), nullable=True),
        sa.Column("x_fecha_actualizacion", sa.DateTime(), nullable=True),
        sa.Column("x_fecha_cierre", sa.DateTime(), nullable=True),
    )
    _crear_indices("excepciones_envio", [
        ("ix_excepciones_envio_id", ["id"], False),
        ("ix_excepciones_envio_envio_id", ["envio_id"], False),
        ("ix_excepciones_envio_x_estado", ["x_estado"], False),
        ("ix_excepciones_envio_x_tipo", ["x_tipo"], False),
        ("ix_excepciones_envio_x_fecha_creacion", ["x_fecha_creacion"], False),
    ])

    op.create_table(
        "movimientos_excepcion",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("reporte_id", sa.Integer(), nullable=False),
        sa.Column("m_tipo", sa.String(80), nullable=False),
        sa.Column("m_detalle", sa.String(1500), nullable=False),
        sa.Column("m_fecha", sa.DateTime(), nullable=True),
    )
    _crear_indices("movimientos_excepcion", [
        ("ix_movimientos_excepcion_id", ["id"], False),
        ("ix_movimientos_excepcion_reporte_id", ["reporte_id"], False),
        ("ix_movimientos_excepcion_m_fecha", ["m_fecha"], False),
    ])

    op.create_table(
        "remitentes",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("r_nombre", sa.String(), nullable=False),
        sa.Column("r_correo", sa.String(), nullable=True),
        sa.Column("r_division", sa.String(), nullable=True),
        sa.Column("r_centro_costo", sa.String(), nullable=True),
    )
    _crear_indices("remitentes", [
        ("ix_remitentes_id", ["id"], False),
        ("ix_remitentes_r_nombre", ["r_nombre"], False),
        ("ix_remitentes_r_correo", ["r_correo"], False),
    ])

    op.create_table(
        "solicitudes_recuperacion_clave",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("sr_usuario", sa.String(120), nullable=False),
        sa.Column("sr_correo", sa.String(255), nullable=False),
        sa.Column("sr_correo_enmascarado", sa.String(255), nullable=True),
        sa.Column("sr_rut", sa.String(20), nullable=True),
        sa.Column("sr_ip", sa.String(80), nullable=True),
        sa.Column("sr_estado", sa.String(40), nullable=False),
        sa.Column("sr_nota", sa.String(1000), nullable=True),
        sa.Column("sr_clave_temporal_generada", sa.Boolean(), nullable=False),
        sa.Column("sr_fecha_creacion", sa.DateTime(), nullable=True),
        sa.Column("sr_fecha_revision", sa.DateTime(), nullable=True),
        sa.Column("sr_revisado_por", sa.String(120), nullable=True),
    )
    _crear_indices("solicitudes_recuperacion_clave", [
        ("ix_solicitudes_recuperacion_clave_id", ["id"], False),
        ("ix_solicitudes_recuperacion_clave_sr_usuario", ["sr_usuario"], False),
        ("ix_solicitudes_recuperacion_clave_sr_estado", ["sr_estado"], False),
        ("ix_solicitudes_recuperacion_clave_sr_fecha_creacion", ["sr_fecha_creacion"], False),
    ])

    op.create_table(
        "usuarios_sistema",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("u_usuario", sa.String(120), nullable=False),
        sa.Column("u_nombre", sa.String(160), nullable=False),
        sa.Column("u_rut", sa.String(20), nullable=True),
        sa.Column("u_clave_hash", sa.String(255), nullable=False),
        sa.Column("u_area", sa.String(80), nullable=False),
        sa.Column("u_rol", sa.String(40), nullable=False),
        sa.Column("u_activo", sa.Boolean(), nullable=False),
        sa.Column("u_debe_cambiar_clave", sa.Boolean(), nullable=False),
        sa.Column("u_ultimo_acceso", sa.DateTime(), nullable=True),
        sa.Column("u_ultimo_ip", sa.String(80), nullable=True),
        sa.Column("u_fecha_creacion", sa.DateTime(), nullable=True),
        sa.Column("u_fecha_actualizacion", sa.DateTime(), nullable=True),
    )
    _crear_indices("usuarios_sistema", [
        ("ix_usuarios_sistema_id", ["id"], False),
        ("ix_usuarios_sistema_u_usuario", ["u_usuario"], True),
        ("ix_usuarios_sistema_u_rut", ["u_rut"], False),
        ("ix_usuarios_sistema_u_area", ["u_area"], False),
        ("ix_usuarios_sistema_u_rol", ["u_rol"], False),
        ("ix_usuarios_sistema_u_activo", ["u_activo"], False),
        ("ix_usuarios_sistema_u_debe_cambiar_clave", ["u_debe_cambiar_clave"], False),
        ("ix_usuarios_sistema_u_fecha_creacion", ["u_fecha_creacion"], False),
    ])


def downgrade() -> None:
    for tabla in [
        "usuarios_sistema",
        "solicitudes_recuperacion_clave",
        "remitentes",
        "movimientos_excepcion",
        "excepciones_envio",
        "evidencias_excepcion",
        "envios",
        "destinatarios",
        "comunas",
        "auditoria",
        "areas_operativas",
    ]:
        op.drop_table(tabla)
