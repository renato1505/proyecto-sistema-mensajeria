"""Auditoria read-only del esquema y datos previos a migraciones.

Usar idealmente una URL PostgreSQL con permisos exclusivamente SELECT sobre una
copia restaurada. El script no crea tablas ni importa ``main``.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect, text


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from config.settings import DATABASE_URL  # noqa: E402
from database.modelos import Base  # noqa: E402


def normalizar_url(url):
    if not url:
        raise ValueError("Falta DATABASE_URL o --database-url")
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def _tipo_normalizado(tipo, dialecto):
    return " ".join(str(tipo.compile(dialect=dialecto)).lower().split())


def _es_varchar(tipo):
    return re.fullmatch(r"(?:character varying|varchar)(?:\(\d+\))?", tipo) is not None


def _es_secuencia_pk_equivalente(columna, default_bd):
    """Reconoce el default que PostgreSQL crea para una PK autoincremental."""
    if not columna.primary_key or columna.server_default is not None or not default_bd:
        return False
    return re.fullmatch(r"nextval\('(?:[^']|'')+'::regclass\)", default_bd, re.IGNORECASE) is not None


def _defaults_equivalentes(columna, default_modelo, default_bd):
    if default_modelo == default_bd:
        return True
    if isinstance(columna.type, sa.Boolean):
        valores_false = {"false", "0", "'false'", "(false)", "(0)"}
        valores_true = {"true", "1", "'true'", "(true)", "(1)"}
        modelo = str(default_modelo).strip().lower() if default_modelo is not None else None
        real = str(default_bd).strip().lower() if default_bd is not None else None
        return (modelo in valores_false and real in valores_false) or (modelo in valores_true and real in valores_true)
    return False


def resumir_diferencias(diferencias):
    conteo = Counter(diferencia["nivel"] for diferencia in diferencias)
    return {
        "criticas": conteo["critico"],
        "relevantes": conteo["relevante"],
        "informativas": conteo["informativo"],
    }


def describir_esquema(engine):
    inspector = inspect(engine)
    resultado = {}
    for tabla in sorted(inspector.get_table_names()):
        resultado[tabla] = {
            "columnas": [
                {
                    "nombre": columna["name"],
                    "tipo": _tipo_normalizado(columna["type"], engine.dialect),
                    "nullable": columna["nullable"],
                    "default": str(columna.get("default")) if columna.get("default") is not None else None,
                }
                for columna in inspector.get_columns(tabla)
            ],
            "pk": inspector.get_pk_constraint(tabla),
            "fk": inspector.get_foreign_keys(tabla),
            "indices": inspector.get_indexes(tabla),
            "unique": inspector.get_unique_constraints(tabla),
        }
    return resultado


def comparar_metadata(engine, esquema):
    diferencias = []
    tablas_modelo = set(Base.metadata.tables)
    tablas_bd = set(esquema) - {"alembic_version"}

    for tabla in sorted(tablas_modelo - tablas_bd):
        diferencias.append({"nivel": "critico", "objeto": tabla, "detalle": "tabla ausente en BD"})
    for tabla in sorted(tablas_bd - tablas_modelo):
        diferencias.append({"nivel": "informativo", "objeto": tabla, "detalle": "tabla no representada en ORM"})

    for nombre in sorted(tablas_modelo & tablas_bd):
        tabla = Base.metadata.tables[nombre]
        columnas_bd = {item["nombre"]: item for item in esquema[nombre]["columnas"]}
        columnas_modelo = {columna.name: columna for columna in tabla.columns}

        for columna in sorted(columnas_modelo.keys() - columnas_bd.keys()):
            diferencias.append({"nivel": "critico", "objeto": f"{nombre}.{columna}", "detalle": "columna ausente en BD"})
        for columna in sorted(columnas_bd.keys() - columnas_modelo.keys()):
            diferencias.append({"nivel": "informativo", "objeto": f"{nombre}.{columna}", "detalle": "columna no representada en ORM"})

        for columna in sorted(columnas_modelo.keys() & columnas_bd.keys()):
            modelo = columnas_modelo[columna]
            real = columnas_bd[columna]
            tipo_modelo = _tipo_normalizado(modelo.type, engine.dialect)
            if tipo_modelo != real["tipo"]:
                nivel = "relevante" if _es_varchar(tipo_modelo) and _es_varchar(real["tipo"]) else "critico"
                diferencias.append({
                    "nivel": nivel,
                    "objeto": f"{nombre}.{columna}",
                    "detalle": f"tipo ORM={tipo_modelo}, BD={real['tipo']}",
                })
            if bool(modelo.nullable) != bool(real["nullable"]):
                diferencias.append({
                    "nivel": "critico",
                    "objeto": f"{nombre}.{columna}",
                    "detalle": f"nullable ORM={modelo.nullable}, BD={real['nullable']}",
                })
            default_modelo = str(modelo.server_default.arg) if modelo.server_default is not None else None
            default_bd = real["default"]
            if not _defaults_equivalentes(modelo, default_modelo, default_bd):
                if _es_secuencia_pk_equivalente(modelo, default_bd):
                    diferencias.append({
                        "nivel": "informativo",
                        "objeto": f"{nombre}.{columna}",
                        "detalle": "secuencia PK PostgreSQL equivalente al autoincrement ORM",
                    })
                else:
                    diferencias.append({
                        "nivel": "relevante",
                        "objeto": f"{nombre}.{columna}",
                        "detalle": f"server_default ORM={default_modelo}, BD={default_bd}",
                    })

        pk_modelo = {columna.name for columna in tabla.primary_key.columns}
        pk_bd = set(esquema[nombre]["pk"].get("constrained_columns") or [])
        if pk_modelo != pk_bd:
            diferencias.append({"nivel": "critico", "objeto": nombre, "detalle": f"PK ORM={sorted(pk_modelo)}, BD={sorted(pk_bd)}"})

        indices_modelo = {
            indice.name: {"columnas": [col.name for col in indice.columns], "unique": bool(indice.unique)}
            for indice in tabla.indexes
        }
        indices_bd = {
            indice["name"]: {"columnas": indice.get("column_names") or [], "unique": bool(indice.get("unique"))}
            for indice in esquema[nombre]["indices"]
        }
        for indice in sorted(indices_modelo.keys() - indices_bd.keys()):
            diferencias.append({"nivel": "relevante", "objeto": f"{nombre}.{indice}", "detalle": "indice ORM ausente en BD"})
        for indice in sorted(indices_bd.keys() - indices_modelo.keys()):
            diferencias.append({"nivel": "informativo", "objeto": f"{nombre}.{indice}", "detalle": "indice BD no representado en ORM"})
        for indice in sorted(indices_modelo.keys() & indices_bd.keys()):
            if indices_modelo[indice] != indices_bd[indice]:
                diferencias.append({"nivel": "relevante", "objeto": f"{nombre}.{indice}", "detalle": f"indice ORM={indices_modelo[indice]}, BD={indices_bd[indice]}"})

        fk_modelo = sorted(
            (fk.parent.name, fk.target_fullname)
            for columna in tabla.columns
            for fk in columna.foreign_keys
        )
        fk_bd = sorted(
            (columna, f"{fk['referred_table']}.{referida}")
            for fk in esquema[nombre]["fk"]
            for columna, referida in zip(fk.get("constrained_columns") or [], fk.get("referred_columns") or [])
        )
        if fk_modelo != fk_bd:
            diferencias.append({"nivel": "critico", "objeto": nombre, "detalle": f"FK ORM={fk_modelo}, BD={fk_bd}"})

        unique_modelo = sorted(
            sorted(columna.name for columna in constraint.columns)
            for constraint in tabla.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        )
        unique_bd = sorted(
            sorted(constraint.get("column_names") or [])
            for constraint in esquema[nombre]["unique"]
        )
        if unique_modelo != unique_bd:
            diferencias.append({"nivel": "critico", "objeto": nombre, "detalle": f"UNIQUE ORM={unique_modelo}, BD={unique_bd}"})

    return diferencias


def consultas_auditoria_envios(columnas):
    consultas = {
        "total_envios": "SELECT COUNT(*) FROM envios",
        "estados": "SELECT e_estado, COUNT(*) FROM envios GROUP BY e_estado ORDER BY e_estado",
        "of_null_no_null": "SELECT COUNT(*) FILTER (WHERE e_orden_flete IS NULL), COUNT(*) FILTER (WHERE e_orden_flete IS NOT NULL) FROM envios",
        "of_resumen": "SELECT COUNT(e_orden_flete), COUNT(DISTINCT e_orden_flete) FROM envios",
        "of_duplicadas": "SELECT MIN(id), COUNT(*) FROM envios WHERE e_orden_flete IS NOT NULL GROUP BY e_orden_flete HAVING COUNT(*) > 1 ORDER BY COUNT(*) DESC, MIN(id)",
        "anulados": "SELECT COUNT(*) FROM envios WHERE e_anulado IS TRUE",
        "bultos": "SELECT e_bultos, COUNT(*) FROM envios GROUP BY e_bultos ORDER BY e_bultos",
    }
    if "e_codigo_agencia" in columnas:
        consultas["codigo_agencia_distribucion"] = (
            "SELECT "
            "COUNT(*) FILTER (WHERE e_codigo_agencia IS NULL), "
            "COUNT(*) FILTER (WHERE e_codigo_agencia IS NOT NULL AND LENGTH(e_codigo_agencia) = 0), "
            "COUNT(*) FILTER (WHERE e_codigo_agencia IS NOT NULL AND LENGTH(e_codigo_agencia) > 0 AND LENGTH(TRIM(e_codigo_agencia)) = 0), "
            "COUNT(*) FILTER (WHERE e_codigo_agencia IS NOT NULL AND LENGTH(TRIM(e_codigo_agencia)) > 0) "
            "FROM envios"
        )
    for columna in sorted(columnas):
        consultas[f"nulos_{columna}"] = f"SELECT COUNT(*) FROM envios WHERE {columna} IS NULL"
    return consultas


def auditar_datos(connection, esquema):
    if "envios" not in esquema:
        return {"advertencia": "La tabla envios no existe"}
    columnas = {item["nombre"] for item in esquema["envios"]["columnas"]}
    resultado = {}
    for nombre, consulta in consultas_auditoria_envios(columnas).items():
        filas = connection.execute(text(consulta)).all()
        resultado[nombre] = [list(fila) for fila in filas]
    return resultado


def ejecutar_auditoria(database_url):
    engine = create_engine(normalizar_url(database_url), pool_pre_ping=True)
    try:
        esquema = describir_esquema(engine)
        with engine.connect() as connection:
            transaccion = connection.begin()
            try:
                if engine.dialect.name == "postgresql":
                    connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                datos = auditar_datos(connection, esquema)
            finally:
                transaccion.rollback()
        diferencias = comparar_metadata(engine, esquema)
        return {
            "dialecto": engine.dialect.name,
            "esquema": esquema,
            "diferencias_metadata": diferencias,
            "resumen_diferencias": resumir_diferencias(diferencias),
            "datos": datos,
        }
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Audita esquema y datos sin realizar escrituras")
    parser.add_argument("--database-url", default=os.getenv("AUDIT_DATABASE_URL") or DATABASE_URL)
    parser.add_argument("--json", action="store_true", help="Emite el informe como JSON")
    args = parser.parse_args()

    resultado = ejecutar_auditoria(args.database_url)
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
        return

    print(f"Dialecto: {resultado['dialecto']}")
    print(f"Tablas: {', '.join(sorted(resultado['esquema'])) or 'ninguna'}")
    diferencias = resultado["diferencias_metadata"]
    print(f"Diferencias metadata/BD: {len(diferencias)}")
    print(f"Clasificacion: {resultado['resumen_diferencias']}")
    for diferencia in diferencias:
        print(f"- [{diferencia['nivel']}] {diferencia['objeto']}: {diferencia['detalle']}")
    print("Datos relevantes:")
    print(json.dumps(resultado["datos"], ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
