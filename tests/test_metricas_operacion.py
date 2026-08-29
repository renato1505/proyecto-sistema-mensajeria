import os
import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database.modelos import Base, Envio, PuntoRetiro, RetiroEnvio, RetiroStarken
from services.metricas_operacion import obtener_metricas_retiros_hoy
from services.retiros import anular_retiro, obtener_resumen_envios_elegibles


HOY = datetime(2026, 8, 29, 14, 30)


class MetricasOperacionTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.local = self._punto("MENSAJERIA_LOCAL", True)
        self.academia = self._punto("ACADEMIA", False)
        self.externo = self._punto("EXTERNO", False)
        self.db.commit()
        self.secuencia = 0

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _punto(self, codigo, incluir_metricas):
        punto = PuntoRetiro(
            pr_codigo=codigo,
            pr_nombre=codigo,
            pr_es_local=incluir_metricas,
            pr_incluir_metricas_locales=incluir_metricas,
            pr_activo=True,
        )
        self.db.add(punto)
        self.db.flush()
        return punto

    def _envio(self, nombre, punto=None, bultos=1, con_of=True):
        envio = Envio(
            e_remitente=f"Remitente {nombre}",
            e_destinatario=nombre,
            e_direccion="Direccion",
            e_comuna="Santiago",
            e_tipo_envio="Domicilio",
            e_bultos=bultos,
            e_kilos=1,
            e_estado="historico",
            e_orden_flete=f"OF-{nombre}" if con_of else None,
            e_fecha_of=HOY - timedelta(hours=2) if con_of else None,
            e_punto_retiro_id=(punto or self.local).id,
            e_anulado=False,
        )
        self.db.add(envio)
        self.db.flush()
        return envio

    def _retiro(self, nombre, fecha, bultos, punto=None, anulado=False, vigente=True):
        envio = self._envio(nombre, punto=punto, bultos=bultos)
        self.secuencia += 1
        retiro = RetiroStarken(
            rs_codigo=f"RET-METRICA-{self.secuencia}",
            punto_retiro_id=(punto or self.local).id,
            rs_fecha_retiro=fecha,
            rs_fecha_confirmacion=HOY,
            rs_anulado=anulado,
        )
        self.db.add(retiro)
        self.db.flush()
        asociacion = RetiroEnvio(
            retiro_id=retiro.id,
            envio_id=envio.id,
            re_bultos_snapshot=bultos,
            re_fecha_asociacion=HOY,
            re_vigente=vigente,
        )
        self.db.add(asociacion)
        self.db.flush()
        return envio, retiro, asociacion

    def test_sin_retiros_hoy_devuelve_ceros(self):
        metricas = obtener_metricas_retiros_hoy(self.db, HOY)
        self.assertEqual(metricas.envios, 0)
        self.assertEqual(metricas.bultos, 0)

    def test_suma_snapshots_y_envios_de_multiples_retiros_en_una_consulta(self):
        envio, _retiro, _asociacion = self._retiro("A", HOY.replace(hour=8), 10)
        self._retiro("B", HOY.replace(hour=12), 17)
        self.db.commit()
        envio.e_bultos = 999
        self.db.commit()
        consultas = []

        def contar(_conn, _cursor, statement, _parameters, _context, _executemany):
            consultas.append(statement)

        event.listen(self.engine, "before_cursor_execute", contar)
        try:
            metricas = obtener_metricas_retiros_hoy(self.db, HOY)
        finally:
            event.remove(self.engine, "before_cursor_execute", contar)

        self.assertEqual(metricas.envios, 2)
        self.assertEqual(metricas.bultos, 27)
        self.assertEqual(len(consultas), 1)

    def test_excluye_fechas_fuera_del_dia_anulados_no_vigentes_y_otros_puntos(self):
        self._retiro("Valido", HOY.replace(hour=0, minute=0), 4)
        self._retiro("Anterior", HOY.replace(hour=0, minute=0) - timedelta(seconds=1), 50)
        self._retiro("Futuro", HOY.replace(hour=0, minute=0) + timedelta(days=1), 50)
        self._retiro("Anulado", HOY, 50, anulado=True)
        self._retiro("NoVigente", HOY, 50, vigente=False)
        self._retiro("Academia", HOY, 50, punto=self.academia)
        self._retiro("Externo", HOY, 50, punto=self.externo)
        self.db.commit()

        metricas = obtener_metricas_retiros_hoy(self.db, HOY)
        self.assertEqual(metricas.envios, 1)
        self.assertEqual(metricas.bultos, 4)

    def test_anular_retiro_actualiza_kpi_sin_agregado_persistido(self):
        _envio, retiro, _asociacion = self._retiro("Anulable", HOY, 7)
        self.db.commit()
        self.assertEqual(obtener_metricas_retiros_hoy(self.db, HOY).bultos, 7)

        anular_retiro(self.db, retiro.id, "Correccion QA")

        metricas = obtener_metricas_retiros_hoy(self.db, HOY)
        self.assertEqual(metricas.envios, 0)
        self.assertEqual(metricas.bultos, 0)

    def test_resumen_elegibles_reutiliza_reglas_y_agrega_en_sql(self):
        self._envio("Elegible-1", bultos=3)
        self._envio("Elegible-2", bultos=6)
        self._envio("Sin-OF", bultos=20, con_of=False)
        self._envio("Academia", punto=self.academia, bultos=20)
        self.db.commit()
        self.assertEqual(obtener_resumen_envios_elegibles(self.db), {"envios": 2, "bultos": 9})


if __name__ == "__main__":
    unittest.main()
