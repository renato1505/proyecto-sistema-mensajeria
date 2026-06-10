import csv
import io
import os
import unicodedata
from pathlib import Path

from config.settings import RESPALDOS_LOTES_DIR


DIVISIONES_SIGLAS = {
    "Consumer Products": "DPGP",
    "Corporate Multidivision": "DOP",
    "Dermatological Beauty": "LDB",
    "L'Oreal Luxe": "DL",
    "Loreal Luxe": "DL",
    "Professional Products": "DPP",
    "DPGP": "DPGP",
    "DOP": "DOP",
    "LDB": "LDB",
    "DL": "DL",
    "DPP": "DPP",
}

HEADERS_STARKEN = [
    "CODIGO AGENCIA DESTINO",
    "RUT DESTINATARIO",
    "DIGITO VERIFICADOR (DEL RUT)",
    "*NOMBRE DESTINATARIO O RAZON SOCIAL",
    "*APELLIDO PATERNO",
    "*APELLIDO MATERNO",
    "*DIRECCION DESTINATARIO",
    "*NUMERO DIRECCION DESTINATARIO",
    "NUMERO DEPARTAMENTO",
    "*COMUNA DESTINATARIO",
    "TELEFONO DESTINATARIO",
    "E-MAIL DESTINATARIO",
    "NOMBRE CONTACTO DESTINATARIO",
    "*TIPO DE ENTREGA (1)AGENCIA (2)DOMICILIO",
    "*TIPO DE PAGO (2)CTA. CTE. (3)POR PAGAR",
    "NUMERO CTA. CTE.",
    "DIGITO VERIFICADOR CTA. CTE.",
    "NUMERO CENTRO DE COSTO",
    "*VALOR DECLARADO",
    "*CONTENIDO",
    "*CANTIDAD BULTOS",
    "CANTIDAD SOBRES",
    "*KILOS",
    "TIPO SERVICIO (0)NORM (1)EXPR",
    "TIPO DOCUMENTO_1 (26)FACTURA (27)GUIA (28)BOLETA",
    "NUMERO DOCUMENTO_1",
    "TIPO DOCUMENTO_2 (26)FACTURA (27)GUIA (28)BOLETA",
    "NUMERO DOCUMENTO_2",
    "TIPO DOCUMENTO_3 (26)FACTURA (27)GUIA (28)BOLETA",
    "NUMERO DOC 3",
    "TIPO DOCUMENTO_4 (26)FACTURA (27)GUIA (28)BOLETA",
    "NUMERO DOCUMENTO_4",
    "TIPO DOCUMENTO_5 (26)FACTURA (27)GUIA (28)BOLETA",
    "NUMERO DOC 5",
    "TIPO ENCARGO 1",
    "CANTIDAD",
    "TIPO ENCARGO 2",
    "CANTIDAD_2",
    "TIPO ENCARGO 3",
    "CANTIDAD_3",
    "TIPO ENCARGO 4",
    "CANTIDAD_4",
    "TIPO ENCARGO 5",
    "CANTIDAD_5",
    "LATITUD",
    "LONGITUD",
    "OBSERVACION",
    "OBSERVACION_CLIENTE",
    "ANCHO(CM)",
    "ALTO(CM)",
    "LARGO(CM)",
    "PESO FISICO",
    "PESO VOLUMETRICO",
    "DIAMETRO",
]


def normalizar_comuna(texto):
    if not texto:
        return ""

    texto = str(texto).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    return texto.upper()


def obtener_sigla_division(division):
    if not division:
        return ""
    return DIVISIONES_SIGLAS.get(str(division).strip(), str(division).strip())


def construir_fila_starken(envio):
    tipo_entrega = "1" if envio.e_tipo_envio == "Agencia" else "2"
    codigo_agencia = envio.e_codigo_agencia if envio.e_tipo_envio == "Agencia" else ""
    division_sigla = obtener_sigla_division(envio.e_division)

    return [
        codigo_agencia,
        "",
        "",
        envio.e_destinatario or "",
        division_sigla,
        envio.e_centro_costo or "",
        envio.e_direccion or "",
        ".",
        "",
        normalizar_comuna(envio.e_comuna),
        envio.e_telefono_destinatario or "",
        "",
        envio.e_centro_costo or "",
        tipo_entrega,
        "2",
        "42315",
        "7",
        "0",
        "50000",
        "varios",
        envio.e_bultos or 0,
        "",
        envio.e_kilos or 0,
        "0",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]


def generar_csv_starken(envios, fecha_actual):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    writer.writerow(HEADERS_STARKEN)

    for envio in envios:
        writer.writerow(construir_fila_starken(envio))

    contenido_csv = output.getvalue()
    output.close()

    contenido_bytes = contenido_csv.encode("cp1252", errors="replace")
    nombre_archivo = (
        f"starken_{fecha_actual.strftime('%Y-%m-%d_%H-%M-%S')}_"
        f"{len(envios)}-envios.csv"
    )

    return nombre_archivo, contenido_bytes


def guardar_respaldo_lote(nombre_archivo, contenido_bytes):
    carpeta = Path(RESPALDOS_LOTES_DIR)
    if not carpeta.is_absolute():
        carpeta = Path(__file__).resolve().parent.parent / carpeta

    os.makedirs(carpeta, exist_ok=True)

    ruta_archivo = carpeta / nombre_archivo
    ruta_archivo.write_bytes(contenido_bytes)
    return ruta_archivo

