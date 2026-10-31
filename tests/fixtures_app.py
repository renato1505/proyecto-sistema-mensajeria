"""Preparación explícita de la base global usada por pruebas de main.app."""
from tests.entorno_aislado import preparar_entorno_pruebas, validar_destino_pruebas


def preparar_base_app():
    raiz = preparar_entorno_pruebas()
    from database.conexion import engine
    from database.modelos import Base, PuntoRetiro
    from sqlalchemy.orm import Session

    validar_destino_pruebas(engine.url, raiz)
    # Es preparación de fixture, no parte del arranque operativo. S2B conservará
    # este paso aun cuando main deje de crear tablas y normalizar registros.
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for codigo, local in (("MENSAJERIA_LOCAL", True), ("ACADEMIA", False)):
            if not db.query(PuntoRetiro).filter_by(pr_codigo=codigo).first():
                db.add(PuntoRetiro(
                    pr_codigo=codigo, pr_nombre=codigo, pr_es_local=local,
                    pr_incluir_metricas_locales=local, pr_activo=True,
                ))
        db.commit()
    return engine


def obtener_app_aislada():
    preparar_base_app()
    from main import app
    return app
