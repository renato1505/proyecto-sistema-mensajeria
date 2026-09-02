"""Crea la persistencia independiente de Avisos V2.

Revision ID: 20260829_05
Revises: 20260829_04
Create Date: 2026-08-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260829_05"
down_revision: Union[str, None] = "20260829_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avisos_envio",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("envio_id", sa.Integer(), nullable=False),
        sa.Column("av_tipo", sa.String(30), nullable=False),
        sa.Column("av_correo_snapshot", sa.String(255), nullable=True),
        sa.Column("av_estado", sa.String(30), nullable=False),
        sa.Column("av_intentos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("av_fecha_creacion", sa.DateTime(), nullable=False),
        sa.Column("av_fecha_procesamiento", sa.DateTime(), nullable=True),
        sa.Column("av_fecha_envio", sa.DateTime(), nullable=True),
        sa.Column("av_ultimo_error", sa.String(1500), nullable=True),
        sa.Column("av_clave_idempotencia", sa.String(160), nullable=False),
        sa.Column("av_message_id", sa.String(255), nullable=True),
        sa.CheckConstraint(
            "av_tipo IN ('FUNCIONARIO', 'DESTINATARIO')",
            name="ck_avisos_envio_tipo_valido",
        ),
        sa.CheckConstraint(
            "av_estado IN ('PENDIENTE', 'PROCESANDO', 'ENVIADO', 'ERROR', 'INCIERTO', 'CANCELADO')",
            name="ck_avisos_envio_estado_valido",
        ),
        sa.CheckConstraint(
            "av_intentos >= 0",
            name="ck_avisos_envio_intentos_no_negativo",
        ),
        sa.ForeignKeyConstraint(
            ["envio_id"],
            ["envios.id"],
            name="fk_avisos_envio_envio",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "envio_id",
            "av_tipo",
            name="uq_avisos_envio_envio_tipo",
        ),
        sa.UniqueConstraint(
            "av_clave_idempotencia",
            name="uq_avisos_envio_clave_idempotencia",
        ),
    )
    op.create_index("ix_avisos_envio_envio_id", "avisos_envio", ["envio_id"])
    op.create_index("ix_avisos_envio_av_estado", "avisos_envio", ["av_estado"])
    op.create_index("ix_avisos_envio_av_tipo", "avisos_envio", ["av_tipo"])
    op.create_index(
        "ix_avisos_envio_av_fecha_creacion",
        "avisos_envio",
        ["av_fecha_creacion"],
    )


def downgrade() -> None:
    op.drop_index("ix_avisos_envio_av_fecha_creacion", table_name="avisos_envio")
    op.drop_index("ix_avisos_envio_av_tipo", table_name="avisos_envio")
    op.drop_index("ix_avisos_envio_av_estado", table_name="avisos_envio")
    op.drop_index("ix_avisos_envio_envio_id", table_name="avisos_envio")
    op.drop_table("avisos_envio")
