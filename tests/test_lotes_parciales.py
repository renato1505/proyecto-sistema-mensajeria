import csv
import io
import os
import unittest
from datetime import datetime
from unittest.mock import patch


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.modelos import Base, Envio
from routes import starken_lotes


FECHA_LOTE = datetime(2026, 8, 24, 15, 30, 0)


def envio_pendiente(destinatario, **cambios):
    datos = {
        "e_remitente": "Funcionario",
        "e_correo_remitente": "funcionario@example.com",
        "e_division": "DPGP",
        "e_centro_costo": "100",
        "e_destinatario": destinatario,
        "e_rut_destinatario": "12345678-9",
        "e_direccion": "Direccion 123",
        "e_comuna": "Santiago",
        "e_region": "Metropolitana",
        "e_telefono_destinatario": "56912345678",
        "e_tipo_envio": "Domicilio",
        "e_codigo_agencia": None,
        "e_bultos": 1,
        "e_kilos": 2,
        "e_estado": "pendiente",
        "e_anulado": False,
    }
    datos.update(cambios)
    return Envio(**datos)


class LotesParcialesTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.app = Flask(__name__)
        self.app.secret_key = "test"
        starken_lotes.registrar_rutas_starken_lotes(self.app)
        self.client = self.app.test_client()

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _guardar(self, *envios):
        db = self.Session()
        db.add_all(envios)
        db.commit()
        ids = [envio.id for envio in envios]
        db.close()
        return ids

    def _generar(self, ids):
        with patch.object(starken_lotes, "SessionLocal", self.Session), patch.object(
            starken_lotes, "ahora_chile", return_value=FECHA_LOTE
        ), patch.object(starken_lotes, "guardar_respaldo_lote"):
            return self.client.post(
                "/generar_excel",
                data={"accion": "descargar", "envio_ids": [str(envio_id) for envio_id in ids]},
            )

    def _envios(self):
        db = self.Session()
        try:
            return [
                {
                    "id": envio.id,
                    "destinatario": envio.e_destinatario,
                    "estado": envio.e_estado,
                    "lote": envio.e_lote,
                    "fila": envio.e_fila_excel,
                    "fecha": envio.e_fecha_exportacion,
                }
                for envio in db.query(Envio).order_by(Envio.id.asc()).all()
            ]
        finally:
            db.close()

    def _mensajes_flash(self):
        with self.client.session_transaction() as sesion:
            return [mensaje for _, mensaje in sesion.get("_flashes", [])]

    def test_subconjunto_genera_csv_y_muta_solo_seleccionados_en_orden_id(self):
        ids = self._guardar(
            envio_pendiente("A", e_bultos=2, e_kilos=3),
            envio_pendiente("B"),
            envio_pendiente("C", e_bultos=4, e_kilos=5),
        )

        respuesta = self._generar([ids[2], ids[0]])

        self.assertEqual(respuesta.status_code, 200)
        filas = list(csv.reader(io.StringIO(respuesta.data.decode("cp1252")), delimiter=";"))
        self.assertEqual([fila[3] for fila in filas[1:]], ["A", "C"])
        guardados = self._envios()
        self.assertEqual([fila["estado"] for fila in guardados], ["en_proceso", "pendiente", "en_proceso"])
        self.assertEqual([fila["fila"] for fila in guardados], [2, None, 3])
        self.assertIsNone(guardados[1]["lote"])
        self.assertIsNone(guardados[1]["fecha"])
        self.assertEqual(guardados[0]["lote"], guardados[2]["lote"])

    def test_seleccion_vacia_es_rechazada(self):
        self._guardar(envio_pendiente("A"))
        respuesta = self._generar([])
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(any("seleccionar" in mensaje.lower() for mensaje in self._mensajes_flash()))
        self.assertEqual(self._envios()[0]["estado"], "pendiente")

    def test_id_inexistente_es_rechazado_sin_mutaciones(self):
        ids = self._guardar(envio_pendiente("A"))
        respuesta = self._generar([ids[0], 999999])
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(any("no existen" in mensaje.lower() for mensaje in self._mensajes_flash()))
        self.assertEqual(self._envios()[0]["estado"], "pendiente")

    def test_id_duplicado_es_rechazado_sin_mutaciones(self):
        ids = self._guardar(envio_pendiente("A"))
        respuesta = self._generar([ids[0], ids[0]])
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(any("duplicados" in mensaje.lower() for mensaje in self._mensajes_flash()))
        self.assertEqual(self._envios()[0]["estado"], "pendiente")

    def test_envio_que_ya_no_esta_pendiente_es_rechazado(self):
        ids = self._guardar(envio_pendiente("A", e_estado="en_proceso", e_lote="LOTE-ANTERIOR"))
        respuesta = self._generar(ids)
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(any("ya no estan pendientes" in mensaje.lower() for mensaje in self._mensajes_flash()))
        self.assertEqual(self._envios()[0]["lote"], "LOTE-ANTERIOR")

    def test_envio_anulado_manipulado_desde_peticion_es_rechazado(self):
        ids = self._guardar(envio_pendiente("Anulado", e_anulado=True))
        respuesta = self._generar(ids)
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(any("ya no estan pendientes" in mensaje.lower() for mensaje in self._mensajes_flash()))
        self.assertEqual(self._envios()[0]["estado"], "pendiente")

    def test_agencia_invalida_seleccionada_bloquea_lote_completo(self):
        ids = self._guardar(
            envio_pendiente("Valido"),
            envio_pendiente("Agencia invalida", e_tipo_envio="Agencia", e_codigo_agencia=None),
        )
        respuesta = self._generar(ids)
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(any("agencia sin codigo" in mensaje.lower() for mensaje in self._mensajes_flash()))
        self.assertEqual([fila["estado"] for fila in self._envios()], ["pendiente", "pendiente"])

    def test_agencia_invalida_no_seleccionada_no_bloquea(self):
        ids = self._guardar(
            envio_pendiente("Valido"),
            envio_pendiente("Agencia invalida", e_tipo_envio="Agencia", e_codigo_agencia=None),
        )
        respuesta = self._generar([ids[0]])
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([fila["estado"] for fila in self._envios()], ["en_proceso", "pendiente"])


if __name__ == "__main__":
    unittest.main()
