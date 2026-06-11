from collections import Counter
from datetime import datetime

from database.modelos import Envio


MESES_CORTOS = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


def _ultimos_meses(cantidad=6):
    hoy = datetime.now()
    meses = []
    year = hoy.year
    month = hoy.month

    for _ in range(cantidad):
        meses.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    return list(reversed(meses))


def _top(counter, limite=5):
    total = sum(counter.values()) or 1
    return [
        {
            "nombre": nombre or "Sin dato",
            "cantidad": cantidad,
            "porcentaje": round((cantidad / total) * 100),
        }
        for nombre, cantidad in counter.most_common(limite)
    ]


def obtener_dashboard_mensajeria(db):
    """Calcula indicadores ejecutivos simples para el inicio del modulo."""
    envios = (
        db.query(Envio)
        .filter(Envio.e_estado == "historico")
        .order_by(Envio.e_fecha_creacion.desc())
        .all()
    )

    hoy = datetime.now()
    envios_mes = [
        envio for envio in envios
        if envio.e_fecha_creacion
        and envio.e_fecha_creacion.year == hoy.year
        and envio.e_fecha_creacion.month == hoy.month
    ]

    meses = _ultimos_meses()
    conteo_mensual = Counter()
    for envio in envios:
        if envio.e_fecha_creacion:
            conteo_mensual[(envio.e_fecha_creacion.year, envio.e_fecha_creacion.month)] += 1

    tendencia = []
    max_mes = max([conteo_mensual[mes] for mes in meses] + [1])
    for year, month in meses:
        cantidad = conteo_mensual[(year, month)]
        tendencia.append({
            "periodo": f"{MESES_CORTOS[month]} {year}",
            "cantidad": cantidad,
            "porcentaje": max(4, round((cantidad / max_mes) * 100)) if cantidad else 0,
        })

    solicitantes = Counter(envio.e_remitente for envio in envios if envio.e_remitente)
    divisiones = Counter(envio.e_division for envio in envios if envio.e_division)
    regiones = Counter(envio.e_region for envio in envios if envio.e_region)
    tipos_mes = Counter(envio.e_tipo_envio for envio in envios_mes if envio.e_tipo_envio)

    division_principal = divisiones.most_common(1)[0][0] if divisiones else "Sin datos"
    region_principal = regiones.most_common(1)[0][0] if regiones else "Sin datos"

    return {
        "resumen_mes": {
            "envios": len(envios_mes),
            "bultos": sum(envio.e_bultos or 0 for envio in envios_mes),
            "funcionarios": len({
                (envio.e_correo_remitente or envio.e_remitente or "").strip().lower()
                for envio in envios_mes
                if envio.e_correo_remitente or envio.e_remitente
            }),
            "division_principal": division_principal,
            "region_principal": region_principal,
            "domicilio": tipos_mes.get("Domicilio", 0),
            "agencia": tipos_mes.get("Agencia", 0),
        },
        "tendencia_mensual": tendencia,
        "top_solicitantes": _top(solicitantes),
        "top_divisiones": _top(divisiones),
        "top_regiones": _top(regiones),
        "total_historico": len(envios),
    }
