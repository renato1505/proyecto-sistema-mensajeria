import csv
import io
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

# Impide que los imports de rutas dependan de PostgreSQL. Cada prueba crea
# ademas su propia base SQLite en memoria y nunca usa SessionLocal productivo.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pandas as pd
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.modelos import Base, Envio
from routes import avisos as avisos_routes
from routes import starken_lotes
from services import avisos
from services.lotes import buscar_lote_por_nombre_archivo, lote_coincide_con_archivo
from services.of_processor import OFProcessingError, procesar_archivo_of
from services.starken import HEADERS_STARKEN, generar_csv_starken


LOTE = "LOTE-20260822-120000"
NOMBRE_CSV = "starken_2026-08-22_12-00-00_2-envios.csv"


def crear_envio(**cambios):
    datos = {
        "e_remitente": "Ana Remitente",
        "e_correo_remitente": "ana@example.com",
        "e_division": "Consumer Products",
        "e_centro_costo": "CC-100",
        "e_destinatario": "Destino Base",
        "e_rut_destinatario": "12345678-9",
        "e_direccion": "Av. Principal 123",
        "e_comuna": "Nunoa",
        "e_region": "Metropolitana",
        "e_telefono_destinatario": "912345678",
        "e_correo_destinatario": "destino@example.com",
        "e_observacion": "Entregar en recepcion",
        "e_tipo_envio": "Domicilio",
        "e_codigo_agencia": None,
        "e_bultos": 1,
        "e_kilos": 2,
        "e_estado": "en_proceso",
        "e_lote": LOTE,
        "e_fila_excel": 2,
        "e_nombre_archivo": NOMBRE_CSV,
        "e_resultado_of": None,
        "e_orden_flete": None,
        "e_aviso_funcionario_estado": None,
        "e_anulado": False,
    }
    datos.update(cambios)
    return Envio(**datos)


def excel_of_bytes(filas):
    salida = io.BytesIO()
    pd.DataFrame(filas).to_excel(salida, index=False, engine="openpyxl")
    salida.seek(0)
    return salida


class SQLiteTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()


class GeneracionCSVTests(SQLiteTestCase):
    def test_csv_starken_conserva_formato_productivo_y_orden_de_entrada(self):
        primero = crear_envio(
            e_destinatario="Primero",
            e_comuna="Nunoa",
            e_correo_destinatario="primero@example.com",
            e_observacion="Observacion uno",
        )
        segundo = crear_envio(
            e_destinatario="Segundo",
            e_tipo_envio="Agencia",
            e_codigo_agencia="AG-77",
            e_correo_destinatario="segundo@example.com",
            e_observacion="Observacion dos",
        )

        nombre, contenido = generar_csv_starken(
            [primero, segundo], datetime(2026, 8, 22, 12, 0, 0)
        )
        filas = list(csv.reader(io.StringIO(contenido.decode("cp1252")), delimiter=";"))

        self.assertEqual(nombre, NOMBRE_CSV)
        self.assertEqual(filas[0], HEADERS_STARKEN)
        self.assertEqual(len(filas), 3)
        self.assertTrue(all(len(fila) == len(HEADERS_STARKEN) for fila in filas))
        self.assertEqual(filas[1][3], "Primero")
        self.assertEqual(filas[2][3], "Segundo")
        self.assertEqual(filas[1][9], "NUNOA")
        self.assertEqual(filas[1][11], "primero@example.com")
        self.assertEqual(filas[1][47], "Observacion uno")
        self.assertEqual(filas[2][0], "AG-77")
        self.assertEqual(filas[2][13], "1")

    def test_generacion_de_lote_asigna_e_fila_excel_segun_orden_del_csv(self):
        primero = crear_envio(
            e_estado="pendiente", e_lote=None, e_fila_excel=None,
            e_nombre_archivo=None, e_destinatario="Primero",
        )
        segundo = crear_envio(
            e_estado="pendiente", e_lote=None, e_fila_excel=None,
            e_nombre_archivo=None, e_destinatario="Segundo",
        )
        self.db.add_all([primero, segundo])
        self.db.commit()

        app = Flask(__name__)
        app.secret_key = "test"
        starken_lotes.registrar_rutas_starken_lotes(app)
        fecha = datetime(2026, 8, 22, 12, 0, 0)

        with patch.object(starken_lotes, "SessionLocal", self.Session), patch.object(
            starken_lotes, "ahora_chile", return_value=fecha
        ), patch.object(starken_lotes, "guardar_respaldo_lote"):
            respuesta = app.test_client().post(
                "/generar_excel",
                data={"accion": "descargar", "envio_ids": [str(primero.id), str(segundo.id)]},
            )

        self.assertEqual(respuesta.status_code, 200)
        filas_csv = list(
            csv.reader(io.StringIO(respuesta.data.decode("cp1252")), delimiter=";")
        )
        verificacion = self.Session()
        try:
            guardados = verificacion.query(Envio).order_by(Envio.id.asc()).all()
            self.assertEqual([e.e_fila_excel for e in guardados], [2, 3])
            self.assertEqual([e.e_destinatario for e in guardados], ["Primero", "Segundo"])
            self.assertEqual([fila[3] for fila in filas_csv[1:]], ["Primero", "Segundo"])
            self.assertEqual({e.e_estado for e in guardados}, {"en_proceso"})
            self.assertEqual({e.e_lote for e in guardados}, {LOTE})
            self.assertEqual({e.e_nombre_archivo for e in guardados}, {NOMBRE_CSV})
        finally:
            verificacion.close()


class ProcesamientoOFTests(SQLiteTestCase):
    def _agregar_lote(self):
        envio_2 = crear_envio(e_fila_excel=2, e_destinatario="Fila dos")
        envio_3 = crear_envio(e_fila_excel=3, e_destinatario="Fila tres")
        self.db.add_all([envio_2, envio_3])
        self.db.commit()
        return envio_2, envio_3

    def test_of_valida_correlacion_por_e_fila_excel_y_estados_finales(self):
        envio_2, envio_3 = self._agregar_lote()
        archivo = excel_of_bytes([
            {"Estado": "ERROR", "Fila": 3, "Orden Flete": None, "Detalle": "Direccion"},
            {"Estado": "OK", "Fila": 2, "Orden Flete": 272472119.0, "Detalle": "Correcto"},
        ])

        resultado = procesar_archivo_of(self.db, LOTE, archivo, "respuesta.xlsx")

        self.db.refresh(envio_2)
        self.db.refresh(envio_3)
        self.assertEqual(resultado["total_ok"], 1)
        self.assertEqual(resultado["total_error"], 1)
        self.assertEqual(resultado["total_sin_match"], 0)
        self.assertEqual(envio_2.e_orden_flete, "272472119")
        self.assertEqual(envio_2.e_estado, "historico")
        self.assertEqual(envio_2.e_resultado_of, "OK")
        self.assertEqual(envio_3.e_estado, "en_proceso")
        self.assertEqual(envio_3.e_resultado_of, "ERROR")
        self.assertIsNone(envio_3.e_orden_flete)

    def test_rechaza_cantidad_de_filas_distinta_al_lote(self):
        envios = self._agregar_lote()
        archivo = excel_of_bytes([
            {"Estado": "OK", "Fila": 2, "Orden Flete": "100", "Detalle": "OK"},
        ])

        with self.assertRaisesRegex(OFProcessingError, "no coincide"):
            procesar_archivo_of(self.db, LOTE, archivo, "respuesta.xlsx")

        self.assertEqual([e.e_estado for e in envios], ["en_proceso", "en_proceso"])

    def test_rechaza_si_falta_una_fila_esperada_del_lote(self):
        envios = self._agregar_lote()
        archivo = excel_of_bytes([
            {"Estado": "OK", "Fila": 2, "Orden Flete": "100", "Detalle": "OK"},
        ])

        with self.assertRaises(OFProcessingError):
            procesar_archivo_of(self.db, LOTE, archivo, "respuesta.xlsx")

        self.assertEqual([e.e_estado for e in envios], ["en_proceso", "en_proceso"])
        self.assertTrue(all(e.e_resultado_of is None for e in envios))

    def test_rechaza_si_aparece_una_fila_ajena_adicional(self):
        envios = self._agregar_lote()
        archivo = excel_of_bytes([
            {"Estado": "OK", "Fila": 2, "Orden Flete": "100", "Detalle": "OK"},
            {"Estado": "OK", "Fila": 3, "Orden Flete": "101", "Detalle": "OK"},
            {"Estado": "OK", "Fila": 4, "Orden Flete": "102", "Detalle": "OK"},
        ])

        with self.assertRaises(OFProcessingError):
            procesar_archivo_of(self.db, LOTE, archivo, "respuesta.xlsx")

        self.assertEqual([e.e_estado for e in envios], ["en_proceso", "en_proceso"])
        self.assertTrue(all(e.e_resultado_of is None for e in envios))

    def test_rechaza_falta_y_sobra_con_igual_cantidad_total(self):
        envios = self._agregar_lote()
        archivo = excel_of_bytes([
            {"Estado": "OK", "Fila": 2, "Orden Flete": "100", "Detalle": "OK"},
            {"Estado": "OK", "Fila": 5, "Orden Flete": "101", "Detalle": "OK"},
        ])

        with self.assertRaisesRegex(OFProcessingError, "no coinciden exactamente"):
            procesar_archivo_of(self.db, LOTE, archivo, "respuesta.xlsx")

        self.assertEqual([e.e_estado for e in envios], ["en_proceso", "en_proceso"])
        self.assertTrue(all(e.e_resultado_of is None for e in envios))

    def test_rechaza_filas_of_duplicadas(self):
        self._agregar_lote()
        archivo = excel_of_bytes([
            {"Estado": "OK", "Fila": 2, "Orden Flete": "100", "Detalle": "OK"},
            {"Estado": "OK", "Fila": 2, "Orden Flete": "101", "Detalle": "OK"},
        ])

        with self.assertRaisesRegex(OFProcessingError, "filas repetidas"):
            procesar_archivo_of(self.db, LOTE, archivo, "respuesta.xlsx")

    def test_rechaza_ordenes_de_flete_duplicadas_en_el_archivo(self):
        self._agregar_lote()
        archivo = excel_of_bytes([
            {"Estado": "OK", "Fila": 2, "Orden Flete": "100", "Detalle": "OK"},
            {"Estado": "OK", "Fila": 3, "Orden Flete": "100.0", "Detalle": "OK"},
        ])

        with self.assertRaisesRegex(OFProcessingError, "ordenes de flete duplicadas"):
            procesar_archivo_of(self.db, LOTE, archivo, "respuesta.xlsx")

    def test_rechaza_of_ya_registrada_en_otro_lote(self):
        self._agregar_lote()
        existente = crear_envio(
            e_lote="LOTE-ANTERIOR",
            e_estado="historico",
            e_fila_excel=2,
            e_orden_flete="272472119",
            e_resultado_of="OK",
        )
        self.db.add(existente)
        self.db.commit()
        archivo = excel_of_bytes([
            {"Estado": "OK", "Fila": 2, "Orden Flete": 272472119.0, "Detalle": "OK"},
            {"Estado": "ERROR", "Fila": 3, "Orden Flete": None, "Detalle": "Error"},
        ])

        with self.assertRaisesRegex(OFProcessingError, "Ya existen ordenes"):
            procesar_archivo_of(self.db, LOTE, archivo, "respuesta.xlsx")


class MatchingLoteArchivoTests(SQLiteTestCase):
    def test_matching_e_nombre_archivo_es_exacto_sin_importar_mayusculas_o_espacios(self):
        lotes = [
            {"lote": "LOTE-A", "nombre_archivo": "starken_A.csv"},
            {"lote": "LOTE-B", "nombre_archivo": "starken_B.csv"},
        ]

        encontrado = buscar_lote_por_nombre_archivo(lotes, "  STARKEN_b.CSV ")

        self.assertEqual(encontrado["lote"], "LOTE-B")
        self.assertIsNone(buscar_lote_por_nombre_archivo(lotes, "otro.csv"))

    def test_rechaza_archivo_of_asociado_a_otro_lote(self):
        self.db.add_all([
            crear_envio(e_lote="LOTE-A", e_nombre_archivo="starken_A.csv"),
            crear_envio(e_lote="LOTE-B", e_nombre_archivo="starken_B.csv"),
        ])
        self.db.commit()

        self.assertTrue(lote_coincide_con_archivo(self.db, "LOTE-A", "STARKEN_a.CSV"))
        self.assertFalse(lote_coincide_con_archivo(self.db, "LOTE-A", "starken_B.csv"))


class AvisosRegresionTests(SQLiteTestCase):
    def test_envio_historico_anulado_no_aparece_como_aviso_pendiente(self):
        anulado = crear_envio(
            e_estado="historico",
            e_resultado_of="OK",
            e_orden_flete="272472119",
            e_aviso_funcionario_estado="pendiente",
            e_anulado=True,
        )
        self.db.add(anulado)
        self.db.commit()

        lotes = avisos.obtener_lotes_con_avisos(self.db)
        cantidad = avisos.contar_lotes_avisos_pendientes(self.db)
        resumen = avisos.preparar_resumen_avisos([anulado])

        self.assertEqual(
            (lotes, cantidad),
            ([], 0),
            "Regla esperada incumplida: un envio historico anulado aparece como aviso pendiente",
        )
        self.assertEqual(resumen["total_lote"], 0)
        self.assertEqual(resumen["total_ok"], 0)
        self.assertEqual(resumen["total_error"], 0)
        self.assertEqual(resumen["funcionarios"], [])

        anulado.e_aviso_funcionario_estado = None
        self.db.commit()
        avisos.marcar_avisos_pendientes_lote(self.db, LOTE)
        self.db.refresh(anulado)
        self.assertIsNone(anulado.e_aviso_funcionario_estado)

    def test_fallo_en_tercer_correo_deja_dos_enviados_reales_y_bd_pendiente(self):
        self.db.add_all([
            crear_envio(
                e_estado="historico", e_fila_excel=2, e_resultado_of="OK",
                e_orden_flete="OF-A", e_aviso_funcionario_estado="pendiente",
                e_correo_destinatario="a@example.com", e_destinatario="Destino A",
            ),
            crear_envio(
                e_estado="historico", e_fila_excel=3, e_resultado_of="OK",
                e_orden_flete="OF-B", e_aviso_funcionario_estado="pendiente",
                e_correo_destinatario="b@example.com", e_destinatario="Destino B",
            ),
        ])
        self.db.commit()
        self.db.close()

        app = Flask(__name__)
        app.secret_key = "test"
        avisos_routes.registrar_rutas_avisos(app)
        salieron = []

        def correo_fake(destinatario, *args, **kwargs):
            if len(salieron) == 2:
                raise RuntimeError("fallo simulado en correo C")
            salieron.append(destinatario)

        with patch.object(avisos_routes, "SessionLocal", self.Session), patch.object(
            avisos, "correo_avisos_configurado", return_value=True
        ), patch.object(avisos, "_enviar_correo", side_effect=correo_fake):
            respuesta = app.test_client().post(
                f"/enviar_avisos_lote/{LOTE}",
                data={"correos": ["ana@example.com"]},
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.location.endswith(f"/avisos_lote/{LOTE}"))
        self.assertEqual(salieron, ["ana@example.com", "a@example.com"])

        verificacion = self.Session()
        try:
            estados = [
                fila[0]
                for fila in verificacion.query(Envio.e_aviso_funcionario_estado)
                .order_by(Envio.e_fila_excel.asc())
                .all()
            ]
            self.assertEqual(estados, ["pendiente", "pendiente"])
        finally:
            verificacion.close()


if __name__ == "__main__":
    unittest.main()
