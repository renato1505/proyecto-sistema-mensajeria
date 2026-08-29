import unittest
import re
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_DIR / "scripts" / "run_demo.ps1"


class RunDemoScriptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contenido = SCRIPT.read_text(encoding="utf-8")

    def test_demo_usa_sqlite_y_archivos_bajo_temp(self):
        self.assertIn('Join-Path $env:TEMP "mensajeria-v2-demo"', self.contenido)
        self.assertIn('$env:DATABASE_URL = "sqlite:///$SqlitePath"', self.contenido)
        self.assertIn('$env:RESPALDOS_LOTES_DIR = $DemoBackups', self.contenido)
        self.assertIn('$env:LOGS_DIR = $DemoLogs', self.contenido)

    def test_demo_aborta_ante_indicadores_productivos(self):
        self.assertIn('$renderValue.Trim().ToLowerInvariant() -eq "true"', self.contenido)
        self.assertIn('("production", "produccion", "prod")', self.contenido)
        self.assertIn('$databaseUrl -match "^postgres', self.contenido)

    def test_demo_deshabilita_correo_e_imap(self):
        self.assertIn('$env:EMAIL_PROVIDER = "disabled"', self.contenido)
        self.assertIn('$env:OF_IMAP_PORT = "0"', self.contenido)

    def test_demo_crea_usuario_hash_y_datos_solo_con_seed(self):
        self.assertIn('u_usuario="demo"', self.contenido)
        self.assertIn('generate_password_hash("Demo1234!")', self.contenido)
        self.assertIn('environ.get("DEMO_SEED") == "1"', self.contenido)
        self.assertIn("$SetupDemoEncoded", self.contenido)
        self.assertIn("generar_envios_ficticios", self.contenido)
        self.assertNotIn("e_kilos=2", self.contenido)

    def test_demo_ofrece_limpieza_acotada_y_abre_navegador(self):
        self.assertIn('[switch]$Clean', self.contenido)
        self.assertIn('$DemoRoot.StartsWith($TempRoot', self.contenido)
        self.assertIn("Start-Process '$DemoUrl'", self.contenido)

    def test_demo_detecta_esquema_antiguo_y_ofrece_escenarios(self):
        self.assertIn('requeridas = {"e_fecha_of", "e_punto_retiro_id"}', self.contenido)
        self.assertIn("SQLite demo incompatible", self.contenido)
        self.assertIn('[string]$Scenario', self.contenido)
        self.assertIn('[switch]$NoStart', self.contenido)
        self.assertIn("scripts/demo_operacion.py", self.contenido)

    def test_bloque_python_embebido_es_sintacticamente_valido(self):
        bloque = re.search(r"\$SetupDemo = @'\r?\n(.*?)\r?\n'@", self.contenido, re.DOTALL)
        self.assertIsNotNone(bloque)
        compile(bloque.group(1), "run_demo_setup", "exec")


if __name__ == "__main__":
    unittest.main()
