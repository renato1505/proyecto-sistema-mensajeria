import os
import unittest
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import create_engine, event
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
    AVISO_TIPO_DESTINATARIO,
    AVISO_TIPO_FUNCIONARIO,
    AvisoEnvio,
    Base,
    Envio,
    PuntoRetiro,
    RetiroEnvio,
    RetiroStarken,
    construir_clave_idempotencia_aviso,
)
from services import avisos_v2
from services.avisos_v2 import (
    obtener_envios_elegibles_avisos,
    sincronizar_avisos_elegibles,
    sincronizar_avisos_envio,
)


FECHA = datetime(2026, 9, 2, 10, 0, 0)


class ServicioAvisosV2Test(unittest.TestCase):
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
        self.db = sessionmaker(bind=self.engine)()
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

    def _envio(self, nombre, **cambios):
        datos = {
            "e_remitente": f"Funcionario {nombre}",
            "e_correo_remitente": f" {nombre.lower()}@example.com ",
            "e_destinatario": f"Destino {nombre}",
            "e_correo_destinatario": f"DESTINO-{nombre}@EXAMPLE.COM",
            "e_direccion": "Direccion",
            "e_comuna": "Comuna",
            "e_tipo_envio": "Domicilio",
            "e_bultos": 1,
            "e_kilos": 1,
            "e_estado": "historico",
            "e_orden_flete": f"OF-{nombre}",
            "e_fecha_of": FECHA,
            "e_punto_retiro_id": self.punto.id,
            "e_anulado": False,
        }
        datos.update(cambios)
        envio = Envio(**datos)
        self.db.add(envio)
        self.db.flush()
        return envio

    def _retirar(self, envio, codigo=None, vigente=True, anulado=False):
        retiro = RetiroStarken(
            rs_codigo=codigo or f"RET-{envio.id}",
            punto_retiro_id=self.punto.id,
            rs_fecha_retiro=FECHA,
            rs_fecha_confirmacion=FECHA,
            rs_anulado=anulado,
        )
        self.db.add(retiro)
        self.db.flush()
        asociacion = RetiroEnvio(
            retiro_id=retiro.id,
            envio_id=envio.id,
            re_bultos_snapshot=envio.e_bultos,
            re_fecha_asociacion=FECHA,
            re_vigente=vigente,
        )
        self.db.add(asociacion)
        self.db.commit()
        return retiro, asociacion

    def _aviso(self, envio, tipo, estado):
        aviso = AvisoEnvio(
            envio_id=envio.id,
            av_tipo=tipo,
            av_correo_snapshot="original@example.com",
            av_estado=estado,
            av_intentos=3,
            av_ultimo_error="detalle existente",
            av_clave_idempotencia=construir_clave_idempotencia_aviso(envio.id, tipo),
        )
        self.db.add(aviso)
        self.db.commit()
        return aviso

    def test_elegibilidad_exige_of_fecha_y_retiro_vigente_no_anulado(self):
        valido = self._envio("Valido")
        self._retirar(valido)
        sin_of = self._envio("SinOF", e_orden_flete=" ")
        self._retirar(sin_of)
        sin_fecha = self._envio("SinFecha", e_fecha_of=None)
        self._retirar(sin_fecha)
        envio_anulado = self._envio("EnvioAnulado", e_anulado=True)
        self._retirar(envio_anulado)
        retiro_anulado = self._envio("RetiroAnulado")
        self._retirar(retiro_anulado, anulado=True)
        no_vigente = self._envio("NoVigente")
        self._retirar(no_vigente, vigente=False)
        solo_historico = self._envio("SoloHistorico")
        solo_historico.e_lote = "LOTE"
        self.db.commit()

        consultas = []
        def contar(_conn, _cursor, statement, _params, _context, _many):
            consultas.append(statement)
        event.listen(self.engine, "before_cursor_execute", contar)
        try:
            resultado = obtener_envios_elegibles_avisos(self.db)
        finally:
            event.remove(self.engine, "before_cursor_execute", contar)

        self.assertEqual([item.envio_id for item in resultado], [valido.id])
        self.assertEqual(len(consultas), 1)

    def test_crea_dos_avisos_con_origen_legacy_snapshot_y_estado_pendiente(self):
        envio = self._envio("Uno")
        self._retirar(envio)
        resultado = sincronizar_avisos_envio(self.db, envio.id)
        avisos = self.db.query(AvisoEnvio).order_by(AvisoEnvio.av_tipo).all()

        self.assertEqual(resultado.creados, 2)
        self.assertEqual([a.av_tipo for a in avisos], ["DESTINATARIO", "FUNCIONARIO"])
        self.assertEqual([a.av_estado for a in avisos], [AVISO_ESTADO_PENDIENTE] * 2)
        self.assertEqual(avisos[0].av_correo_snapshot, "destino-uno@example.com")
        self.assertEqual(avisos[1].av_correo_snapshot, "uno@example.com")
        self.assertTrue(all(a.av_intentos == 0 and a.av_ultimo_error is None for a in avisos))
        self.assertTrue(all(a.av_fecha_creacion is not None for a in avisos))
        self.assertTrue(all(a.av_fecha_procesamiento is None for a in avisos))
        self.assertTrue(all(a.av_fecha_envio is None for a in avisos))
        self.assertEqual(
            {a.av_clave_idempotencia for a in avisos},
            {
                f"ENVIO-{envio.id}-FUNCIONARIO",
                f"ENVIO-{envio.id}-DESTINATARIO",
            },
        )

    def test_correo_ausente_o_invalido_crea_cancelado_sin_snapshot(self):
        envio = self._envio(
            "SinCorreo",
            e_correo_remitente="correo-invalido",
            e_correo_destinatario="   ",
        )
        self._retirar(envio)
        sincronizar_avisos_envio(self.db, envio.id)
        avisos = self.db.query(AvisoEnvio).all()
        self.assertEqual(len(avisos), 2)
        self.assertTrue(all(a.av_estado == AVISO_ESTADO_CANCELADO for a in avisos))
        self.assertTrue(all(a.av_correo_snapshot is None for a in avisos))
        self.assertTrue(all(a.av_ultimo_error is None for a in avisos))

    def test_repeticion_es_idempotente_y_no_actualiza_snapshot_ni_estado(self):
        envio = self._envio("Estable")
        self._retirar(envio)
        sincronizar_avisos_envio(self.db, envio.id)
        funcionario = self.db.query(AvisoEnvio).filter_by(av_tipo=AVISO_TIPO_FUNCIONARIO).one()
        funcionario.av_estado = AVISO_ESTADO_ERROR
        funcionario.av_intentos = 4
        envio.e_correo_remitente = "nuevo@example.com"
        self.db.commit()

        resultado = sincronizar_avisos_envio(self.db, envio.id)
        self.db.refresh(funcionario)
        self.assertEqual(resultado.creados, 0)
        self.assertEqual(self.db.query(AvisoEnvio).count(), 2)
        self.assertEqual(funcionario.av_correo_snapshot, "estable@example.com")
        self.assertEqual(funcionario.av_estado, AVISO_ESTADO_ERROR)
        self.assertEqual(funcionario.av_intentos, 4)

    def test_reconcilia_solo_pendiente_y_error_cuando_deja_de_ser_elegible(self):
        estados = [
            AVISO_ESTADO_PENDIENTE,
            AVISO_ESTADO_ERROR,
            AVISO_ESTADO_PROCESANDO,
            AVISO_ESTADO_INCIERTO,
            AVISO_ESTADO_ENVIADO,
            AVISO_ESTADO_CANCELADO,
        ]
        avisos = []
        for indice, estado in enumerate(estados):
            envio = self._envio(f"E{indice}")
            _retiro, asociacion = self._retirar(envio)
            aviso = self._aviso(envio, AVISO_TIPO_FUNCIONARIO, estado)
            asociacion.re_vigente = False
            self.db.commit()
            sincronizar_avisos_envio(self.db, envio.id)
            avisos.append(aviso)

        esperados = [
            AVISO_ESTADO_CANCELADO,
            AVISO_ESTADO_CANCELADO,
            AVISO_ESTADO_PROCESANDO,
            AVISO_ESTADO_INCIERTO,
            AVISO_ESTADO_ENVIADO,
            AVISO_ESTADO_CANCELADO,
        ]
        self.assertEqual([a.av_estado for a in avisos], esperados)

    def test_anulacion_envio_o_retiro_cancela_aviso_pendiente(self):
        envio = self._envio("Anulado")
        retiro, _asociacion = self._retirar(envio)
        aviso = self._aviso(envio, AVISO_TIPO_FUNCIONARIO, AVISO_ESTADO_PENDIENTE)
        envio.e_anulado = True
        self.db.commit()
        sincronizar_avisos_envio(self.db, envio.id)
        self.assertEqual(aviso.av_estado, AVISO_ESTADO_CANCELADO)

        otro = self._envio("Retiro")
        otro_retiro, _ = self._retirar(otro)
        otro_aviso = self._aviso(otro, AVISO_TIPO_FUNCIONARIO, AVISO_ESTADO_ERROR)
        otro_retiro.rs_anulado = True
        self.db.commit()
        sincronizar_avisos_envio(self.db, otro.id)
        self.assertEqual(otro_aviso.av_estado, AVISO_ESTADO_CANCELADO)

    def test_nuevo_retiro_no_reactiva_cancelado_existente(self):
        envio = self._envio("SegundoCiclo")
        _retiro, asociacion = self._retirar(envio)
        sincronizar_avisos_envio(self.db, envio.id)
        asociacion.re_vigente = False
        self.db.commit()
        sincronizar_avisos_envio(self.db, envio.id)
        self._retirar(envio, codigo="RET-NUEVO")

        resultado = sincronizar_avisos_envio(self.db, envio.id)
        self.assertEqual(resultado.creados, 0)
        self.assertEqual(self.db.query(AvisoEnvio).count(), 2)
        self.assertTrue(all(a.av_estado == AVISO_ESTADO_CANCELADO for a in envio.avisos))

    def test_error_inesperado_revierte_ambos_avisos(self):
        envio = self._envio("Rollback")
        self._retirar(envio)
        original = avisos_v2._crear_aviso
        llamadas = 0

        def fallar_segundo(db, item, tipo):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise RuntimeError("fallo controlado")
            return original(db, item, tipo)

        with patch("services.avisos_v2._crear_aviso", side_effect=fallar_segundo):
            with self.assertRaises(RuntimeError):
                sincronizar_avisos_envio(self.db, envio.id)
        self.assertEqual(self.db.query(AvisoEnvio).count(), 0)

    def test_integrity_error_de_carrera_se_reintenta_sin_duplicar(self):
        envio = self._envio("Carrera")
        self._retirar(envio)
        original = avisos_v2._sincronizar_intento
        llamadas = 0

        def carrera(db, envio_id):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 1:
                raise IntegrityError("INSERT", {}, Exception("unique"))
            return original(db, envio_id)

        with patch("services.avisos_v2._sincronizar_intento", side_effect=carrera):
            resultado = sincronizar_avisos_envio(self.db, envio.id)
        self.assertEqual(llamadas, 2)
        self.assertEqual(resultado.creados, 2)
        self.assertEqual(self.db.query(AvisoEnvio).count(), 2)

    def test_sincronizacion_masiva_cinco_retirados_es_idempotente(self):
        ids = []
        for indice in range(5):
            envio = self._envio(f"Masivo{indice}")
            self._retirar(envio)
            ids.append(envio.id)
        primera = sincronizar_avisos_elegibles(self.db)
        segunda = sincronizar_avisos_elegibles(self.db)
        self.assertEqual(len(primera), 5)
        self.assertEqual(len(segunda), 5)
        self.assertEqual(self.db.query(AvisoEnvio).count(), 10)
        self.assertTrue(all(item.creados == 0 for item in segunda))

    def test_filtro_ids_solo_procesa_subconjunto_y_normaliza_repetidos(self):
        primero = self._envio("Primero")
        segundo = self._envio("Segundo")
        self._retirar(primero)
        self._retirar(segundo)
        resultados = sincronizar_avisos_elegibles(self.db, [primero.id, primero.id])
        self.assertEqual(len(resultados), 1)
        self.assertEqual(self.db.query(AvisoEnvio).count(), 2)
        self.assertEqual(resultados[0].envio_id, primero.id)


if __name__ == "__main__":
    unittest.main()
