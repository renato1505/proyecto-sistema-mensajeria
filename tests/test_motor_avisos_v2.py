import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine, event
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
    AVISO_TIPO_FUNCIONARIO,
    AvisoEnvio,
    Base,
    Envio,
    PuntoRetiro,
    RetiroEnvio,
    RetiroStarken,
)
from services.avisos_v2 import sincronizar_avisos_envio
from services.motor_avisos_v2 import (
    AvisoNoProcesable,
    obtener_avisos_procesando_antiguos,
    procesar_aviso,
    procesar_avisos,
)
from services.proveedor_avisos import ProveedorCorreoFake, ResultadoEnvioCorreo
from services.proveedor_avisos import SolicitudCorreoAviso, enviar_correo_aviso
from services.email_client import ResultadoEmail


FECHA = datetime(2026, 9, 2, 10, 0, 0)


class MotorAvisosV2Test(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def activar_fk(dbapi_connection, _record):
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

    def _crear_envio_retirado(self, nombre, **cambios):
        datos = {
            "e_remitente": f"Funcionario {nombre}",
            "e_correo_remitente": f"{nombre.lower()}@example.com",
            "e_destinatario": f"Destino {nombre}",
            "e_correo_destinatario": f"destino-{nombre.lower()}@example.com",
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
        retiro = RetiroStarken(
            rs_codigo=f"RET-{nombre}-{envio.id}",
            punto_retiro_id=self.punto.id,
            rs_fecha_retiro=FECHA,
            rs_fecha_confirmacion=FECHA,
        )
        self.db.add(retiro)
        self.db.flush()
        asociacion = RetiroEnvio(
            retiro_id=retiro.id,
            envio_id=envio.id,
            re_bultos_snapshot=1,
            re_fecha_asociacion=FECHA,
            re_vigente=True,
        )
        self.db.add(asociacion)
        self.db.commit()
        sincronizar_avisos_envio(self.db, envio.id)
        return envio, retiro, asociacion

    def _aviso_funcionario(self, envio):
        return self.db.query(AvisoEnvio).filter_by(
            envio_id=envio.id,
            av_tipo=AVISO_TIPO_FUNCIONARIO,
        ).one()

    def test_pendiente_claim_commit_proveedor_y_enviado_persisten_independientes(self):
        envio, _retiro, _asociacion = self._crear_envio_retirado("Exito")
        aviso = self._aviso_funcionario(envio)
        snapshot = aviso.av_correo_snapshot
        envio.e_correo_remitente = "editado@example.com"
        self.db.commit()
        observado = []

        def proveedor(solicitud):
            sesion = self.Session()
            try:
                persistido = sesion.get(AvisoEnvio, aviso.id)
                observado.append((persistido.av_estado, persistido.av_intentos, solicitud.destinatario))
            finally:
                sesion.close()
            return ResultadoEnvioCorreo.exito("provider-123")

        resultado = procesar_aviso(self.Session, aviso.id, proveedor=proveedor)
        self.db.expire_all()
        aviso = self.db.get(AvisoEnvio, aviso.id)
        self.assertEqual(observado, [(AVISO_ESTADO_PROCESANDO, 1, snapshot)])
        self.assertEqual(resultado.estado, AVISO_ESTADO_ENVIADO)
        self.assertEqual(aviso.av_estado, AVISO_ESTADO_ENVIADO)
        self.assertEqual(aviso.av_intentos, 1)
        self.assertIsNotNone(aviso.av_fecha_procesamiento)
        self.assertIsNotNone(aviso.av_fecha_envio)
        self.assertEqual(aviso.av_message_id, "provider-123")
        self.assertIsNone(aviso.av_ultimo_error)

    def test_error_confirmado_solo_reintenta_explicitamente_e_incrementa_intentos(self):
        envio, _retiro, _asociacion = self._crear_envio_retirado("Retry")
        aviso = self._aviso_funcionario(envio)
        fallo = ProveedorCorreoFake({aviso.id: ResultadoEnvioCorreo.error_confirmado("HTTP 400 rechazo")})
        procesar_aviso(self.Session, aviso.id, proveedor=fallo)
        self.db.expire_all()
        self.assertEqual(self.db.get(AvisoEnvio, aviso.id).av_estado, AVISO_ESTADO_ERROR)
        self.assertEqual(self.db.get(AvisoEnvio, aviso.id).av_intentos, 1)

        sin_autorizacion = ProveedorCorreoFake()
        with self.assertRaises(AvisoNoProcesable):
            procesar_aviso(self.Session, aviso.id, proveedor=sin_autorizacion)
        self.assertEqual(len(sin_autorizacion.invocaciones), 0)

        exito = ProveedorCorreoFake()
        procesar_aviso(self.Session, aviso.id, permitir_reintento_error=True, proveedor=exito)
        self.db.expire_all()
        self.assertEqual(self.db.get(AvisoEnvio, aviso.id).av_estado, AVISO_ESTADO_ENVIADO)
        self.assertEqual(self.db.get(AvisoEnvio, aviso.id).av_intentos, 2)

    def test_incierto_no_es_reintentable_ni_con_autorizacion_error(self):
        envio, _retiro, _asociacion = self._crear_envio_retirado("Incierto")
        aviso = self._aviso_funcionario(envio)
        fake = ProveedorCorreoFake({aviso.id: ResultadoEnvioCorreo.incierto("timeout ambiguo")})
        procesar_aviso(self.Session, aviso.id, proveedor=fake)
        segundo = ProveedorCorreoFake()
        with self.assertRaises(AvisoNoProcesable):
            procesar_aviso(self.Session, aviso.id, permitir_reintento_error=True, proveedor=segundo)
        self.assertEqual(len(segundo.invocaciones), 0)
        self.db.expire_all()
        self.assertEqual(self.db.get(AvisoEnvio, aviso.id).av_estado, AVISO_ESTADO_INCIERTO)

    def test_enviado_cancelado_y_procesando_no_invocan_proveedor(self):
        for indice, estado in enumerate((AVISO_ESTADO_ENVIADO, AVISO_ESTADO_CANCELADO, AVISO_ESTADO_PROCESANDO)):
            envio, _retiro, _asociacion = self._crear_envio_retirado(f"Terminal{indice}")
            aviso = self._aviso_funcionario(envio)
            aviso.av_estado = estado
            self.db.commit()
            fake = ProveedorCorreoFake()
            with self.assertRaises(AvisoNoProcesable):
                procesar_aviso(self.Session, aviso.id, permitir_reintento_error=True, proveedor=fake)
            self.assertEqual(len(fake.invocaciones), 0)

    def test_perdida_elegibilidad_cancela_pendiente_y_error_sin_enviar(self):
        for indice, estado in enumerate((AVISO_ESTADO_PENDIENTE, AVISO_ESTADO_ERROR)):
            envio, _retiro, asociacion = self._crear_envio_retirado(f"Cancel{indice}")
            aviso = self._aviso_funcionario(envio)
            aviso.av_estado = estado
            asociacion.re_vigente = False
            self.db.commit()
            fake = ProveedorCorreoFake()
            with self.assertRaises(AvisoNoProcesable) as contexto:
                procesar_aviso(self.Session, aviso.id, permitir_reintento_error=True, proveedor=fake)
            self.assertEqual(contexto.exception.estado, AVISO_ESTADO_CANCELADO)
            self.db.expire_all()
            self.assertEqual(self.db.get(AvisoEnvio, aviso.id).av_estado, AVISO_ESTADO_CANCELADO)
            self.assertEqual(self.db.get(AvisoEnvio, aviso.id).av_intentos, 0)
            self.assertEqual(len(fake.invocaciones), 0)

    def test_reclamo_concurrente_solo_invoca_una_vez_al_proveedor(self):
        envio, _retiro, _asociacion = self._crear_envio_retirado("Concurrente")
        aviso = self._aviso_funcionario(envio)
        segundo = ProveedorCorreoFake()
        resultados_segundo = []

        def proveedor_primero(_solicitud):
            with self.assertRaises(AvisoNoProcesable) as contexto:
                procesar_aviso(self.Session, aviso.id, proveedor=segundo)
            resultados_segundo.append(contexto.exception.estado)
            return ResultadoEnvioCorreo.exito("primero")

        procesar_aviso(self.Session, aviso.id, proveedor=proveedor_primero)
        self.assertEqual(resultados_segundo, [AVISO_ESTADO_PROCESANDO])
        self.assertEqual(len(segundo.invocaciones), 0)

    def test_batch_continua_y_conserva_exitos_error_incierto_y_cancelado(self):
        avisos = []
        asociaciones = []
        for indice in range(6):
            envio, _retiro, asociacion = self._crear_envio_retirado(f"Batch{indice}")
            avisos.append(self._aviso_funcionario(envio))
            asociaciones.append(asociacion)
        asociaciones[5].re_vigente = False
        self.db.commit()
        fake = ProveedorCorreoFake({
            avisos[0].id: ResultadoEnvioCorreo.exito("ok-1"),
            avisos[1].id: ResultadoEnvioCorreo.exito("ok-2"),
            avisos[2].id: ResultadoEnvioCorreo.error_confirmado("rechazado"),
            avisos[3].id: ResultadoEnvioCorreo.incierto("conexion interrumpida"),
            avisos[4].id: ResultadoEnvioCorreo.exito("ok-5"),
        })
        resumen = procesar_avisos(self.Session, [a.id for a in avisos], proveedor=fake)
        self.assertEqual((resumen.total, resumen.enviados, resumen.errores), (6, 3, 1))
        self.assertEqual((resumen.inciertos, resumen.cancelados, resumen.omitidos), (1, 1, 1))
        self.assertEqual(len(fake.invocaciones), 5)
        self.db.expire_all()
        self.assertEqual(
            [self.db.get(AvisoEnvio, a.id).av_estado for a in avisos],
            [
                AVISO_ESTADO_ENVIADO,
                AVISO_ESTADO_ENVIADO,
                AVISO_ESTADO_ERROR,
                AVISO_ESTADO_INCIERTO,
                AVISO_ESTADO_ENVIADO,
                AVISO_ESTADO_CANCELADO,
            ],
        )

    def test_excepcion_inesperada_del_proveedor_es_incierta_y_sanitizada(self):
        envio, _retiro, _asociacion = self._crear_envio_retirado("Secreto")
        aviso = self._aviso_funcionario(envio)

        def proveedor(_solicitud):
            raise RuntimeError("token=abc123 https://usuario:clave@correo.example fallo")

        resultado = procesar_aviso(self.Session, aviso.id, proveedor=proveedor)
        self.db.expire_all()
        aviso = self.db.get(AvisoEnvio, aviso.id)
        self.assertEqual(resultado.estado, AVISO_ESTADO_INCIERTO)
        self.assertNotIn("abc123", aviso.av_ultimo_error)
        self.assertNotIn("usuario:clave", aviso.av_ultimo_error)

    def test_detecta_procesando_antiguos_sin_modificarlos(self):
        antiguo, _retiro, _asociacion = self._crear_envio_retirado("Antiguo")
        reciente, _retiro2, _asociacion2 = self._crear_envio_retirado("Reciente")
        aviso_antiguo = self._aviso_funcionario(antiguo)
        aviso_reciente = self._aviso_funcionario(reciente)
        aviso_antiguo.av_estado = AVISO_ESTADO_PROCESANDO
        aviso_antiguo.av_fecha_procesamiento = FECHA - timedelta(minutes=16)
        aviso_reciente.av_estado = AVISO_ESTADO_PROCESANDO
        aviso_reciente.av_fecha_procesamiento = FECHA - timedelta(minutes=14)
        self.db.commit()
        encontrados = obtener_avisos_procesando_antiguos(self.db, ahora=FECHA)
        self.assertEqual([a.id for a in encontrados], [aviso_antiguo.id])
        self.assertEqual(aviso_antiguo.av_estado, AVISO_ESTADO_PROCESANDO)

    def test_adaptador_productivo_usa_cliente_existente_y_resultado_normalizado(self):
        solicitud = SolicitudCorreoAviso(
            aviso_id=10,
            envio_id=20,
            tipo=AVISO_TIPO_FUNCIONARIO,
            destinatario="snapshot@example.com",
            remitente_nombre="Ana Ejemplo",
            destinatario_nombre="Destino",
            orden_flete="OF-20",
            direccion="Direccion",
            comuna="Comuna",
            region="Region",
            telefono="12345678",
            observacion="",
        )
        with patch(
            "services.proveedor_avisos.enviar_mensaje",
            return_value=ResultadoEmail(True, "brevo", "m-20", 201),
        ) as cliente:
            resultado = enviar_correo_aviso(solicitud)
        self.assertTrue(resultado.aceptado)
        self.assertEqual(resultado.message_id, "m-20")
        self.assertEqual(cliente.call_count, 1)
        mensaje = cliente.call_args.args[0]
        self.assertEqual(mensaje["To"], "snapshot@example.com")

    def test_message_id_brevo_se_persiste_hasta_aviso_envio(self):
        envio, _retiro, _asociacion = self._crear_envio_retirado("Brevo")
        aviso = self._aviso_funcionario(envio)
        with patch(
            "services.proveedor_avisos.enviar_mensaje",
            return_value=ResultadoEmail(True, "brevo", "brevo-persistido", 201),
        ):
            procesar_aviso(self.Session, aviso.id, proveedor=enviar_correo_aviso)
        self.db.expire_all()
        aviso = self.db.get(AvisoEnvio, aviso.id)
        self.assertEqual(aviso.av_estado, AVISO_ESTADO_ENVIADO)
        self.assertEqual(aviso.av_message_id, "brevo-persistido")


if __name__ == "__main__":
    unittest.main()
