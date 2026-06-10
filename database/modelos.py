from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

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


class Comuna(Base):
    __tablename__ = "comunas"

    id = Column(Integer, primary_key=True, index=True)
    c_nombre = Column(String, nullable=False, index=True)
    c_region = Column(String, nullable=False)


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

    # Datos del envío
    e_tipo_envio = Column(String, nullable=False)
    e_codigo_agencia = Column(String)
    e_bultos = Column(Integer, nullable=False)
    e_kilos = Column(Integer, nullable=False)

    # Flujo del envío
    e_estado = Column(String, default="pendiente", index=True)
    e_orden_flete = Column(String, index=True)

    # Nuevos campos para proceso Starken
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

    # Fechas internas
    e_fecha_creacion = Column(DateTime, default=datetime.utcnow, index=True)
