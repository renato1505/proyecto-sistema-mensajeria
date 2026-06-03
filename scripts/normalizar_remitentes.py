import os
import sys
import unicodedata

# Agregar la raíz del proyecto al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.conexion import SessionLocal
from database.modelos import Remitente


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


def quitar_tildes(texto):
    if not texto:
        return ""
    texto = str(texto).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    return texto


def normalizar_nombre(nombre):
    if not nombre:
        return ""

    nombre = quitar_tildes(nombre)
    nombre = " ".join(nombre.replace(",", " ").split())
    partes = [p.capitalize() for p in nombre.split()]
    return " ".join(partes)


def normalizar_correo(correo):
    if not correo:
        return ""
    return str(correo).strip().lower()


def normalizar_division(division):
    if not division:
        return ""
    return DIVISIONES_SIGLAS.get(str(division).strip(), str(division).strip())


def ejecutar():
    db = SessionLocal()
    remitentes = db.query(Remitente).all()

    for remitente in remitentes:
        remitente.r_nombre = normalizar_nombre(remitente.r_nombre)
        remitente.r_correo = normalizar_correo(remitente.r_correo)
        remitente.r_division = normalizar_division(remitente.r_division)

    db.commit()
    db.close()

    print("Remitentes normalizados correctamente.")


if __name__ == "__main__":
    ejecutar()