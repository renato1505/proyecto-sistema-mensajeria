import os
import uuid

from werkzeug.utils import secure_filename


EXTENSIONES_EVIDENCIA = {".png", ".jpg", ".jpeg", ".webp"}
MAX_EVIDENCIA_BYTES = 6 * 1024 * 1024


def archivo_supera_limite(archivo, content_length=None):
    try:
        posicion = archivo.stream.tell()
        archivo.stream.seek(0, os.SEEK_END)
        tamano = archivo.stream.tell()
        archivo.stream.seek(posicion)
        return tamano > MAX_EVIDENCIA_BYTES
    except Exception:
        margen_multipart = 1024 * 1024
        return bool(content_length and content_length > MAX_EVIDENCIA_BYTES + margen_multipart)


def validar_archivo_evidencia(archivo, content_length=None):
    if not archivo or not archivo.filename:
        return "Debes seleccionar una imagen de evidencia."

    extension = os.path.splitext(archivo.filename)[1].lower()
    if extension not in EXTENSIONES_EVIDENCIA:
        return "La evidencia debe ser una imagen PNG, JPG, JPEG o WEBP."

    if archivo_supera_limite(archivo, content_length):
        return "La evidencia no puede superar 6 MB."

    return None


def guardar_archivo_evidencia(archivo, reporte_id, carpeta):
    extension = os.path.splitext(archivo.filename)[1].lower()
    os.makedirs(carpeta, exist_ok=True)
    nombre_base = secure_filename(archivo.filename) or f"evidencia{extension}"
    nombre_archivo = f"reporte_{reporte_id}_{uuid.uuid4().hex[:12]}_{nombre_base}"
    ruta_destino = os.path.join(carpeta, nombre_archivo)
    archivo.save(ruta_destino)
    return nombre_archivo
