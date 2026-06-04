import json
import re
import uuid
from collections import defaultdict
from numbers import Number
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from database.modelos import Comuna, Envio
from utils.validaciones import (
    email_valido,
    normalizar_telefono_chile,
    rut_operativo_valido,
    telefono_chile_valido,
)


COLUMNAS_PLANTILLA = [
    "Remitente",
    "Correo remitente",
    "Centro costo",
    "Division",
    "Destinatario",
    "RUT destinatario",
    "Direccion",
    "Region",
    "Comuna",
    "Telefono",
    "Tipo envio",
    "Bultos",
    "Kilos",
    "Observacion",
]

DIVISIONES = ["DPGP", "DOP", "LDB", "DL", "DPP"]
TIPOS_ENVIO = ["Domicilio", "Agencia"]
MAX_FILAS_CARGA = 300
TMP_CARGAS_DIR = Path(__file__).resolve().parent.parent / "tmp_cargas"


MAPA_COLUMNAS = {
    "remitente": "remitente",
    "correo remitente": "correo_remitente",
    "centro costo": "centro_costo",
    "division": "division",
    "destinatario": "destinatario",
    "rut destinatario": "rut_destinatario",
    "rut": "rut_destinatario",
    "direccion": "direccion",
    "region": "region",
    "comuna": "comuna",
    "telefono": "telefono_destinatario",
    "numero telefono": "telefono_destinatario",
    "tipo envio": "tipo_envio",
    "tipo de envio": "tipo_envio",
    "bultos": "bultos",
    "kilos": "kilos",
    "observacion": "observacion",
}


def _normalizar_columna(valor):
    texto = str(valor or "").strip().lower()
    texto = (
        texto.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _texto(valor):
    if pd.isna(valor):
        return ""
    if isinstance(valor, Number) and float(valor).is_integer():
        return str(int(valor)).strip()
    return str(valor).strip()


def _telefono(valor):
    return normalizar_telefono_chile(_texto(valor))


def _numero_entero(valor):
    if pd.isna(valor) or str(valor).strip() == "":
        return None
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


def _obtener_catalogo_comunas(db):
    comunas = db.query(Comuna).order_by(Comuna.c_region.asc(), Comuna.c_nombre.asc()).all()
    por_region = defaultdict(list)
    region_por_comuna = {}

    for comuna in comunas:
        region = comuna.c_region.strip()
        nombre = comuna.c_nombre.strip()
        por_region[region].append(nombre)
        region_por_comuna[_normalizar_columna(nombre)] = region

    return dict(por_region), region_por_comuna


def generar_plantilla_carga_masiva(db):
    por_region, _ = _obtener_catalogo_comunas(db)
    regiones = sorted(por_region)

    wb = Workbook()
    ws = wb.active
    ws.title = "Envios"

    header_fill = PatternFill("solid", fgColor="111827")
    header_font = Font(color="FFFFFF", bold=True)

    for col, titulo in enumerate(COLUMNAS_PLANTILLA, start=1):
        cell = ws.cell(row=1, column=col, value=titulo)
        cell.fill = header_fill
        cell.font = header_font
        ws.column_dimensions[cell.column_letter].width = max(16, len(titulo) + 4)

    for row in range(2, 302):
        ws.cell(row=row, column=6).number_format = "@"
        ws.cell(row=row, column=10).number_format = "@"

    ejemplo = [
        "Nombre Apellido",
        "correo@loreal.com",
        "123456",
        "DPGP",
        "Destinatario Ejemplo",
        "0",
        "Av. Ejemplo 123",
        regiones[0] if regiones else "",
        por_region[regiones[0]][0] if regiones and por_region[regiones[0]] else "",
        "912345678",
        "Domicilio",
        1,
        1,
        "",
    ]
    for col, valor in enumerate(ejemplo, start=1):
        ws.cell(row=2, column=col, value=valor)

    listas = wb.create_sheet("Listas")
    for row, region in enumerate(regiones, start=1):
        listas.cell(row=row, column=1, value=region)
    for row, division in enumerate(DIVISIONES, start=1):
        listas.cell(row=row, column=2, value=division)
    for row, tipo in enumerate(TIPOS_ENVIO, start=1):
        listas.cell(row=row, column=3, value=tipo)

    comunas_ws = wb.create_sheet("Comunas por region")
    for col, region in enumerate(regiones, start=1):
        comunas_ws.cell(row=1, column=col, value=region)
        for row, comuna in enumerate(por_region[region], start=2):
            comunas_ws.cell(row=row, column=col, value=comuna)

    rango_region = f"Listas!$A$1:$A${max(1, len(regiones))}"
    rango_division = f"Listas!$B$1:$B${len(DIVISIONES)}"
    rango_tipo = f"Listas!$C$1:$C${len(TIPOS_ENVIO)}"
    dv_region = DataValidation(type="list", formula1=f"={rango_region}", allow_blank=False)
    dv_division = DataValidation(type="list", formula1=f"={rango_division}", allow_blank=False)
    dv_tipo = DataValidation(type="list", formula1=f"={rango_tipo}", allow_blank=False)
    formula_comunas = (
        '=OFFSET(\'Comunas por region\'!$A$2,0,'
        'MATCH($H2,\'Comunas por region\'!$A$1:$Z$1,0)-1,'
        'COUNTA(OFFSET(\'Comunas por region\'!$A:$A,0,'
        'MATCH($H2,\'Comunas por region\'!$A$1:$Z$1,0)-1))-1,1)'
    )
    dv_comuna = DataValidation(type="list", formula1=formula_comunas, allow_blank=False)

    ws.add_data_validation(dv_region)
    ws.add_data_validation(dv_division)
    ws.add_data_validation(dv_tipo)
    ws.add_data_validation(dv_comuna)
    dv_division.add("D2:D301")
    dv_region.add("H2:H301")
    dv_comuna.add("I2:I301")
    dv_tipo.add("K2:K301")

    ws.freeze_panes = "A2"
    listas.sheet_state = "hidden"
    comunas_ws.sheet_state = "hidden"
    return wb


def _mapear_dataframe(df):
    columnas = {}
    for columna in df.columns:
        normalizada = _normalizar_columna(columna)
        if normalizada in MAPA_COLUMNAS:
            columnas[columna] = MAPA_COLUMNAS[normalizada]

    return df.rename(columns=columnas)


def validar_archivo_carga_masiva(archivo, db):
    df = pd.read_excel(archivo, sheet_name="Envios")
    df = _mapear_dataframe(df)
    df = df.dropna(how="all")

    if len(df) > MAX_FILAS_CARGA:
        return {
            "ok": False,
            "errores_archivo": [f"La carga no puede superar {MAX_FILAS_CARGA} filas por archivo"],
            "filas": [],
            "resumen": {},
            "token": None,
        }

    requeridas = [
        "remitente",
        "correo_remitente",
        "centro_costo",
        "division",
        "destinatario",
        "rut_destinatario",
        "direccion",
        "region",
        "comuna",
        "telefono_destinatario",
        "tipo_envio",
        "bultos",
        "kilos",
    ]

    faltantes = [col for col in requeridas if col not in df.columns]
    if faltantes:
        return {
            "ok": False,
            "errores_archivo": ["Faltan columnas obligatorias: " + ", ".join(faltantes)],
            "filas": [],
            "resumen": {},
            "token": None,
        }

    registros = []
    for index, row in df.iterrows():
        registros.append({
            "numero": int(index) + 2,
            "remitente": _texto(row.get("remitente")),
            "correo_remitente": _texto(row.get("correo_remitente")),
            "centro_costo": _texto(row.get("centro_costo")),
            "division": _texto(row.get("division")).upper(),
            "destinatario": _texto(row.get("destinatario")),
            "rut_destinatario": _texto(row.get("rut_destinatario")),
            "direccion": _texto(row.get("direccion")),
            "region": _texto(row.get("region")),
            "comuna": _texto(row.get("comuna")),
            "telefono_destinatario": _telefono(row.get("telefono_destinatario")),
            "tipo_envio": _texto(row.get("tipo_envio")).capitalize(),
            "bultos": _numero_entero(row.get("bultos")),
            "kilos": _numero_entero(row.get("kilos")),
            "observacion": _texto(row.get("observacion")),
        })

    return validar_registros_carga_masiva(registros, db)


def validar_registros_carga_masiva(registros, db):
    por_region, region_por_comuna = _obtener_catalogo_comunas(db)
    regiones_validas = {_normalizar_columna(region): region for region in por_region}
    filas = []
    registros_validos = []

    requeridas = [
        "remitente",
        "correo_remitente",
        "centro_costo",
        "division",
        "destinatario",
        "rut_destinatario",
        "direccion",
        "region",
        "comuna",
        "telefono_destinatario",
        "tipo_envio",
        "bultos",
        "kilos",
    ]

    for index, registro in enumerate(registros):
        data = {
            "remitente": _texto(registro.get("remitente")),
            "correo_remitente": _texto(registro.get("correo_remitente")),
            "centro_costo": _texto(registro.get("centro_costo")),
            "division": _texto(registro.get("division")).upper(),
            "destinatario": _texto(registro.get("destinatario")),
            "rut_destinatario": _texto(registro.get("rut_destinatario")),
            "direccion": _texto(registro.get("direccion")),
            "region": _texto(registro.get("region")),
            "comuna": _texto(registro.get("comuna")),
            "telefono_destinatario": _telefono(registro.get("telefono_destinatario")),
            "tipo_envio": _texto(registro.get("tipo_envio")).capitalize(),
            "bultos": _numero_entero(registro.get("bultos")),
            "kilos": _numero_entero(registro.get("kilos")),
            "observacion": _texto(registro.get("observacion")),
        }
        errores = []
        advertencias = []

        for campo in requeridas:
            if data[campo] in {"", None}:
                errores.append(f"{campo}: obligatorio")

        if data["correo_remitente"] and not email_valido(data["correo_remitente"]):
            errores.append("correo_remitente: formato invalido")

        if data["rut_destinatario"] and not rut_operativo_valido(data["rut_destinatario"]):
            errores.append("rut_destinatario: ingresa RUT o 0")

        if data["telefono_destinatario"] and not telefono_chile_valido(data["telefono_destinatario"]):
            errores.append("telefono_destinatario: debe tener 8 o 9 digitos")

        if data["division"] and data["division"] not in DIVISIONES:
            errores.append("division: valor no permitido")

        if data["tipo_envio"] and data["tipo_envio"] not in TIPOS_ENVIO:
            errores.append("tipo_envio: usa Domicilio o Agencia")

        if data["bultos"] is not None and not 1 <= data["bultos"] <= 9999:
            errores.append("bultos: debe estar entre 1 y 9999")

        if data["kilos"] is not None and not 1 <= data["kilos"] <= 9999:
            errores.append("kilos: debe estar entre 1 y 9999")

        region_normalizada = _normalizar_columna(data["region"])
        comuna_normalizada = _normalizar_columna(data["comuna"])
        region_catalogo = regiones_validas.get(region_normalizada)
        region_de_comuna = region_por_comuna.get(comuna_normalizada)

        if data["region"] and not region_catalogo:
            errores.append("region: no existe en el catalogo")

        if data["comuna"] and not region_de_comuna:
            errores.append("comuna: no existe en el catalogo")

        if region_catalogo and region_de_comuna and region_catalogo != region_de_comuna:
            errores.append("comuna: no corresponde a la region seleccionada")

        if data["tipo_envio"] == "Agencia":
            advertencias.append("Requiere completar codigo de agencia antes de generar lote")

        estado = "error" if errores else ("advertencia" if advertencias else "listo")
        fila = {
            "numero": int(registro.get("numero") or index + 2),
            "data": data,
            "errores": errores,
            "advertencias": advertencias,
            "estado": estado,
        }
        filas.append(fila)

        if not errores:
            registros_validos.append(data)

    token = None
    if registros_validos and not any(fila["errores"] for fila in filas):
        token = guardar_carga_temporal(registros_validos)

    return {
        "ok": not any(fila["errores"] for fila in filas),
        "errores_archivo": [],
        "filas": filas,
        "resumen": {
            "total": len(filas),
            "listos": sum(1 for fila in filas if fila["estado"] == "listo"),
            "advertencias": sum(1 for fila in filas if fila["estado"] == "advertencia"),
            "errores": sum(1 for fila in filas if fila["estado"] == "error"),
        },
        "token": token,
    }


def guardar_carga_temporal(registros):
    TMP_CARGAS_DIR.mkdir(exist_ok=True)
    token = uuid.uuid4().hex
    ruta = TMP_CARGAS_DIR / f"{token}.json"
    ruta.write_text(json.dumps(registros, ensure_ascii=False), encoding="utf-8")
    return token


def leer_carga_temporal(token):
    if not re.fullmatch(r"[a-f0-9]{32}", token or ""):
        return None

    ruta = TMP_CARGAS_DIR / f"{token}.json"
    if not ruta.exists():
        return None

    return json.loads(ruta.read_text(encoding="utf-8"))


def eliminar_carga_temporal(token):
    if not re.fullmatch(r"[a-f0-9]{32}", token or ""):
        return

    ruta = TMP_CARGAS_DIR / f"{token}.json"
    if ruta.exists():
        ruta.unlink()


def construir_envio_desde_carga(data):
    return Envio(
        e_estado="pendiente",
        e_remitente=data["remitente"],
        e_correo_remitente=data["correo_remitente"],
        e_division=data["division"],
        e_centro_costo=data["centro_costo"],
        e_destinatario=data["destinatario"],
        e_rut_destinatario=data["rut_destinatario"],
        e_direccion=data["direccion"],
        e_comuna=data["comuna"],
        e_region=data["region"],
        e_telefono_destinatario=data["telefono_destinatario"],
        e_tipo_envio=data["tipo_envio"],
        e_codigo_agencia="",
        e_bultos=data["bultos"],
        e_kilos=data["kilos"],
    )
