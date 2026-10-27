import unittest
from datetime import datetime

from sqlalchemy import create_engine, delete, event, insert, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.modelos import (
    Base, ConciliacionH2H, Envio, IntentoOF, MovimientoEnvio, RegistroOF,
    METODO_VERIFICACION_STARKEN,
)


class PersistenciaOFTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def activar_fk(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.envio = self._envio("Destino ficticio")
        self.db.commit()

    def tearDown(self):
        self.db.close()
        # Descartar la SQLite en memoria evita borrar cadenas con FK RESTRICT.
        self.engine.dispose()

    def _envio(self, nombre):
        envio = Envio(
            e_remitente="Funcionario ficticio", e_destinatario=nombre,
            e_direccion="Direccion demo", e_comuna="Comuna demo", e_tipo_envio="Domicilio",
            e_bultos=1, e_kilos=1, e_estado="en_proceso", e_lote="LOTE-DEMO",
            e_fila_excel=2, e_resultado_of="ERROR", e_detalle_of="Error al enviar fila 2 a servicio H2H",
        )
        self.db.add(envio)
        self.db.flush()
        return envio

    def _intento(self, **cambios):
        datos = dict(
            envio_id=self.envio.id, io_secuencia=1, io_transportista="STARKEN",
            io_lote="LOTE-DEMO", io_fila=2, io_archivo="demo.csv", io_estado="EN_VERIFICACION",
        )
        datos.update(cambios)
        intento = IntentoOF(**datos)
        self.db.add(intento)
        self.db.flush()
        return intento

    def _caso(self, intento, **cambios):
        datos = dict(
            intento_id=intento.id, envio_id=intento.envio_id,
            ch_resultado_original=" ERROR ",
            ch_detalle_original="Error al enviar fila 2 a servicio H2H",
        )
        datos.update(cambios)
        caso = ConciliacionH2H(**datos)
        self.db.add(caso)
        self.db.flush()
        return caso

    def _registro(self, intento, **cambios):
        datos = dict(
            intento_id=intento.id, envio_id=intento.envio_id,
            ro_transportista=intento.io_transportista, ro_numero="000123456789012345678901234567890",
            ro_origen="RESPUESTA_PROVEEDOR",
        )
        datos.update(cambios)
        registro = RegistroOF(**datos)
        self.db.add(registro)
        self.db.flush()
        return registro

    def _movimiento(self, **cambios):
        datos = dict(
            envio_id=self.envio.id, me_tipo="DETECCION_H2H", me_actor="operador-demo",
            me_detalle={"resultado": "ERROR", "detalle": "servicio H2H"},
        )
        datos.update(cambios)
        movimiento = MovimientoEnvio(**datos)
        self.db.add(movimiento)
        self.db.flush()
        return movimiento

    def test_varios_intentos_conservan_lote_y_anterior_del_mismo_envio(self):
        anterior = self._intento(io_estado="SIN_OF_VERIFICADA")
        sucesor = self._intento(io_secuencia=2, io_anterior_id=anterior.id, io_lote="LOTE-NUEVO")
        self.db.commit()
        self.assertEqual(sucesor.anterior.id, anterior.id)
        self.assertEqual(anterior.io_lote, "LOTE-DEMO")
        self.assertEqual(sucesor.envio.id, self.envio.id)
        self.assertEqual(self.db.query(IntentoOF).count(), 2)

    def test_secuencia_duplicada_es_rechazada(self):
        self._intento(io_estado="CANCELADO")
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self._intento(io_estado="CON_OF")
        self.db.rollback()

    def test_solo_un_intento_abierto_por_envio(self):
        self._intento()
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self._intento(io_secuencia=2, io_estado="ABIERTO")
        self.db.rollback()

    def test_no_admite_anterior_de_otro_envio(self):
        anterior = self._intento(io_estado="SIN_OF_VERIFICADA")
        otro = self._envio("Otro ficticio")
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self._intento(envio_id=otro.id, io_anterior_id=anterior.id)
        self.db.rollback()

    def test_no_admite_dos_sucesores_del_mismo_intento(self):
        anterior = self._intento(io_estado="SIN_OF_VERIFICADA")
        self._intento(io_secuencia=2, io_anterior_id=anterior.id, io_estado="CANCELADO")
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self._intento(io_secuencia=3, io_anterior_id=anterior.id)
        self.db.rollback()

    def test_checks_secuencia_fila_estado_y_transportista_fuera_del_orm(self):
        base = dict(envio_id=self.envio.id, io_secuencia=1, io_transportista="STARKEN", io_estado="ABIERTO")
        for cambios in [dict(io_secuencia=0), dict(io_fila=0), dict(io_estado="OTRO"), dict(io_transportista="starken")]:
            with self.subTest(cambios=cambios):
                with self.assertRaises(IntegrityError):
                    self.db.execute(insert(IntentoOF.__table__).values(**{**base, **cambios}))
                    self.db.commit()
                self.db.rollback()

    def test_conciliacion_pendiente_tiene_snapshot_y_no_inventa_fecha_deteccion(self):
        intento = self._intento()
        caso = self._caso(intento)
        self.db.commit()
        self.assertEqual(caso.intento.id, intento.id)
        self.assertEqual(caso.ch_estado, "PENDIENTE")
        self.assertIsNone(caso.ch_fecha_deteccion)
        self.assertIsNone(caso.ch_fecha_verificacion)
        self.assertIsNone(caso.ch_observacion)
        self.assertIsNotNone(caso.ch_fecha_creacion)
        self.envio.e_detalle_of = "Otra proyeccion"
        self.db.commit()
        self.assertEqual(caso.ch_resultado_original, " ERROR ")
        self.assertEqual(caso.ch_detalle_original, "Error al enviar fila 2 a servicio H2H")

    def test_conciliacion_unica_por_intento(self):
        intento = self._intento()
        self._caso(intento)
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self._caso(intento)
        self.db.rollback()

    def test_conciliacion_no_puede_apuntar_a_otro_envio(self):
        intento = self._intento()
        otro = self._envio("Otro ficticio")
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self._caso(intento, envio_id=otro.id)
        self.db.rollback()

    def test_evidencia_original_no_se_sobrescribe_mediante_orm(self):
        caso = self._caso(self._intento())
        self.db.commit()
        caso.ch_detalle_original = "Reemplazo indebido"
        with self.assertRaisesRegex(ValueError, "evidencia original"):
            self.db.commit()
        self.db.rollback()
        self.assertEqual(caso.ch_detalle_original, "Error al enviar fila 2 a servicio H2H")

    def test_resolucion_exige_observacion_operador_metodo_y_fecha(self):
        caso = self._caso(self._intento())
        self.db.commit()
        validos = dict(
            ch_estado="OF_INEXISTENTE", ch_fecha_verificacion=datetime(2026, 10, 25, 12),
            ch_operador="operador-demo", ch_metodo=METODO_VERIFICACION_STARKEN,
            ch_observacion="Verificado en plataforma de Starken",
        )
        caso_id = caso.id
        for campo in ("ch_fecha_verificacion", "ch_operador", "ch_metodo", "ch_observacion"):
            with self.subTest(campo=campo):
                with self.assertRaises(IntegrityError):
                    self.db.execute(update(ConciliacionH2H.__table__).where(
                        ConciliacionH2H.id == caso_id
                    ).values(**{**validos, campo: None}))
                    self.db.commit()
                self.db.rollback()
        self.db.execute(update(ConciliacionH2H.__table__).where(ConciliacionH2H.id == caso_id).values(**validos))
        self.db.commit()
        self.db.refresh(caso)
        self.assertEqual(caso.ch_estado, "OF_INEXISTENTE")

    def test_estado_conciliacion_invalido_es_rechazado_por_bd(self):
        caso = self._caso(self._intento())
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self.db.execute(update(ConciliacionH2H.__table__).values(ch_estado="OTRO"))
            self.db.commit()
        self.db.rollback()
        self.assertEqual(caso.ch_estado, "PENDIENTE")

    def test_registro_of_conserva_texto_ceros_y_numero_largo(self):
        registro = self._registro(self._intento(), ro_numero=" 000123456789012345678901234567890 ")
        self.db.commit()
        self.assertIsInstance(registro.ro_numero, str)
        self.assertEqual(registro.ro_numero, "000123456789012345678901234567890")
        self.assertEqual(registro.intento.envio_id, self.envio.id)

    def test_registro_of_rechaza_enteros_y_texto_vacio(self):
        for numero in (123, None, "", "  "):
            with self.subTest(numero=numero):
                with self.assertRaises(ValueError):
                    RegistroOF(ro_numero=numero)

    def test_of_unica_por_transportista_incluso_para_envios_distintos(self):
        self._registro(self._intento())
        otro = self._envio("Otro ficticio")
        segundo = self._intento(envio_id=otro.id)
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self._registro(segundo)
        self.db.rollback()

    def test_un_registro_por_intento_y_numero_reutilizable_en_otro_transportista(self):
        primero = self._intento()
        self._registro(primero)
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self._registro(primero, ro_numero="OTRA-OF-DEMO")
        self.db.rollback()
        otro = self._envio("Otro transporte")
        segundo = self._intento(envio_id=otro.id, io_transportista="TRANSPORTE_DEMO")
        self._registro(segundo)
        self.db.commit()
        self.assertEqual(self.db.query(RegistroOF).count(), 2)

    def test_registro_rechaza_envio_o_transportista_incompatibles(self):
        intento = self._intento()
        otro = self._envio("Otro ficticio")
        self.db.commit()
        for cambios in [dict(envio_id=otro.id), dict(ro_transportista="OTRO")]:
            with self.subTest(cambios=cambios):
                with self.assertRaises(IntegrityError):
                    self._registro(intento, **cambios)
                self.db.rollback()

    def test_of_existente_exige_registro_del_mismo_intento(self):
        intento = self._intento()
        registro = self._registro(intento)
        caso = self._caso(intento)
        self.db.commit()
        registro_id = registro.id
        caso.ch_estado = "OF_EXISTENTE"
        caso.ch_fecha_verificacion = datetime(2026, 10, 25, 12)
        caso.ch_operador = "operador-demo"
        caso.ch_metodo = METODO_VERIFICACION_STARKEN
        caso.ch_observacion = "Confirmado en plataforma"
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()
        caso.ch_estado = "OF_EXISTENTE"
        caso.ch_fecha_verificacion = datetime(2026, 10, 25, 12)
        caso.ch_operador = "operador-demo"
        caso.ch_metodo = METODO_VERIFICACION_STARKEN
        caso.ch_observacion = "Confirmado en plataforma"
        caso.ch_registro_of_id = registro_id
        self.db.commit()
        self.assertEqual(caso.registro_of.id, registro.id)

    def test_autorizacion_solo_vincula_sucesor_directo_del_mismo_envio(self):
        anterior = self._intento(io_estado="SIN_OF_VERIFICADA")
        caso = self._caso(
            anterior, ch_estado="OF_INEXISTENTE", ch_fecha_verificacion=datetime(2026, 10, 25, 12),
            ch_operador="operador-demo", ch_metodo=METODO_VERIFICACION_STARKEN, ch_observacion="OF inexistente verificada",
        )
        sucesor = self._intento(io_secuencia=2, io_anterior_id=anterior.id)
        caso.ch_intento_sucesor_id = sucesor.id
        self.db.commit()
        self.assertEqual(caso.intento_sucesor.id, sucesor.id)
        with self.assertRaises(IntegrityError):
            self.db.execute(update(ConciliacionH2H.__table__).values(ch_intento_sucesor_id=anterior.id))
            self.db.commit()
        self.db.rollback()

    def test_autorizacion_rechaza_sucesor_ajeno_y_uso_en_pendiente(self):
        anterior = self._intento(io_estado="SIN_OF_VERIFICADA")
        caso = self._caso(anterior)
        sucesor = self._intento(io_secuencia=2, io_anterior_id=anterior.id)
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self.db.execute(update(ConciliacionH2H.__table__).values(ch_intento_sucesor_id=sucesor.id))
            self.db.commit()
        self.db.rollback()
        otro = self._envio("Otro ficticio")
        ajeno = self._intento(envio_id=otro.id)
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self.db.execute(update(ConciliacionH2H.__table__).values(
                ch_estado="OF_INEXISTENTE", ch_fecha_verificacion=datetime(2026, 10, 25, 12),
                ch_operador="demo", ch_metodo=METODO_VERIFICACION_STARKEN,
                ch_observacion="Verificado", ch_intento_sucesor_id=ajeno.id,
            ))
            self.db.commit()
        self.db.rollback()
        self.assertIsNone(caso.ch_intento_sucesor_id)

    def test_movimientos_independientes_con_y_sin_intento(self):
        intento = self._intento()
        primero = self._movimiento(intento_id=intento.id, me_clave_idempotencia="DEMO-1")
        segundo = self._movimiento(me_tipo="NOTA", me_detalle={"nota": "Seguimiento"})
        self.db.commit()
        self.assertNotEqual(primero.id, segundo.id)
        self.assertEqual(primero.intento.id, intento.id)
        self.assertIsNone(segundo.intento_id)
        self.assertEqual(self.db.query(MovimientoEnvio).count(), 2)

    def test_movimientos_rechazan_idempotencia_duplicada(self):
        self._movimiento(me_clave_idempotencia="DEMO-UNICA")
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self._movimiento(me_clave_idempotencia="DEMO-UNICA")
        self.db.rollback()

    def test_movimientos_no_se_sobrescriben_ni_eliminan_por_orm(self):
        movimiento = self._movimiento()
        self.db.commit()
        movimiento.me_detalle = {"resultado": "Reemplazo"}
        with self.assertRaisesRegex(ValueError, "inmutables"):
            self.db.commit()
        self.db.rollback()
        self.db.delete(movimiento)
        with self.assertRaisesRegex(ValueError, "inmutables"):
            self.db.commit()
        self.db.rollback()
        self.assertEqual(self.db.query(MovimientoEnvio).count(), 1)

    def test_fk_impiden_asociaciones_huerfanas_y_borrados_destructivos(self):
        intento = self._intento()
        self._caso(intento)
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self._movimiento(envio_id=99999)
        self.db.rollback()
        with self.assertRaises(IntegrityError):
            self.db.delete(self.envio)
            self.db.commit()
        self.db.rollback()
        intento_id = intento.id
        with self.assertRaises(IntegrityError):
            self.db.execute(delete(IntentoOF.__table__).where(IntentoOF.id == intento_id))
            self.db.commit()
        self.db.rollback()

    def test_movimiento_no_admite_intento_de_otro_envio(self):
        intento = self._intento()
        otro = self._envio("Otro ficticio")
        self.db.commit()
        with self.assertRaises(IntegrityError):
            self._movimiento(envio_id=otro.id, intento_id=intento.id)
        self.db.rollback()

    def test_nuevas_filas_no_alteran_proyeccion_legacy(self):
        columnas = Envio.__table__.columns
        antes = {col.name: getattr(self.envio, col.name) for col in columnas}
        intento = self._intento()
        self._caso(intento)
        self._movimiento(intento_id=intento.id)
        self.db.commit()
        self.db.refresh(self.envio)
        self.assertEqual({col.name: getattr(self.envio, col.name) for col in columnas}, antes)


    def _snapshot_persistencia(self):
        with self.db.no_autoflush:
            return {
                modelo.__tablename__: [dict(fila) for fila in self.db.execute(
                    modelo.__table__.select().order_by(modelo.__table__.c.id)
                ).mappings()]
                for modelo in (Envio, IntentoOF, RegistroOF, ConciliacionH2H, MovimientoEnvio)
            }

    def _rechazar_modificacion(self, objeto, campo, valor):
        antes = self._snapshot_persistencia()
        setattr(objeto, campo, valor)
        with self.assertRaises(ValueError):
            self.db.commit()
        self.db.rollback()
        self.assertEqual(self._snapshot_persistencia(), antes)

    def _rechazar_eliminacion(self, objeto):
        antes = self._snapshot_persistencia()
        self.db.delete(objeto)
        with self.assertRaisesRegex(ValueError, "evidencia operativa"):
            self.db.commit()
        self.db.rollback()
        self.assertEqual(self._snapshot_persistencia(), antes)

    def _resuelta(self, estado):
        envio = self._envio("Ficticio " + estado)
        intento = self._intento(
            envio_id=envio.id, io_estado="CON_OF" if estado == "OF_EXISTENTE" else "SIN_OF_VERIFICADA",
        )
        registro = self._registro(intento) if estado == "OF_EXISTENTE" else None
        caso = self._caso(
            intento, ch_estado=estado, ch_fecha_verificacion=datetime(2026, 10, 25, 12),
            ch_operador="operador-demo", ch_metodo=METODO_VERIFICACION_STARKEN,
            ch_observacion="Constatacion ficticia", ch_referencia="REF-DEMO",
            ch_registro_of_id=registro.id if registro else None,
        )
        self.db.commit()
        return caso, intento

    def test_contexto_intento_persistido_no_admite_modificaciones(self):
        intento = self._intento()
        otro = self._envio("Otro ficticio")
        self.db.commit()
        cambios = {
            "id": intento.id + 1000, "envio_id": otro.id, "io_secuencia": 2,
            "io_transportista": "OTRO", "io_lote": "LOTE-SUSTITUTO", "io_fila": 9,
            "io_archivo": "otro.csv", "io_fecha_creacion": datetime(2000, 1, 1),
            "io_anterior_id": intento.id,
        }
        for campo, valor in cambios.items():
            with self.subTest(campo=campo):
                self._rechazar_modificacion(intento, campo, valor)

    def test_cambio_de_relacion_envio_de_intento_es_rechazado(self):
        intento = self._intento()
        otro = self._envio("Otro ficticio")
        self.db.commit()
        self._rechazar_modificacion(intento, "envio", otro)

    def test_intento_no_tiene_transiciones_genericas_de_estado(self):
        intento = self._intento()
        self.db.commit()
        self._rechazar_modificacion(intento, "io_estado", "CON_OF")

    def test_eliminacion_intento_con_lote_sin_hijos_es_rechazada(self):
        intento = self._intento()
        self.db.commit()
        self._rechazar_eliminacion(intento)

    def test_eliminacion_intento_con_conciliacion_es_rechazada_por_orm(self):
        intento = self._intento()
        self._caso(intento)
        self.db.commit()
        self._rechazar_eliminacion(intento)

    def test_conciliacion_pendiente_no_se_puede_eliminar(self):
        caso = self._caso(self._intento())
        self.db.commit()
        self._rechazar_eliminacion(caso)

    def test_conciliacion_definitiva_no_se_puede_eliminar(self):
        caso, _ = self._resuelta("OF_INEXISTENTE")
        self._rechazar_eliminacion(caso)

    def test_resoluciones_definitivas_conservan_estado_y_metadatos(self):
        for estado in ("OF_EXISTENTE", "OF_INEXISTENTE"):
            with self.subTest(estado=estado):
                caso, _ = self._resuelta(estado)
                cambios = {
                    "ch_estado": "PENDIENTE", "ch_fecha_verificacion": datetime(2000, 1, 1),
                    "ch_operador": "otro", "ch_metodo": "OTRO", "ch_observacion": "Reemplazo",
                    "ch_referencia": "OTRA-REFERENCIA", "ch_registro_of_id": None if estado == "OF_EXISTENTE" else 999,
                }
                for campo, valor in cambios.items():
                    with self.subTest(campo=campo):
                        self._rechazar_modificacion(caso, campo, valor)

    def test_resolucion_no_puede_cambiar_a_otro_resultado_definitivo(self):
        caso, _ = self._resuelta("OF_INEXISTENTE")
        self._rechazar_modificacion(caso, "ch_estado", "OF_EXISTENTE")

    def test_identidad_y_evidencia_de_conciliacion_permanecen_inmutables(self):
        intento = self._intento()
        caso = self._caso(intento)
        otro = self._envio("Otro ficticio")
        self.db.commit()
        cambios = {
            "id": caso.id + 1000, "envio_id": otro.id, "intento_id": intento.id + 1000,
            "ch_resultado_original": "OK", "ch_detalle_original": "Sin error",
            "ch_fecha_creacion": datetime(2000, 1, 1), "ch_fecha_deteccion": datetime(2000, 1, 1),
        }
        for campo, valor in cambios.items():
            with self.subTest(campo=campo):
                self._rechazar_modificacion(caso, campo, valor)

    def test_registro_of_no_permite_cambios_de_identidad_ni_contexto(self):
        registro = self._registro(self._intento())
        otro = self._envio("Otro ficticio")
        self.db.commit()
        cambios = {
            "id": registro.id + 1000, "ro_numero": "OTRA-OF-DEMO", "ro_transportista": "OTRO",
            "intento_id": registro.intento_id + 1000, "envio_id": otro.id,
            "ro_origen": "OTRO_ORIGEN", "ro_fecha_registro": datetime(2000, 1, 1),
        }
        for campo, valor in cambios.items():
            with self.subTest(campo=campo):
                self._rechazar_modificacion(registro, campo, valor)

    def test_registro_of_no_permite_cambiar_relacion_envio(self):
        registro = self._registro(self._intento())
        otro = self._envio("Otro ficticio")
        self.db.commit()
        self._rechazar_modificacion(registro, "envio", otro)

    def test_registro_of_no_se_elimina_ni_libera_su_numero(self):
        registro = self._registro(self._intento())
        otro = self._envio("Otro ficticio")
        intento_otro = self._intento(envio_id=otro.id)
        self.db.commit()
        self._rechazar_eliminacion(registro)
        with self.assertRaises(IntegrityError):
            self._registro(intento_otro)
        self.db.rollback()
        self.assertEqual(self.db.query(RegistroOF).count(), 1)

    def _caso_con_sucesor(self):
        caso, anterior = self._resuelta("OF_INEXISTENTE")
        sucesor = self._intento(envio_id=anterior.envio_id, io_secuencia=2, io_anterior_id=anterior.id)
        caso.ch_intento_sucesor_id = sucesor.id
        self.db.commit()
        return caso, sucesor

    def test_sucesor_consumido_no_puede_limpiar_su_referencia(self):
        caso, _ = self._caso_con_sucesor()
        self._rechazar_modificacion(caso, "ch_intento_sucesor_id", None)

    def test_sucesor_consumido_no_puede_sustituirse(self):
        caso, _ = self._caso_con_sucesor()
        otro = self._envio("Otro ficticio")
        sustituto = self._intento(envio_id=otro.id)
        self.db.commit()
        self._rechazar_modificacion(caso, "ch_intento_sucesor_id", sustituto.id)

    def test_consumo_desde_objeto_expirado_preserva_resolucion(self):
        caso, anterior = self._resuelta("OF_INEXISTENTE")
        sucesor = self._intento(envio_id=anterior.envio_id, io_secuencia=2, io_anterior_id=anterior.id)
        sucesor_id = sucesor.id
        self.db.commit()
        antes = self._snapshot_persistencia()
        self.db.expire(caso)
        caso.ch_intento_sucesor_id = sucesor_id
        self.db.commit()
        despues = self._snapshot_persistencia()
        fila = antes["conciliaciones_h2h"][0]
        self.assertIsNone(fila["ch_intento_sucesor_id"])
        fila["ch_intento_sucesor_id"] = sucesor_id
        self.assertEqual(despues, antes)

    def test_objeto_desactualizado_no_sobrescribe_resolucion_definitiva(self):
        caso = self._caso(self._intento())
        self.db.commit()
        caso_id = caso.id
        from sqlalchemy.orm import Session
        with Session(bind=self.engine) as otra:
            copia = otra.get(ConciliacionH2H, caso_id)
            copia.ch_estado = "OF_INEXISTENTE"
            copia.ch_fecha_verificacion = datetime(2026, 10, 25, 12)
            copia.ch_operador = "operador-demo"
            copia.ch_metodo = METODO_VERIFICACION_STARKEN
            copia.ch_observacion = "Verificado"
            otra.commit()
        self._rechazar_modificacion(caso, "ch_observacion", "Nota de copia vieja")

    def test_multiples_of_legitimas_en_intentos_distintos_del_mismo_envio(self):
        original = self._intento(io_estado="CON_OF")
        primera = self._registro(original, ro_numero="000111")
        retorno = self._intento(io_secuencia=2, io_estado="CON_OF", io_anterior_id=original.id)
        segunda = self._registro(retorno, ro_numero="000222")
        self.db.commit()
        self.assertEqual(primera.envio_id, segunda.envio_id)
        self.assertNotEqual(primera.intento_id, segunda.intento_id)
        self.assertEqual([item.ro_numero for item in self.db.query(RegistroOF).order_by(RegistroOF.id)], ["000111", "000222"])

    def test_limite_de_hooks_no_impide_actualizaciones_core(self):
        movimiento = self._movimiento()
        self.db.commit()
        movimiento_id = movimiento.id
        self.db.execute(update(MovimientoEnvio.__table__).where(
            MovimientoEnvio.id == movimiento_id
        ).values(me_detalle={"nota": "Core elude hooks de mapper"}))
        self.db.commit()
        self.db.refresh(movimiento)
        self.assertEqual(movimiento.me_detalle, {"nota": "Core elude hooks de mapper"})


if __name__ == "__main__":
    unittest.main()
