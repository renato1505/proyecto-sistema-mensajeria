import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from tests.entorno_aislado import preparar_entorno_pruebas

preparar_entorno_pruebas()

import ast
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest

from sqlalchemy import create_engine

from tests.entorno_aislado import (
    AccesoExternoBloqueado, DestinoPruebasInvalido,
    _antes_de_conectar, validar_destino_pruebas,
    ejecutar_python_aislado, entorno_subproceso_autorizado,
)


class EntornoAisladoTest(unittest.TestCase):
    def test_destino_ya_esta_aislado_antes_de_configuracion(self):
        raiz = preparar_entorno_pruebas()
        from config.settings import DATABASE_URL
        validar_destino_pruebas(DATABASE_URL, raiz)
        self.assertNotEqual(os.environ["EMAIL_PROVIDER"], "smtp")
        self.assertEqual(os.environ["OF_IMAP_PORT"], "0")

    def test_rechaza_postgresql_y_otras_bases_sin_imprimir_url(self):
        for url in ("postgresql://usuario:SECRETO@host/base",
                    "postgres://usuario:SECRETO@host/base",
                    "mysql://usuario:SECRETO@host/base"):
            with self.subTest(esquema=url.split(":")[0]):
                with self.assertRaises(DestinoPruebasInvalido) as error:
                    validar_destino_pruebas(url, preparar_entorno_pruebas())
                self.assertNotIn("SECRETO", str(error.exception))

    def test_rechaza_sqlite_operativa(self):
        ruta = Path(__file__).resolve().parent.parent / "logs" / "desarrollo-local.sqlite3"
        with self.assertRaises(DestinoPruebasInvalido):
            validar_destino_pruebas("sqlite:///" + ruta.as_posix(), preparar_entorno_pruebas())

    def test_barrera_dns_y_conexion_sin_realizar_red(self):
        for evento, args in (
            ("socket.getaddrinfo", ("example.invalid", 443, 0, 0, 0)),
            ("socket.connect", (None, ("127.0.0.1", 1))),
        ):
            with self.assertRaises(AccesoExternoBloqueado):
                sys.audit(evento, *args)

    def test_barrera_motor_no_sqlite_antes_de_driver(self):
        with self.assertRaises(AccesoExternoBloqueado):
            _antes_de_conectar(SimpleNamespace(name="postgresql"), None, [], {})

    def test_barrera_dbapi_impide_sqlite_fuera_de_fixture(self):
        # Audit explícito: no abrimos ni siquiera un archivo fuera de pruebas.
        with self.assertRaises(AccesoExternoBloqueado):
            sys.audit("sqlite3.connect", str(Path.cwd() / "logs" / "desarrollo-local.sqlite3"))

    def test_sqlite_temporal_real_permitida(self):
        ruta = preparar_entorno_pruebas() / "prueba-barrera.sqlite3"
        engine = create_engine("sqlite:///" + ruta.as_posix())
        try:
            with engine.connect() as c:
                self.assertEqual(c.exec_driver_sql("SELECT 1").scalar_one(), 1)
        finally:
            engine.dispose()

    def test_subproceso_prepara_aislamiento_antes_de_importar_app(self):
        codigo = """
import sys, os
assert 'main' not in sys.modules
assert 'database.conexion' not in sys.modules
assert 'config.settings' not in sys.modules
from tests.entorno_aislado import preparar_entorno_pruebas
raiz = preparar_entorno_pruebas()
from tests.fixtures_app import obtener_app_aislada
app = obtener_app_aislada()
from database.conexion import engine
from tests.entorno_aislado import validar_destino_pruebas
validar_destino_pruebas(engine.url, raiz)
assert app.test_client().get('/login').status_code == 200
print('APP_AISLADA_OK')
"""
        resultado = ejecutar_python_aislado(["-c", codigo],
                                           capture_output=True, text=True, check=True)
        self.assertIn("APP_AISLADA_OK", resultado.stdout)

    def test_subprocesos_no_eluden_barreras(self):
        resultado = ejecutar_python_aislado(
            ["-c", "import sys; sys.audit('socket.connect', None, ('127.0.0.1', 1))"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("AccesoExternoBloqueado", resultado.stderr)

    def test_bootstrap_rechaza_destino_externo_heredado(self):
        env = os.environ.copy()
        env["DATABASE_URL"] = "postgresql://usuario:SECRETO@host/base"
        resultado = subprocess.run([sys.executable, "-c", "raise AssertionError('no debe ejecutar')"],
                                   env=env, capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 79)
        self.assertNotIn("SECRETO", resultado.stdout + resultado.stderr)

    def test_configurar_despues_de_settings_es_rechazado(self):
        # Proceso sin sitecustomize para probar exclusivamente el orden erróneo,
        # sin importar ningún módulo real de configuración.
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        codigo = """
import sys
from types import ModuleType
from tests.entorno_aislado import preparar_entorno_pruebas, DestinoPruebasInvalido
sys.modules['config.settings'] = ModuleType('config.settings')
try:
    preparar_entorno_pruebas()
except DestinoPruebasInvalido:
    print('ORDEN_RECHAZADO')
else:
    raise AssertionError('se acepto configuracion tardia')
"""
        resultado = subprocess.run([sys.executable, "-c", codigo], env=env,
                                   capture_output=True, text=True, check=True)
        self.assertIn("ORDEN_RECHAZADO", resultado.stdout)

    def test_preparacion_explicita_funciona_sin_operaciones_legacy(self):
        # El fixture pasa su contrato explícito; la validación real no se mockea.
        codigo = """
from unittest.mock import patch
from tests.fixtures_app import preparar_base_app
from database.validacion_esquema import validar_esquema, contrato_fixture_sqlite
from sqlalchemy import event
engine = preparar_base_app()
assert validar_esquema(engine, contrato_fixture_sqlite()).compatible
sentencias = []
@event.listens_for(engine, 'before_cursor_execute')
def registrar(c, cursor, sql, params, context, many):
    sentencias.append(sql.strip().upper())
with patch('sqlalchemy.MetaData.create_all') as crear, \
     patch('database.schema.asegurar_columnas_operativas') as columnas, \
     patch('services.normalizacion_operativa.normalizar_datos_operativos') as normalizar:
    from aplicacion import crear_app
    app = crear_app(contrato=contrato_fixture_sqlite())
    assert app.test_client().get('/login').status_code == 200
    assert crear.call_count == columnas.call_count == normalizar.call_count == 0
assert not any(s.startswith(('CREATE', 'ALTER', 'INSERT', 'UPDATE', 'DELETE', 'DROP')) for s in sentencias)
print('ENSAYO_S2B_OK')
"""
        resultado = ejecutar_python_aislado(["-c", codigo],
                                           capture_output=True, text=True, check=True)
        self.assertIn("ENSAYO_S2B_OK", resultado.stdout)

    def test_main_no_invoca_operaciones_legacy(self):
        raiz = Path(__file__).resolve().parent.parent
        prohibidas = {"Base.metadata.create_all", "asegurar_columnas_operativas",
                      "normalizar_datos_operativos"}
        for nombre in ("main.py", "aplicacion.py"):
            tree = ast.parse((raiz / nombre).read_text(encoding="utf-8"))
            llamadas = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
            self.assertFalse(prohibidas.intersection(llamadas))

    def _codigo_arranque(self):
        return "from tests.entorno_aislado import preparar_entorno_pruebas; preparar_entorno_pruebas(); print('AUTORIZADO')"

    def _env_principal_nuevo(self):
        env = os.environ.copy()
        for nombre in ("MENSAJERIA_TEST_ROOT", "MENSAJERIA_TEST_RUN", "MENSAJERIA_TEST_AUTORIZACION"):
            env.pop(nombre, None)
        env["DATABASE_URL"] = "sqlite:///:memory:"
        # Prueba del punto de entrada principal sin un sitecustomize heredado.
        # El código ejecutado invoca primero el bootstrap, nunca main.
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        return env

    def test_principal_nuevo_crea_raices_distintas(self):
        codigo = "from tests.entorno_aislado import preparar_entorno_pruebas; print(preparar_entorno_pruebas())"
        salidas = [
            subprocess.run([sys.executable, "-c", codigo], env=self._env_principal_nuevo(),
                           capture_output=True, text=True, check=True).stdout.strip()
            for _ in range(2)
        ]
        self.assertNotEqual(salidas[0], salidas[1])
        self.assertNotIn(str(preparar_entorno_pruebas()), salidas)

    def test_raiz_arbitraria_con_prefijo_no_autoriza(self):
        raiz = preparar_entorno_pruebas() / "mensajeria-tests-arbitraria"
        raiz.mkdir(exist_ok=True)
        env = os.environ.copy()
        env["MENSAJERIA_TEST_ROOT"] = str(raiz)
        resultado = subprocess.run([sys.executable, "-c", self._codigo_arranque()],
                                   env=env, capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 79)
        self.assertNotIn("AUTORIZADO", resultado.stdout)

    def test_sqlite_existente_en_raiz_arbitraria_permanece_intacta(self):
        raiz = preparar_entorno_pruebas() / "mensajeria-tests-con-datos"
        raiz.mkdir(exist_ok=True)
        ruta = raiz / "existente.sqlite3"
        engine = create_engine("sqlite:///" + ruta.as_posix())
        with engine.begin() as c:
            c.exec_driver_sql("CREATE TABLE IF NOT EXISTS evidencia (valor TEXT)")
            c.exec_driver_sql("INSERT INTO evidencia VALUES ('ficticio')")
        engine.dispose()
        antes = ruta.read_bytes()
        env = os.environ.copy()
        env["MENSAJERIA_TEST_ROOT"] = str(raiz)
        env["DATABASE_URL"] = "sqlite:///" + ruta.as_posix()
        resultado = subprocess.run([sys.executable, "-c", self._codigo_arranque()],
                                   env=env, capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 79)
        self.assertEqual(antes, ruta.read_bytes())

    def test_principal_rechaza_archivo_heredado_incluso_de_otra_sesion_valida(self):
        ruta = preparar_entorno_pruebas() / "no-reutilizar.sqlite3"
        ruta.write_bytes(b"archivo ficticio que no debe abrirse")
        env = self._env_principal_nuevo()
        env["DATABASE_URL"] = "sqlite:///" + ruta.as_posix()
        resultado = subprocess.run([sys.executable, "-c", self._codigo_arranque()],
                                   env=env, capture_output=True, text=True)
        self.assertNotEqual(resultado.returncode, 0)
        self.assertEqual(ruta.read_bytes(), b"archivo ficticio que no debe abrirse")
        self.assertNotIn("AUTORIZADO", resultado.stdout)

    def test_permiso_de_un_uso_no_se_puede_reutilizar(self):
        with entorno_subproceso_autorizado() as env:
            primero = subprocess.run([sys.executable, "-c", self._codigo_arranque()],
                                     env=env, capture_output=True, text=True)
            segundo = subprocess.run([sys.executable, "-c", self._codigo_arranque()],
                                     env=env, capture_output=True, text=True)
        self.assertEqual(primero.returncode, 0, primero.stderr)
        self.assertIn("AUTORIZADO", primero.stdout)
        self.assertEqual(segundo.returncode, 79)

    def test_permiso_no_autoriza_otra_raiz(self):
        otra = preparar_entorno_pruebas() / "mensajeria-tests-otra"
        otra.mkdir(exist_ok=True)
        with entorno_subproceso_autorizado() as env:
            env["MENSAJERIA_TEST_ROOT"] = str(otra)
            r = subprocess.run([sys.executable, "-c", self._codigo_arranque()],
                               env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 79)

    def test_permiso_no_autoriza_otro_destino(self):
        with entorno_subproceso_autorizado() as env:
            env["DATABASE_URL"] = "postgresql://usuario:SECRETO@host/base"
            r = subprocess.run([sys.executable, "-c", self._codigo_arranque()],
                               env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 79)
        self.assertNotIn("SECRETO", r.stdout + r.stderr)

    def test_variables_de_sesion_inconsistentes_son_rechazadas(self):
        with entorno_subproceso_autorizado() as env:
            env["MENSAJERIA_TEST_RUN"] = "0" * 64
            r = subprocess.run([sys.executable, "-c", self._codigo_arranque()],
                               env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 79)

    def test_permiso_de_otro_padre_es_rechazado(self):
        import json
        with entorno_subproceso_autorizado() as env:
            ruta = preparar_entorno_pruebas() / ".permisos" / (env["MENSAJERIA_TEST_AUTORIZACION"] + ".json")
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            datos["padre"] = os.getpid() + 1000000
            ruta.write_text(json.dumps(datos), encoding="utf-8")
            r = subprocess.run([sys.executable, "-c", self._codigo_arranque()],
                               env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 79)

    def test_subproceso_sin_permiso_no_ejecuta_codigo(self):
        env = os.environ.copy()
        env.pop("MENSAJERIA_TEST_AUTORIZACION", None)
        r = subprocess.run([sys.executable, "-c", self._codigo_arranque()],
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 79)
        self.assertNotIn("AUTORIZADO", r.stdout)

    def test_hijo_legitimo_comparte_solo_sesion_autorizada(self):
        codigo = "from tests.entorno_aislado import preparar_entorno_pruebas; print(preparar_entorno_pruebas())"
        r = ejecutar_python_aislado(["-c", codigo], capture_output=True, text=True, check=True)
        self.assertEqual(r.stdout.strip(), str(preparar_entorno_pruebas()))


if __name__ == "__main__":
    unittest.main()
