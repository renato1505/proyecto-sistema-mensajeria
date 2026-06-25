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
- `routes/auth.py`: login, sesion, vencimiento por inactividad, bloqueo temporal por intentos fallidos y carga de usuarios.
- `routes/admin.py`: administracion de usuarios, areas, auditoria y seguridad de acceso.
- `services/catalogos_operativos.py`: reglas compartidas de catalogos, validaciones y persistencia.
- `services/historico.py`: filtros, queries, exportacion y respaldo del historico.
- `services/starken.py`: formato CSV compatible con Starken.
- `services/of_processor.py`: validacion y aplicacion de archivos OF.
- `services/correo_of.py`: lectura asistida de correos con OF.
- `services/avisos.py`: generacion de Excel y envio de avisos/respaldo.
- `services/auditoria.py`: registro y consulta de acciones sensibles del portal.
- `services/permisos.py`: matriz central de permisos por area/rol y proteccion de rutas.
- `services/carga_masiva.py`: plantilla Excel, validacion y construccion de envios masivos.
- `services/lotes.py`: reglas de cruce entre lotes, CSV y correos OF.
- `services/normalizacion_operativa.py`: limpieza de datos operativos existentes al iniciar la app.
- `utils/texto.py`: normalizacion de nombres, textos y ordenes de flete.

## Separacion de pantallas grandes

Para mejorar mantenibilidad, las pantallas con mas carga visual se separan en parciales.

### Administracion

- `templates/admin.html`: orquestador principal.
- `templates/admin/_header_tabs.html`: hero y navegacion interna.
- `templates/admin/_usuarios.html`: metricas, areas y tarjetas de usuarios.
- `templates/admin/_seguridad.html`: bloqueos, recuperacion, accesos y permisos.
- `templates/admin/_auditoria.html`: filtros, listado y exportacion.
- `templates/admin/_modals.html`: modales de areas, usuarios, accesos y recuperacion.
- `routes/admin.py`: panel principal y registro de submodulos.
- `routes/admin_usuarios.py`: endpoints de usuarios y areas.
- `routes/admin_seguridad.py`: endpoints de bloqueos, politica de acceso y recuperacion de clave.
- `routes/admin_auditoria.py`: exportacion de auditoria.
- `routes/admin_helpers.py`: validaciones compartidas de permisos admin y confirmacion de usuario.
- `services/admin_context.py`: construye el contexto completo del panel para que `routes/admin.py` no concentre consultas visuales.
- `static/css/admin.css`: indice de imports para estilos de Administracion.
- `static/css/admin/*.css`: estilos separados por layout, usuarios, seguridad, auditoria y responsive.

### Reportes

- `templates/reportes.html`: orquestador principal.
- `templates/reportes/_hero.html`: cabecera y metricas.
- `templates/reportes/_lista.html`: grupos, casos, detalle, acciones y modales de caso.
- `templates/reportes/_formulario.html`: creacion de nuevo reporte.
- `static/js/reportes.js`: modales, autocompletados y apertura directa por hash.
- `static/css/reportes.css`: indice de imports para estilos de Reportes.
- `static/css/reportes/*.css`: estilos separados por layout, lista, formularios, modales y responsive.

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
- Normalizar OF tipo Excel para evitar valores como `272472119.0`.
- Guardar nombres de remitentes y destinatarios con mayuscula inicial por palabra.
- Eliminar tildes de nombres, comunas, regiones, direcciones y observaciones operativas para evitar duplicados funcionales.
- No mostrar avisos antiguos si no fueron marcados desde el nuevo flujo.
- El respaldo a Mensajeria se intenta enviar inmediatamente al procesar OF.
- Los avisos a funcionarios son manuales/asistidos para evitar correos prematuros.
- Los avisos a destinatarios solo se envian si existe correo destinatario registrado.
- La anulacion de OF no elimina datos; mantiene trazabilidad.
- El login bloquea temporalmente una combinacion usuario/IP tras varios intentos fallidos.
- El administrador puede ver y liberar bloqueos temporales desde `/admin`.
- Las acciones sensibles quedan registradas en la tabla `auditoria`.
- Los permisos de menu y rutas criticas se centralizan en `services/permisos.py`.
- Los intentos de acceso sin permiso se registran como `permiso_denegado`.
- `.env`, respaldos, logs y archivos Excel reales no deben subirse a Git.

## Pendientes de orden tecnico

- Agregar pruebas unitarias para `services/of_processor.py`, `services/avisos.py` y `services/starken.py`.
- Evaluar migraciones formales con Alembic cuando la base quede instalada en otro equipo.
- Revisar si conviene dividir `services/carga_masiva.py` en plantilla, lectura y validacion cuando crezcan las reglas.
- Persistir bloqueos de login en base de datos si se requiere trazabilidad de seguridad posterior a reinicios.
