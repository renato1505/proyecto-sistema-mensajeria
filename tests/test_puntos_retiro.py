import os
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database.modelos import Base, Envio, PuntoRetiro
from services.puntos_retiro import (
    PUNTO_ACADEMIA,
    PUNTO_MENSAJERIA_LOCAL,
    asignar_punto_retiro_nuevo_envio,
    codigo_punto_retiro_para_centro_costo,
)


class PuntoRetiroTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.local = PuntoRetiro(
            pr_codigo=PUNTO_MENSAJERIA_LOCAL,
            pr_nombre="Mensajeria local",
            pr_es_local=True,
            pr_incluir_metricas_locales=True,
            pr_activo=True,
        )
        self.academia = PuntoRetiro(
            pr_codigo=PUNTO_ACADEMIA,
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

    def test_clasificacion_acm_es_exacta_y_normalizada(self):
        casos = {
            "ACM": PUNTO_ACADEMIA,
            " acm ": PUNTO_ACADEMIA,
            "ACM123": PUNTO_MENSAJERIA_LOCAL,
            "123ACM": PUNTO_MENSAJERIA_LOCAL,
            "CC-100": PUNTO_MENSAJERIA_LOCAL,
            None: PUNTO_MENSAJERIA_LOCAL,
        }
        for centro_costo, esperado in casos.items():
            with self.subTest(centro_costo=centro_costo):
                self.assertEqual(codigo_punto_retiro_para_centro_costo(centro_costo), esperado)

    def test_nuevo_envio_persiste_punto_local(self):
        envio = Envio(e_centro_costo="CC-100")
        punto = asignar_punto_retiro_nuevo_envio(self.db, envio)
        self.assertEqual(punto.pr_codigo, PUNTO_MENSAJERIA_LOCAL)
        self.assertEqual(envio.e_punto_retiro_id, self.local.id)

    def test_nuevo_envio_acm_persiste_academia(self):
        envio = Envio(e_centro_costo="acm")
        punto = asignar_punto_retiro_nuevo_envio(self.db, envio)
        self.assertEqual(punto.pr_codigo, PUNTO_ACADEMIA)
        self.assertEqual(envio.e_punto_retiro_id, self.academia.id)


if __name__ == "__main__":
    unittest.main()
