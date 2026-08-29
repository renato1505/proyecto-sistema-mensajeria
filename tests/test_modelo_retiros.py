import os
import unittest
from datetime import datetime

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database.modelos import Base, Envio, PuntoRetiro, RetiroEnvio, RetiroStarken


class ModeloRetiroTest(unittest.TestCase):
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
        self.punto = PuntoRetiro(
            pr_codigo="MENSAJERIA_LOCAL",
            pr_nombre="Mensajeria local",
            pr_es_local=True,
            pr_incluir_metricas_locales=True,
            pr_activo=True,
        )
        self.db.add(self.punto)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _envio(self, nombre, bultos=1):
        envio = Envio(
            e_remitente="Remitente",
            e_destinatario=nombre,
            e_direccion="Direccion",
            e_comuna="Comuna",
            e_tipo_envio="Domicilio",
            e_bultos=bultos,
            e_kilos=bultos,
            e_estado="historico",
            e_anulado=False,
        )
        self.db.add(envio)
        self.db.flush()
        return envio

    def _retiro(self, codigo):
        retiro = RetiroStarken(
            rs_codigo=codigo,
            punto_retiro_id=self.punto.id,
            rs_fecha_retiro=datetime(2026, 8, 29, 10, 0, 0),
            rs_fecha_confirmacion=datetime(2026, 8, 29, 10, 5, 0),
        )
        self.db.add(retiro)
        self.db.flush()
        return retiro

    def test_retiro_contiene_muchos_envios_y_snapshot_persiste(self):
        primero = self._envio("Primero", 2)
        segundo = self._envio("Segundo", 5)
        retiro = self._retiro("RET-001")
        retiro.asociaciones.extend([
            RetiroEnvio(envio=primero, re_bultos_snapshot=primero.e_bultos),
            RetiroEnvio(envio=segundo, re_bultos_snapshot=segundo.e_bultos),
        ])
        self.db.commit()

        self.assertEqual(len(retiro.asociaciones), 2)
        self.assertEqual([item.re_bultos_snapshot for item in retiro.asociaciones], [2, 5])
        self.assertFalse(retiro.rs_anulado)
        self.assertTrue(all(item.re_vigente for item in retiro.asociaciones))
        segundo.e_bultos = 8
        self.db.commit()
        self.assertEqual(retiro.asociaciones[1].re_bultos_snapshot, 5)

    def test_snapshot_menor_a_uno_es_rechazado(self):
        envio = self._envio("Invalido")
        retiro = self._retiro("RET-002")
        self.db.add(RetiroEnvio(retiro=retiro, envio=envio, re_bultos_snapshot=0))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_envio_no_admite_dos_asociaciones_vigentes(self):
        envio = self._envio("Unico")
        primero = self._retiro("RET-003")
        segundo = self._retiro("RET-004")
        self.db.add(RetiroEnvio(retiro=primero, envio=envio, re_bultos_snapshot=1))
        self.db.commit()
        self.db.add(RetiroEnvio(retiro=segundo, envio=envio, re_bultos_snapshot=1))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_asociacion_no_vigente_permite_nueva_asociacion(self):
        envio = self._envio("Reasociable")
        anterior = self._retiro("RET-005")
        nuevo = self._retiro("RET-006")
        self.db.add(RetiroEnvio(
            retiro=anterior,
            envio=envio,
            re_bultos_snapshot=1,
            re_vigente=False,
        ))
        self.db.commit()
        self.db.add(RetiroEnvio(retiro=nuevo, envio=envio, re_bultos_snapshot=1))
        self.db.commit()

        asociaciones = self.db.query(RetiroEnvio).filter(RetiroEnvio.envio_id == envio.id).all()
        self.assertEqual(len(asociaciones), 2)
        self.assertEqual(sum(1 for item in asociaciones if item.re_vigente), 1)


if __name__ == "__main__":
    unittest.main()
