from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func

from database.modelos import PuntoRetiro, RetiroEnvio, RetiroStarken
from utils.fechas import a_hora_chile, ahora_chile


@dataclass(frozen=True)
class MetricasRetirosDia:
    envios: int
    bultos: int


def obtener_metricas_retiros_hoy(db, fecha_actual=None):
    """Resume retiros fisicos del dia operativo local de Chile."""
    fecha_local = a_hora_chile(fecha_actual or ahora_chile())
    inicio_dia = fecha_local.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_dia = inicio_dia + timedelta(days=1)

    bultos, envios = (
        db.query(
            func.coalesce(func.sum(RetiroEnvio.re_bultos_snapshot), 0),
            func.count(RetiroEnvio.id),
        )
        .select_from(RetiroEnvio)
        .join(RetiroStarken, RetiroStarken.id == RetiroEnvio.retiro_id)
        .join(PuntoRetiro, PuntoRetiro.id == RetiroStarken.punto_retiro_id)
        .filter(
            RetiroStarken.rs_anulado.is_(False),
            RetiroEnvio.re_vigente.is_(True),
            PuntoRetiro.pr_incluir_metricas_locales.is_(True),
            RetiroStarken.rs_fecha_retiro >= inicio_dia,
            RetiroStarken.rs_fecha_retiro < fin_dia,
        )
        .one()
    )
    return MetricasRetirosDia(envios=int(envios or 0), bultos=int(bultos or 0))
