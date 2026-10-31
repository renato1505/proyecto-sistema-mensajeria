import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from tests.entorno_aislado import preparar_entorno_pruebas, ejecutar_python_aislado

preparar_entorno_pruebas()

from dataclasses import replace
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import Column, MetaData, String, Table, create_engine, event, text

from database.modelos import Base, PuntoRetiro
from database.validacion_esquema import (
    CONTRATO_V2, contrato_fixture_sqlite, validar_esquema,
)


class ValidacionEsquemaTest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "esquema.sqlite3"
        self.engine = create_engine("sqlite:///" + self.ruta.as_posix())
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

    def sql(self, sentencia):
        with self.engine.begin() as c:
            c.exec_driver_sql(sentencia)

    def revision(self, valor):
        with self.engine.begin() as c:
            c.execute(text("UPDATE alembic_version SET version_num=:valor"), {"valor": valor})

    def test_base_valida_revision_y_referencias(self):
        resultado = validar_esquema(self.engine)
        self.assertTrue(resultado.compatible, resultado.como_dict())
        self.assertEqual(resultado.revisiones, ("20261025_06",))
        self.assertEqual(resultado.hallazgos, ())

    def test_base_vacia(self):
        engine = create_engine("sqlite:///:memory:")
        self.addCleanup(engine.dispose)
        r = validar_esquema(engine)
        self.assertEqual(r.estado, "REVISION_AUSENTE")
        self.assertTrue(any(h.codigo == "ESTRUCTURA_INCOMPLETA" for h in r.hallazgos))

    def test_version_ausente_aunque_haya_tablas(self):
        self.sql("DROP TABLE alembic_version")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_AUSENTE")

    def test_revision_antigua(self):
        self.revision("20260829_05")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_INSUFICIENTE")

    def test_revision_desconocida_no_se_expone(self):
        secreto = "postgresql://usuario:SECRETO@host/base"
        self.revision(secreto)
        resultado = validar_esquema(self.engine)
        self.assertEqual(resultado.estado, "REVISION_MANUAL")
        self.assertNotIn(secreto, str(resultado.como_dict()))

    def test_registro_version_vacio(self):
        self.sql("DELETE FROM alembic_version")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_multiples_revisiones_requieren_revision(self):
        self.sql("INSERT INTO alembic_version VALUES ('20260829_05')")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_tabla_version_malformada(self):
        self.sql("DROP TABLE alembic_version")
        self.sql("CREATE TABLE alembic_version (otra TEXT)")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_tabla_indispensable_ausente(self):
        self.sql("DROP TABLE comunas")
        self.assertEqual(validar_esquema(self.engine).estado, "ESTRUCTURA_INCOMPLETA")

    def test_columna_indispensable_ausente(self):
        self.sql("ALTER TABLE comunas DROP COLUMN c_region")
        self.assertEqual(validar_esquema(self.engine).estado, "ESTRUCTURA_INCOMPLETA")

    def test_punto_obligatorio_ausente(self):
        self.sql("DELETE FROM puntos_retiro WHERE pr_codigo='ACADEMIA'")
        self.assertEqual(validar_esquema(self.engine).estado, "REFERENCIAS_INCOMPLETAS")

    def test_punto_inactivo(self):
        self.sql("UPDATE puntos_retiro SET pr_activo=0 WHERE pr_codigo='MENSAJERIA_LOCAL'")
        self.assertEqual(validar_esquema(self.engine).estado, "REFERENCIAS_INCOMPLETAS")

    def test_clasificacion_punto_incorrecta(self):
        self.sql("UPDATE puntos_retiro SET pr_es_local=1 WHERE pr_codigo='ACADEMIA'")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_unicidad_esencial_ausente(self):
        self.sql("DROP INDEX ix_usuarios_sistema_u_usuario")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_indice_parcial_ausente(self):
        self.sql("DROP INDEX uq_intentos_of_envio_abierto")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_indice_global_no_sustituye_parcial(self):
        self.sql("DROP INDEX uq_intentos_of_envio_abierto")
        self.sql("CREATE UNIQUE INDEX uq_intentos_of_envio_abierto ON intentos_of(envio_id)")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_predicado_parcial_incorrecto(self):
        self.sql("DROP INDEX uq_intentos_of_envio_abierto")
        self.sql("CREATE UNIQUE INDEX uq_intentos_of_envio_abierto ON intentos_of(envio_id) WHERE io_estado='ABIERTO'")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_relacion_cruzada_no_satisface_contrato(self):
        with self.engine.begin() as c:
            ddl = c.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name='envios'").scalar_one()
            self.assertIn("REFERENCES puntos_retiro (id)", ddl)
            c.exec_driver_sql("DROP TABLE envios")
            c.exec_driver_sql(ddl.replace("REFERENCES puntos_retiro (id)", "REFERENCES comunas (id)"))
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_estado_activo_invalido_no_se_acepta_como_verdadero(self):
        self.sql("UPDATE puntos_retiro SET pr_activo=2 WHERE pr_codigo='ACADEMIA'")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_politica_no_admite_revisiones_menores_que_su_minimo(self):
        contrato = replace(CONTRATO_V2, revisiones_aceptadas=("20260829_05",))
        self.assertEqual(validar_esquema(self.engine, contrato).estado, "REVISION_MANUAL")

    def test_checks_esenciales_se_inspeccionan(self):
        self.sql("DROP TABLE retiro_envios")
        self.sql("CREATE TABLE retiro_envios (id INTEGER PRIMARY KEY, retiro_id INTEGER, envio_id INTEGER, re_bultos_snapshot INTEGER, re_fecha_asociacion DATETIME, re_vigente BOOLEAN)")
        resultado = validar_esquema(self.engine)
        self.assertTrue(any("ck_retiro_envios_bultos_snapshot_positivo" in h.mensaje for h in resultado.hallazgos))

    def test_fixture_explicito_admite_metadata_sin_version(self):
        self.sql("DROP TABLE alembic_version")
        self.assertTrue(validar_esquema(self.engine, contrato_fixture_sqlite()).compatible)

    def test_fixture_no_omite_estructura_ni_referencias(self):
        self.sql("DROP TABLE alembic_version")
        self.sql("DELETE FROM puntos_retiro WHERE pr_codigo='ACADEMIA'")
        self.assertFalse(validar_esquema(self.engine, contrato_fixture_sqlite()).compatible)

    def test_no_hay_llamadas_a_reparacion(self):
        with patch.object(Base.metadata, "create_all", side_effect=AssertionError("reparacion")), \
             patch("database.schema.asegurar_columnas_operativas", side_effect=AssertionError("reparacion")), \
             patch("services.normalizacion_operativa.normalizar_datos_operativos", side_effect=AssertionError("reparacion")), \
             patch("alembic.command.upgrade", side_effect=AssertionError("reparacion")), \
             patch("alembic.command.stamp", side_effect=AssertionError("reparacion")):
            self.assertTrue(validar_esquema(self.engine).compatible)

    def test_validar_dos_veces_no_cambia_archivo_ni_confirma(self):
        sentencias = []
        commits = []
        def registrar(_c, _cursor, sql, _params, _context, _many):
            sentencias.append(sql.strip().upper())
        def confirmar(_c):
            commits.append(True)
        event.listen(self.engine, "before_cursor_execute", registrar)
        event.listen(self.engine, "commit", confirmar)
        antes = self.ruta.read_bytes()
        for _ in range(2):
            self.assertTrue(validar_esquema(self.engine).compatible)
        self.assertEqual(antes, self.ruta.read_bytes())
        self.assertEqual(commits, [])
        self.assertTrue(sentencias)
        self.assertTrue(all(s.startswith(("SELECT", "PRAGMA")) for s in sentencias))

    def test_valida_con_sqlite_en_query_only(self):
        with self.engine.connect() as c:
            c.exec_driver_sql("PRAGMA query_only=ON")
        self.assertTrue(validar_esquema(self.engine).compatible)

    def test_error_driver_no_expone_secretos(self):
        secreto = "postgresql://usuario:CLAVE_REAL@host/base?token=TOKEN_REAL"
        with patch.object(self.engine, "connect", side_effect=RuntimeError(secreto)):
            resultado = validar_esquema(self.engine)
        self.assertEqual(resultado.estado, "REVISION_MANUAL")
        self.assertNotIn("CLAVE_REAL", str(resultado.como_dict()))
        self.assertNotIn("TOKEN_REAL", str(resultado.como_dict()))
        self.assertNotIn("usuario", str(resultado.como_dict()))

    def test_contrato_no_depende_de_head_dinamico(self):
        self.assertEqual(CONTRATO_V2.revision_requerida, "20261025_06")
        contrato = replace(CONTRATO_V2, revision_requerida="20260829_05",
                           revisiones_aceptadas=("20260829_05",))
        self.assertEqual(validar_esquema(self.engine, contrato).estado, "REVISION_MANUAL")
        self.revision("20260829_05")
        self.assertTrue(validar_esquema(self.engine, contrato).compatible)

    def test_esquema_preparado_por_alembic_sqlite(self):
        ruta = Path(self.temporal.name) / "migrada.sqlite3"
        env = os.environ.copy()
        env["DATABASE_URL"] = "sqlite:///" + ruta.as_posix()
        ejecutar_python_aislado(
            ["-c", "from alembic.config import main; main()", "upgrade", "head"],
            env=env, check=True, capture_output=True, text=True,
        )
        engine = create_engine(env["DATABASE_URL"])
        self.addCleanup(engine.dispose)
        self.assertTrue(validar_esquema(engine).compatible)

    def test_literales_en_minusculas_no_equivalen_a_estados_validos(self):
        self.sql("DROP INDEX uq_intentos_of_envio_abierto")
        self.sql("CREATE UNIQUE INDEX uq_intentos_of_envio_abierto ON intentos_of(envio_id) WHERE io_estado IN ('abierto', 'en_verificacion')")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_espacios_internos_de_literales_no_se_borran(self):
        self.sql("DROP INDEX uq_intentos_of_envio_abierto")
        self.sql("CREATE UNIQUE INDEX uq_intentos_of_envio_abierto ON intentos_of(envio_id) WHERE io_estado IN ('ABI ERTO', 'EN_VERIFICACION')")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_formato_y_mayusculas_fuera_de_literales_son_equivalentes(self):
        self.sql("DROP INDEX uq_intentos_of_envio_abierto")
        self.sql("CREATE UNIQUE INDEX uq_intentos_of_envio_abierto ON intentos_of(envio_id) WHERE ( IO_ESTADO  in ( 'ABIERTO' , 'EN_VERIFICACION' ) )")
        self.assertTrue(validar_esquema(self.engine).compatible)

    def test_predicado_ampliado_no_se_acepta(self):
        self.sql("DROP INDEX uq_intentos_of_envio_abierto")
        self.sql("CREATE UNIQUE INDEX uq_intentos_of_envio_abierto ON intentos_of(envio_id) WHERE io_estado IN ('ABIERTO', 'EN_VERIFICACION') OR 1=1")
        self.assertEqual(validar_esquema(self.engine).estado, "REVISION_MANUAL")

    def test_expresiones_desconocidas_no_equivalen_ni_a_si_mismas(self):
        from database.validacion_esquema import _expresiones_equivalentes
        self.assertFalse(_expresiones_equivalentes("funcion_desconocida()", "funcion_desconocida()"))
        self.assertFalse(_expresiones_equivalentes("io_estado IN ('ABIERTO)", "io_estado IN ('ABIERTO)"))

    def test_forma_postgresql_reconocida_sin_conexion(self):
        from database.validacion_esquema import _expresiones_equivalentes
        esperada = "io_estado IN ('ABIERTO', 'EN_VERIFICACION')"
        reflejada = "((io_estado)::text = ANY ((ARRAY['ABIERTO'::character varying, 'EN_VERIFICACION'::character varying])::text[]))"
        self.assertTrue(_expresiones_equivalentes(reflejada, esperada))
        self.assertFalse(_expresiones_equivalentes(reflejada.replace("'ABIERTO'", "'abierto'"), esperada))

    def test_contenido_escapado_de_literal_se_preserva(self):
        from database.validacion_esquema import _expresiones_equivalentes
        self.assertFalse(_expresiones_equivalentes(
            "io_estado IN ('AB''IERTO', 'EN_VERIFICACION')",
            "io_estado IN ('ABIERTO', 'EN_VERIFICACION')"))


if __name__ == "__main__":
    unittest.main()
