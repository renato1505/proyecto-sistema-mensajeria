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


def rut_operativo_valido(rut):
    rut = str(rut or "").strip()

    if rut == "0":
        return True

    return bool(rut)
