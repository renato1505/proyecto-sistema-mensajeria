import os
import re
from datetime import datetime
from urllib.parse import urlencode

import pandas as pd
from sqlalchemy import func

from database.modelos import Envio


OPCIONES_PER_PAGE_HISTORICO = [25, 50, 100]
MESES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def construir_url_historico(
    mes,
    of="",
    destinatario="",
    remitente="",
    fecha="",
    fecha_desde="",
    fecha_hasta="",
    page=None,
    per_page=None,
):
    params = {
        "mes": mes,
        "of": of,
        "destinatario": destinatario,
        "remitente": remitente,
        "fecha": fecha,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
    }

    if page is not None:
        params["page"] = page

    if per_page is not None:
        params["per_page"] = per_page

    return "/historico?" + urlencode(params)


def limpiar_nombre_archivo(texto):
    texto = str(texto or "").strip()
    texto = re.sub(r"[^A-Za-z0-9_.-]+", "_", texto)
    return texto[:80] or "archivo"


def leer_filtros_historico(args):
    return {
        "mes": args.get("mes", "").strip(),
        "of": args.get("of", "").strip(),
        "destinatario": args.get("destinatario", "").strip(),
        "remitente": args.get("remitente", "").strip(),
        "fecha": args.get("fecha", "").strip(),
        "fecha_desde": args.get("fecha_desde", "").strip(),
        "fecha_hasta": args.get("fecha_hasta", "").strip(),
    }


def leer_paginacion_historico(args):
    try:
        page = int(args.get("page", "1"))
    except ValueError:
        page = 1

    try:
        per_page = int(args.get("per_page", "25"))
    except ValueError:
        per_page = 25

    if page < 1:
        page = 1

    if per_page not in OPCIONES_PER_PAGE_HISTORICO:
        per_page = 25

    return page, per_page


def construir_query_historico(
    db,
    mes_seleccionado,
    filtro_of,
    filtro_destinatario,
    filtro_remitente,
    filtro_fecha,
    fecha_desde,
    fecha_hasta,
):
    query = db.query(Envio).filter(Envio.e_estado == "historico")

    if mes_seleccionado and mes_seleccionado != "todos":
        try:
            mes_obj = datetime.strptime(mes_seleccionado, "%Y-%m")
        except ValueError:
            mes_obj = None
    else:
        mes_obj = None

    if mes_obj and not fecha_desde and not fecha_hasta and not filtro_fecha:
        query = query.filter(
            func.extract("year", Envio.e_fecha_creacion) == mes_obj.year,
            func.extract("month", Envio.e_fecha_creacion) == mes_obj.month,
        )

    if filtro_of:
        query = query.filter(Envio.e_orden_flete.ilike(f"%{filtro_of}%"))

    if filtro_destinatario:
        query = query.filter(Envio.e_destinatario.ilike(f"%{filtro_destinatario}%"))

    if filtro_remitente:
        query = query.filter(Envio.e_remitente.ilike(f"%{filtro_remitente}%"))

    if filtro_fecha:
        try:
            fecha_obj = datetime.strptime(filtro_fecha, "%Y-%m-%d").date()
            query = query.filter(func.date(Envio.e_fecha_creacion) == fecha_obj)
        except ValueError:
            pass

    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, "%Y-%m-%d")
            query = query.filter(Envio.e_fecha_creacion >= fecha_desde_obj)
        except ValueError:
            pass

    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, "%Y-%m-%d")
            fecha_hasta_obj = fecha_hasta_obj.replace(hour=23, minute=59, second=59)
            query = query.filter(Envio.e_fecha_creacion <= fecha_hasta_obj)
        except ValueError:
            pass

    return query


def query_desde_filtros(db, filtros):
    return construir_query_historico(
        db,
        filtros["mes"] or "todos",
        filtros["of"],
        filtros["destinatario"],
        filtros["remitente"],
        filtros["fecha"],
        filtros["fecha_desde"],
        filtros["fecha_hasta"],
    )


def url_desde_filtros(filtros, page=None, per_page=None):
    return construir_url_historico(
        filtros["mes"],
        filtros["of"],
        filtros["destinatario"],
        filtros["remitente"],
        filtros["fecha"],
        filtros["fecha_desde"],
        filtros["fecha_hasta"],
        page,
        per_page,
    )


def meses_disponibles(registros_historicos):
    meses_disponibles_resultado = [{"valor": "todos", "nombre": "Todos los registros"}]
    meses_vistos = set()

    for envio in registros_historicos:
        if not envio.e_fecha_creacion:
            continue

        clave = envio.e_fecha_creacion.strftime("%Y-%m")
        nombre = f"{MESES_ES[envio.e_fecha_creacion.month]} {envio.e_fecha_creacion.year}"

        if clave not in meses_vistos:
            meses_disponibles_resultado.append({"valor": clave, "nombre": nombre})
            meses_vistos.add(clave)

    return meses_disponibles_resultado


def convertir_envios_a_dataframe(envios):
    data = []

    for envio in envios:
        data.append({
            "Fecha": envio.e_fecha_creacion.strftime("%d/%m/%Y %H:%M") if envio.e_fecha_creacion else "",
            "Remitente": envio.e_remitente,
            "Correo remitente": envio.e_correo_remitente,
            "Division": envio.e_division,
            "Centro de costo": envio.e_centro_costo,
            "Destinatario": envio.e_destinatario,
            "RUT destinatario": envio.e_rut_destinatario,
            "Direccion": envio.e_direccion,
            "Comuna": envio.e_comuna,
            "Region": envio.e_region,
            "Telefono": envio.e_telefono_destinatario,
            "Tipo envio": envio.e_tipo_envio,
            "Codigo agencia": envio.e_codigo_agencia if envio.e_tipo_envio == "Agencia" else "No aplica",
            "Bultos": envio.e_bultos,
            "Kilos": envio.e_kilos,
            "Orden de flete": envio.e_orden_flete,
        })

    return pd.DataFrame(data)


def guardar_respaldo_historico(envios):
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    carpeta_respaldos = os.path.join(project_dir, "respaldos_historico")
    os.makedirs(carpeta_respaldos, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nombre_archivo = f"respaldo_historico_{timestamp}.xlsx"
    ruta_archivo = os.path.join(carpeta_respaldos, nombre_archivo)

    df = convertir_envios_a_dataframe(envios)

    with pd.ExcelWriter(ruta_archivo, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Historico")

    return nombre_archivo, ruta_archivo
