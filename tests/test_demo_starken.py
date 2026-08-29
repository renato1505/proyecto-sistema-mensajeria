import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database.modelos import Base, Envio
from services.demo_starken import (
    DemoEnvironmentError,
    crear_lote_demo,
    generar_envios_ficticios,
    procesar_respuesta_of_demo,
    validar_entorno_demo,
)
from services.retiros import obtener_envios_elegibles


class DemoStarkenTest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temporal.name).resolve()
        self.db_path = self.raiz / "mensajeria_demo.sqlite3"
        self.database_url = f"sqlite:///{self.db_path.as_posix()}"
        self.engine = create_engine(self.database_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.patcher = patch("services.demo_starken.raiz_demo_permitida", return_value=self.raiz)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.db.close()
        self.engine.dispose()
        self.temporal.cleanup()

    def test_protecciones_rechazan_postgresql_produccion_y_ruta_externa(self):
        casos = [
            ("postgresql://usuario:clave@localhost/base", "test", "false", self.raiz),
            (self.database_url, "production", "false", self.raiz),
            (self.database_url, "test", "true", self.raiz),
            (self.database_url, "test", "false", self.raiz / "otro"),
        ]
        for url, entorno, render, raiz in casos:
            with self.subTest(url=url, entorno=entorno, render=render), self.assertRaises(DemoEnvironmentError):
                validar_entorno_demo(url, entorno, render, raiz)
        self.assertEqual(validar_entorno_demo(self.database_url, "test", "false", self.raiz), self.db_path)

    def test_generacion_ficticia_es_determinista_y_kilos_igual_bultos(self):
        envios = generar_envios_ficticios(self.db, 10, incluir_academia=True)
        self.db.commit()
        self.assertEqual(len(envios), 10)
        self.assertTrue(all(envio.e_kilos == envio.e_bultos >= 1 for envio in envios))
        self.assertTrue(all(envio.e_correo_remitente.endswith("@demo.invalid") for envio in envios))
        self.assertTrue(any(envio.e_tipo_envio == "Agencia" for envio in envios))
        self.assertTrue(any(envio.e_centro_costo == "ACM" for envio in envios))

    def test_cantidad_demo_admite_valores_utiles(self):
        for cantidad in (1, 5, 10, 50):
            with self.subTest(cantidad=cantidad):
                envios = generar_envios_ficticios(self.db, cantidad)
                self.assertEqual(len(envios), cantidad)
                self.db.rollback()

    def test_lote_y_escenarios_of_recorrer_flujo_real(self):
        fecha_base = datetime(2026, 8, 29, 9, 0, 0)
        esperados = {
            "TODOS_OK": (3, 0),
            "UNO_ERROR": (2, 1),
            "MIXTO": (2, 1),
            "H2H_AMBIGUO": (2, 1),
        }
        ofs = set()
        for indice, (escenario, esperado) in enumerate(esperados.items()):
            envios = generar_envios_ficticios(self.db, 3)
            self.db.commit()
            lote = crear_lote_demo(
                self.db,
                [envio.id for envio in envios],
                self.raiz,
                fecha_actual=fecha_base + timedelta(minutes=indice),
            )
            resultado = procesar_respuesta_of_demo(self.db, lote["lote"], escenario, self.raiz)
            self.assertEqual((resultado["total_ok"], resultado["total_error"]), esperado)
            self.assertTrue(lote["ruta_csv"].is_file())
            self.assertTrue(resultado["ruta_of"].is_file())
            self.assertTrue(lote["ruta_csv"].is_relative_to(self.raiz))
            self.assertTrue(resultado["ruta_of"].is_relative_to(self.raiz))
            guardados = self.db.query(Envio).filter(Envio.e_lote == lote["lote"]).all()
            for envio in guardados:
                if envio.e_resultado_of == "OK":
                    self.assertIsNotNone(envio.e_fecha_of)
                    self.assertIsNotNone(envio.e_orden_flete)
                    self.assertTrue(envio.e_orden_flete not in ofs)
                    ofs.add(envio.e_orden_flete)
                else:
                    self.assertEqual(envio.e_estado, "en_proceso")
                    self.assertIsNone(envio.e_fecha_of)
                    self.assertIsNone(envio.e_orden_flete)
            if escenario == "H2H_AMBIGUO":
                error = next(envio for envio in guardados if envio.e_resultado_of == "ERROR")
                self.assertIn("servicio H2H", error.e_detalle_of)

        self.assertEqual(len(obtener_envios_elegibles(self.db)), sum(ok for ok, _ in esperados.values()))

    def test_sqlite_nueva_contiene_modelo_actual(self):
        columnas = {item["name"] for item in inspect(self.engine).get_columns("envios")}
        self.assertIn("e_fecha_of", columnas)
        self.assertIn("e_punto_retiro_id", columnas)
        self.assertIn("retiros_starken", inspect(self.engine).get_table_names())


if __name__ == "__main__":
    unittest.main()
