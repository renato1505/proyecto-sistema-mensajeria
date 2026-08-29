"""Incorpora fecha OF y punto de retiro persistido.

Revision ID: 20260828_03
Revises: 20260828_02
Create Date: 2026-08-28
"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_03"
down_revision: Union[str, None] = "20260828_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "puntos_retiro",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("pr_codigo", sa.String(40), nullable=False),
        sa.Column("pr_nombre", sa.String(120), nullable=False),
        sa.Column("pr_es_local", sa.Boolean(), nullable=False),
        sa.Column("pr_incluir_metricas_locales", sa.Boolean(), nullable=False),
        sa.Column("pr_activo", sa.Boolean(), nullable=False),
        sa.Column("pr_fecha_creacion", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("pr_codigo", name="uq_puntos_retiro_pr_codigo"),
    )

    puntos_retiro = sa.table(
        "puntos_retiro",
        sa.column("pr_codigo", sa.String(40)),
        sa.column("pr_nombre", sa.String(120)),
        sa.column("pr_es_local", sa.Boolean()),
        sa.column("pr_incluir_metricas_locales", sa.Boolean()),
        sa.column("pr_activo", sa.Boolean()),
        sa.column("pr_fecha_creacion", sa.DateTime()),
    )
    fecha_creacion = datetime.now()
    op.bulk_insert(puntos_retiro, [
        {
            "pr_codigo": "MENSAJERIA_LOCAL",
            "pr_nombre": "Mensajeria local",
            "pr_es_local": True,
            "pr_incluir_metricas_locales": True,
            "pr_activo": True,
            "pr_fecha_creacion": fecha_creacion,
        },
        {
            "pr_codigo": "ACADEMIA",
            "pr_nombre": "Academia",
            "pr_es_local": False,
            "pr_incluir_metricas_locales": False,
            "pr_activo": True,
            "pr_fecha_creacion": fecha_creacion,
        },
    ])

    with op.batch_alter_table("envios") as batch_op:
        batch_op.add_column(sa.Column("e_fecha_of", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("e_punto_retiro_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_envios_punto_retiro",
            "puntos_retiro",
            ["e_punto_retiro_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_envios_e_fecha_of", ["e_fecha_of"], unique=False)
        batch_op.create_index("ix_envios_e_punto_retiro_id", ["e_punto_retiro_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("envios") as batch_op:
        batch_op.drop_index("ix_envios_e_punto_retiro_id")
        batch_op.drop_index("ix_envios_e_fecha_of")
        batch_op.drop_constraint("fk_envios_punto_retiro", type_="foreignkey")
        batch_op.drop_column("e_punto_retiro_id")
        batch_op.drop_column("e_fecha_of")
    op.drop_table("puntos_retiro")
