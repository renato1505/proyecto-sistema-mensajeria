from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    JSON,
    Text,
    event,
    inspect,
    Index,
    Integer,
    String,
    text,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.orm import declarative_base, relationship, validates

from utils.fechas import ahora_chile

Base = declarative_base()


AVISO_TIPO_FUNCIONARIO = "FUNCIONARIO"
AVISO_TIPO_DESTINATARIO = "DESTINATARIO"
AVISO_TIPOS_VALIDOS = frozenset({AVISO_TIPO_FUNCIONARIO, AVISO_TIPO_DESTINATARIO})

AVISO_ESTADO_PENDIENTE = "PENDIENTE"
AVISO_ESTADO_PROCESANDO = "PROCESANDO"
AVISO_ESTADO_ENVIADO = "ENVIADO"
AVISO_ESTADO_ERROR = "ERROR"
AVISO_ESTADO_INCIERTO = "INCIERTO"
AVISO_ESTADO_CANCELADO = "CANCELADO"
AVISO_ESTADOS_VALIDOS = frozenset({
    AVISO_ESTADO_PENDIENTE,
    AVISO_ESTADO_PROCESANDO,
    AVISO_ESTADO_ENVIADO,
    AVISO_ESTADO_ERROR,
    AVISO_ESTADO_INCIERTO,
    AVISO_ESTADO_CANCELADO,
})


def validar_tipo_aviso(valor):
    tipo = str(valor or "").strip().upper()
    if tipo not in AVISO_TIPOS_VALIDOS:
        raise ValueError(f"Tipo de aviso no permitido: {valor}")
    return tipo


def validar_estado_aviso(valor):
    estado = str(valor or "").strip().upper()
    if estado not in AVISO_ESTADOS_VALIDOS:
        raise ValueError(f"Estado de aviso no permitido: {valor}")
    return estado


def construir_clave_idempotencia_aviso(envio_id, tipo):
    try:
        identificador = int(envio_id)
    except (TypeError, ValueError):
        raise ValueError("El envio del aviso debe tener un ID valido") from None
    if identificador < 1:
        raise ValueError("El envio del aviso debe tener un ID valido")
    return f"ENVIO-{identificador}-{validar_tipo_aviso(tipo)}"


class Remitente(Base):
    __tablename__ = "remitentes"

    id = Column(Integer, primary_key=True, index=True)
    r_nombre = Column(String, nullable=False, index=True)
    r_correo = Column(String, index=True)
    r_division = Column(String)
    r_centro_costo = Column(String)


class Destinatario(Base):
    __tablename__ = "destinatarios"

    id = Column(Integer, primary_key=True, index=True)
    d_nombre = Column(String, nullable=False, index=True)
    d_rut = Column(String, nullable=False)
    d_direccion = Column(String)
    d_comuna = Column(String)
    d_region = Column(String)
    d_telefono = Column(String)
    d_correo = Column(String(255))
    d_observacion = Column(String(500))


class Comuna(Base):
    __tablename__ = "comunas"

    id = Column(Integer, primary_key=True, index=True)
    c_nombre = Column(String, nullable=False, index=True)
    c_region = Column(String, nullable=False)


class AreaOperativa(Base):
    __tablename__ = "areas_operativas"

    id = Column(Integer, primary_key=True, index=True)
    ar_codigo = Column(String(80), nullable=False, unique=True, index=True)
    ar_nombre = Column(String(120), nullable=False)
    ar_activa = Column(Boolean, default=True, nullable=False, index=True)
    ar_fecha_creacion = Column(DateTime, default=ahora_chile, index=True)


class UsuarioSistema(Base):
    __tablename__ = "usuarios_sistema"

    id = Column(Integer, primary_key=True, index=True)
    u_usuario = Column(String(120), nullable=False, unique=True, index=True)
    u_nombre = Column(String(160), nullable=False)
    u_rut = Column(String(20), index=True)
    u_clave_hash = Column(String(255), nullable=False)
    u_area = Column(String(80), nullable=False, index=True)
    u_rol = Column(String(40), default="usuario", nullable=False, index=True)
    u_activo = Column(Boolean, default=True, nullable=False, index=True)
    u_debe_cambiar_clave = Column(Boolean, default=False, nullable=False, index=True)
    u_ultimo_acceso = Column(DateTime)
    u_ultimo_ip = Column(String(80))
    u_fecha_creacion = Column(DateTime, default=ahora_chile, index=True)
    u_fecha_actualizacion = Column(DateTime, default=ahora_chile)


class PuntoRetiro(Base):
    __tablename__ = "puntos_retiro"

    id = Column(Integer, primary_key=True)
    pr_codigo = Column(String(40), nullable=False, unique=True)
    pr_nombre = Column(String(120), nullable=False)
    pr_es_local = Column(Boolean, nullable=False)
    pr_incluir_metricas_locales = Column(Boolean, nullable=False)
    pr_activo = Column(Boolean, nullable=False)
    pr_fecha_creacion = Column(DateTime, default=ahora_chile, nullable=False)
    retiros = relationship("RetiroStarken", back_populates="punto_retiro", passive_deletes=True)


class Envio(Base):
    __tablename__ = "envios"

    id = Column(Integer, primary_key=True, index=True)

    # Remitente
    e_remitente = Column(String, nullable=False)
    e_correo_remitente = Column(String)
    e_division = Column(String)
    e_centro_costo = Column(String)

    # Destinatario
    e_destinatario = Column(String, nullable=False)
    e_rut_destinatario = Column(String)
    e_direccion = Column(String, nullable=False)
    e_comuna = Column(String, nullable=False)
    e_region = Column(String)
    e_telefono_destinatario = Column(String)
    e_correo_destinatario = Column(String(255))
    e_observacion = Column(String(500))

    # Datos del envio
    e_tipo_envio = Column(String, nullable=False)
    e_codigo_agencia = Column(String)
    e_bultos = Column(Integer, nullable=False)
    e_kilos = Column(Integer, nullable=False)

    # Flujo del envio
    e_estado = Column(String, default="pendiente", index=True)
    e_orden_flete = Column(String, index=True)

    # Datos del lote y procesamiento Starken
    e_lote = Column(String, index=True)
    e_fila_excel = Column(Integer)
    e_resultado_of = Column(String)   # OK / ERROR
    e_detalle_of = Column(String)
    e_fecha_exportacion = Column(DateTime)
    e_fecha_of = Column(DateTime, nullable=True, index=True)
    e_punto_retiro_id = Column(
        Integer,
        ForeignKey("puntos_retiro.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    
    e_nombre_archivo = Column(String(255), nullable=True)
    e_correo_destino = Column(String(255), nullable=True)
    e_fecha_envio_correo = Column(DateTime, nullable=True)
    e_estado_correo = Column(String(50), nullable=True)

    e_aviso_funcionario_estado = Column(String(50), nullable=True, index=True)
    e_fecha_aviso_funcionario = Column(DateTime, nullable=True)

    e_anulado = Column(Boolean, default=False, server_default=false(), nullable=False, index=True)
    e_fecha_anulacion = Column(DateTime, nullable=True)
    e_motivo_anulacion = Column(String(500), nullable=True)

    # Fechas internas
    e_fecha_creacion = Column(DateTime, default=ahora_chile, index=True)
    retiro_asociaciones = relationship("RetiroEnvio", back_populates="envio", passive_deletes=True)
    avisos = relationship("AvisoEnvio", back_populates="envio", passive_deletes=True)


class AvisoEnvio(Base):
    __tablename__ = "avisos_envio"
    __table_args__ = (
        CheckConstraint(
            "av_tipo IN ('FUNCIONARIO', 'DESTINATARIO')",
            name="ck_avisos_envio_tipo_valido",
        ),
        CheckConstraint(
            "av_estado IN ('PENDIENTE', 'PROCESANDO', 'ENVIADO', 'ERROR', 'INCIERTO', 'CANCELADO')",
            name="ck_avisos_envio_estado_valido",
        ),
        CheckConstraint("av_intentos >= 0", name="ck_avisos_envio_intentos_no_negativo"),
        UniqueConstraint("envio_id", "av_tipo", name="uq_avisos_envio_envio_tipo"),
        UniqueConstraint("av_clave_idempotencia", name="uq_avisos_envio_clave_idempotencia"),
    )

    id = Column(Integer, primary_key=True)
    envio_id = Column(
        Integer,
        ForeignKey("envios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    av_tipo = Column(String(30), nullable=False, index=True)
    av_correo_snapshot = Column(String(255), nullable=True)
    av_estado = Column(
        String(30),
        default=AVISO_ESTADO_PENDIENTE,
        nullable=False,
        index=True,
    )
    av_intentos = Column(Integer, default=0, server_default=text("0"), nullable=False)
    av_fecha_creacion = Column(DateTime, default=ahora_chile, nullable=False, index=True)
    av_fecha_procesamiento = Column(DateTime, nullable=True)
    av_fecha_envio = Column(DateTime, nullable=True)
    av_ultimo_error = Column(String(1500), nullable=True)
    av_clave_idempotencia = Column(String(160), nullable=False)
    av_message_id = Column(String(255), nullable=True)

    envio = relationship("Envio", back_populates="avisos")

    @validates("av_tipo")
    def _validar_tipo(self, _clave, valor):
        return validar_tipo_aviso(valor)

    @validates("av_estado")
    def _validar_estado(self, _clave, valor):
        return validar_estado_aviso(valor)


class RetiroStarken(Base):
    __tablename__ = "retiros_starken"

    id = Column(Integer, primary_key=True)
    rs_codigo = Column(String(40), nullable=False, unique=True)
    punto_retiro_id = Column(
        Integer,
        ForeignKey("puntos_retiro.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rs_fecha_retiro = Column(DateTime, nullable=False, index=True)
    rs_fecha_confirmacion = Column(DateTime, default=ahora_chile, nullable=False)
    rs_responsable = Column(String(160), nullable=True)
    rs_observacion = Column(String(1000), nullable=True)
    rs_anulado = Column(Boolean, default=False, server_default=false(), nullable=False, index=True)
    rs_fecha_anulacion = Column(DateTime, nullable=True)
    rs_motivo_anulacion = Column(String(500), nullable=True)

    punto_retiro = relationship("PuntoRetiro", back_populates="retiros")
    asociaciones = relationship("RetiroEnvio", back_populates="retiro", passive_deletes=True)


class RetiroEnvio(Base):
    __tablename__ = "retiro_envios"
    __table_args__ = (
        CheckConstraint("re_bultos_snapshot >= 1", name="ck_retiro_envios_bultos_snapshot_positivo"),
    )

    id = Column(Integer, primary_key=True)
    retiro_id = Column(
        Integer,
        ForeignKey("retiros_starken.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    envio_id = Column(
        Integer,
        ForeignKey("envios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    re_bultos_snapshot = Column(Integer, nullable=False)
    re_fecha_asociacion = Column(DateTime, default=ahora_chile, nullable=False)
    re_vigente = Column(Boolean, default=True, server_default=true(), nullable=False)

    retiro = relationship("RetiroStarken", back_populates="asociaciones")
    envio = relationship("Envio", back_populates="retiro_asociaciones")


Index(
    "uq_retiro_envios_envio_vigente",
    RetiroEnvio.envio_id,
    unique=True,
    postgresql_where=RetiroEnvio.re_vigente.is_(True),
    sqlite_where=RetiroEnvio.re_vigente.is_(True),
)


class ExcepcionEnvio(Base):
    __tablename__ = "excepciones_envio"

    id = Column(Integer, primary_key=True, index=True)
    envio_id = Column(Integer, nullable=False, index=True)
    x_estado = Column(String(50), default="abierto", nullable=False, index=True)
    x_tipo = Column(String(80), nullable=False, index=True)
    x_prioridad = Column(String(30), default="normal", nullable=False)
    x_contacto_starken = Column(String(120))
    x_detalle = Column(String(1000))
    x_indicacion = Column(String(1000))
    x_respuesta = Column(String(1000))
    x_resultado_final = Column(String(80))
    x_resumen_cierre = Column(String(1500))
    x_of_retorno = Column(String(80))
    x_fecha_anulacion = Column(DateTime)
    x_motivo_anulacion = Column(String(500))
    x_fecha_creacion = Column(DateTime, default=ahora_chile, index=True)
    x_fecha_actualizacion = Column(DateTime, default=ahora_chile)
    x_fecha_cierre = Column(DateTime)


class MovimientoExcepcion(Base):
    __tablename__ = "movimientos_excepcion"

    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, nullable=False, index=True)
    m_tipo = Column(String(80), nullable=False)
    m_detalle = Column(String(1500), nullable=False)
    m_fecha = Column(DateTime, default=ahora_chile, index=True)


class EvidenciaExcepcion(Base):
    __tablename__ = "evidencias_excepcion"

    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, nullable=False, index=True)
    ev_nombre_original = Column(String(255), nullable=False)
    ev_nombre_archivo = Column(String(255), nullable=False)
    ev_descripcion = Column(String(500))
    ev_fecha = Column(DateTime, default=ahora_chile, index=True)


class RegistroAuditoria(Base):
    __tablename__ = "auditoria"

    id = Column(Integer, primary_key=True, index=True)
    a_fecha = Column(DateTime, default=ahora_chile, index=True)
    a_usuario = Column(String(120), nullable=False, index=True)
    a_accion = Column(String(120), nullable=False, index=True)
    a_entidad = Column(String(80), nullable=False, index=True)
    a_entidad_id = Column(String(80))
    a_detalle = Column(String(1500))


class SolicitudRecuperacionClave(Base):
    __tablename__ = "solicitudes_recuperacion_clave"

    id = Column(Integer, primary_key=True, index=True)
    sr_usuario = Column(String(120), nullable=False, index=True)
    sr_correo = Column(String(255), nullable=False)
    sr_correo_enmascarado = Column(String(255))
    sr_rut = Column(String(20))
    sr_ip = Column(String(80))
    sr_estado = Column(String(40), default="pendiente", nullable=False, index=True)
    sr_nota = Column(String(1000))
    sr_clave_temporal_generada = Column(Boolean, default=False, nullable=False)
    sr_fecha_creacion = Column(DateTime, default=ahora_chile, index=True)
    sr_fecha_revision = Column(DateTime)
    sr_revisado_por = Column(String(120))


# Persistencia OF aditiva. Ningun flujo operativo crea o resuelve estas filas aun.
INTENTO_OF_ESTADOS = frozenset({
    "ABIERTO", "EN_VERIFICACION", "CON_OF", "SIN_OF_VERIFICADA", "CANCELADO",
})
CONCILIACION_H2H_ESTADOS = frozenset({"PENDIENTE", "OF_EXISTENTE", "OF_INEXISTENTE"})
METODO_VERIFICACION_STARKEN = "PLATAFORMA_STARKEN"


def _texto_of_requerido(valor):
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError("La OF debe ser texto no vacio")
    return valor.strip()


def _transportista_of(valor):
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError("El transportista debe ser texto no vacio")
    return valor.strip().upper()


class IntentoOF(Base):
    __tablename__ = "intentos_of"
    __table_args__ = (
        UniqueConstraint("envio_id", "io_secuencia", name="uq_intentos_of_envio_secuencia"),
        UniqueConstraint("id", "envio_id", name="uq_intentos_of_id_envio"),
        UniqueConstraint("id", "envio_id", "io_transportista", name="uq_intentos_of_id_envio_transporte"),
        UniqueConstraint("id", "envio_id", "io_anterior_id", name="uq_intentos_of_id_envio_anterior"),
        UniqueConstraint("io_anterior_id", name="uq_intentos_of_sucesor"),
        ForeignKeyConstraint(
            ["io_anterior_id", "envio_id"], ["intentos_of.id", "intentos_of.envio_id"],
            name="fk_intentos_of_anterior_mismo_envio", ondelete="RESTRICT",
        ),
        CheckConstraint("io_secuencia >= 1", name="ck_intentos_of_secuencia_positiva"),
        CheckConstraint("io_fila IS NULL OR io_fila >= 1", name="ck_intentos_of_fila_positiva"),
        CheckConstraint("io_anterior_id IS NULL OR io_anterior_id <> id", name="ck_intentos_of_no_autorreferencia"),
        CheckConstraint(
            "length(trim(io_transportista)) > 0 AND io_transportista = upper(trim(io_transportista))",
            name="ck_intentos_of_transportista_normalizado",
        ),
        CheckConstraint(
            "io_estado IN ('ABIERTO', 'EN_VERIFICACION', 'CON_OF', 'SIN_OF_VERIFICADA', 'CANCELADO')",
            name="ck_intentos_of_estado",
        ),
    )

    id = Column(Integer, primary_key=True)
    envio_id = Column(Integer, ForeignKey("envios.id", ondelete="RESTRICT"), nullable=False, index=True)
    io_secuencia = Column(Integer, nullable=False)
    io_transportista = Column(String(80), nullable=False)
    io_lote = Column(String(255), nullable=True, index=True)
    io_fila = Column(Integer, nullable=True)
    io_archivo = Column(String(255), nullable=True)
    # Creacion de esta fila, nunca una fecha historica de exportacion inferida.
    io_fecha_creacion = Column(DateTime, default=ahora_chile, nullable=False)
    io_estado = Column(String(30), default="ABIERTO", nullable=False, index=True)
    io_anterior_id = Column(Integer, nullable=True)

    envio = relationship("Envio", foreign_keys=[envio_id])
    anterior = relationship(
        "IntentoOF", remote_side=[id, envio_id],
        foreign_keys=[io_anterior_id, envio_id], viewonly=True,
    )

    @validates("io_transportista")
    def _validar_transportista(self, _clave, valor):
        return _transportista_of(valor)

    @validates("io_estado")
    def _validar_estado(self, _clave, valor):
        estado = str(valor or "").strip().upper()
        if estado not in INTENTO_OF_ESTADOS:
            raise ValueError("Estado de intento OF no permitido")
        return estado


Index(
    "uq_intentos_of_envio_abierto", IntentoOF.envio_id, unique=True,
    postgresql_where=IntentoOF.io_estado.in_(["ABIERTO", "EN_VERIFICACION"]),
    sqlite_where=IntentoOF.io_estado.in_(["ABIERTO", "EN_VERIFICACION"]),
)


class RegistroOF(Base):
    __tablename__ = "registros_of"
    __table_args__ = (
        ForeignKeyConstraint(
            ["intento_id", "envio_id", "ro_transportista"],
            ["intentos_of.id", "intentos_of.envio_id", "intentos_of.io_transportista"],
            name="fk_registros_of_intento_envio_transporte", ondelete="RESTRICT",
        ),
        UniqueConstraint("intento_id", name="uq_registros_of_intento"),
        UniqueConstraint("ro_transportista", "ro_numero", name="uq_registros_of_transporte_numero"),
        UniqueConstraint("id", "intento_id", "envio_id", name="uq_registros_of_id_intento_envio"),
        CheckConstraint(
            "length(trim(ro_numero)) > 0 AND ro_numero = trim(ro_numero)",
            name="ck_registros_of_numero_normalizado",
        ),
        CheckConstraint("length(trim(ro_origen)) > 0", name="ck_registros_of_origen"),
    )

    id = Column(Integer, primary_key=True)
    intento_id = Column(Integer, nullable=False)
    envio_id = Column(Integer, ForeignKey("envios.id", ondelete="RESTRICT"), nullable=False, index=True)
    ro_transportista = Column(String(80), nullable=False)
    ro_numero = Column(Text, nullable=False)
    ro_fecha_registro = Column(DateTime, default=ahora_chile, nullable=False)
    ro_origen = Column(String(80), nullable=False)

    envio = relationship("Envio", foreign_keys=[envio_id])
    intento = relationship("IntentoOF", foreign_keys=[intento_id, envio_id, ro_transportista], viewonly=True)

    @validates("ro_numero")
    def _validar_numero(self, _clave, valor):
        return _texto_of_requerido(valor)

    @validates("ro_transportista")
    def _validar_transportista(self, _clave, valor):
        return _transportista_of(valor)


class ConciliacionH2H(Base):
    __tablename__ = "conciliaciones_h2h"
    __table_args__ = (
        ForeignKeyConstraint(
            ["intento_id", "envio_id"], ["intentos_of.id", "intentos_of.envio_id"],
            name="fk_conciliaciones_h2h_intento_envio", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ch_intento_sucesor_id", "envio_id", "intento_id"],
            ["intentos_of.id", "intentos_of.envio_id", "intentos_of.io_anterior_id"],
            name="fk_conciliaciones_h2h_sucesor", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ch_registro_of_id", "intento_id", "envio_id"],
            ["registros_of.id", "registros_of.intento_id", "registros_of.envio_id"],
            name="fk_conciliaciones_h2h_registro_of", ondelete="RESTRICT",
        ),
        UniqueConstraint("intento_id", name="uq_conciliaciones_h2h_intento"),
        UniqueConstraint("ch_intento_sucesor_id", name="uq_conciliaciones_h2h_consumo"),
        CheckConstraint(
            "ch_estado IN ('PENDIENTE', 'OF_EXISTENTE', 'OF_INEXISTENTE')",
            name="ck_conciliaciones_h2h_estado",
        ),
        CheckConstraint(
            "ch_estado = 'PENDIENTE' OR (ch_fecha_verificacion IS NOT NULL "
            "AND ch_operador IS NOT NULL AND length(trim(ch_operador)) > 0 "
            "AND ch_metodo IS NOT NULL AND length(trim(ch_metodo)) > 0 "
            "AND ch_observacion IS NOT NULL AND length(trim(ch_observacion)) > 0)",
            name="ck_conciliaciones_h2h_verificacion",
        ),
        CheckConstraint(
            "(ch_estado = 'OF_EXISTENTE' AND ch_registro_of_id IS NOT NULL) OR "
            "(ch_estado <> 'OF_EXISTENTE' AND ch_registro_of_id IS NULL)",
            name="ck_conciliaciones_h2h_of_confirmada",
        ),
        CheckConstraint(
            "ch_intento_sucesor_id IS NULL OR "
            "(ch_estado = 'OF_INEXISTENTE' AND ch_intento_sucesor_id <> intento_id)",
            name="ck_conciliaciones_h2h_reintento",
        ),
        CheckConstraint(
            "length(trim(ch_resultado_original)) > 0 AND length(trim(ch_detalle_original)) > 0",
            name="ck_conciliaciones_h2h_evidencia",
        ),
    )

    id = Column(Integer, primary_key=True)
    intento_id = Column(Integer, nullable=False)
    envio_id = Column(Integer, ForeignKey("envios.id", ondelete="RESTRICT"), nullable=False, index=True)
    ch_resultado_original = Column(Text, nullable=False)
    ch_detalle_original = Column(Text, nullable=False)
    ch_estado = Column(String(30), default="PENDIENTE", nullable=False, index=True)
    ch_fecha_creacion = Column(DateTime, default=ahora_chile, nullable=False)
    ch_fecha_deteccion = Column(DateTime, nullable=True)
    ch_fecha_verificacion = Column(DateTime, nullable=True)
    ch_operador = Column(String(120), nullable=True)
    ch_metodo = Column(String(80), nullable=True)
    ch_observacion = Column(Text, nullable=True)
    ch_referencia = Column(Text, nullable=True)
    ch_registro_of_id = Column(Integer, nullable=True)
    # NULL: sin sucesor consumidor registrado. Una asignacion no nula es irreversible por ORM.
    ch_intento_sucesor_id = Column(Integer, nullable=True)

    envio = relationship("Envio", foreign_keys=[envio_id])
    intento = relationship(
        "IntentoOF", foreign_keys=[intento_id, envio_id], viewonly=True,
        primaryjoin="and_(ConciliacionH2H.intento_id == IntentoOF.id, "
                    "ConciliacionH2H.envio_id == IntentoOF.envio_id)",
    )
    intento_sucesor = relationship(
        "IntentoOF", foreign_keys=[ch_intento_sucesor_id, envio_id, intento_id], viewonly=True,
        primaryjoin="and_(ConciliacionH2H.ch_intento_sucesor_id == IntentoOF.id, "
                    "ConciliacionH2H.envio_id == IntentoOF.envio_id, "
                    "ConciliacionH2H.intento_id == IntentoOF.io_anterior_id)",
    )
    registro_of = relationship(
        "RegistroOF", foreign_keys=[ch_registro_of_id, intento_id, envio_id], viewonly=True,
    )

    @validates("ch_estado")
    def _validar_estado(self, _clave, valor):
        estado = str(valor or "").strip().upper()
        if estado not in CONCILIACION_H2H_ESTADOS:
            raise ValueError("Estado de conciliacion H2H no permitido")
        return estado


class MovimientoEnvio(Base):
    __tablename__ = "movimientos_envio"
    __table_args__ = (
        ForeignKeyConstraint(
            ["intento_id", "envio_id"], ["intentos_of.id", "intentos_of.envio_id"],
            name="fk_movimientos_envio_intento", ondelete="RESTRICT",
        ),
        UniqueConstraint("me_clave_idempotencia", name="uq_movimientos_envio_idempotencia"),
        CheckConstraint("length(trim(me_tipo)) > 0", name="ck_movimientos_envio_tipo"),
        CheckConstraint("length(trim(me_actor)) > 0", name="ck_movimientos_envio_actor"),
        CheckConstraint(
            "me_clave_idempotencia IS NULL OR length(trim(me_clave_idempotencia)) > 0",
            name="ck_movimientos_envio_idempotencia",
        ),
    )

    id = Column(Integer, primary_key=True)
    envio_id = Column(Integer, ForeignKey("envios.id", ondelete="RESTRICT"), nullable=False, index=True)
    intento_id = Column(Integer, nullable=True, index=True)
    me_tipo = Column(String(80), nullable=False)
    me_fecha = Column(DateTime, default=ahora_chile, nullable=False, index=True)
    me_actor = Column(String(120), nullable=False)
    me_detalle = Column(JSON(none_as_null=True), default=dict, nullable=False)
    me_clave_idempotencia = Column(String(160), nullable=True)

    envio = relationship("Envio", foreign_keys=[envio_id])
    intento = relationship("IntentoOF", foreign_keys=[intento_id, envio_id], viewonly=True)


def _contexto_of_persistido(mapper, connection, objeto):
    """Leer la fila original evita depender del historial de atributos expirados.

    El lock solo tiene efecto en motores que admiten FOR UPDATE. No protege
    escrituras bulk/SQL directo: estas guardas pertenecen al flush ordinario ORM.
    """
    estado = inspect(objeto)
    tabla = mapper.local_table
    original = connection.execute(
        tabla.select().where(tabla.c.id == estado.identity[0]).with_for_update()
    ).mappings().one()
    propuesto = {
        columna.key: estado.dict.get(columna.key, original[columna.key])
        for columna in tabla.columns
    }
    return original, propuesto


def _rechazar_cambios_of(original, propuesto, campos, mensaje):
    if any(propuesto[campo] != original[campo] for campo in campos):
        raise ValueError(mensaje)


@event.listens_for(IntentoOF, "before_update")
def _conservar_intento_of(mapper, connection, intento):
    original, propuesto = _contexto_of_persistido(mapper, connection, intento)
    # No hay transiciones de estado autorizadas en esta fase de persistencia.
    _rechazar_cambios_of(
        original, propuesto, original.keys(),
        "El contexto y estado de un intento OF persistido son inmutables",
    )


@event.listens_for(RegistroOF, "before_update")
def _conservar_registro_of(mapper, connection, registro):
    original, propuesto = _contexto_of_persistido(mapper, connection, registro)
    _rechazar_cambios_of(
        original, propuesto, original.keys(),
        "El registro OF y su reserva son inmutables",
    )


@event.listens_for(IntentoOF, "before_delete")
@event.listens_for(RegistroOF, "before_delete")
@event.listens_for(ConciliacionH2H, "before_delete")
def _impedir_borrado_evidencia_of(_mapper, _connection, _objeto):
    raise ValueError("No se puede eliminar evidencia operativa OF mediante el ORM")


@event.listens_for(ConciliacionH2H, "before_update")
def _conservar_evidencia_h2h(mapper, connection, conciliacion):
    original, propuesto = _contexto_of_persistido(mapper, connection, conciliacion)
    campos = (
        "id", "intento_id", "envio_id", "ch_resultado_original", "ch_detalle_original",
        "ch_fecha_creacion", "ch_fecha_deteccion",
    )
    _rechazar_cambios_of(
        original, propuesto, campos, "La evidencia original H2H no se puede sobrescribir",
    )
    sucesor_original = original["ch_intento_sucesor_id"]
    sucesor_propuesto = propuesto["ch_intento_sucesor_id"]
    if sucesor_original is not None and sucesor_propuesto != sucesor_original:
        raise ValueError("El sucesor que consumio la autorizacion no se puede borrar ni sustituir")

    if original["ch_estado"] != "PENDIENTE":
        _rechazar_cambios_of(
            original, propuesto,
            [campo for campo in original if campo != "ch_intento_sucesor_id"],
            "Una resolucion H2H definitiva es inmutable",
        )
    if sucesor_propuesto is not None and propuesto["ch_estado"] != "OF_INEXISTENTE":
        raise ValueError("Solo OF_INEXISTENTE admite un sucesor consumiendo la autorizacion")
    # La FK compuesta y los CHECK validan el sucesor directo del mismo envio.
    # PENDIENTE puede completar metadatos y pasar una vez a un estado definitivo;
    # no se implementa aqui la accion de negocio que autoriza esa resolucion.


@event.listens_for(MovimientoEnvio, "before_update")
@event.listens_for(MovimientoEnvio, "before_delete")
def _conservar_movimiento_envio(_mapper, _connection, _movimiento):
    raise ValueError("Los movimientos de envio son registros inmutables")
