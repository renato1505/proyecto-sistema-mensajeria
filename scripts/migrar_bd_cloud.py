import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine, delete, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from config.settings import DATABASE_URL  # noqa: E402
from database.modelos import Base, Comuna, Destinatario, Envio, Remitente  # noqa: E402
from utils.fechas import ahora_chile  # noqa: E402


MODELOS = (Comuna, Remitente, Destinatario, Envio)
RESPALDO_DIR = PROJECT_DIR / "respaldos_migracion"


def normalizar_url(url):
    if not url:
        return ""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def ocultar_url(url):
    try:
        parsed = make_url(normalizar_url(url))
        return parsed.render_as_string(hide_password=True)
    except Exception:
        return "URL configurada"


def serializar_valor(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return valor


def fila_a_dict(objeto):
    return {
        columna.name: serializar_valor(getattr(objeto, columna.name))
        for columna in objeto.__table__.columns
    }


def contar_registros(session):
    return {
        modelo.__tablename__: len(session.execute(select(modelo.id)).scalars().all())
        for modelo in MODELOS
    }


def respaldar_origen(session):
    RESPALDO_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = ahora_chile().strftime("%Y%m%d_%H%M%S")
    ruta = RESPALDO_DIR / f"backup_local_{timestamp}.json"

    respaldo = {}
    for modelo in MODELOS:
        filas = session.execute(select(modelo).order_by(modelo.id)).scalars().all()
        respaldo[modelo.__tablename__] = [fila_a_dict(fila) for fila in filas]

    ruta.write_text(
        json.dumps(respaldo, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return ruta


def clonar_tablas(origen_session, destino_session):
    for modelo in MODELOS:
        filas = origen_session.execute(select(modelo).order_by(modelo.id)).scalars().all()
        destino_session.bulk_insert_mappings(
            modelo,
            [fila_a_dict(fila) for fila in filas],
        )


def resetear_secuencias(destino_engine):
    with destino_engine.begin() as conexion:
        for modelo in MODELOS:
            tabla = modelo.__tablename__
            conexion.exec_driver_sql(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{tabla}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {tabla}), 1),
                    (SELECT COUNT(*) FROM {tabla}) > 0
                )
                """
            )


def limpiar_destino(destino_session):
    for modelo in reversed(MODELOS):
        destino_session.execute(delete(modelo))


def validar_tablas(engine):
    inspector = inspect(engine)
    faltantes = [
        modelo.__tablename__
        for modelo in MODELOS
        if not inspector.has_table(modelo.__tablename__)
    ]
    return faltantes


def main():
    parser = argparse.ArgumentParser(
        description="Migra datos desde la base local a una base cloud PostgreSQL."
    )
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Ejecuta la migracion. Sin esto, solo muestra diagnostico.",
    )
    parser.add_argument(
        "--reemplazar-destino",
        action="store_true",
        help="Borra datos existentes en cloud antes de migrar.",
    )
    args = parser.parse_args()

    origen_url = normalizar_url(DATABASE_URL)
    destino_url = normalizar_url(os.getenv("CLOUD_DATABASE_URL", ""))

    if not origen_url:
        raise SystemExit("Falta DATABASE_URL local.")
    if not destino_url:
        raise SystemExit("Falta CLOUD_DATABASE_URL. Agregala al .env local.")
    if origen_url == destino_url:
        raise SystemExit("DATABASE_URL y CLOUD_DATABASE_URL apuntan al mismo destino.")

    origen_engine = create_engine(origen_url, pool_pre_ping=True)
    destino_engine = create_engine(destino_url, pool_pre_ping=True)

    Base.metadata.create_all(bind=destino_engine)

    OrigenSession = sessionmaker(bind=origen_engine)
    DestinoSession = sessionmaker(bind=destino_engine)

    with OrigenSession() as origen_session, DestinoSession() as destino_session:
        faltantes = validar_tablas(destino_engine)
        if faltantes:
            raise SystemExit(f"Faltan tablas en destino: {', '.join(faltantes)}")

        conteo_origen = contar_registros(origen_session)
        conteo_destino = contar_registros(destino_session)

        print("Origen:", ocultar_url(origen_url))
        print("Destino:", ocultar_url(destino_url))
        print("Registros origen:", conteo_origen)
        print("Registros destino:", conteo_destino)

        if not args.confirmar:
            print("Diagnostico listo. Ejecuta con --confirmar para migrar.")
            return

        destino_tiene_datos = any(cantidad > 0 for cantidad in conteo_destino.values())
        if destino_tiene_datos and not args.reemplazar_destino:
            raise SystemExit(
                "El destino ya tiene datos. Usa --reemplazar-destino si quieres sobrescribir."
            )

        ruta_respaldo = respaldar_origen(origen_session)
        print(f"Respaldo local creado: {ruta_respaldo}")

        if args.reemplazar_destino:
            limpiar_destino(destino_session)

        clonar_tablas(origen_session, destino_session)
        destino_session.commit()
        resetear_secuencias(destino_engine)

        conteo_final = contar_registros(destino_session)
        print("Migracion finalizada:", conteo_final)


if __name__ == "__main__":
    main()
