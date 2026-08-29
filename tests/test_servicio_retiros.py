import os
import inspect as python_inspect
import re
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database.modelos import Base, Envio, PuntoRetiro, RetiroEnvio, RetiroStarken
from services.retiros import (
    RetiroConcurrenciaError,
    RetiroValidacionError,
    anular_retiro,
    confirmar_retiro,
    construir_codigo_retiro,
    obtener_envios_elegibles,
)


FECHA_SISTEMA = datetime(2026, 8, 29, 12, 0, 0)
FECHA_RETIRO = datetime(2026, 8, 29, 11, 30, 0)


class ServicioRetirosTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def activar_fk(dbapi_connection, _connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.local = PuntoRetiro(
            pr_codigo="MENSAJERIA_LOCAL",
            pr_nombre="Mensajeria local",
            pr_es_local=True,
            pr_incluir_metricas_locales=True,
            pr_activo=True,
        )
        self.academia = PuntoRetiro(
            pr_codigo="ACADEMIA",
            pr_nombre="Academia",
            pr_es_local=False,
            pr_incluir_metricas_locales=False,
            pr_activo=True,
        )
        self.db.add_all([self.local, self.academia])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _envio(self, nombre, **cambios):
        datos = {
            "e_remitente": f"Remitente {nombre}",
            "e_destinatario": nombre,
            "e_direccion": "Direccion",
            "e_comuna": "Comuna",
            "e_tipo_envio": "Domicilio",
            "e_bultos": 1,
            "e_kilos": 1,
            "e_estado": "historico",
            "e_orden_flete": f"OF-{nombre}",
            "e_fecha_of": datetime(2026, 8, 29, 8, 0, 0),
            "e_punto_retiro_id": self.local.id,
            "e_anulado": False,
        }
        datos.update(cambios)
        envio = Envio(**datos)
        self.db.add(envio)
        self.db.flush()
        return envio

    def _confirmar(self, ids, **opciones):
        with patch("services.retiros.ahora_chile", return_value=FECHA_SISTEMA):
            return confirmar_retiro(
                self.db,
                ids,
                opciones.pop("fecha_retiro", FECHA_RETIRO),
                **opciones,
            )

    def test_listado_incluye_solo_elegibles_y_evitar_n_mas_uno(self):
        temprano = self._envio("Temprano", e_fecha_of=datetime(2026, 8, 29, 7, 0, 0))
        mismo_horario = self._envio("Mismo", e_fecha_of=datetime(2026, 8, 29, 8, 0, 0))
        self._envio("SinOF", e_fecha_of=None)
        self._envio("SinOrden", e_orden_flete=" ")
        self._envio("Anulado", e_anulado=True)
        self._envio("Academia", e_punto_retiro_id=self.academia.id)
        self._envio("Legacy", e_punto_retiro_id=None)
        inactivo = PuntoRetiro(
            pr_codigo="LOCAL_INACTIVO",
            pr_nombre="Local inactivo",
            pr_es_local=True,
            pr_incluir_metricas_locales=True,
            pr_activo=False,
        )
        self.db.add(inactivo)
        self.db.flush()
        self._envio("Inactivo", e_punto_retiro_id=inactivo.id)
        retirado = self._envio("Retirado")
        retiro = RetiroStarken(
            rs_codigo="RET-EXISTENTE",
            punto_retiro_id=self.local.id,
            rs_fecha_retiro=FECHA_RETIRO,
            rs_fecha_confirmacion=FECHA_SISTEMA,
        )
        self.db.add(retiro)
        self.db.flush()
        self.db.add(RetiroEnvio(
            retiro_id=retiro.id,
            envio_id=retirado.id,
            re_bultos_snapshot=1,
            re_fecha_asociacion=FECHA_SISTEMA,
        ))
        self.db.commit()

        consultas = []

        def contar(_conn, _cursor, statement, _parameters, _context, _executemany):
            consultas.append(statement)

        event.listen(self.engine, "before_cursor_execute", contar)
        try:
            elegibles = obtener_envios_elegibles(self.db)
        finally:
            event.remove(self.engine, "before_cursor_execute", contar)

        self.assertEqual([item.envio_id for item in elegibles], [temprano.id, mismo_horario.id])
        self.assertEqual(len(consultas), 1)
        self.assertEqual(elegibles[0].punto_codigo, "MENSAJERIA_LOCAL")

    def test_confirmar_un_envio_persiste_snapshot_fechas_y_no_cambia_estado(self):
        envio = self._envio("Uno", e_bultos=4, e_estado="en_proceso")
        self.db.commit()
        retiro = self._confirmar(
            [envio.id],
            responsable=" Operador ",
            observacion=" Retiro real ",
        )

        asociacion = self.db.query(RetiroEnvio).one()
        self.db.refresh(envio)
        self.assertEqual(retiro.rs_fecha_retiro, FECHA_RETIRO)
        self.assertEqual(retiro.rs_fecha_confirmacion, FECHA_SISTEMA)
        self.assertEqual(retiro.rs_responsable, "Operador")
        self.assertEqual(asociacion.re_bultos_snapshot, 4)
        self.assertEqual(envio.e_estado, "en_proceso")
        envio.e_bultos = 9
        self.db.commit()
        self.assertEqual(asociacion.re_bultos_snapshot, 4)

    def test_confirmar_varios_y_volumen_no_crea_filas_por_bulto(self):
        envios = [self._envio(f"Masivo-{indice}", e_bultos=3) for indice in range(60)]
        self.db.commit()
        retiro = self._confirmar([envio.id for envio in envios])

        asociaciones = self.db.query(RetiroEnvio).filter(RetiroEnvio.retiro_id == retiro.id).all()
        self.assertEqual(len(asociaciones), 60)
        self.assertEqual(sum(item.re_bultos_snapshot for item in asociaciones), 180)

    def test_codigo_definitivo_usa_fecha_efectiva_e_id(self):
        envio = self._envio("Codigo")
        self.db.commit()
        retiro = self._confirmar([envio.id])
        self.assertRegex(retiro.rs_codigo, r"^RET-20260829-\d{6,}$")
        self.assertEqual(retiro.rs_codigo, construir_codigo_retiro(FECHA_RETIRO, retiro.id))

    def test_dos_retiros_mismo_dia_tienen_codigos_distintos_y_ordenables(self):
        primero = self._envio("Codigo-1")
        segundo = self._envio("Codigo-2")
        self.db.commit()
        retiro_1 = self._confirmar([primero.id])
        retiro_2 = self._confirmar([segundo.id])
        self.assertLess(retiro_1.id, retiro_2.id)
        self.assertLess(retiro_1.rs_codigo, retiro_2.rs_codigo)
        self.assertNotEqual(retiro_1.rs_codigo, retiro_2.rs_codigo)

    def test_generacion_no_depende_de_contar_filas(self):
        fuente = python_inspect.getsource(construir_codigo_retiro).lower()
        self.assertNotIn("count", fuente)
        self.assertNotIn("max", fuente)
        self.assertIn("retiro_id", fuente)

    def test_rechaza_seleccion_vacia_ids_duplicados_e_inexistentes(self):
        envio = self._envio("Validacion")
        self.db.commit()
        casos = [
            ([], "al menos un envio"),
            ([envio.id, envio.id], "duplicados"),
            ([999999], "No existen"),
        ]
        for ids, mensaje in casos:
            with self.subTest(ids=ids), self.assertRaisesRegex(RetiroValidacionError, mensaje):
                self._confirmar(ids)
        self.assertEqual(self.db.query(RetiroStarken).count(), 0)

    def test_rechaza_envio_no_elegible_y_mezcla_de_puntos(self):
        valido = self._envio("Valido")
        academia = self._envio("AcademiaConfirmar", e_punto_retiro_id=self.academia.id)
        self.db.commit()
        with self.assertRaisesRegex(RetiroValidacionError, "Mensajeria local"):
            self._confirmar([valido.id, academia.id])
        self.assertEqual(self.db.query(RetiroStarken).count(), 0)

    def test_rechaza_fecha_absurdamente_futura(self):
        envio = self._envio("Futuro")
        self.db.commit()
        with self.assertRaisesRegex(RetiroValidacionError, "futuro"):
            self._confirmar([envio.id], fecha_retiro=FECHA_SISTEMA + timedelta(hours=1))

    def test_doble_retiro_es_rechazado(self):
        envio = self._envio("Doble")
        self.db.commit()
        self._confirmar([envio.id])
        with self.assertRaisesRegex(RetiroValidacionError, "retiro vigente"):
            self._confirmar([envio.id])
        self.assertEqual(self.db.query(RetiroEnvio).count(), 1)

    def test_integrity_error_se_traduce_y_revierte(self):
        envio = self._envio("Integridad")
        self.db.commit()
        envio_id = envio.id
        error = IntegrityError("insert", {}, Exception("uq_retiro_envios_envio_vigente"))
        with patch.object(self.db, "flush", side_effect=error):
            with self.assertRaises(RetiroConcurrenciaError):
                self._confirmar([envio_id])
        self.assertEqual(self.db.query(RetiroStarken).count(), 0)
        self.assertEqual(self.db.query(RetiroEnvio).count(), 0)
        codigos = [codigo for (codigo,) in self.db.query(RetiroStarken.rs_codigo).all()]
        self.assertFalse(any(re.match(r"^TMP-RETIRO-", codigo) for codigo in codigos))

    def test_fallo_de_asociacion_revierte_retiro_completo(self):
        primero = self._envio("Rollback-1")
        segundo = self._envio("Rollback-2")
        self.db.commit()
        llamadas = {"cantidad": 0}

        def fallar_segunda(_mapper, _connection, _target):
            llamadas["cantidad"] += 1
            if llamadas["cantidad"] == 2:
                raise RuntimeError("fallo simulado")

        event.listen(RetiroEnvio, "before_insert", fallar_segunda)
        try:
            with self.assertRaisesRegex(RuntimeError, "fallo simulado"):
                self._confirmar([primero.id, segundo.id])
        finally:
            event.remove(RetiroEnvio, "before_insert", fallar_segunda)
        self.assertEqual(self.db.query(RetiroStarken).count(), 0)
        self.assertEqual(self.db.query(RetiroEnvio).count(), 0)
        codigos = [codigo for (codigo,) in self.db.query(RetiroStarken.rs_codigo).all()]
        self.assertFalse(any(re.match(r"^TMP-RETIRO-", codigo) for codigo in codigos))

    def test_anulacion_completa_libera_envio_y_no_borra_historia(self):
        envio = self._envio("Anulable")
        self.db.commit()
        retiro = self._confirmar([envio.id])
        fecha_anulacion = datetime(2026, 8, 29, 13, 0, 0)
        with patch("services.retiros.ahora_chile", return_value=fecha_anulacion):
            anulado = anular_retiro(self.db, retiro.id, " Error operativo ")

        asociacion = self.db.query(RetiroEnvio).one()
        self.assertTrue(anulado.rs_anulado)
        self.assertEqual(anulado.rs_fecha_anulacion, fecha_anulacion)
        self.assertEqual(anulado.rs_motivo_anulacion, "Error operativo")
        self.assertFalse(asociacion.re_vigente)
        self.assertEqual(self.db.query(RetiroStarken).count(), 1)
        self.assertEqual(self.db.query(RetiroEnvio).count(), 1)
        self.assertEqual([item.envio_id for item in obtener_envios_elegibles(self.db)], [envio.id])

    def test_anulacion_requiere_motivo_y_rechaza_doble_anulacion(self):
        envio = self._envio("Motivo")
        self.db.commit()
        retiro = self._confirmar([envio.id])
        with self.assertRaisesRegex(RetiroValidacionError, "obligatorio"):
            anular_retiro(self.db, retiro.id, " ")
        anular_retiro(self.db, retiro.id, "Duplicado")
        with self.assertRaisesRegex(RetiroValidacionError, "ya esta anulado"):
            anular_retiro(self.db, retiro.id, "Otra vez")

    def test_anular_retiro_inexistente_es_rechazado(self):
        with self.assertRaisesRegex(RetiroValidacionError, "no existe"):
            anular_retiro(self.db, 999999, "No existe")


if __name__ == "__main__":
    unittest.main()
