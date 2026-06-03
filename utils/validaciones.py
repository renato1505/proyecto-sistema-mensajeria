import re


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def email_valido(email):
    if not email:
        return False
    return bool(EMAIL_RE.match(str(email).strip()))


def normalizar_telefono_chile(telefono):
    return re.sub(r"\D", "", str(telefono or ""))


def telefono_chile_valido(telefono):
    telefono = normalizar_telefono_chile(telefono)
    return len(telefono) in {8, 9}


def rut_operativo_valido(rut):
    rut = str(rut or "").strip()

    if rut == "0":
        return True

    return bool(rut)
