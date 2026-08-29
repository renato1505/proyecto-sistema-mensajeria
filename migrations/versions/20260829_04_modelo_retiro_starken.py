"""Crea la persistencia de retiros fisicos Starken.

Revision ID: 20260829_04
Revises: 20260828_03
Create Date: 2026-08-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260829_04"
down_revision: Union[str, None] = "20260828_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "retiros_starken",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("rs_codigo", sa.String(40), nullable=False),
        sa.Column("punto_retiro_id", sa.Integer(), nullable=False),
        sa.Column("rs_fecha_retiro", sa.DateTime(), nullable=False),
        sa.Column("rs_fecha_confirmacion", sa.DateTime(), nullable=False),
        sa.Column("rs_responsable", sa.String(160), nullable=True),
        sa.Column("rs_observacion", sa.String(1000), nullable=True),
        sa.Column("rs_anulado", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("rs_fecha_anulacion", sa.DateTime(), nullable=True),
        sa.Column("rs_motivo_anulacion", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(
            ["punto_retiro_id"],
            ["puntos_retiro.id"],
            name="fk_retiros_starken_punto_retiro",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("rs_codigo", name="uq_retiros_starken_rs_codigo"),
    )
    op.create_index("ix_retiros_starken_punto_retiro_id", "retiros_starken", ["punto_retiro_id"])
    op.create_index("ix_retiros_starken_rs_fecha_retiro", "retiros_starken", ["rs_fecha_retiro"])
    op.create_index("ix_retiros_starken_rs_anulado", "retiros_starken", ["rs_anulado"])

    op.create_table(
        "retiro_envios",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("retiro_id", sa.Integer(), nullable=False),
        sa.Column("envio_id", sa.Integer(), nullable=False),
        sa.Column("re_bultos_snapshot", sa.Integer(), nullable=False),
        sa.Column("re_fecha_asociacion", sa.DateTime(), nullable=False),
        sa.Column("re_vigente", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.CheckConstraint(
            "re_bultos_snapshot >= 1",
            name="ck_retiro_envios_bultos_snapshot_positivo",
        ),
        sa.ForeignKeyConstraint(
            ["retiro_id"],
            ["retiros_starken.id"],
            name="fk_retiro_envios_retiro",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["envio_id"],
            ["envios.id"],
            name="fk_retiro_envios_envio",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_retiro_envios_retiro_id", "retiro_envios", ["retiro_id"])
    op.create_index(
        "uq_retiro_envios_envio_vigente",
        "retiro_envios",
        ["envio_id"],
        unique=True,
        postgresql_where=sa.text("re_vigente IS TRUE"),
        sqlite_where=sa.text("re_vigente = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_retiro_envios_envio_vigente", table_name="retiro_envios")
    op.drop_index("ix_retiro_envios_retiro_id", table_name="retiro_envios")
    op.drop_table("retiro_envios")

    op.drop_index("ix_retiros_starken_rs_anulado", table_name="retiros_starken")
    op.drop_index("ix_retiros_starken_rs_fecha_retiro", table_name="retiros_starken")
    op.drop_index("ix_retiros_starken_punto_retiro_id", table_name="retiros_starken")
    op.drop_table("retiros_starken")
