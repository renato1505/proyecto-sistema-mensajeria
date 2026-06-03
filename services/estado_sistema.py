from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from config.settings import LOGS_DIR, RESPALDOS_LOTES_DIR
from database.conexion import SessionLocal
from database.modelos import Comuna, Destinatario, Envio, Remitente
from services.correo import correo_starken_configurado, obtener_correo_destino_starken


def _resolver_carpeta(ruta):
    carpeta = Path(ruta)
    if not carpeta.is_absolute():
        carpeta = Path(__file__).resolve().parent.parent / carpeta
    return carpeta


def _estado_carpeta(ruta):
    carpeta = _resolver_carpeta(ruta)

    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        prueba = carpeta / ".write_test"
        prueba.write_text("ok", encoding="utf-8")
        prueba.unlink(missing_ok=True)
        return {
            "ok": True,
            "ruta": str(carpeta),
            "detalle": "Disponible para escritura",
        }
    except Exception as exc:
        return {
            "ok": False,
            "ruta": str(carpeta),
            "detalle": f"No disponible: {exc}",
        }


def _ultimo_log():
    carpeta_logs = _resolver_carpeta(LOGS_DIR)
    archivo_log = carpeta_logs / "sistema_mensajeria.log"

    if not archivo_log.exists():
        return {
            "existe": False,
            "ruta": str(archivo_log),
            "ultima_linea": "Sin log registrado todavia",
            "fecha_modificacion": None,
        }

    try:
        lineas = archivo_log.read_text(encoding="utf-8", errors="replace").splitlines()
        ultima_linea = lineas[-1] if lineas else "Log vacio"
        fecha_modificacion = datetime.fromtimestamp(archivo_log.stat().st_mtime)
        return {
            "existe": True,
            "ruta": str(archivo_log),
            "ultima_linea": ultima_linea,
            "fecha_modificacion": fecha_modificacion,
        }
    except Exception as exc:
        return {
            "existe": False,
            "ruta": str(archivo_log),
            "ultima_linea": f"No se pudo leer el log: {exc}",
            "fecha_modificacion": None,
        }


def _conteos_db(db):
    pendientes = db.query(Envio).filter(Envio.e_estado == "pendiente").count()
    en_proceso = db.query(Envio).filter(Envio.e_estado == "en_proceso").count()
    historico = db.query(Envio).filter(Envio.e_estado == "historico").count()

    ultimo_lote = (
        db.query(Envio)
        .filter(Envio.e_lote.isnot(None))
        .order_by(Envio.e_fecha_exportacion.desc().nullslast(), Envio.id.desc())
        .first()
    )

    ultimo_envio = db.query(Envio).order_by(Envio.e_fecha_creacion.desc()).first()

    return {
        "envios_total": pendientes + en_proceso + historico,
        "pendientes": pendientes,
        "en_proceso": en_proceso,
        "historico": historico,
        "remitentes": db.query(Remitente).count(),
        "destinatarios": db.query(Destinatario).count(),
        "comunas": db.query(Comuna).count(),
        "ultimo_lote": ultimo_lote.e_lote if ultimo_lote else "Sin lotes registrados",
        "ultimo_lote_fecha": ultimo_lote.e_fecha_exportacion if ultimo_lote else None,
        "ultimo_envio_fecha": ultimo_envio.e_fecha_creacion if ultimo_envio else None,
    }


def obtener_estado_sistema():
    estado = {
        "fecha_revision": datetime.now(),
        "db": {
            "ok": False,
            "detalle": "No revisada",
        },
        "correo": {
            "ok": correo_starken_configurado(),
            "destino": obtener_correo_destino_starken() or "No configurado",
            "detalle": "Configurado" if correo_starken_configurado() else "Faltan datos en .env",
        },
        "respaldos_lotes": _estado_carpeta(RESPALDOS_LOTES_DIR),
        "logs": _estado_carpeta(LOGS_DIR),
        "ultimo_log": _ultimo_log(),
        "conteos": {},
    }

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        estado["db"] = {
            "ok": True,
            "detalle": "Conexion activa",
        }
        estado["conteos"] = _conteos_db(db)
    except Exception as exc:
        estado["db"] = {
            "ok": False,
            "detalle": f"No se pudo conectar: {exc}",
        }
    finally:
        db.close()

    estado["general_ok"] = all([
        estado["db"]["ok"],
        estado["correo"]["ok"],
        estado["respaldos_lotes"]["ok"],
        estado["logs"]["ok"],
    ])

    return estado
