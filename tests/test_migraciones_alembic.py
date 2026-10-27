import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.modelos import Base
from scripts.auditar_esquema import (
    _es_secuencia_pk_equivalente,
    consultas_auditoria_envios,
    ejecutar_auditoria,
)


PROJECT_DIR = Path(__file__).resolve().parent.parent
BASELINE = PROJECT_DIR / "migrations" / "versions" / "20260826_01_baseline_esquema_actual.py"


class AlembicBaselineTest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temporal.name) / "baseline.sqlite3"
        self.database_url = f"sqlite:///{self.db_path.as_posix()}"
        self.env = os.environ.copy()
        self.env.update({
            "DATABASE_URL": self.database_url,
            "APP_ENV": "test",
            "RENDER": "false",
        })

    def tearDown(self):
        self.temporal.cleanup()

    def _alembic(self, *argumentos):
        comando = [
            sys.executable,
            "-c",
            "from alembic.config import main; main()",
            *argumentos,
        ]
        return subprocess.run(
            comando,
            cwd=PROJECT_DIR,
            env=self.env,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_upgrade_head_crea_esquema_actual_desde_base_vacia(self):
        self._alembic("upgrade", "head")
        engine = create_engine(self.database_url)
        try:
            tablas = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()

        self.assertEqual(tablas, set(Base.metadata.tables) | {"alembic_version"})
        self.assertIn("puntos_retiro", tablas)
        self.assertIn("retiros_starken", tablas)
        self.assertIn("retiro_envios", tablas)
        self.assertIn("avisos_envio", tablas)

    def test_current_history_y_auditoria_coinciden_con_metadata(self):
        self._alembic("upgrade", "head")
        current = self._alembic("current").stdout
        history = self._alembic("history").stdout
        auditoria = ejecutar_auditoria(self.database_url)

        self.assertIn("20261025_06", current)
        self.assertIn("20260826_01", history)
        self.assertIn("20260828_02", history)
        self.assertIn("20260828_03", history)
        self.assertIn("20260829_04", history)
        self.assertIn("20260829_05", history)
        self.assertIn("20261025_06", history)
        self.assertEqual(auditoria["diferencias_metadata"], [])
        self.assertEqual(auditoria["resumen_diferencias"], {"criticas": 0, "relevantes": 0, "informativas": 0})
        self.assertEqual(auditoria["datos"]["total_envios"], [[0]])

    def test_reconciliacion_agrega_indice_solo_despues_del_baseline(self):
        self._alembic("upgrade", "20260826_01")
        engine = create_engine(self.database_url)
        try:
            indices_baseline = {item["name"] for item in inspect(engine).get_indexes("envios")}
        finally:
            engine.dispose()
        self.assertNotIn("ix_envios_e_anulado", indices_baseline)

        self._alembic("upgrade", "head")
        engine = create_engine(self.database_url)
        try:
            indices_head = {item["name"] for item in inspect(engine).get_indexes("envios")}
        finally:
            engine.dispose()
        self.assertIn("ix_envios_e_anulado", indices_head)

    def test_migracion_funcional_preserva_historico_y_crea_puntos(self):
        self._alembic("upgrade", "20260828_02")
        engine = create_engine(self.database_url)
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO envios ("
                    "e_remitente, e_destinatario, e_direccion, e_comuna, "
                    "e_tipo_envio, e_bultos, e_kilos, e_estado, e_orden_flete, e_anulado"
                    ") VALUES ("
                    "'Historico', 'Destino', 'Direccion', 'Comuna', "
                    "'Domicilio', 1, 1, 'historico', 'OF-LEGACY', 0"
                    ")"
                ))
        finally:
            engine.dispose()

        self._alembic("upgrade", "head")
        engine = create_engine(self.database_url)
        try:
            inspector = inspect(engine)
            columnas = {item["name"] for item in inspector.get_columns("envios")}
            with engine.connect() as connection:
                puntos = connection.execute(text(
                    "SELECT pr_codigo, pr_es_local, pr_incluir_metricas_locales, pr_activo "
                    "FROM puntos_retiro ORDER BY pr_codigo"
                )).all()
                historico = connection.execute(text(
                    "SELECT e_fecha_of, e_punto_retiro_id FROM envios WHERE e_orden_flete = 'OF-LEGACY'"
                )).one()
        finally:
            engine.dispose()

        self.assertIn("e_fecha_of", columnas)
        self.assertIn("e_punto_retiro_id", columnas)
        self.assertEqual(puntos, [
            ("ACADEMIA", False, False, True),
            ("MENSAJERIA_LOCAL", True, True, True),
        ])
        self.assertEqual(historico, (None, None))

    def test_migracion_retiro_desde_03_preserva_envios_y_crea_integridad(self):
        self._alembic("upgrade", "20260828_03")
        engine = create_engine(self.database_url)
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO envios ("
                    "e_remitente, e_destinatario, e_direccion, e_comuna, "
                    "e_tipo_envio, e_bultos, e_kilos, e_estado, e_orden_flete, e_anulado"
                    ") VALUES ("
                    "'Historico retiro', 'Destino', 'Direccion', 'Comuna', "
                    "'Domicilio', 3, 3, 'historico', 'OF-RETIRO-LEGACY', 0"
                    ")"
                ))
        finally:
            engine.dispose()

        self._alembic("upgrade", "head")
        engine = create_engine(self.database_url)
        try:
            inspector = inspect(engine)
            tablas = set(inspector.get_table_names())
            fk_retiros = inspector.get_foreign_keys("retiros_starken")
            fk_asociaciones = inspector.get_foreign_keys("retiro_envios")
            checks = inspector.get_check_constraints("retiro_envios")
            indices = {item["name"]: item for item in inspector.get_indexes("retiro_envios")}
            columnas_retiro = {item["name"]: item for item in inspector.get_columns("retiros_starken")}
            columnas_asociacion = {item["name"]: item for item in inspector.get_columns("retiro_envios")}
            with engine.connect() as connection:
                conteos = connection.execute(text(
                    "SELECT (SELECT COUNT(*) FROM retiros_starken), "
                    "(SELECT COUNT(*) FROM retiro_envios)"
                )).one()
                historico = connection.execute(text(
                    "SELECT e_estado, e_bultos FROM envios WHERE e_orden_flete = 'OF-RETIRO-LEGACY'"
                )).one()
        finally:
            engine.dispose()

        self.assertIn("retiros_starken", tablas)
        self.assertIn("retiro_envios", tablas)
        self.assertEqual(conteos, (0, 0))
        self.assertEqual(historico, ("historico", 3))
        self.assertEqual(fk_retiros[0]["referred_table"], "puntos_retiro")
        self.assertEqual(fk_retiros[0]["options"].get("ondelete"), "RESTRICT")
        self.assertEqual(
            {(fk["constrained_columns"][0], fk["referred_table"], fk["options"].get("ondelete")) for fk in fk_asociaciones},
            {("retiro_id", "retiros_starken", "RESTRICT"), ("envio_id", "envios", "RESTRICT")},
        )
        self.assertTrue(any("re_bultos_snapshot >= 1" in item["sqltext"] for item in checks))
        self.assertTrue(indices["uq_retiro_envios_envio_vigente"]["unique"])
        self.assertEqual(str(columnas_retiro["rs_anulado"]["default"]), "0")
        self.assertEqual(str(columnas_asociacion["re_vigente"]["default"]), "1")

    def test_downgrade_retiro_vuelve_a_03_sin_tocar_envios(self):
        self._alembic("upgrade", "head")
        engine = create_engine(self.database_url)
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO envios ("
                    "e_remitente, e_destinatario, e_direccion, e_comuna, "
                    "e_tipo_envio, e_bultos, e_kilos, e_estado, e_anulado"
                    ") VALUES ('Persistente', 'Destino', 'Direccion', 'Comuna', "
                    "'Domicilio', 1, 1, 'historico', 0)"
                ))
        finally:
            engine.dispose()

        self._alembic("downgrade", "20260828_03")
        engine = create_engine(self.database_url)
        try:
            tablas = set(inspect(engine).get_table_names())
            with engine.connect() as connection:
                total = connection.execute(text("SELECT COUNT(*) FROM envios")).scalar_one()
        finally:
            engine.dispose()
        self.assertNotIn("retiros_starken", tablas)
        self.assertNotIn("retiro_envios", tablas)
        self.assertEqual(total, 1)

    def test_migracion_avisos_desde_04_es_aditiva_y_crea_integridad(self):
        self._alembic("upgrade", "20260829_04")
        engine = create_engine(self.database_url)
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO envios ("
                    "e_remitente, e_destinatario, e_direccion, e_comuna, "
                    "e_tipo_envio, e_bultos, e_kilos, e_estado, e_estado_correo, "
                    "e_aviso_funcionario_estado, e_anulado"
                    ") VALUES ("
                    "'Legacy avisos', 'Destino', 'Direccion', 'Comuna', "
                    "'Domicilio', 1, 1, 'historico', 'enviado', 'pendiente', 0"
                    ")"
                ))
        finally:
            engine.dispose()

        self._alembic("upgrade", "head")
        engine = create_engine(self.database_url)
        try:
            inspector = inspect(engine)
            fk = inspector.get_foreign_keys("avisos_envio")
            checks = {item["name"]: item["sqltext"] for item in inspector.get_check_constraints("avisos_envio")}
            uniques = {
                item["name"]: tuple(item["column_names"])
                for item in inspector.get_unique_constraints("avisos_envio")
            }
            indices = {item["name"] for item in inspector.get_indexes("avisos_envio")}
            with engine.connect() as connection:
                conteos = connection.execute(text(
                    "SELECT (SELECT COUNT(*) FROM envios), "
                    "(SELECT COUNT(*) FROM avisos_envio)"
                )).one()
                legacy = connection.execute(text(
                    "SELECT e_estado_correo, e_aviso_funcionario_estado FROM envios"
                )).one()
        finally:
            engine.dispose()

        self.assertEqual(conteos, (1, 0))
        self.assertEqual(legacy, ("enviado", "pendiente"))
        self.assertEqual(fk[0]["referred_table"], "envios")
        self.assertEqual(fk[0]["options"].get("ondelete"), "RESTRICT")
        self.assertIn("ck_avisos_envio_tipo_valido", checks)
        self.assertIn("ck_avisos_envio_estado_valido", checks)
        self.assertIn("ck_avisos_envio_intentos_no_negativo", checks)
        self.assertEqual(uniques["uq_avisos_envio_envio_tipo"], ("envio_id", "av_tipo"))
        self.assertEqual(uniques["uq_avisos_envio_clave_idempotencia"], ("av_clave_idempotencia",))
        self.assertEqual(indices, {
            "ix_avisos_envio_envio_id",
            "ix_avisos_envio_av_estado",
            "ix_avisos_envio_av_tipo",
            "ix_avisos_envio_av_fecha_creacion",
        })

    def test_downgrade_avisos_vuelve_a_04_sin_tocar_envios(self):
        self._alembic("upgrade", "head")
        engine = create_engine(self.database_url)
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO envios ("
                    "e_remitente, e_destinatario, e_direccion, e_comuna, "
                    "e_tipo_envio, e_bultos, e_kilos, e_estado, e_anulado"
                    ") VALUES ('Persistente avisos', 'Destino', 'Direccion', 'Comuna', "
                    "'Domicilio', 1, 1, 'historico', 0)"
                ))
        finally:
            engine.dispose()

        self._alembic("downgrade", "20260829_04")
        engine = create_engine(self.database_url)
        try:
            tablas = set(inspect(engine).get_table_names())
            with engine.connect() as connection:
                total = connection.execute(text("SELECT COUNT(*) FROM envios")).scalar_one()
        finally:
            engine.dispose()
        self.assertNotIn("avisos_envio", tablas)
        self.assertIn("retiros_starken", tablas)
        self.assertEqual(total, 1)

    def test_migracion_of_desde_05_preserva_datos_y_no_hace_backfill(self):
        self._alembic("upgrade", "20260829_05")
        engine = create_engine(self.database_url)
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO envios (e_remitente, e_destinatario, e_direccion, e_comuna, "
                    "e_tipo_envio, e_bultos, e_kilos, e_estado, e_lote, e_fila_excel, "
                    "e_resultado_of, e_detalle_of, e_anulado) VALUES "
                    "('Ficticio', 'Destino demo', 'Direccion demo', 'Comuna demo', 'Domicilio', "
                    "1, 1, 'en_proceso', 'LOTE-DEMO', 2, 'ERROR', 'servicio H2H', 0)"
                ))
                antes = connection.execute(text("SELECT * FROM envios")).all()
        finally:
            engine.dispose()
        self._alembic("upgrade", "head")
        engine = create_engine(self.database_url)
        try:
            inspector = inspect(engine)
            with engine.connect() as connection:
                despues = connection.execute(text("SELECT * FROM envios")).all()
                for tabla in ("intentos_of", "registros_of", "conciliaciones_h2h", "movimientos_envio"):
                    self.assertIn(tabla, inspector.get_table_names())
                    self.assertEqual(connection.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar_one(), 0)
            self.assertEqual(antes, despues)
            fk = inspector.get_foreign_keys("registros_of")
            self.assertTrue(any(
                item["constrained_columns"] == ["intento_id", "envio_id", "ro_transportista"]
                and item["options"].get("ondelete") == "RESTRICT" for item in fk
            ))
            indice = {item["name"]: item for item in inspector.get_indexes("intentos_of")}
            self.assertTrue(indice["uq_intentos_of_envio_abierto"]["unique"])
            uniques = {item["name"] for item in inspector.get_unique_constraints("registros_of")}
            self.assertIn("uq_registros_of_transporte_numero", uniques)
        finally:
            engine.dispose()

    def test_esquema_of_migrado_rechaza_duplicados_y_relaciones_incorrectas(self):
        from datetime import datetime
        from sqlalchemy.orm import sessionmaker
        from database.modelos import ConciliacionH2H, Envio, IntentoOF, MovimientoEnvio, RegistroOF
        from sqlalchemy.exc import IntegrityError

        self._alembic("upgrade", "head")
        engine = create_engine(self.database_url)
        try:
            with engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
                with sessionmaker(bind=connection)() as db:
                    envio = Envio(e_remitente="Demo", e_destinatario="Demo", e_direccion="Demo",
                                  e_comuna="Demo", e_tipo_envio="Domicilio", e_bultos=1, e_kilos=1)
                    db.add(envio)
                    db.flush()
                    intento = IntentoOF(envio_id=envio.id, io_secuencia=1, io_transportista="STARKEN")
                    db.add(intento)
                    db.flush()
                    caso = ConciliacionH2H(intento_id=intento.id, envio_id=envio.id,
                                          ch_resultado_original="ERROR", ch_detalle_original="servicio H2H")
                    registro = RegistroOF(intento_id=intento.id, envio_id=envio.id, ro_transportista="STARKEN",
                                          ro_numero="000012345678901234567890", ro_origen="DEMO")
                    db.add_all([caso, registro, MovimientoEnvio(envio_id=envio.id, intento_id=intento.id,
                                                             me_tipo="DEMO", me_actor="demo", me_detalle={"original": True})])
                    db.commit()
                    self.assertEqual(registro.ro_numero, "000012345678901234567890")
                    envio_id, intento_id = envio.id, intento.id
                    with self.assertRaises(IntegrityError):
                        db.add(IntentoOF(envio_id=envio_id, io_secuencia=1, io_transportista="STARKEN", io_estado="CANCELADO"))
                        db.commit()
                    db.rollback()
                    with self.assertRaises(IntegrityError):
                        db.add(MovimientoEnvio(envio_id=99999, intento_id=intento_id, me_tipo="DEMO", me_actor="demo"))
                        db.commit()
                    db.rollback()
                    with self.assertRaises(IntegrityError):
                        db.execute(text("UPDATE conciliaciones_h2h SET ch_estado='OF_INEXISTENTE'"))
                        db.commit()
                    db.rollback()
        finally:
            engine.dispose()

    def test_downgrade_of_a_05_conserva_envios(self):
        self._alembic("upgrade", "head")
        engine = create_engine(self.database_url)
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO envios (e_remitente, e_destinatario, e_direccion, e_comuna, "
                    "e_tipo_envio, e_bultos, e_kilos, e_estado, e_anulado) "
                    "VALUES ('Demo', 'Demo', 'Demo', 'Demo', 'Domicilio', 1, 1, 'pendiente', 0)"
                ))
                antes = connection.execute(text("SELECT * FROM envios")).all()
        finally:
            engine.dispose()
        self._alembic("downgrade", "20260829_05")
        engine = create_engine(self.database_url)
        try:
            tablas = set(inspect(engine).get_table_names())
            self.assertTrue({"intentos_of", "registros_of", "conciliaciones_h2h", "movimientos_envio"}.isdisjoint(tablas))
            self.assertIn("avisos_envio", tablas)
            with engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT * FROM envios")).all(), antes)
        finally:
            engine.dispose()

    def test_guardas_orm_conservan_evidencia_en_esquema_creado_por_alembic(self):
        from sqlalchemy.orm import Session
        from database.modelos import ConciliacionH2H, Envio, IntentoOF, RegistroOF

        self._alembic("upgrade", "head")
        engine = create_engine(self.database_url)
        try:
            with engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
                with Session(bind=connection) as db:
                    envio = Envio(e_remitente="Demo", e_destinatario="Demo", e_direccion="Demo",
                                  e_comuna="Demo", e_tipo_envio="Domicilio", e_bultos=1, e_kilos=1)
                    db.add(envio)
                    db.flush()
                    intento = IntentoOF(envio_id=envio.id, io_secuencia=1, io_transportista="STARKEN",
                                        io_lote="LOTE-DEMO", io_estado="CON_OF")
                    db.add(intento)
                    db.flush()
                    registro = RegistroOF(intento_id=intento.id, envio_id=envio.id,
                                          ro_transportista="STARKEN", ro_numero="000123", ro_origen="DEMO")
                    caso = ConciliacionH2H(intento_id=intento.id, envio_id=envio.id,
                                          ch_resultado_original="ERROR", ch_detalle_original="servicio H2H")
                    db.add_all([registro, caso])
                    db.commit()

                    def snapshot():
                        with db.no_autoflush:
                            return {
                                modelo.__tablename__: [dict(fila) for fila in db.execute(
                                    modelo.__table__.select().order_by(modelo.id)
                                ).mappings()]
                                for modelo in (Envio, IntentoOF, RegistroOF, ConciliacionH2H)
                            }

                    antes = snapshot()
                    for objeto, campo, valor in [
                        (intento, "io_lote", "LOTE-ALTERADO"),
                        (registro, "ro_numero", "OTRA-OF"),
                        (caso, "ch_detalle_original", "Detalle alterado"),
                    ]:
                        with self.subTest(campo=campo):
                            setattr(objeto, campo, valor)
                            with self.assertRaises(ValueError):
                                db.commit()
                            db.rollback()
                            self.assertEqual(snapshot(), antes)
                    for objeto in (intento, registro, caso):
                        with self.subTest(borrado=type(objeto).__name__):
                            db.delete(objeto)
                            with self.assertRaises(ValueError):
                                db.commit()
                            db.rollback()
                            self.assertEqual(snapshot(), antes)
        finally:
            engine.dispose()

    def test_ddl_of_compila_para_postgresql_sin_conexion(self):
        from sqlalchemy.dialects import postgresql
        from sqlalchemy.schema import CreateIndex, CreateTable

        for nombre in ("intentos_of", "registros_of", "conciliaciones_h2h", "movimientos_envio"):
            with self.subTest(tabla=nombre):
                tabla = Base.metadata.tables[nombre]
                ddl = str(CreateTable(tabla).compile(dialect=postgresql.dialect()))
                self.assertIn("CREATE TABLE", ddl)
                for indice in tabla.indexes:
                    self.assertIn("CREATE", str(CreateIndex(indice).compile(dialect=postgresql.dialect())))

    def test_secuencia_postgresql_de_pk_es_equivalente_al_autoincrement(self):
        columna = Base.metadata.tables["envios"].c.id
        self.assertTrue(_es_secuencia_pk_equivalente(columna, "nextval('envios_id_seq'::regclass)"))
        self.assertFalse(_es_secuencia_pk_equivalente(columna, "false"))

    def test_baseline_y_configuracion_no_contienen_credenciales(self):
        ini = (PROJECT_DIR / "alembic.ini").read_text(encoding="utf-8")
        env = (PROJECT_DIR / "migrations" / "env.py").read_text(encoding="utf-8")
        baseline = BASELINE.read_text(encoding="utf-8")

        self.assertIn("from config.settings import DATABASE_URL", env)
        self.assertNotIn("postgresql://", ini)
        self.assertNotIn("password", ini.lower())
        for elemento_futuro in ("puntos_retiro", "retiros_starken", "retiro_envios", "avisos_envio", "e_fecha_of", "e_punto_retiro_id"):
            self.assertNotIn(elemento_futuro, baseline)

    def test_consultas_de_auditoria_son_read_only(self):
        consultas = consultas_auditoria_envios({"id", "e_estado", "e_orden_flete", "e_codigo_agencia"})
        self.assertIn("codigo_agencia_distribucion", consultas)
        self.assertNotIn("e_orden_flete, COUNT", consultas["of_duplicadas"])
        self.assertTrue(consultas)
        for nombre, consulta in consultas.items():
            with self.subTest(nombre=nombre):
                self.assertTrue(consulta.lstrip().upper().startswith("SELECT"))
                for palabra in ("INSERT ", "UPDATE ", "DELETE ", "ALTER ", "DROP ", "CREATE "):
                    self.assertNotIn(palabra, consulta.upper())


if __name__ == "__main__":
    unittest.main()
