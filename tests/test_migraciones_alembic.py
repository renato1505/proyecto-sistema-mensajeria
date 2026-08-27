import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect


os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.modelos import Base
from scripts.auditar_esquema import consultas_auditoria_envios, ejecutar_auditoria


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
        self.assertNotIn("puntos_retiro", tablas)
        self.assertNotIn("retiros_starken", tablas)
        self.assertNotIn("retiro_envios", tablas)

    def test_current_history_y_auditoria_coinciden_con_metadata(self):
        self._alembic("upgrade", "head")
        current = self._alembic("current").stdout
        history = self._alembic("history").stdout
        auditoria = ejecutar_auditoria(self.database_url)

        self.assertIn("20260826_01", current)
        self.assertIn("20260826_01", history)
        self.assertEqual(auditoria["diferencias_metadata"], [])
        self.assertEqual(auditoria["datos"]["total_envios"], [[0]])

    def test_baseline_y_configuracion_no_contienen_credenciales(self):
        ini = (PROJECT_DIR / "alembic.ini").read_text(encoding="utf-8")
        env = (PROJECT_DIR / "migrations" / "env.py").read_text(encoding="utf-8")
        baseline = BASELINE.read_text(encoding="utf-8")

        self.assertIn("from config.settings import DATABASE_URL", env)
        self.assertNotIn("postgresql://", ini)
        self.assertNotIn("password", ini.lower())
        for elemento_futuro in ("puntos_retiro", "retiros_starken", "retiro_envios", "e_fecha_of", "e_punto_retiro_id"):
            self.assertNotIn(elemento_futuro, baseline)

    def test_consultas_de_auditoria_son_read_only(self):
        consultas = consultas_auditoria_envios({"id", "e_estado", "e_orden_flete"})
        self.assertTrue(consultas)
        for nombre, consulta in consultas.items():
            with self.subTest(nombre=nombre):
                self.assertTrue(consulta.lstrip().upper().startswith("SELECT"))
                for palabra in ("INSERT ", "UPDATE ", "DELETE ", "ALTER ", "DROP ", "CREATE "):
                    self.assertNotIn(palabra, consulta.upper())


if __name__ == "__main__":
    unittest.main()
