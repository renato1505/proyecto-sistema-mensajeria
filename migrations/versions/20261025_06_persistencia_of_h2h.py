"""Persistencia aditiva de intentos OF, conciliaciones y movimientos.

Revision ID: 20261025_06
Revises: 20260829_05
Sin backfill ni modificaciones a envios existentes.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261025_06"
down_revision = "20260829_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'intentos_of',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('envio_id', sa.Integer(), nullable=False),
        sa.Column('io_secuencia', sa.Integer(), nullable=False),
        sa.Column('io_transportista', sa.String(length=80), nullable=False),
        sa.Column('io_lote', sa.String(length=255), nullable=True),
        sa.Column('io_fila', sa.Integer(), nullable=True),
        sa.Column('io_archivo', sa.String(length=255), nullable=True),
        sa.Column('io_fecha_creacion', sa.DateTime(), nullable=False),
        sa.Column('io_estado', sa.String(length=30), nullable=False),
        sa.Column('io_anterior_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['envio_id'], ['envios.id'], ondelete='RESTRICT'),
        sa.CheckConstraint("io_estado IN ('ABIERTO', 'EN_VERIFICACION', 'CON_OF', 'SIN_OF_VERIFICADA', 'CANCELADO')", name='ck_intentos_of_estado'),
        sa.CheckConstraint('io_fila IS NULL OR io_fila >= 1', name='ck_intentos_of_fila_positiva'),
        sa.CheckConstraint('io_anterior_id IS NULL OR io_anterior_id <> id', name='ck_intentos_of_no_autorreferencia'),
        sa.CheckConstraint('io_secuencia >= 1', name='ck_intentos_of_secuencia_positiva'),
        sa.CheckConstraint('length(trim(io_transportista)) > 0 AND io_transportista = upper(trim(io_transportista))', name='ck_intentos_of_transportista_normalizado'),
        sa.ForeignKeyConstraint(['io_anterior_id', 'envio_id'], ['intentos_of.id', 'intentos_of.envio_id'], name='fk_intentos_of_anterior_mismo_envio', ondelete='RESTRICT'),
        sa.UniqueConstraint('envio_id', 'io_secuencia', name='uq_intentos_of_envio_secuencia'),
        sa.UniqueConstraint('id', 'envio_id', name='uq_intentos_of_id_envio'),
        sa.UniqueConstraint('id', 'envio_id', 'io_anterior_id', name='uq_intentos_of_id_envio_anterior'),
        sa.UniqueConstraint('id', 'envio_id', 'io_transportista', name='uq_intentos_of_id_envio_transporte'),
        sa.UniqueConstraint('io_anterior_id', name='uq_intentos_of_sucesor'),
    )
    op.create_index('ix_intentos_of_envio_id', 'intentos_of', ['envio_id'], unique=False)
    op.create_index('ix_intentos_of_io_estado', 'intentos_of', ['io_estado'], unique=False)
    op.create_index('ix_intentos_of_io_lote', 'intentos_of', ['io_lote'], unique=False)
    op.create_index('uq_intentos_of_envio_abierto', 'intentos_of', ['envio_id'], unique=True, sqlite_where=sa.text("intentos_of.io_estado IN ('ABIERTO', 'EN_VERIFICACION')"), postgresql_where=sa.text("intentos_of.io_estado IN ('ABIERTO', 'EN_VERIFICACION')"))
    op.create_table(
        'registros_of',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('intento_id', sa.Integer(), nullable=False),
        sa.Column('envio_id', sa.Integer(), nullable=False),
        sa.Column('ro_transportista', sa.String(length=80), nullable=False),
        sa.Column('ro_numero', sa.Text(), nullable=False),
        sa.Column('ro_fecha_registro', sa.DateTime(), nullable=False),
        sa.Column('ro_origen', sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(['envio_id'], ['envios.id'], ondelete='RESTRICT'),
        sa.CheckConstraint('length(trim(ro_numero)) > 0 AND ro_numero = trim(ro_numero)', name='ck_registros_of_numero_normalizado'),
        sa.CheckConstraint('length(trim(ro_origen)) > 0', name='ck_registros_of_origen'),
        sa.ForeignKeyConstraint(['intento_id', 'envio_id', 'ro_transportista'], ['intentos_of.id', 'intentos_of.envio_id', 'intentos_of.io_transportista'], name='fk_registros_of_intento_envio_transporte', ondelete='RESTRICT'),
        sa.UniqueConstraint('id', 'intento_id', 'envio_id', name='uq_registros_of_id_intento_envio'),
        sa.UniqueConstraint('intento_id', name='uq_registros_of_intento'),
        sa.UniqueConstraint('ro_transportista', 'ro_numero', name='uq_registros_of_transporte_numero'),
    )
    op.create_index('ix_registros_of_envio_id', 'registros_of', ['envio_id'], unique=False)
    op.create_table(
        'conciliaciones_h2h',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('intento_id', sa.Integer(), nullable=False),
        sa.Column('envio_id', sa.Integer(), nullable=False),
        sa.Column('ch_resultado_original', sa.Text(), nullable=False),
        sa.Column('ch_detalle_original', sa.Text(), nullable=False),
        sa.Column('ch_estado', sa.String(length=30), nullable=False),
        sa.Column('ch_fecha_creacion', sa.DateTime(), nullable=False),
        sa.Column('ch_fecha_deteccion', sa.DateTime(), nullable=True),
        sa.Column('ch_fecha_verificacion', sa.DateTime(), nullable=True),
        sa.Column('ch_operador', sa.String(length=120), nullable=True),
        sa.Column('ch_metodo', sa.String(length=80), nullable=True),
        sa.Column('ch_observacion', sa.Text(), nullable=True),
        sa.Column('ch_referencia', sa.Text(), nullable=True),
        sa.Column('ch_registro_of_id', sa.Integer(), nullable=True),
        sa.Column('ch_intento_sucesor_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['envio_id'], ['envios.id'], ondelete='RESTRICT'),
        sa.CheckConstraint("ch_estado IN ('PENDIENTE', 'OF_EXISTENTE', 'OF_INEXISTENTE')", name='ck_conciliaciones_h2h_estado'),
        sa.CheckConstraint('length(trim(ch_resultado_original)) > 0 AND length(trim(ch_detalle_original)) > 0', name='ck_conciliaciones_h2h_evidencia'),
        sa.CheckConstraint("(ch_estado = 'OF_EXISTENTE' AND ch_registro_of_id IS NOT NULL) OR (ch_estado <> 'OF_EXISTENTE' AND ch_registro_of_id IS NULL)", name='ck_conciliaciones_h2h_of_confirmada'),
        sa.CheckConstraint("ch_intento_sucesor_id IS NULL OR (ch_estado = 'OF_INEXISTENTE' AND ch_intento_sucesor_id <> intento_id)", name='ck_conciliaciones_h2h_reintento'),
        sa.CheckConstraint("ch_estado = 'PENDIENTE' OR (ch_fecha_verificacion IS NOT NULL AND ch_operador IS NOT NULL AND length(trim(ch_operador)) > 0 AND ch_metodo IS NOT NULL AND length(trim(ch_metodo)) > 0 AND ch_observacion IS NOT NULL AND length(trim(ch_observacion)) > 0)", name='ck_conciliaciones_h2h_verificacion'),
        sa.ForeignKeyConstraint(['intento_id', 'envio_id'], ['intentos_of.id', 'intentos_of.envio_id'], name='fk_conciliaciones_h2h_intento_envio', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['ch_registro_of_id', 'intento_id', 'envio_id'], ['registros_of.id', 'registros_of.intento_id', 'registros_of.envio_id'], name='fk_conciliaciones_h2h_registro_of', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['ch_intento_sucesor_id', 'envio_id', 'intento_id'], ['intentos_of.id', 'intentos_of.envio_id', 'intentos_of.io_anterior_id'], name='fk_conciliaciones_h2h_sucesor', ondelete='RESTRICT'),
        sa.UniqueConstraint('ch_intento_sucesor_id', name='uq_conciliaciones_h2h_consumo'),
        sa.UniqueConstraint('intento_id', name='uq_conciliaciones_h2h_intento'),
    )
    op.create_index('ix_conciliaciones_h2h_ch_estado', 'conciliaciones_h2h', ['ch_estado'], unique=False)
    op.create_index('ix_conciliaciones_h2h_envio_id', 'conciliaciones_h2h', ['envio_id'], unique=False)
    op.create_table(
        'movimientos_envio',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('envio_id', sa.Integer(), nullable=False),
        sa.Column('intento_id', sa.Integer(), nullable=True),
        sa.Column('me_tipo', sa.String(length=80), nullable=False),
        sa.Column('me_fecha', sa.DateTime(), nullable=False),
        sa.Column('me_actor', sa.String(length=120), nullable=False),
        sa.Column('me_detalle', sa.JSON(none_as_null=True), nullable=False),
        sa.Column('me_clave_idempotencia', sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(['envio_id'], ['envios.id'], ondelete='RESTRICT'),
        sa.CheckConstraint('length(trim(me_actor)) > 0', name='ck_movimientos_envio_actor'),
        sa.CheckConstraint('me_clave_idempotencia IS NULL OR length(trim(me_clave_idempotencia)) > 0', name='ck_movimientos_envio_idempotencia'),
        sa.CheckConstraint('length(trim(me_tipo)) > 0', name='ck_movimientos_envio_tipo'),
        sa.ForeignKeyConstraint(['intento_id', 'envio_id'], ['intentos_of.id', 'intentos_of.envio_id'], name='fk_movimientos_envio_intento', ondelete='RESTRICT'),
        sa.UniqueConstraint('me_clave_idempotencia', name='uq_movimientos_envio_idempotencia'),
    )
    op.create_index('ix_movimientos_envio_envio_id', 'movimientos_envio', ['envio_id'], unique=False)
    op.create_index('ix_movimientos_envio_intento_id', 'movimientos_envio', ['intento_id'], unique=False)
    op.create_index('ix_movimientos_envio_me_fecha', 'movimientos_envio', ['me_fecha'], unique=False)


def downgrade() -> None:
    # Destructivo solo sobre las tablas nuevas; requiere revision si contienen datos.
    op.drop_table('movimientos_envio')
    op.drop_table('conciliaciones_h2h')
    op.drop_table('registros_of')
    op.drop_table('intentos_of')
