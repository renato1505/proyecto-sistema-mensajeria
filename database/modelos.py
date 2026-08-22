from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

from utils.fechas import ahora_chile

Base = declarative_base()


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
    d_correo = Column(String)
    d_observacion = Column(String)


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
    e_correo_destinatario = Column(String)
    e_observacion = Column(String)

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
    
    e_nombre_archivo = Column(String(255), nullable=True)
    e_correo_destino = Column(String(255), nullable=True)
    e_fecha_envio_correo = Column(DateTime, nullable=True)
    e_estado_correo = Column(String(50), nullable=True)

    e_aviso_funcionario_estado = Column(String(50), nullable=True, index=True)
    e_fecha_aviso_funcionario = Column(DateTime, nullable=True)

    e_anulado = Column(Boolean, default=False, nullable=False, index=True)
    e_fecha_anulacion = Column(DateTime, nullable=True)
    e_motivo_anulacion = Column(String(500), nullable=True)

    # Fechas internas
    e_fecha_creacion = Column(DateTime, default=ahora_chile, index=True)


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
