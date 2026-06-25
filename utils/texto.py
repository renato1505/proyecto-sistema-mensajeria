import re
import unicodedata
from numbers import Number


def quitar_acentos(texto):
    texto = str(texto or "")
    texto = unicodedata.normalize("NFKD", texto)
    return texto.encode("ascii", "ignore").decode("utf-8")


def normalizar_texto_operativo(texto, upper=False):
    if texto is None:
        return ""

    texto = quitar_acentos(texto)
    texto = re.sub(r"\s+", " ", str(texto)).strip()

    if upper:
        return texto.upper()

    return texto


def normalizar_nombre_operativo(texto):
    texto = normalizar_texto_operativo(texto)
    return texto.title()


def normalizar_nombre_remitente(texto):
    nombre = normalizar_nombre_operativo(texto)
    partes = nombre.split()

    if len(partes) <= 2:
        return nombre

    if len(partes) == 3:
        return f"{partes[0]} {partes[-1]}"

    return f"{partes[0]} {partes[-2]}"


def normalizar_correo_operativo(texto):
    return normalizar_texto_operativo(texto).lower()


def normalizar_observacion_operativa(texto):
    texto = normalizar_texto_operativo(texto)
    texto = re.sub(r"[.,;]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def normalizar_orden_flete(valor):
    if valor is None:
        return ""

    if isinstance(valor, Number):
        try:
            numero = float(valor)
            if numero.is_integer():
                return str(int(numero))
        except (TypeError, ValueError, OverflowError):
            pass

    texto = str(valor or "").strip()
    if re.fullmatch(r"\d+\.0+", texto):
        return texto.split(".", 1)[0]

    return texto


def clave_texto_operativo(texto):
    return normalizar_texto_operativo(texto).lower()
