import logging
import re
from dataclasses import dataclass
from datetime import timedelta

from database.modelos import (
    AVISO_ESTADO_CANCELADO,
    AVISO_ESTADO_ENVIADO,
    AVISO_ESTADO_ERROR,
    AVISO_ESTADO_INCIERTO,
    AVISO_ESTADO_PENDIENTE,
    AVISO_ESTADO_PROCESANDO,
    AVISO_TIPOS_VALIDOS,
    AvisoEnvio,
    Envio,
)
from services.avisos_v2 import envio_es_elegible_avisos
from services.proveedor_avisos import (
    ResultadoEnvioCorreo,
    SolicitudCorreoAviso,
    enviar_correo_aviso,
)
from utils.fechas import ahora_chile
from utils.validaciones import email_valido


logger = logging.getLogger(__name__)
UMBRAL_PROCESANDO_ANTIGUO = timedelta(minutes=15)


class AvisoMotorError(Exception):
    pass


class AvisoNoProcesable(AvisoMotorError):
    def __init__(self, aviso_id, estado, razon):
        super().__init__(razon)
        self.aviso_id = aviso_id
        self.estado = estado
        self.razon = razon


@dataclass(frozen=True)
class ResultadoProcesamientoAviso:
    aviso_id: int
    envio_id: int
    estado: str
    intento: int
    omitido: bool = False
    razon: str | None = None


@dataclass(frozen=True)
class ResumenProcesamientoAvisos:
    total: int
    enviados: int
    errores: int
    inciertos: int
    omitidos: int
    cancelados: int
    resultados: tuple


def _sanitizar_error(error):
    texto = " ".join(str(error or "Error no especificado").split())
    texto = re.sub(r"(?i)(authorization|api[-_ ]?key|token|password|secret)\s*[:=]\s*\S+", r"\1=[REDACTADO]", texto)
    texto = re.sub(r"(?i)(https?://)[^/@\s]+:[^/@\s]+@", r"\1[REDACTADO]@", texto)
    return texto[:1500]


def _solicitud(aviso, envio):
    return SolicitudCorreoAviso(
        aviso_id=aviso.id,
        envio_id=envio.id,
        tipo=aviso.av_tipo,
        destinatario=aviso.av_correo_snapshot,
        remitente_nombre=envio.e_remitente or "Funcionario",
        destinatario_nombre=envio.e_destinatario or "Destinatario",
        orden_flete=str(envio.e_orden_flete or "Sin OF").strip(),
        direccion=envio.e_direccion or "",
        comuna=envio.e_comuna or "",
        region=envio.e_region or "",
        telefono=envio.e_telefono_destinatario or "",
        observacion=envio.e_observacion or "",
    )


def _rechazar(aviso, razon):
    raise AvisoNoProcesable(aviso.id, aviso.av_estado, razon)


def _reclamar_aviso(db_factory, aviso_id, permitir_reintento_error):
    db = db_factory()
    try:
        fila = (
            db.query(AvisoEnvio, Envio)
            .join(Envio, Envio.id == AvisoEnvio.envio_id)
            .filter(AvisoEnvio.id == aviso_id)
            .one_or_none()
        )
        if fila is None:
            raise AvisoNoProcesable(aviso_id, None, "El aviso no existe")
        aviso, envio = fila
        if aviso.av_tipo not in AVISO_TIPOS_VALIDOS:
            _rechazar(aviso, "El tipo de aviso no es valido")
        if aviso.av_estado == AVISO_ESTADO_ERROR and not permitir_reintento_error:
            _rechazar(aviso, "El reintento de un aviso ERROR requiere autorizacion explicita")
        if aviso.av_estado not in {AVISO_ESTADO_PENDIENTE, AVISO_ESTADO_ERROR}:
            _rechazar(aviso, f"El aviso en estado {aviso.av_estado} no es procesable")

        if (
            not envio_es_elegible_avisos(db, envio.id)
            or not aviso.av_correo_snapshot
            or not email_valido(aviso.av_correo_snapshot)
        ):
            aviso.av_estado = AVISO_ESTADO_CANCELADO
            db.commit()
            raise AvisoNoProcesable(
                aviso.id,
                AVISO_ESTADO_CANCELADO,
                "El aviso perdio elegibilidad y fue cancelado",
            )

        estados_reclamables = [AVISO_ESTADO_PENDIENTE]
        if permitir_reintento_error:
            estados_reclamables.append(AVISO_ESTADO_ERROR)
        fecha = ahora_chile()
        actualizados = (
            db.query(AvisoEnvio)
            .filter(
                AvisoEnvio.id == aviso.id,
                AvisoEnvio.av_estado.in_(estados_reclamables),
            )
            .update(
                {
                    AvisoEnvio.av_estado: AVISO_ESTADO_PROCESANDO,
                    AvisoEnvio.av_intentos: AvisoEnvio.av_intentos + 1,
                    AvisoEnvio.av_fecha_procesamiento: fecha,
                    AvisoEnvio.av_ultimo_error: None,
                },
                synchronize_session=False,
            )
        )
        if actualizados != 1:
            db.rollback()
            raise AvisoNoProcesable(aviso.id, None, "El aviso ya fue reclamado por otro proceso")
        solicitud = _solicitud(aviso, envio)
        intento = aviso.av_intentos + 1
        db.commit()
        logger.info(
            "aviso_v2_reclamado",
            extra={"aviso_id": aviso.id, "envio_id": envio.id, "tipo": aviso.av_tipo, "intento": intento},
        )
        return solicitud, intento
    except AvisoNoProcesable:
        if db.in_transaction():
            db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _persistir_resultado(db_factory, solicitud, intento, resultado):
    db = db_factory()
    try:
        aviso = db.query(AvisoEnvio).filter(AvisoEnvio.id == solicitud.aviso_id).one()
        if aviso.av_estado != AVISO_ESTADO_PROCESANDO:
            raise AvisoNoProcesable(aviso.id, aviso.av_estado, "El aviso ya no esta PROCESANDO")
        if resultado.aceptado:
            aviso.av_estado = AVISO_ESTADO_ENVIADO
            aviso.av_fecha_envio = ahora_chile()
            aviso.av_message_id = str(resultado.message_id)[:255] if resultado.message_id else None
            aviso.av_ultimo_error = None
        elif resultado.resultado_incierto:
            aviso.av_estado = AVISO_ESTADO_INCIERTO
            aviso.av_fecha_envio = None
            aviso.av_ultimo_error = _sanitizar_error(resultado.error)
        else:
            aviso.av_estado = AVISO_ESTADO_ERROR
            aviso.av_fecha_envio = None
            aviso.av_ultimo_error = _sanitizar_error(resultado.error)
        estado = aviso.av_estado
        db.commit()
        logger.info(
            "aviso_v2_resultado",
            extra={
                "aviso_id": aviso.id,
                "envio_id": aviso.envio_id,
                "tipo": aviso.av_tipo,
                "intento": intento,
                "estado_resultante": estado,
            },
        )
        return ResultadoProcesamientoAviso(aviso.id, aviso.envio_id, estado, intento)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def procesar_aviso(db_factory, aviso_id, permitir_reintento_error=False, proveedor=enviar_correo_aviso):
    solicitud, intento = _reclamar_aviso(db_factory, aviso_id, permitir_reintento_error)
    try:
        resultado = proveedor(solicitud)
        if not isinstance(resultado, ResultadoEnvioCorreo):
            raise TypeError("El proveedor devolvio un resultado no reconocido")
    except Exception as exc:
        resultado = ResultadoEnvioCorreo.incierto(_sanitizar_error(exc))
    return _persistir_resultado(db_factory, solicitud, intento, resultado)


def procesar_avisos(db_factory, aviso_ids, permitir_reintento_error=False, proveedor=enviar_correo_aviso):
    resultados = []
    for aviso_id in aviso_ids:
        try:
            resultados.append(procesar_aviso(
                db_factory,
                aviso_id,
                permitir_reintento_error=permitir_reintento_error,
                proveedor=proveedor,
            ))
        except AvisoNoProcesable as exc:
            resultados.append(ResultadoProcesamientoAviso(
                aviso_id=exc.aviso_id,
                envio_id=0,
                estado=exc.estado or "OMITIDO",
                intento=0,
                omitido=True,
                razon=exc.razon,
            ))
        except Exception as exc:
            logger.exception("aviso_v2_error_inesperado", extra={"aviso_id": aviso_id})
            resultados.append(ResultadoProcesamientoAviso(
                aviso_id=int(aviso_id),
                envio_id=0,
                estado=AVISO_ESTADO_INCIERTO,
                intento=0,
                omitido=True,
                razon=_sanitizar_error(exc),
            ))
    return ResumenProcesamientoAvisos(
        total=len(resultados),
        enviados=sum(r.estado == AVISO_ESTADO_ENVIADO for r in resultados),
        errores=sum(r.estado == AVISO_ESTADO_ERROR for r in resultados),
        inciertos=sum(r.estado == AVISO_ESTADO_INCIERTO and not r.omitido for r in resultados),
        omitidos=sum(r.omitido for r in resultados),
        cancelados=sum(r.estado == AVISO_ESTADO_CANCELADO for r in resultados),
        resultados=tuple(resultados),
    )


def obtener_avisos_procesando_antiguos(db, ahora=None, umbral=UMBRAL_PROCESANDO_ANTIGUO):
    ahora = ahora or ahora_chile()
    limite = ahora - umbral
    return (
        db.query(AvisoEnvio)
        .filter(
            AvisoEnvio.av_estado == AVISO_ESTADO_PROCESANDO,
            AvisoEnvio.av_fecha_procesamiento.isnot(None),
            AvisoEnvio.av_fecha_procesamiento <= limite,
        )
        .order_by(AvisoEnvio.av_fecha_procesamiento.asc(), AvisoEnvio.id.asc())
        .all()
    )
