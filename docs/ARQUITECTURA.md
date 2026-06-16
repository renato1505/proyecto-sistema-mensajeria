# Arquitectura del Portal Operativo

Este documento resume como esta organizado el Portal Operativo. Actualmente el modulo principal es Mensajeria, con una estructura preparada para crecer hacia otras areas sin mezclar reglas de negocio.

## Flujo operativo

1. `Nuevo envio` registra pedidos en estado `pendiente`.
2. `Carga masiva` permite importar pedidos desde plantilla Excel y dejarlos en `pendiente`.
3. `Pendientes` revisa pedidos y genera el CSV Starken.
4. Al generar CSV, el sistema muestra un modal con dos opciones:
   - Descargar CSV para cargarlo manualmente en Starken.
   - Enviar CSV por correo cuando sea necesario.
5. Los pedidos pasan a `en_proceso` y quedan asociados a un `e_lote`.
6. `En proceso` permite cargar OF manualmente o buscar OF desde correo.
7. Al procesar OF:
   - Los pedidos OK pasan a `historico`.
   - Se envia respaldo completo a Mensajeria.
   - Se marcan avisos a funcionarios como `pendiente`.
   - Se muestra pantalla de exito con primera y ultima OF copiables.
8. `Avisos` muestra solo lotes con avisos pendientes.
9. Al enviar avisos, los pedidos quedan marcados como `enviado` y se notifica tambien a destinatarios con correo registrado.
10. Los avisos pueden cancelarse si no corresponde enviar correos.
11. `Historico` permite filtrar, exportar, anular y respaldar registros cerrados.

## Modulos principales

- `routes/paginas.py`: inicio, pendientes y en proceso.
- `routes/envios.py`: nuevo envio, edicion y eliminacion de envios individuales.
- `routes/carga_masiva.py`: plantilla Excel, validacion, revalidacion y confirmacion de cargas masivas.
- `routes/starken_lotes.py`: generacion de CSV, envio a Starken, carga OF, pantalla de exito OF, OF desde correo y cancelacion de lote.
- `routes/historico.py`: vista, exportacion, descarga y eliminacion respaldada del historico.
- `routes/historico_ajax.py`: autocompletados del historico.
- `routes/catalogos.py`: pantalla administrativa de remitentes y destinatarios.
- `routes/catalogos_ajax.py`: autocompletados y guardado rapido desde formularios operativos.
- `routes/avisos.py`: pantallas y acciones para avisos a funcionarios/destinatarios y cancelacion de avisos.
- `services/catalogos_operativos.py`: reglas compartidas de catalogos, validaciones y persistencia.
- `services/historico.py`: filtros, queries, exportacion y respaldo del historico.
- `services/starken.py`: formato CSV compatible con Starken.
- `services/of_processor.py`: validacion y aplicacion de archivos OF.
- `services/correo_of.py`: lectura asistida de correos con OF.
- `services/avisos.py`: generacion de Excel y envio de avisos/respaldo.
- `services/carga_masiva.py`: plantilla Excel, validacion y construccion de envios masivos.
- `services/lotes.py`: reglas de cruce entre lotes, CSV y correos OF.

## Estados relevantes

- `e_estado`
  - `pendiente`: listo para revision antes de generar CSV.
  - `en_proceso`: CSV generado y esperando OF.
  - `historico`: envio cerrado con OF OK.
- `e_estado_correo`
  - `pendiente`: lote generado con intencion de correo.
  - `descargado`: CSV descargado para carga manual en Starken.
  - `enviado`: CSV enviado por correo.
  - `error`: fallo envio de correo.
- `e_aviso_funcionario_estado`
  - `pendiente`: falta avisar al funcionario.
  - `enviado`: aviso ya enviado.
  - `cancelado`: se decidio no enviar el aviso.
- `e_anulado`
  - `false`: OF vigente.
  - `true`: OF marcada como anulada en historico.

## Reglas de seguridad operativa

- No procesar OF si el archivo no coincide en filas, ordenes o lote.
- No mostrar avisos antiguos si no fueron marcados desde el nuevo flujo.
- El respaldo a Mensajeria se intenta enviar inmediatamente al procesar OF.
- Los avisos a funcionarios son manuales/asistidos para evitar correos prematuros.
- Los avisos a destinatarios solo se envian si existe correo destinatario registrado.
- La anulacion de OF no elimina datos; mantiene trazabilidad.
- `.env`, respaldos, logs y archivos Excel reales no deben subirse a Git.

## Pendientes de orden tecnico

- Agregar pruebas unitarias para `services/of_processor.py`, `services/avisos.py` y `services/starken.py`.
- Evaluar migraciones formales con Alembic cuando la base quede instalada en otro equipo.
- Revisar si conviene dividir `services/carga_masiva.py` en plantilla, lectura y validacion cuando crezcan las reglas.
