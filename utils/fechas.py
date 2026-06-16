from datetime import datetime
from zoneinfo import ZoneInfo


ZONA_CHILE = ZoneInfo("America/Santiago")


def ahora_chile():
    """Devuelve la fecha/hora actual de Chile como datetime naive para la base actual."""
    return datetime.now(ZONA_CHILE).replace(tzinfo=None)


def timestamp_archivo_chile():
    return ahora_chile().strftime("%Y-%m-%d_%H-%M-%S")


def fecha_hora_chile_texto():
    return ahora_chile().strftime("%d/%m/%Y %H:%M")


def desde_timestamp_chile(timestamp):
    return datetime.fromtimestamp(timestamp, ZONA_CHILE).replace(tzinfo=None)


def a_hora_chile(fecha):
    if not fecha:
        return None
    if fecha.tzinfo is None:
        return fecha
    return fecha.astimezone(ZONA_CHILE).replace(tzinfo=None)
