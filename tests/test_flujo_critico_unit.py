import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from tests.entorno_aislado import preparar_entorno_pruebas

preparar_entorno_pruebas()

import csv
import io
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
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
from routes import envios as envios_routes
from routes import starken_lotes
from services import avisos
from services.lotes import (
    buscar_lote_por_nombre_archivo,
    lote_coincide_con_archivo,
    obtener_envios_seleccionados_para_lote,
)
from services.of_processor import (
    OFProcessingError,
    procesar_archivo_of,
    resultado_h2h_ambiguo,
)
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

    def test_of_ok_asigna_una_fecha_unica_y_error_permanece_sin_fecha(self):
        envio_2, envio_3 = self._agregar_lote()
        fecha_exportacion = datetime(2026, 8, 20, 10, 0, 0)
        fecha_of = datetime(2026, 8, 28, 15, 30, 0)
        envio_2.e_fecha_exportacion = fecha_exportacion
        envio_3.e_fecha_exportacion = fecha_exportacion
        self.db.commit()
        archivo = excel_of_bytes([
            {"Estado": "OK", "Fila": 2, "Orden Flete": "100", "Detalle": "OK"},
            {"Estado": "ERROR", "Fila": 3, "Orden Flete": None, "Detalle": "Error"},
        ])

        with patch("services.of_processor.ahora_chile", return_value=fecha_of):
            procesar_archivo_of(self.db, LOTE, archivo, "respuesta.xlsx")

        self.db.refresh(envio_2)
        self.db.refresh(envio_3)
        self.assertEqual(envio_2.e_fecha_of, fecha_of)
        self.assertNotEqual(envio_2.e_fecha_of, envio_2.e_fecha_exportacion)
        self.assertIsNone(envio_3.e_fecha_of)

    def test_todas_las_filas_ok_del_archivo_comparten_hora_de_procesamiento(self):
        envio_2, envio_3 = self._agregar_lote()
        fecha_of = datetime(2026, 8, 28, 16, 0, 0)
        archivo = excel_of_bytes([
            {"Estado": "OK", "Fila": 2, "Orden Flete": "100", "Detalle": "OK"},
            {"Estado": "OK", "Fila": 3, "Orden Flete": "101", "Detalle": "OK"},
        ])

        with patch("services.of_processor.ahora_chile", return_value=fecha_of) as reloj:
            procesar_archivo_of(self.db, LOTE, archivo, "respuesta.xlsx")

        self.db.refresh(envio_2)
        self.db.refresh(envio_3)
        self.assertEqual(envio_2.e_fecha_of, fecha_of)
        self.assertEqual(envio_3.e_fecha_of, fecha_of)
        reloj.assert_called_once_with()

    def test_of_error_y_reintento_posterior_ok_asigna_fecha_del_reintento(self):
        envio_2, envio_3 = self._agregar_lote()
        primer_archivo = excel_of_bytes([
            {"Estado": "ERROR", "Fila": 2, "Orden Flete": None, "Detalle": "Temporal"},
            {"Estado": "OK", "Fila": 3, "Orden Flete": "103", "Detalle": "OK"},
        ])
        primera_fecha = datetime(2026, 8, 28, 10, 0, 0)
        with patch("services.of_processor.ahora_chile", return_value=primera_fecha):
            procesar_archivo_of(self.db, LOTE, primer_archivo, "respuesta.xlsx")
        self.db.refresh(envio_2)
        self.assertIsNone(envio_2.e_fecha_of)

        segundo_archivo = excel_of_bytes([
            {"Estado": "OK", "Fila": 2, "Orden Flete": "102", "Detalle": "OK"},
        ])
        segunda_fecha = datetime(2026, 8, 28, 11, 0, 0)
        with patch("services.of_processor.ahora_chile", return_value=segunda_fecha):
            procesar_archivo_of(self.db, LOTE, segundo_archivo, "respuesta.xlsx")

        self.db.refresh(envio_2)
        self.assertEqual(envio_2.e_estado, "historico")
        self.assertEqual(envio_2.e_fecha_of, segunda_fecha)

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


class CancelacionH2HTests(SQLiteTestCase):
    def setUp(self):
        super().setUp()
        from utils.csrf import validar_csrf

        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY="h2h-test-local")
        self.app.before_request(validar_csrf)
        starken_lotes.registrar_rutas_starken_lotes(self.app)
        envios_routes.registrar_rutas_envios(self.app)
        self.client = self.app.test_client()
        with self.client.session_transaction() as sesion:
            sesion["_csrf_token"] = "csrf-h2h-test"

    def _guardar(self, *envios):
        self.db.add_all(envios)
        self.db.commit()
        return [envio.id for envio in envios]

    def _snapshot(self):
        # Sesion nueva: compara todas las columnas realmente persistidas.
        with self.Session() as db:
            return [
                {columna.name: getattr(envio, columna.name) for columna in Envio.__table__.columns}
                for envio in db.query(Envio).order_by(Envio.id.asc()).all()
            ]

    def _cancelar(self, lote=LOTE, **datos):
        with patch.object(starken_lotes, "SessionLocal", self.Session):
            return self.client.post(
                f"/cancelar_lote/{lote}",
                data={"csrf_token": "csrf-h2h-test", **datos},
            )

    def _ambiguo(self, **cambios):
        datos = {
            "e_resultado_of": "ERROR",
            "e_detalle_of": "Error al enviar fila 2 a servicio H2H",
            "e_fecha_exportacion": datetime(2026, 8, 22, 12, 0),
            "e_estado_correo": "enviado",
        }
        datos.update(cambios)
        return crear_envio(**datos)

    def test_regla_usa_resultado_y_h2h_sin_depender_de_of_vacia(self):
        casos = [
            ("ERROR", "Error al enviar fila 2 a servicio H2H", None, True),
            (" error ", "Error: servicio h2h no responde", "OF-FICTICIA", True),
            ("ERROR", "Timeout H2H: resultado desconocido", None, True),
            ("ERROR", "Codigo de agencia invalido", None, False),
            ("ERROR", "Error HTTP sin respuesta", None, False),
            ("ERROR", "Error H2HTTP", None, False),
            ("OK", "Procesado por servicio H2H", "OF-FICTICIA", False),
            (None, None, None, False),
            ("ERROR", None, None, False),
        ]
        for resultado, detalle, of, esperado in casos:
            with self.subTest(resultado=resultado, detalle=detalle, of=of):
                envio = crear_envio(e_resultado_of=resultado, e_detalle_of=detalle, e_orden_flete=of)
                self.assertEqual(resultado_h2h_ambiguo(envio), esperado)

    def test_ambiguo_bloquea_y_conserva_todas_las_columnas(self):
        self._guardar(self._ambiguo())
        antes = self._snapshot()
        respuesta = self._cancelar()
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.location.endswith("/en_proceso"))
        self.assertEqual(self._snapshot(), antes)
        with self.client.session_transaction() as sesion:
            mensajes = " ".join(mensaje for _, mensaje in sesion["_flashes"])
        self.assertIn("requiere verificación de OF", mensajes)
        self.assertIn("evitar duplicaciones", mensajes)

    def test_un_ambiguo_bloquea_lote_completo_incluso_otras_etapas(self):
        self._guardar(
            crear_envio(e_fila_excel=2),
            self._ambiguo(e_fila_excel=3),
            crear_envio(e_fila_excel=4, e_resultado_of="ERROR", e_detalle_of="Direccion invalida"),
            crear_envio(e_fila_excel=5, e_estado="historico", e_resultado_of="OK", e_orden_flete="OF-DEMO"),
        )
        antes = self._snapshot()
        self._cancelar()
        self.assertEqual(self._snapshot(), antes)

    def test_repetir_cancelacion_bloqueada_no_altera_registros(self):
        self._guardar(self._ambiguo(), crear_envio(e_fila_excel=3))
        antes = self._snapshot()
        for _ in range(3):
            self._cancelar()
            self.assertEqual(self._snapshot(), antes)

    def test_lote_sin_resultados_conserva_cancelacion_permitida(self):
        self._guardar(crear_envio(), crear_envio(e_fila_excel=3))
        self._cancelar()
        for envio in self._snapshot():
            self.assertEqual(envio["e_estado"], "pendiente")
            for campo in ("e_lote", "e_fila_excel", "e_resultado_of", "e_detalle_of", "e_orden_flete"):
                self.assertIsNone(envio[campo])

    def test_error_no_h2h_se_cancela_sin_modificar_historico(self):
        self._guardar(
            crear_envio(e_resultado_of="ERROR", e_detalle_of="Codigo de agencia invalido"),
            crear_envio(e_fila_excel=3, e_estado="historico", e_resultado_of="OK", e_orden_flete="OF-DEMO"),
        )
        historico = self._snapshot()[1]
        self._cancelar()
        despues = self._snapshot()
        self.assertEqual(despues[0]["e_estado"], "pendiente")
        self.assertEqual(despues[1], historico)

    def test_post_directo_no_permite_forzar_cancelacion_ambigua(self):
        self._guardar(self._ambiguo(e_orden_flete="OF-POR-VERIFICAR"))
        antes = self._snapshot()
        self._cancelar(forzar="1", e_resultado_of="OK", e_detalle_of="", e_estado="pendiente")
        self.assertEqual(self._snapshot(), antes)

    def test_ambiguo_de_otro_lote_no_bloquea_lote_valido(self):
        self._guardar(crear_envio(), self._ambiguo(e_lote="LOTE-OTRO"))
        otro = self._snapshot()[1]
        self._cancelar()
        despues = self._snapshot()
        self.assertEqual(despues[0]["e_estado"], "pendiente")
        self.assertEqual(despues[1], otro)

    def test_ambiguo_persistido_fuera_de_en_proceso_tambien_bloquea(self):
        self._guardar(crear_envio(), self._ambiguo(e_fila_excel=3, e_estado="historico"))
        antes = self._snapshot()
        self._cancelar()
        self.assertEqual(self._snapshot(), antes)

    def test_of_importada_con_h2h_impide_cancelar_y_generar_nuevo_lote(self):
        ids = self._guardar(crear_envio(), crear_envio(e_fila_excel=3))
        archivo = excel_of_bytes([
            {"estado": "ERROR", "fila": 2, "orden flete": "", "detalle": "Error al enviar fila 2 a servicio H2H"},
            {"estado": "ERROR", "fila": 3, "orden flete": "", "detalle": "Codigo de agencia invalido"},
        ])
        procesar_archivo_of(self.db, LOTE, archivo, "of_demo.xlsx")
        antes = self._snapshot()
        self._cancelar()
        self.assertEqual(self._snapshot(), antes)
        with self.Session() as db:
            with self.assertRaisesRegex(ValueError, "ya no estan pendientes"):
                obtener_envios_seleccionados_para_lote(db, [str(identificador) for identificador in ids])

    def test_cancelacion_sigue_exigiendo_csrf(self):
        self._guardar(crear_envio())
        antes = self._snapshot()
        with patch.object(starken_lotes, "SessionLocal", self.Session):
            respuesta = self.client.post(f"/cancelar_lote/{LOTE}")
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self._snapshot(), antes)


    def _comprobar_reimportacion_bloqueada(self, estado, detalle):
        ids = self._guardar(
            crear_envio(e_resultado_of="ERROR", e_detalle_of="Error ordinario"),
            self._ambiguo(e_fila_excel=3),
        )
        antes = self._snapshot()
        archivo = excel_of_bytes([
            {"estado": "OK", "fila": 2, "orden flete": "OF-DEMO-2", "detalle": "OK"},
            {"estado": estado, "fila": 3, "orden flete": "OF-DEMO-3" if estado == "OK" else "", "detalle": detalle},
        ])
        with self.assertRaisesRegex(OFProcessingError, "antecedente H2H ambiguo"):
            procesar_archivo_of(self.db, LOTE, archivo, "respuesta_demo.xlsx")
        self.assertFalse(self.db.in_transaction())
        self.assertEqual(self._snapshot(), antes)
        self._cancelar()
        self.assertEqual(self._snapshot(), antes)
        with patch.object(starken_lotes, "SessionLocal", self.Session), patch.object(
            starken_lotes, "guardar_respaldo_lote"
        ) as respaldo, patch.object(starken_lotes, "enviar_archivo_starken") as enviar:
            respuesta = self.client.post(
                "/generar_excel",
                data={"csrf_token": "csrf-h2h-test", "accion": "descargar", "envio_ids": ids},
            )
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.location.endswith("/envios"))
        respaldo.assert_not_called()
        enviar.assert_not_called()
        self.assertEqual(self._snapshot(), antes)

    def test_reimportacion_error_ordinario_no_borra_antecedente_h2h(self):
        self._comprobar_reimportacion_bloqueada("ERROR", "Codigo de agencia invalido")

    def test_reimportacion_detalle_vacio_no_borra_antecedente_h2h(self):
        self._comprobar_reimportacion_bloqueada("ERROR", "")

    def test_reimportacion_ok_no_concilia_automaticamente_h2h(self):
        self._comprobar_reimportacion_bloqueada("OK", "Procesado")

    def test_post_carga_manual_bloquea_ok_posterior_sin_enviar_respaldo(self):
        self._guardar(self._ambiguo())
        antes = self._snapshot()
        archivo = excel_of_bytes([
            {"estado": "OK", "fila": 2, "orden flete": "OF-DEMO-2", "detalle": "OK"},
        ])
        db = self.Session()
        with patch.object(starken_lotes, "SessionLocal", return_value=db), patch.object(
            starken_lotes, "_enviar_respaldo_post_of"
        ) as respaldo, patch.object(db, "close", wraps=db.close) as cerrar:
            respuesta = self.client.post(
                f"/cargar_of/{LOTE}",
                data={"csrf_token": "csrf-h2h-test", "archivo_of": (archivo, "respuesta_demo.xlsx")},
            )
            cerrar.assert_called_once()
        self.assertFalse(db.in_transaction())
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.location.endswith("/en_proceso"))
        respaldo.assert_not_called()
        self.assertEqual(self._snapshot(), antes)
        with self.client.session_transaction() as sesion:
            self.assertTrue(any("antecedente H2H ambiguo" in mensaje for _, mensaje in sesion["_flashes"]))

    def test_post_of_correo_bloquea_respuesta_y_conserva_evidencia(self):
        self._guardar(self._ambiguo())
        antes = self._snapshot()
        contenido = excel_of_bytes([
            {"estado": "ERROR", "fila": 2, "orden flete": "", "detalle": "Otro error"},
        ]).getvalue()
        db = self.Session()
        with patch.object(starken_lotes, "SessionLocal", return_value=db), patch.object(
            starken_lotes, "descargar_adjunto_of", return_value=("respuesta_demo.xlsx", contenido, NOMBRE_CSV)
        ), patch.object(starken_lotes, "_enviar_respaldo_post_of") as respaldo, patch.object(
            db, "close", wraps=db.close
        ) as cerrar:
            respuesta = self.client.post(
                "/procesar_of_correo",
                data={"csrf_token": "csrf-h2h-test", "lote": LOTE, "uid": "demo", "indice_adjunto": "0"},
            )
            cerrar.assert_called_once()
        self.assertFalse(db.in_transaction())
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.location.endswith("/of_correo?buscar=1"))
        respaldo.assert_not_called()
        self.assertEqual(self._snapshot(), antes)

    def _eliminar(self, envio_id, **datos):
        with patch.object(envios_routes, "SessionLocal", self.Session):
            return self.client.post(
                f"/eliminar_envio/{envio_id}", data={"csrf_token": "csrf-h2h-test", **datos}
            )

    def test_eliminacion_directa_h2h_no_puede_forzarse(self):
        ids = self._guardar(self._ambiguo())
        antes = self._snapshot()
        respuesta = self._eliminar(ids[0], forzar="1", e_estado="pendiente", e_resultado_of="OK")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._snapshot(), antes)

    def test_eliminacion_h2h_pendiente_tambien_conserva_evidencia(self):
        ids = self._guardar(self._ambiguo(e_estado="pendiente", e_lote=None))
        antes = self._snapshot()
        self._eliminar(ids[0])
        self.assertEqual(self._snapshot(), antes)

    def test_eliminacion_rechaza_etapas_y_huellas_operativas(self):
        casos = [
            {"e_estado": "en_proceso"}, {"e_estado": "historico"},
            {"e_lote": LOTE}, {"e_fila_excel": 2},
            {"e_fecha_exportacion": datetime(2026, 8, 22)},
            {"e_resultado_of": "ERROR"}, {"e_detalle_of": "Detalle previo"},
            {"e_orden_flete": "OF-DEMO"}, {"e_fecha_of": datetime(2026, 8, 22)},
            {"e_nombre_archivo": NOMBRE_CSV}, {"e_estado_correo": "enviado"},
            {"e_correo_destino": "demo@example.invalid"},
            {"e_fecha_envio_correo": datetime(2026, 8, 22)},
            {"e_aviso_funcionario_estado": "pendiente"},
            {"e_fecha_aviso_funcionario": datetime(2026, 8, 22)},
            {"e_anulado": True},
        ]
        for cambios in casos:
            with self.subTest(cambios=cambios):
                envio = crear_envio(e_estado="pendiente", e_lote=None, e_fila_excel=None, e_nombre_archivo=None)
                for campo, valor in cambios.items():
                    setattr(envio, campo, valor)
                ids = self._guardar(envio)
                antes = self._snapshot()
                self._eliminar(ids[0])
                self.assertEqual(self._snapshot(), antes)

    def test_eliminacion_rechaza_asociaciones_sin_depender_de_fk(self):
        from database.modelos import AvisoEnvio, ExcepcionEnvio, RetiroEnvio

        # Estas consultas deben bloquear aun si el estado legacy indica pendiente.
        for modelo in (RetiroEnvio, AvisoEnvio, ExcepcionEnvio):
            with self.subTest(modelo=modelo.__name__):
                ids = self._guardar(crear_envio(
                    e_estado="pendiente", e_lote=None, e_fila_excel=None, e_nombre_archivo=None
                ))
                if modelo is AvisoEnvio:
                    asociacion = modelo(
                        envio_id=ids[0], av_tipo="FUNCIONARIO", av_estado="CANCELADO",
                        av_clave_idempotencia=f"ENVIO-{ids[0]}-FUNCIONARIO",
                    )
                elif modelo is ExcepcionEnvio:
                    asociacion = modelo(envio_id=ids[0], x_tipo="demo")
                else:
                    # SQLite de esta fixture no activa FK: demuestra validacion de backend.
                    asociacion = modelo(envio_id=ids[0], retiro_id=999, re_bultos_snapshot=1, re_vigente=False)
                self.db.add(asociacion)
                self.db.commit()
                antes = self._snapshot()
                self._eliminar(ids[0])
                self.assertEqual(self._snapshot(), antes)
                self.assertIsNotNone(self.db.get(modelo, asociacion.id))

    def test_eliminacion_pendiente_sin_operaciones_sigue_permitida(self):
        ids = self._guardar(crear_envio(
            e_estado="pendiente", e_lote=None, e_fila_excel=None, e_nombre_archivo=None
        ))
        respuesta = self._eliminar(ids[0])
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._snapshot(), [])

    def test_reimportacion_sin_h2h_sigue_procesando_ok(self):
        self._guardar(crear_envio(e_resultado_of="ERROR", e_detalle_of="Error ordinario"))
        archivo = excel_of_bytes([
            {"estado": "OK", "fila": 2, "orden flete": "OF-DEMO-2", "detalle": "OK"},
        ])
        resultado = procesar_archivo_of(self.db, LOTE, archivo, "respuesta_demo.xlsx")
        self.assertEqual(resultado["total_ok"], 1)
        self.assertEqual(self._snapshot()[0]["e_estado"], "historico")

    def test_excepcion_al_cancelar_revierte_todo_y_cierra_sesion(self):
        self._guardar(crear_envio(), crear_envio(e_fila_excel=3))
        antes = self._snapshot()
        db = self.Session()

        def fallar_despues_de_flush():
            db.flush()
            raise RuntimeError("Fallo de commit simulado")

        with patch.object(starken_lotes, "SessionLocal", return_value=db), patch.object(
            db, "commit", side_effect=fallar_despues_de_flush
        ), patch.object(db, "close", wraps=db.close) as cerrar:
            with self.assertRaisesRegex(RuntimeError, "Fallo de commit"):
                self.client.post(f"/cancelar_lote/{LOTE}", data={"csrf_token": "csrf-h2h-test"})
            cerrar.assert_called_once()
        self.assertFalse(db.in_transaction())
        self.assertEqual(self._snapshot(), antes)

    def test_excepcion_al_eliminar_revierte_borrado_y_cierra_sesion(self):
        ids = self._guardar(crear_envio(
            e_estado="pendiente", e_lote=None, e_fila_excel=None, e_nombre_archivo=None
        ))
        antes = self._snapshot()
        db = self.Session()

        def fallar_despues_de_flush():
            db.flush()
            raise RuntimeError("Fallo de commit simulado")

        with patch.object(envios_routes, "SessionLocal", return_value=db), patch.object(
            db, "commit", side_effect=fallar_despues_de_flush
        ), patch.object(db, "close", wraps=db.close) as cerrar:
            with self.assertRaisesRegex(RuntimeError, "Fallo de commit"):
                self.client.post(f"/eliminar_envio/{ids[0]}", data={"csrf_token": "csrf-h2h-test"})
            cerrar.assert_called_once()
        self.assertFalse(db.in_transaction())
        self.assertEqual(self._snapshot(), antes)


    def test_csv_rechaza_h2h_aunque_figure_pendiente(self):
        ids = self._guardar(self._ambiguo(e_estado="pendiente"))
        antes = self._snapshot()
        with patch.object(starken_lotes, "SessionLocal", self.Session), patch.object(
            starken_lotes, "guardar_respaldo_lote"
        ) as respaldo, patch.object(starken_lotes, "enviar_archivo_starken") as enviar:
            respuesta = self.client.post(
                "/generar_excel",
                data={"csrf_token": "csrf-h2h-test", "accion": "descargar", "envio_ids": ids},
            )
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.location.endswith("/envios"))
        respaldo.assert_not_called()
        enviar.assert_not_called()
        self.assertEqual(self._snapshot(), antes)

    def test_excepcion_importacion_permitida_revierte_todo_y_cierra_sesion(self):
        self._guardar(crear_envio(), crear_envio(e_fila_excel=3))
        antes = self._snapshot()
        archivo = excel_of_bytes([
            {"estado": "OK", "fila": 2, "orden flete": "OF-DEMO-2", "detalle": "OK"},
            {"estado": "ERROR", "fila": 3, "orden flete": "", "detalle": "Error ordinario"},
        ])
        db = self.Session()

        def fallar_despues_de_flush():
            db.flush()
            raise RuntimeError("Fallo de commit simulado")

        with patch.object(starken_lotes, "SessionLocal", return_value=db), patch.object(
            db, "commit", side_effect=fallar_despues_de_flush
        ), patch.object(db, "close", wraps=db.close) as cerrar, patch.object(
            starken_lotes, "_enviar_respaldo_post_of"
        ) as respaldo, patch.object(starken_lotes.logger, "exception"):
            respuesta = self.client.post(
                f"/cargar_of/{LOTE}",
                data={"csrf_token": "csrf-h2h-test", "archivo_of": (archivo, "respuesta_demo.xlsx")},
            )
            cerrar.assert_called_once()
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(db.in_transaction())
        respaldo.assert_not_called()
        self.assertEqual(self._snapshot(), antes)


if __name__ == "__main__":
    unittest.main()
