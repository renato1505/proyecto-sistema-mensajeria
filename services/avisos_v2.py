from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from database.modelos import (
    AVISO_ESTADO_CANCELADO,
    AVISO_ESTADO_ERROR,
    AVISO_ESTADO_PENDIENTE,
    AVISO_TIPO_DESTINATARIO,
    AVISO_TIPO_FUNCIONARIO,
    AvisoEnvio,
    Envio,
    RetiroEnvio,
    RetiroStarken,
    construir_clave_idempotencia_aviso,
)
from utils.validaciones import email_valido


ESTADOS_CANCELABLES = frozenset({AVISO_ESTADO_PENDIENTE, AVISO_ESTADO_ERROR})
TIPOS_AVISO = (AVISO_TIPO_FUNCIONARIO, AVISO_TIPO_DESTINATARIO)


class AvisosV2Error(Exception):
    pass


class AvisosV2ValidacionError(AvisosV2Error):
    pass


@dataclass(frozen=True)
class EnvioElegibleAvisos:
    envio_id: int
    retiro_id: int
    orden_flete: str
    correo_funcionario: str | None
    correo_destinatario: str | None


@dataclass(frozen=True)
class ResultadoSincronizacionAvisos:
    envio_id: int
    elegible: bool
    creados: int
    existentes: int
    cancelados: int


def _consulta_elegibles(db):
    return (
        db.query(Envio, RetiroEnvio, RetiroStarken)
        .join(
            RetiroEnvio,
            (RetiroEnvio.envio_id == Envio.id)
            & RetiroEnvio.re_vigente.is_(True),
        )
        .join(
            RetiroStarken,
            (RetiroStarken.id == RetiroEnvio.retiro_id)
            & RetiroStarken.rs_anulado.is_(False),
        )
        .filter(
            Envio.e_anulado.is_(False),
            Envio.e_fecha_of.isnot(None),
            Envio.e_orden_flete.isnot(None),
            func.length(func.trim(Envio.e_orden_flete)) > 0,
        )
    )


def obtener_envios_elegibles_avisos(db):
    """Obtiene candidatos desde la asociacion de retiro vigente, en una consulta."""
    filas = _consulta_elegibles(db).order_by(RetiroStarken.id.asc(), Envio.id.asc()).all()
    return [
        EnvioElegibleAvisos(
            envio_id=envio.id,
            retiro_id=retiro.id,
            orden_flete=str(envio.e_orden_flete).strip(),
            correo_funcionario=_correo_valido(envio.e_correo_remitente),
            correo_destinatario=_correo_valido(envio.e_correo_destinatario),
        )
        for envio, _asociacion, retiro in filas
    ]


def _correo_valido(valor):
    correo = str(valor or "").strip().lower()
    return correo if email_valido(correo) else None


def envio_es_elegible_avisos(db, envio_id):
    return _consulta_elegibles(db).filter(Envio.id == envio_id).first() is not None


def _crear_aviso(db, envio, tipo):
    correo_origen = (
        envio.e_correo_remitente
        if tipo == AVISO_TIPO_FUNCIONARIO
        else envio.e_correo_destinatario
    )
    correo = _correo_valido(correo_origen)
    aviso = AvisoEnvio(
        envio_id=envio.id,
        av_tipo=tipo,
        av_correo_snapshot=correo,
        av_estado=AVISO_ESTADO_PENDIENTE if correo else AVISO_ESTADO_CANCELADO,
        av_intentos=0,
        av_ultimo_error=None,
        av_clave_idempotencia=construir_clave_idempotencia_aviso(envio.id, tipo),
    )
    db.add(aviso)
    return aviso


def _sincronizar_intento(db, envio_id):
    consulta = db.query(Envio).filter(Envio.id == envio_id)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        consulta = consulta.with_for_update(of=Envio)
    envio = consulta.one_or_none()
    if envio is None:
        raise AvisosV2ValidacionError(f"No existe el envio {envio_id}")

    elegible = envio_es_elegible_avisos(db, envio_id)
    existentes = {
        aviso.av_tipo: aviso
        for aviso in db.query(AvisoEnvio).filter(AvisoEnvio.envio_id == envio_id).all()
    }
    creados = 0
    cancelados = 0
    if elegible:
        for tipo in TIPOS_AVISO:
            if tipo not in existentes:
                _crear_aviso(db, envio, tipo)
                creados += 1
    else:
        for aviso in existentes.values():
            if aviso.av_estado in ESTADOS_CANCELABLES:
                aviso.av_estado = AVISO_ESTADO_CANCELADO
                cancelados += 1

    db.flush()
    return ResultadoSincronizacionAvisos(
        envio_id=envio_id,
        elegible=elegible,
        creados=creados,
        existentes=len(existentes),
        cancelados=cancelados,
    )


def sincronizar_avisos_envio(db, envio_id):
    try:
        envio_id = int(envio_id)
    except (TypeError, ValueError):
        raise AvisosV2ValidacionError("El ID de envio no es valido") from None
    if envio_id < 1:
        raise AvisosV2ValidacionError("El ID de envio no es valido")

    # El bloqueo por envio serializa PostgreSQL. Los UNIQUE siguen siendo la
    # defensa final y este reintento absorbe una carrera normal de insercion.
    for intento in range(2):
        try:
            resultado = _sincronizar_intento(db, envio_id)
            db.commit()
            return resultado
        except IntegrityError:
            db.rollback()
            if intento:
                raise
        except Exception:
            db.rollback()
            raise
    raise AssertionError("Sincronizacion sin resultado")


def _normalizar_ids(envio_ids):
    ids = []
    for valor in envio_ids:
        if isinstance(valor, bool):
            raise AvisosV2ValidacionError("La seleccion contiene un ID invalido")
        try:
            envio_id = int(valor)
        except (TypeError, ValueError):
            raise AvisosV2ValidacionError("La seleccion contiene un ID invalido") from None
        if envio_id < 1:
            raise AvisosV2ValidacionError("La seleccion contiene un ID invalido")
        ids.append(envio_id)
    return sorted(set(ids))


def sincronizar_avisos_elegibles(db, envio_ids=None):
    """Sincroniza de forma atomica por envio; un fallo detiene el lote.

    Sin filtro incluye tanto elegibles como envios con avisos existentes, para
    que la misma pasada pueda reconciliar los que dejaron de ser elegibles.
    """
    if envio_ids is None:
        elegibles = _consulta_elegibles(db).with_entities(Envio.id)
        existentes = db.query(AvisoEnvio.envio_id)
        ids = [fila[0] for fila in elegibles.union(existentes).order_by(Envio.id.asc()).all()]
    else:
        ids = _normalizar_ids(envio_ids)
    return [sincronizar_avisos_envio(db, envio_id) for envio_id in ids]
