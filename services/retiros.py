import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import exists, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from database.modelos import Envio, PuntoRetiro, RetiroEnvio, RetiroStarken
from services.puntos_retiro import PUNTO_MENSAJERIA_LOCAL
from utils.fechas import a_hora_chile, ahora_chile


TOLERANCIA_FECHA_FUTURA = timedelta(minutes=15)


class RetiroError(Exception):
    pass


class RetiroValidacionError(RetiroError):
    pass


class RetiroConcurrenciaError(RetiroError):
    pass


@dataclass(frozen=True)
class EnvioElegibleRetiro:
    envio_id: int
    orden_flete: str
    destinatario: str
    remitente: str
    bultos: int
    fecha_of: datetime
    punto_retiro_id: int
    punto_codigo: str
    punto_nombre: str


def envio_puede_entrar_retiro(envio, punto, tiene_retiro_vigente=False):
    return _razon_no_elegible(envio, punto, tiene_retiro_vigente) is None


def _razon_no_elegible(envio, punto, tiene_retiro_vigente):
    if envio is None:
        return "el envio no existe"
    if envio.e_anulado:
        return "el envio esta anulado"
    if envio.e_fecha_of is None:
        return "el envio no tiene fecha OF"
    if not str(envio.e_orden_flete or "").strip():
        return "el envio no tiene orden de flete"
    if envio.e_punto_retiro_id is None or punto is None:
        return "el envio no tiene punto de retiro"
    if punto.pr_codigo != PUNTO_MENSAJERIA_LOCAL:
        return "el punto de retiro no corresponde a Mensajeria local"
    if not punto.pr_activo:
        return "el punto de retiro esta inactivo"
    if tiene_retiro_vigente:
        return "el envio ya posee un retiro vigente"
    try:
        if int(envio.e_bultos) < 1:
            return "el envio no tiene bultos validos"
    except (TypeError, ValueError):
        return "el envio no tiene bultos validos"
    return None


def _existe_retiro_vigente():
    return exists().where(
        RetiroEnvio.envio_id == Envio.id,
        RetiroEnvio.re_vigente.is_(True),
    )


def obtener_envios_elegibles(db):
    retiro_vigente = _existe_retiro_vigente()
    filas = (
        db.query(Envio, PuntoRetiro)
        .join(PuntoRetiro, PuntoRetiro.id == Envio.e_punto_retiro_id)
        .filter(
            Envio.e_anulado.is_(False),
            Envio.e_fecha_of.isnot(None),
            Envio.e_orden_flete.isnot(None),
            func.length(func.trim(Envio.e_orden_flete)) > 0,
            Envio.e_bultos >= 1,
            PuntoRetiro.pr_codigo == PUNTO_MENSAJERIA_LOCAL,
            PuntoRetiro.pr_activo.is_(True),
            ~retiro_vigente,
        )
        .order_by(Envio.e_fecha_of.asc(), Envio.id.asc())
        .all()
    )
    return [
        EnvioElegibleRetiro(
            envio_id=envio.id,
            orden_flete=envio.e_orden_flete,
            destinatario=envio.e_destinatario,
            remitente=envio.e_remitente,
            bultos=envio.e_bultos,
            fecha_of=envio.e_fecha_of,
            punto_retiro_id=punto.id,
            punto_codigo=punto.pr_codigo,
            punto_nombre=punto.pr_nombre,
        )
        for envio, punto in filas
    ]


def _normalizar_ids_envios(envio_ids):
    if not envio_ids:
        raise RetiroValidacionError("Debes seleccionar al menos un envio")
    ids = []
    for valor in envio_ids:
        if isinstance(valor, bool):
            raise RetiroValidacionError("La seleccion contiene un ID invalido")
        try:
            envio_id = int(valor)
        except (TypeError, ValueError):
            raise RetiroValidacionError("La seleccion contiene un ID invalido") from None
        if envio_id < 1:
            raise RetiroValidacionError("La seleccion contiene un ID invalido")
        ids.append(envio_id)
    if len(ids) != len(set(ids)):
        raise RetiroValidacionError("La seleccion contiene IDs duplicados")
    return ids


def _validar_fecha_retiro(fecha_retiro, fecha_confirmacion):
    if not isinstance(fecha_retiro, datetime):
        raise RetiroValidacionError("La fecha efectiva de retiro es obligatoria")
    fecha_retiro = a_hora_chile(fecha_retiro)
    if fecha_retiro > fecha_confirmacion + TOLERANCIA_FECHA_FUTURA:
        raise RetiroValidacionError("La fecha efectiva de retiro no puede estar en el futuro")
    return fecha_retiro


def construir_codigo_retiro(fecha_retiro, retiro_id):
    return f"RET-{fecha_retiro:%Y%m%d}-{retiro_id:06d}"


def _codigo_temporal_retiro():
    return f"TMP-RETIRO-{uuid.uuid4().hex}"


def _cargar_envios_para_confirmacion(db, ids):
    retiro_vigente = _existe_retiro_vigente().label("tiene_retiro_vigente")
    consulta = (
        db.query(Envio, PuntoRetiro, retiro_vigente)
        .outerjoin(PuntoRetiro, PuntoRetiro.id == Envio.e_punto_retiro_id)
        .filter(Envio.id.in_(ids))
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        consulta = consulta.with_for_update(of=Envio)
    filas = consulta.all()
    por_id = {envio.id: (envio, punto, bool(vigente)) for envio, punto, vigente in filas}
    faltantes = [envio_id for envio_id in ids if envio_id not in por_id]
    if faltantes:
        raise RetiroValidacionError(
            f"No existen los envios seleccionados: {', '.join(map(str, faltantes))}"
        )
    return [por_id[envio_id] for envio_id in ids]


def _confirmar_intento(db, ids, fecha_retiro, fecha_confirmacion, responsable, observacion):
    filas = _cargar_envios_para_confirmacion(db, ids)
    puntos = set()
    for envio, punto, tiene_retiro_vigente in filas:
        razon = _razon_no_elegible(envio, punto, tiene_retiro_vigente)
        if razon:
            raise RetiroValidacionError(f"Envio {envio.id}: {razon}")
        puntos.add(punto.id)
    if len(puntos) != 1:
        raise RetiroValidacionError("Todos los envios deben pertenecer al mismo punto de retiro")

    retiro = RetiroStarken(
        rs_codigo=_codigo_temporal_retiro(),
        punto_retiro_id=puntos.pop(),
        rs_fecha_retiro=fecha_retiro,
        rs_fecha_confirmacion=fecha_confirmacion,
        rs_responsable=responsable,
        rs_observacion=observacion,
    )
    db.add(retiro)
    db.flush()
    retiro.rs_codigo = construir_codigo_retiro(fecha_retiro, retiro.id)
    db.flush()
    for envio, _punto, _vigente in filas:
        db.add(RetiroEnvio(
            retiro_id=retiro.id,
            envio_id=envio.id,
            re_bultos_snapshot=envio.e_bultos,
            re_fecha_asociacion=fecha_confirmacion,
            re_vigente=True,
        ))
    db.flush()
    db.commit()
    return retiro


def confirmar_retiro(db, envio_ids, fecha_retiro, responsable=None, observacion=None):
    ids = _normalizar_ids_envios(envio_ids)
    fecha_confirmacion = ahora_chile()
    fecha_retiro = _validar_fecha_retiro(fecha_retiro, fecha_confirmacion)
    responsable = str(responsable or "").strip() or None
    observacion = str(observacion or "").strip() or None
    if responsable and len(responsable) > 160:
        raise RetiroValidacionError("El responsable no puede superar 160 caracteres")
    if observacion and len(observacion) > 1000:
        raise RetiroValidacionError("La observacion no puede superar 1000 caracteres")

    try:
        return _confirmar_intento(
            db, ids, fecha_retiro, fecha_confirmacion, responsable, observacion
        )
    except RetiroError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise RetiroConcurrenciaError(
            "No se pudo confirmar el retiro porque un envio o codigo ya fue utilizado"
        ) from exc
    except Exception:
        db.rollback()
        raise


def anular_retiro(db, retiro_id, motivo):
    motivo = str(motivo or "").strip()
    if not motivo:
        raise RetiroValidacionError("El motivo de anulacion es obligatorio")
    if len(motivo) > 500:
        raise RetiroValidacionError("El motivo de anulacion no puede superar 500 caracteres")
    try:
        consulta = (
            db.query(RetiroStarken)
            .options(selectinload(RetiroStarken.asociaciones))
            .filter(RetiroStarken.id == retiro_id)
        )
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            consulta = consulta.with_for_update(of=RetiroStarken)
        retiro = consulta.one_or_none()
        if retiro is None:
            raise RetiroValidacionError("El retiro no existe")
        if retiro.rs_anulado:
            raise RetiroValidacionError("El retiro ya esta anulado")

        fecha_anulacion = ahora_chile()
        retiro.rs_anulado = True
        retiro.rs_fecha_anulacion = fecha_anulacion
        retiro.rs_motivo_anulacion = motivo
        for asociacion in retiro.asociaciones:
            if asociacion.re_vigente:
                asociacion.re_vigente = False
        db.commit()
        return retiro
    except RetiroError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
