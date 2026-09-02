import os
import unittest

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database.modelos import (
    AVISO_ESTADO_CANCELADO,
    AVISO_ESTADO_ENVIADO,
    AVISO_ESTADO_ERROR,
    AVISO_ESTADO_INCIERTO,
    AVISO_ESTADO_PENDIENTE,
    AVISO_ESTADO_PROCESANDO,
    AVISO_ESTADOS_VALIDOS,
    AVISO_TIPO_DESTINATARIO,
    AVISO_TIPO_FUNCIONARIO,
    AVISO_TIPOS_VALIDOS,
    AvisoEnvio,
    Base,
    Envio,
    construir_clave_idempotencia_aviso,
)


class ModeloAvisosV2Test(unittest.TestCase):
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

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _envio(self, nombre="Destino"):
        envio = Envio(
            e_remitente="Funcionario",
            e_correo_remitente="funcionario@example.com",
            e_destinatario=nombre,
            e_correo_destinatario="destino@example.com",
            e_direccion="Direccion",
            e_comuna="Comuna",
            e_tipo_envio="Domicilio",
            e_bultos=1,
            e_kilos=1,
            e_estado="historico",
            e_estado_correo="legacy-destinatario",
            e_aviso_funcionario_estado="legacy-funcionario",
            e_anulado=False,
        )
        self.db.add(envio)
        self.db.flush()
        return envio

    def _aviso(self, envio, tipo, **cambios):
        datos = {
            "envio_id": envio.id,
            "av_tipo": tipo,
            "av_correo_snapshot": None,
            "av_estado": AVISO_ESTADO_PENDIENTE,
            "av_clave_idempotencia": construir_clave_idempotencia_aviso(envio.id, tipo),
        }
        datos.update(cambios)
        return AvisoEnvio(**datos)

    def test_constantes_centralizan_tipos_estados_e_incierto(self):
        self.assertEqual(AVISO_TIPOS_VALIDOS, {"FUNCIONARIO", "DESTINATARIO"})
        self.assertEqual(AVISO_ESTADOS_VALIDOS, {
            AVISO_ESTADO_PENDIENTE,
            AVISO_ESTADO_PROCESANDO,
            AVISO_ESTADO_ENVIADO,
            AVISO_ESTADO_ERROR,
            AVISO_ESTADO_INCIERTO,
            AVISO_ESTADO_CANCELADO,
        })
        envio = self._envio()
        for estado in AVISO_ESTADOS_VALIDOS:
            with self.subTest(estado=estado):
                aviso = self._aviso(envio, AVISO_TIPO_FUNCIONARIO, av_estado=estado.lower())
                self.assertEqual(aviso.av_estado, estado)

    def test_un_envio_admite_funcionario_y_destinatario_con_snapshot_nullable(self):
        envio = self._envio()
        funcionario = self._aviso(envio, AVISO_TIPO_FUNCIONARIO)
        destinatario = self._aviso(
            envio,
            AVISO_TIPO_DESTINATARIO,
            av_correo_snapshot="destino-original@example.com",
        )
        self.db.add_all([funcionario, destinatario])
        self.db.commit()

        self.assertEqual(len(envio.avisos), 2)
        self.assertIsNone(funcionario.av_correo_snapshot)
        self.assertEqual(funcionario.av_intentos, 0)
        self.assertEqual(destinatario.av_correo_snapshot, "destino-original@example.com")
        envio.e_correo_destinatario = "correo-nuevo@example.com"
        self.db.commit()
        self.assertEqual(destinatario.av_correo_snapshot, "destino-original@example.com")

    def test_no_admite_dos_avisos_del_mismo_tipo_por_envio(self):
        envio = self._envio()
        self.db.add(self._aviso(envio, AVISO_TIPO_FUNCIONARIO))
        self.db.commit()
        self.db.add(self._aviso(
            envio,
            AVISO_TIPO_FUNCIONARIO,
            av_clave_idempotencia="OTRA-CLAVE",
        ))
        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_clave_idempotencia_es_estable_y_unica(self):
        primero = self._envio("Uno")
        segundo = self._envio("Dos")
        clave = construir_clave_idempotencia_aviso(primero.id, " funcionario ")
        self.assertEqual(clave, f"ENVIO-{primero.id}-FUNCIONARIO")
        self.db.add(self._aviso(primero, AVISO_TIPO_FUNCIONARIO, av_clave_idempotencia=clave))
        self.db.commit()
        self.db.add(self._aviso(segundo, AVISO_TIPO_DESTINATARIO, av_clave_idempotencia=clave))
        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_modelo_y_bd_rechazan_tipo_estado_e_intentos_invalidos(self):
        envio = self._envio()
        with self.assertRaises(ValueError):
            self._aviso(envio, "OTRO")
        with self.assertRaises(ValueError):
            self._aviso(envio, AVISO_TIPO_FUNCIONARIO, av_estado="DESCONOCIDO")

        aviso = self._aviso(envio, AVISO_TIPO_FUNCIONARIO, av_intentos=-1)
        self.db.add(aviso)
        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_fk_restrict_impide_borrar_envio_y_legacy_permanece(self):
        envio = self._envio()
        self.db.add(self._aviso(envio, AVISO_TIPO_FUNCIONARIO))
        self.db.commit()
        self.assertEqual(envio.e_estado_correo, "legacy-destinatario")
        self.assertEqual(envio.e_aviso_funcionario_estado, "legacy-funcionario")

        self.db.delete(envio)
        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_checks_de_bd_protegen_inserciones_fuera_del_orm(self):
        envio = self._envio()
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self.db.execute(text(
                "INSERT INTO avisos_envio "
                "(envio_id, av_tipo, av_estado, av_intentos, av_fecha_creacion, av_clave_idempotencia) "
                "VALUES (:envio_id, 'FUNCIONARIO', 'INVALIDO', 0, CURRENT_TIMESTAMP, 'CLAVE-RAW')"
            ), {"envio_id": envio.id})
            self.db.commit()


if __name__ == "__main__":
    unittest.main()
