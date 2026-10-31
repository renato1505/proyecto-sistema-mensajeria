"""Preparación explícita de SQLite en memoria para la fábrica Flask."""
from tests.entorno_aislado import preparar_entorno_pruebas, validar_destino_pruebas


_APP = None


def preparar_base_app():
    raiz = preparar_entorno_pruebas()
    from database.conexion import engine
    from database.modelos import Base, PuntoRetiro
    from sqlalchemy.orm import Session

    validar_destino_pruebas(engine.url, raiz)
    # El fixture prepara tablas y referencias; la fábrica valida sin repararlas.
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
    global _APP
    preparar_base_app()
    if _APP is None:
        from aplicacion import crear_app
        from database.validacion_esquema import contrato_fixture_sqlite
        _APP = crear_app(contrato=contrato_fixture_sqlite())
    return _APP
