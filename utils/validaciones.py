import re
from numbers import Number


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NOMBRE_PERSONA_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ'´` .-]+$")


def email_valido(email):
    if not email:
        return False
    return bool(EMAIL_RE.match(str(email).strip()))


def nombre_persona_valido(nombre):
    nombre = str(nombre or "").strip()

    if len(nombre) < 3:
        return False

    if any(char.isdigit() for char in nombre):
        return False

    return bool(NOMBRE_PERSONA_RE.fullmatch(nombre))


def centro_costo_valido(centro_costo):
    centro_costo = str(centro_costo or "").strip()
    return bool(centro_costo) and centro_costo.isdigit() and len(centro_costo) <= 20


def normalizar_telefono_chile(telefono):
    if telefono is None:
        return ""

    if isinstance(telefono, Number):
        try:
            telefono = str(int(telefono)) if float(telefono).is_integer() else str(telefono)
        except (TypeError, ValueError, OverflowError):
            telefono = str(telefono)

    telefono = str(telefono or "").strip()
    if re.fullmatch(r"\d+\.0", telefono):
        telefono = telefono[:-2]

    telefono = re.sub(r"\D", "", telefono)

    if telefono.startswith("56") and len(telefono) >= 10:
        telefono = telefono[2:]

    if telefono.startswith("0") and len(telefono) in {9, 10}:
        telefono = telefono[1:]

    return telefono


def telefono_chile_valido(telefono):
    telefono = normalizar_telefono_chile(telefono)
    return len(telefono) in {8, 9}


CODIGOS_TELEFONO_PAIS = {"56", "54", "51", "57", "52", "1", "55", "598"}


def normalizar_codigo_pais_telefono(codigo_pais):
    codigo = re.sub(r"\D", "", str(codigo_pais or "56"))
    return codigo if codigo in CODIGOS_TELEFONO_PAIS else "56"


def normalizar_telefono_operativo(telefono, codigo_pais="56"):
    if telefono is None:
        return ""

    texto_original = str(telefono or "").strip()
    numero_original = re.sub(r"\D", "", texto_original)
    codigo = normalizar_codigo_pais_telefono(codigo_pais)

    if texto_original.startswith("+"):
        for candidato in sorted(CODIGOS_TELEFONO_PAIS, key=len, reverse=True):
            if numero_original.startswith(candidato):
                codigo = candidato
                break

    if codigo == "56":
        return normalizar_telefono_chile(telefono)

    numero = numero_original
    if numero.startswith(codigo):
        numero = numero[len(codigo):]
    if numero.startswith("0"):
        numero = numero[1:]

    return f"{codigo}{numero}"[:15]


def telefono_operativo_valido(telefono, codigo_pais="56"):
    texto_original = str(telefono or "").strip()
    numero_original = re.sub(r"\D", "", texto_original)
    codigo = normalizar_codigo_pais_telefono(codigo_pais)
    if texto_original.startswith("+"):
        for candidato in sorted(CODIGOS_TELEFONO_PAIS, key=len, reverse=True):
            if numero_original.startswith(candidato):
                codigo = candidato
                break

    telefono = normalizar_telefono_operativo(telefono, codigo)

    if codigo == "56":
        return len(telefono) in {8, 9}

    return telefono.isdigit() and 10 <= len(telefono) <= 15


def separar_telefono_operativo(telefono):
    telefono = re.sub(r"\D", "", str(telefono or ""))

    if len(telefono) in {8, 9}:
        return "56", telefono

    for codigo in sorted(CODIGOS_TELEFONO_PAIS - {"56"}, key=len, reverse=True):
        if telefono.startswith(codigo):
            return codigo, telefono[len(codigo):]

    return "56", telefono


def rut_operativo_valido(rut):
    rut = str(rut or "").strip()

    if rut == "0":
        return True

    return bool(rut)


def normalizar_rut_usuario(rut):
    rut = str(rut or "").strip().upper()
    rut = re.sub(r"[^0-9K]", "", rut)
    if not rut:
        return ""
    if len(rut) == 1:
        return rut
    return f"{rut[:-1]}-{rut[-1]}"


def clave_rut_usuario(rut):
    return re.sub(r"[^0-9K]", "", str(rut or "").upper())
