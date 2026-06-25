from collections import Counter

from database.modelos import Envio, ExcepcionEnvio
from utils.fechas import ahora_chile


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

PALETA_DIVISIONES = ["#bd923b", "#071a32", "#98a2b3", "#d0d5dd", "#eaecf0"]


def _ultimos_meses(cantidad=6):
    hoy = ahora_chile()
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


def _donut_divisiones(items):
    if not items:
        return {
            "total": 0,
            "gradient": "conic-gradient(#eaecf0 0% 100%)",
            "items": [],
        }

    inicio = 0
    cortes = []
    for indice, item in enumerate(items):
        color = PALETA_DIVISIONES[indice % len(PALETA_DIVISIONES)]
        fin = min(100, inicio + item["porcentaje"])
        item["color"] = color
        cortes.append(f"{color} {inicio}% {fin}%")
        inicio = fin

    if inicio < 100:
        cortes.append(f"#f2f4f7 {inicio}% 100%")

    return {
        "total": sum(item["cantidad"] for item in items),
        "gradient": f"conic-gradient({', '.join(cortes)})",
        "items": items,
    }


def _mes_anterior(year, month):
    month -= 1
    if month == 0:
        return year - 1, 12
    return year, month


def _envios_del_mes(envios, year, month):
    return [
        envio for envio in envios
        if envio.e_fecha_creacion
        and envio.e_fecha_creacion.year == year
        and envio.e_fecha_creacion.month == month
    ]


def _variacion(actual, anterior, unidad="%", favorable_subir=True):
    if anterior == 0:
        valor = 100 if actual else 0
    else:
        valor = round(((actual - anterior) / anterior) * 100, 1)

    signo = "+" if valor > 0 else ""
    if valor == 0:
        clase = "neutral"
    elif favorable_subir:
        clase = "up" if valor > 0 else "down"
    else:
        clase = "down" if valor > 0 else "up"

    return {
        "valor": valor,
        "texto": f"{signo}{valor:g}{unidad}",
        "clase": clase,
    }


def obtener_dashboard_mensajeria(db):
    """Calcula indicadores ejecutivos simples para el inicio del modulo."""
    envios_todos = (
        db.query(Envio)
        .order_by(Envio.e_fecha_creacion.desc())
        .all()
    )
    reportes = (
        db.query(ExcepcionEnvio)
        .order_by(ExcepcionEnvio.x_fecha_creacion.desc())
        .all()
    )
    envios = [envio for envio in envios_todos if envio.e_estado == "historico"]

    hoy = ahora_chile()
    prev_year, prev_month = _mes_anterior(hoy.year, hoy.month)
    envios_mes = _envios_del_mes(envios, hoy.year, hoy.month)
    envios_mes_anterior = _envios_del_mes(envios, prev_year, prev_month)
    todos_mes = _envios_del_mes(envios_todos, hoy.year, hoy.month)
    todos_mes_anterior = _envios_del_mes(envios_todos, prev_year, prev_month)

    meses = _ultimos_meses()
    conteo_mensual = Counter()
    for envio in envios:
        if envio.e_fecha_creacion:
            conteo_mensual[(envio.e_fecha_creacion.year, envio.e_fecha_creacion.month)] += 1

    tendencia = []
    puntos_linea = []
    max_mes = max([conteo_mensual[mes] for mes in meses] + [1])
    divisor = max(len(meses) - 1, 1)
    for indice, (year, month) in enumerate(meses):
        cantidad = conteo_mensual[(year, month)]
        x = 8 + round((84 / divisor) * indice, 2)
        y = 60 - round((cantidad / max_mes) * 46, 2) if cantidad else 60
        puntos_linea.append(f"{x},{y}")
        tendencia.append({
            "periodo": f"{MESES_CORTOS[month]} {year}",
            "mes": MESES_CORTOS[month],
            "cantidad": cantidad,
            "porcentaje": max(4, round((cantidad / max_mes) * 100)) if cantidad else 0,
            "x": x,
            "y": y,
        })

    solicitantes = Counter(envio.e_remitente for envio in envios if envio.e_remitente)
    divisiones = Counter(envio.e_division for envio in envios if envio.e_division)
    regiones = Counter(envio.e_region for envio in envios if envio.e_region)
    tipos_mes = Counter(envio.e_tipo_envio for envio in envios_mes if envio.e_tipo_envio)
    solicitantes_mes = Counter(envio.e_remitente for envio in envios_mes if envio.e_remitente)
    solicitantes_mes_anterior = Counter(envio.e_remitente for envio in envios_mes_anterior if envio.e_remitente)

    division_principal = divisiones.most_common(1)[0][0] if divisiones else "Sin datos"
    region_principal = regiones.most_common(1)[0][0] if regiones else "Sin datos"
    region_principal_cantidad = regiones.most_common(1)[0][1] if regiones else 0
    bultos_mes = sum(envio.e_bultos or 0 for envio in envios_mes)
    bultos_mes_anterior = sum(envio.e_bultos or 0 for envio in envios_mes_anterior)
    anuladas_mes = sum(1 for envio in envios_mes if envio.e_anulado)
    anuladas_mes_anterior = sum(1 for envio in envios_mes_anterior if envio.e_anulado)
    reportes_mes = [
        reporte for reporte in reportes
        if reporte.x_fecha_creacion
        and reporte.x_fecha_creacion.year == hoy.year
        and reporte.x_fecha_creacion.month == hoy.month
    ]
    reportes_mes_anterior = [
        reporte for reporte in reportes
        if reporte.x_fecha_creacion
        and reporte.x_fecha_creacion.year == prev_year
        and reporte.x_fecha_creacion.month == prev_month
    ]
    top_funcionario_nombre, top_funcionario_envios = (
        solicitantes_mes.most_common(1)[0] if solicitantes_mes else ("Sin datos", 0)
    )
    top_funcionario_anterior = solicitantes_mes_anterior.get(top_funcionario_nombre, 0)

    top_divisiones = _top(divisiones)

    return {
        "resumen_mes": {
            "envios": len(envios_mes),
            "bultos": bultos_mes,
            "funcionarios": len({
                (envio.e_correo_remitente or envio.e_remitente or "").strip().lower()
                for envio in envios_mes
                if envio.e_correo_remitente or envio.e_remitente
            }),
            "division_principal": division_principal,
            "region_principal": region_principal,
            "region_principal_cantidad": region_principal_cantidad,
            "domicilio": tipos_mes.get("Domicilio", 0),
            "agencia": tipos_mes.get("Agencia", 0),
            "anuladas": anuladas_mes,
            "reportes": len(reportes_mes),
            "top_funcionario": {
                "nombre": top_funcionario_nombre,
                "envios": top_funcionario_envios,
                "anterior": top_funcionario_anterior,
            },
        },
        "comparativas": {
            "envios": _variacion(len(envios_mes), len(envios_mes_anterior), favorable_subir=True),
            "bultos": _variacion(bultos_mes, bultos_mes_anterior, favorable_subir=True),
            "top_funcionario": _variacion(
                top_funcionario_envios,
                top_funcionario_anterior,
                favorable_subir=True,
            ),
            "anuladas": _variacion(anuladas_mes, anuladas_mes_anterior, favorable_subir=False),
            "reportes": _variacion(len(reportes_mes), len(reportes_mes_anterior), favorable_subir=False),
        },
        "tendencia_mensual": tendencia,
        "tendencia_linea": {
            "points": " ".join(puntos_linea),
            "ultimo": tendencia[-1] if tendencia else {"cantidad": 0, "x": 92, "y": 60},
            "max": max_mes,
            "medio": round(max_mes / 2),
        },
        "top_solicitantes": _top(solicitantes),
        "top_divisiones": top_divisiones,
        "donut_divisiones": _donut_divisiones(top_divisiones),
        "top_regiones": _top(regiones),
        "total_historico": len(envios),
    }
