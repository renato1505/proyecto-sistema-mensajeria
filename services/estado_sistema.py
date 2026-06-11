from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from config.settings import EMAIL_PROVIDER, LOGS_DIR, RESPALDOS_LOTES_DIR
from database.conexion import SessionLocal
from database.modelos import Comuna, Destinatario, Envio, Remitente
from services.correo import correo_starken_configurado, obtener_correo_destino_starken
from services.historico import (
    correo_respaldo_historico_configurado,
    destinatarios_respaldo_historico,
)


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


def _estado_almacenamiento_temporal():
    respaldos_lotes = _estado_carpeta(RESPALDOS_LOTES_DIR)
    logs = _estado_carpeta(LOGS_DIR)
    disponible = respaldos_lotes["ok"] and logs["ok"]

    return {
        "ok": disponible,
        "detalle": (
            "Disponible solo como almacenamiento temporal de la instancia."
            if disponible
            else "Una o mas carpetas temporales no estan disponibles."
        ),
        "rutas": [
            f"Lotes: {respaldos_lotes['ruta']}",
            f"Logs: {logs['ruta']}",
        ],
        "nota": "En cloud, la informacion critica debe quedar en base de datos o correo.",
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


def _estado_operativo(db):
    limite_lote_antiguo = datetime.now() - timedelta(days=2)
    lotes_en_proceso = (
        db.query(Envio.e_lote)
        .filter(Envio.e_estado == "en_proceso", Envio.e_lote.isnot(None))
        .distinct()
        .count()
    )
    lotes_antiguos = (
        db.query(Envio.e_lote)
        .filter(
            Envio.e_estado == "en_proceso",
            Envio.e_lote.isnot(None),
            Envio.e_fecha_exportacion.isnot(None),
            Envio.e_fecha_exportacion < limite_lote_antiguo,
        )
        .distinct()
        .count()
    )
    avisos_pendientes = (
        db.query(Envio.e_lote)
        .filter(
            Envio.e_estado == "historico",
            Envio.e_lote.isnot(None),
            Envio.e_aviso_funcionario_estado == "pendiente",
        )
        .distinct()
        .count()
    )
    correos_error = (
        db.query(Envio.e_lote)
        .filter(Envio.e_estado_correo == "error", Envio.e_lote.isnot(None))
        .distinct()
        .count()
    )

    return {
        "lotes_en_proceso": lotes_en_proceso,
        "lotes_antiguos": lotes_antiguos,
        "avisos_pendientes": avisos_pendientes,
        "correos_error": correos_error,
        "ok": lotes_antiguos == 0 and correos_error == 0,
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
            "proveedor": EMAIL_PROVIDER,
            "destino": obtener_correo_destino_starken() or "No configurado",
            "detalle": "Configurado" if correo_starken_configurado() else "Faltan datos en .env",
        },
        "respaldo_historico": {
            "ok": correo_respaldo_historico_configurado(),
            "destinos": destinatarios_respaldo_historico(),
            "detalle": (
                "El respaldo de historico eliminado se envia por correo."
                if correo_respaldo_historico_configurado()
                else "Faltan credenciales o destinatarios para respaldo historico."
            ),
        },
        "almacenamiento_temporal": _estado_almacenamiento_temporal(),
        "ultimo_log": _ultimo_log(),
        "conteos": {},
        "operacion": {},
    }

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        estado["db"] = {
            "ok": True,
            "detalle": "Conexion activa",
        }
        estado["conteos"] = _conteos_db(db)
        estado["operacion"] = _estado_operativo(db)
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
        estado["respaldo_historico"]["ok"],
    ])

    return estado
