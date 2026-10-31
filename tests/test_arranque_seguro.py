import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from tests.entorno_aislado import preparar_entorno_pruebas, ejecutar_python_aislado

preparar_entorno_pruebas()

import json
import os
from pathlib import Path
import tempfile
import unittest

from sqlalchemy import Column, MetaData, String, Table, create_engine
from database.modelos import Base, PuntoRetiro, Remitente, Envio


class ArranqueSeguroTest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "arranque.sqlite3"
        self.url = "sqlite:///" + self.ruta.as_posix()
        self.engine = create_engine(self.url)
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        version = Table("alembic_version", MetaData(),
                        Column("version_num", String(32), primary_key=True))
        version.create(self.engine)
        with self.engine.begin() as c:
            c.execute(version.insert().values(version_num="20261025_06"))
            for codigo, local in (("MENSAJERIA_LOCAL", True), ("ACADEMIA", False)):
                c.execute(PuntoRetiro.__table__.insert().values(
                    pr_codigo=codigo, pr_nombre=codigo, pr_es_local=local,
                    pr_incluir_metricas_locales=local, pr_activo=True,
                ))
            # El normalizador antiguo modificaría estos datos y fusionaría filas.
            c.execute(Remitente.__table__.insert(), [
                {"r_nombre": "Nombre HISTORICO UNO", "r_correo": "comun@demo.invalid"},
                {"r_nombre": "OTRO Nombre Historico", "r_correo": "comun@demo.invalid"},
            ])
            c.execute(Envio.__table__.insert().values(
                e_remitente="Nombre HISTORICO COMPLETO", e_correo_remitente="comun@demo.invalid",
                e_destinatario="Destinatario FICTICIO", e_direccion="Direccion FICTICIA",
                e_comuna="Comuna FICTICIA", e_tipo_envio="Domicilio",
                e_bultos=1, e_kilos=1, e_estado="historico", e_orden_flete="900000000001.0",
            ))

    def sql(self, sentencia):
        with self.engine.begin() as c:
            c.exec_driver_sql(sentencia)

    def hijo(self, codigo, *, url=None):
        env = os.environ.copy()
        env["DATABASE_URL"] = self.url if url is None else url
        r = ejecutar_python_aislado(["-c", codigo], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def arrancar(self, esperado="COMPATIBLE", *, repetir=False):
        # El hijo instala las barreras antes de este código. La importación real
        # de main no se mockea y las consultas se observan desde el Engine.
        codigo = """
import importlib,json
from sqlalchemy import event
from sqlalchemy.engine import Engine
sentencias=[]
commits=[]
@event.listens_for(Engine,'before_cursor_execute')
def registrar(c,cursor,sql,params,context,many):
    sentencias.append(sql.strip().upper())
@event.listens_for(Engine,'commit')
def commit(c):
    commits.append(True)
try:
    import main
except RuntimeError as error:
    estado='ERROR'
    mensaje=str(error)
else:
    estado='OK'
    mensaje=''
    if REPETIR:
        importlib.reload(main)
from database.conexion import engine
assert not commits
assert all(s.startswith(('SELECT','PRAGMA','WITH','SET')) for s in sentencias), sentencias
if hasattr(engine.pool,'checkedout'):
    assert engine.pool.checkedout()==0
print(json.dumps({'estado':estado,'mensaje':mensaje,'consultas':len(sentencias)}))
""".replace("REPETIR", repr(repetir))
        antes = self.ruta.read_bytes()
        r = self.hijo(codigo)
        despues = self.ruta.read_bytes()
        self.assertEqual(antes, despues, "El arranque modifico la SQLite de prueba")
        datos = json.loads(r.stdout.strip().splitlines()[-1])
        if esperado == "COMPATIBLE":
            self.assertEqual(datos["estado"], "OK", datos["mensaje"])
        else:
            self.assertEqual(datos["estado"], "ERROR")
            self.assertIn(esperado, datos["mensaje"])
            self.assertIn("Arranque rechazado", datos["mensaje"])
        return datos

    def test_main_real_inicia_con_base_compatible_sin_escrituras(self):
        self.assertGreater(self.arrancar()["consultas"], 0)

    def test_repetir_importacion_no_modifica_datos_ni_duplica_remitentes(self):
        self.arrancar(repetir=True)
        with self.engine.connect() as c:
            self.assertEqual(c.exec_driver_sql("SELECT COUNT(*) FROM remitentes").scalar_one(), 2)
            self.assertEqual(c.exec_driver_sql("SELECT e_orden_flete FROM envios").scalar_one(), "900000000001.0")

    def test_main_no_llama_create_all_ni_helpers_historicos(self):
        codigo = """
from unittest.mock import patch
with patch('sqlalchemy.MetaData.create_all',side_effect=AssertionError('create_all')), \\
     patch('database.schema.asegurar_columnas_operativas',side_effect=AssertionError('columnas')), \\
     patch('services.normalizacion_operativa.normalizar_datos_operativos',side_effect=AssertionError('normalizacion')):
    import main
assert main.app is not None
"""
        self.hijo(codigo)

    def test_base_vacia_rechaza_sin_crear_tablas(self):
        self.engine.dispose()
        # Archivo SQLite vacío preparado explícitamente por el fixture.
        vacia = Path(self.temporal.name) / "vacia.sqlite3"
        e = create_engine("sqlite:///" + vacia.as_posix())
        with e.connect() as c:
            c.exec_driver_sql("SELECT 1")
        e.dispose()
        self.ruta = vacia
        self.url = "sqlite:///" + vacia.as_posix()
        self.arrancar("REVISION_AUSENTE")

    def test_revision_ausente_rechaza_en_app_env_test(self):
        self.sql("DROP TABLE alembic_version")
        self.arrancar("REVISION_AUSENTE")

    def test_revision_insuficiente_rechaza_sin_actualizarla(self):
        self.sql("UPDATE alembic_version SET version_num='20260829_05'")
        self.arrancar("REVISION_INSUFICIENTE")

    def test_revision_desconocida_no_expone_su_contenido(self):
        secreto = "postgresql://usuario:CLAVE_FICTICIA@host/base"
        with self.engine.begin() as c:
            c.execute(Envio.__table__.select().limit(0))
            c.exec_driver_sql("UPDATE alembic_version SET version_num=?", (secreto,))
        datos = self.arrancar("REVISION_MANUAL")
        self.assertNotIn(secreto, datos["mensaje"])
        self.assertNotIn("CLAVE_FICTICIA", datos["mensaje"])

    def test_tabla_ausente_rechaza_sin_recrearla(self):
        self.sql("DROP TABLE comunas")
        self.arrancar("ESTRUCTURA_INCOMPLETA")

    def test_columna_ausente_rechaza_sin_agregarla(self):
        self.sql("ALTER TABLE comunas DROP COLUMN c_region")
        self.arrancar("ESTRUCTURA_INCOMPLETA")

    def test_referencia_ausente_rechaza_sin_insertarla(self):
        self.sql("DELETE FROM puntos_retiro WHERE pr_codigo='ACADEMIA'")
        self.arrancar("REFERENCIAS_INCOMPLETAS")

    def test_referencia_inactiva_rechaza_sin_activarla(self):
        self.sql("UPDATE puntos_retiro SET pr_activo=0 WHERE pr_codigo='ACADEMIA'")
        self.arrancar("REFERENCIAS_INCOMPLETAS")

    def test_contrato_fixture_explicito_en_memoria_es_aceptado(self):
        r = self.hijo("""
from tests.fixtures_app import preparar_base_app
preparar_base_app()
from aplicacion import crear_app
from database.validacion_esquema import contrato_fixture_sqlite
app=crear_app(contrato=contrato_fixture_sqlite())
assert app.test_client().get('/login').status_code==200
""", url="sqlite:///:memory:")
        self.assertEqual(r.returncode, 0)

    def test_fixture_no_admite_archivos_aunque_esten_dentro_del_temporal(self):
        self.hijo("""
from aplicacion import crear_app,ArranqueIncompatible
from database.validacion_esquema import contrato_fixture_sqlite
try:
    crear_app(contrato=contrato_fixture_sqlite())
except ArranqueIncompatible as e:
    assert 'CONTRATO_NO_PERMITIDO' in str(e)
else:
    raise AssertionError('se acepto un archivo con excepcion de fixture')
""")

    def test_postgresql_no_admite_fixture_ni_intenta_conectar(self):
        self.hijo("""
from unittest.mock import patch
from types import SimpleNamespace
import aplicacion
from database.validacion_esquema import contrato_fixture_sqlite
falso=SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))
with patch.object(aplicacion,'engine',falso), \\
     patch.object(aplicacion,'validar_esquema',side_effect=AssertionError('no debe consultar')):
    try:
        aplicacion.crear_app(contrato=contrato_fixture_sqlite())
    except aplicacion.ArranqueIncompatible as e:
        assert 'CONTRATO_NO_PERMITIDO' in str(e)
    else:
        raise AssertionError('se acepto PostgreSQL')
""")

    def test_produccion_no_admite_fixture_incluso_en_memoria(self):
        self.hijo("""
from unittest.mock import patch
import aplicacion
from database.validacion_esquema import contrato_fixture_sqlite
with patch.object(aplicacion,'ES_PRODUCCION',True), \\
     patch.object(aplicacion,'validar_esquema',side_effect=AssertionError('no debe consultar')):
    try:
        aplicacion.crear_app(contrato=contrato_fixture_sqlite())
    except aplicacion.ArranqueIncompatible:
        pass
    else:
        raise AssertionError('se acepto fixture en produccion')
""", url="sqlite:///:memory:")

    def test_contrato_alterado_no_debilita_el_arranque(self):
        self.hijo("""
from dataclasses import replace
from aplicacion import crear_app,ArranqueIncompatible
from database.validacion_esquema import contrato_fixture_sqlite
contrato=replace(contrato_fixture_sqlite(),columnas=(),unicos=(),fks=())
try:
    crear_app(contrato=contrato)
except ArranqueIncompatible:
    pass
else:
    raise AssertionError('se acepto contrato alterado')
""", url="sqlite:///:memory:")

    def test_error_de_driver_no_expone_secretos_en_log_o_excepcion(self):
        self.hijo("""
import io,logging
from unittest.mock import patch
from database.conexion import engine
from aplicacion import crear_app,ArranqueIncompatible
buffer=io.StringIO()
handler=logging.StreamHandler(buffer)
logging.getLogger().addHandler(handler)
with patch.object(engine,'connect',side_effect=RuntimeError('postgresql://usuario:SECRETO_FICTICIO@host/base')):
    try:
        crear_app()
    except ArranqueIncompatible as e:
        mensaje=str(e)
    else:
        raise AssertionError('se acepto error de conexion')
assert 'SECRETO_FICTICIO' not in mensaje+buffer.getvalue()
assert 'postgresql://' not in mensaje+buffer.getvalue()
""")

    def test_rutas_auth_y_csrf_conservan_contratos_en_main_real(self):
        self.hijo("""
from main import app
client=app.test_client()
assert client.get('/login').status_code==200
assert client.get('/').status_code==302
assert client.post('/descargar_historico_seleccionados').status_code==400
from flask import session
with client.session_transaction() as s:
    import time
    s.update(usuario_autenticado=True,usuario_nombre='demo',usuario_display='Demo',
             ultima_actividad=time.time(),debe_cambiar_clave=False)
for ruta in ('/','/envios','/en_proceso','/historico','/operacion/retiros','/configuracion'):
    assert client.get(ruta).status_code==200,ruta
assert client.get('/admin').status_code==404
assert client.get('/reportes').status_code==404
""")

    def test_base_migrada_explicita_inicia_main_sin_ddl(self):
        ruta = Path(self.temporal.name) / "migrada.sqlite3"
        self.hijo("""
from alembic import command
from alembic.config import Config
command.upgrade(Config('alembic.ini'),'head')
from sqlalchemy import event
from sqlalchemy.engine import Engine
sentencias=[]
@event.listens_for(Engine,'before_cursor_execute')
def registrar(c,cursor,sql,params,context,many):
    sentencias.append(sql.strip().upper())
from main import app
assert app is not None
assert all(s.startswith(('SELECT','PRAGMA','WITH','SET')) for s in sentencias)
""", url="sqlite:///" + ruta.as_posix())

    def test_demo_preparada_explicitamente_inicia_main_y_repite_sin_reparar(self):
        # Siempre dentro de la sesión temporal autorizada, no en el demo local
        # habitual del notebook. El script embebido se ejecuta sin mocks.
        raiz = preparar_entorno_pruebas() / "mensajeria-v2-demo"
        raiz.mkdir(exist_ok=True)
        self.hijo("""
from pathlib import Path
import os,re
codigo_demo=re.search(r"\\$SetupDemo = @'\\r?\\n(.*?)\\r?\\n'@",Path('scripts/run_demo.ps1').read_text(encoding='utf-8'),re.S).group(1)
os.environ['DEMO_SEED']='1'
exec(compile(codigo_demo,'demo_setup','exec'))
from database.conexion import engine
from sqlalchemy import text,event
with engine.connect() as c:
    assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='20261025_06'
    antes=c.execute(text('SELECT COUNT(*) FROM envios')).scalar_one()
exec(compile(codigo_demo,'demo_setup','exec'))
with engine.connect() as c:
    assert c.execute(text('SELECT COUNT(*) FROM envios')).scalar_one()==antes
sentencias=[]
@event.listens_for(engine,'before_cursor_execute')
def registrar(c,cursor,sql,params,context,many):
    sentencias.append(sql.strip().upper())
from main import app
assert app.test_client().get('/login').status_code==200
assert all(s.startswith(('SELECT','PRAGMA','WITH','SET')) for s in sentencias)
""", url="sqlite:///" + (raiz / "mensajeria_demo.sqlite3").as_posix())


if __name__ == "__main__":
    unittest.main()
