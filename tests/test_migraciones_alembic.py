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

        self.assertIn("20260829_05", current)
        self.assertIn("20260826_01", history)
        self.assertIn("20260828_02", history)
        self.assertIn("20260828_03", history)
        self.assertIn("20260829_04", history)
        self.assertIn("20260829_05", history)
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
