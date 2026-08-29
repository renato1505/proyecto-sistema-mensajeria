"""Agrega el indice operativo ausente en el esquema legacy restaurado.

Revision ID: 20260828_02
Revises: 20260826_01
Create Date: 2026-08-28

El baseline 20260826_01 representa deliberadamente el esquema PostgreSQL
existente. Esta revision expresa por separado la mejora deseada por el ORM.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260828_02"
down_revision: Union[str, None] = "20260826_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_envios_e_anulado", "envios", ["e_anulado"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_envios_e_anulado", table_name="envios")
