# Operación de Mensajería

Guía del flujo disponible en la rama actual. El estado desplegado debe verificarse
por separado. Para ensayar, usar solo [datos demo](DEMO_OPERATIVA_V2.md).
Los botones de correo de una instancia real pueden enviar mensajes reales.

## Envíos y catálogos

Desde Envios (`/crear_envio`), elegir envío manual (`/nuevo_envio`) o
carga masiva (`/carga_masiva`).
Registrar remitente/correo, división y centro de costo, destinatario, RUT
(`0` si no se informó), dirección, comuna/región, teléfono, tipo de envío,
bultos y kilos; correo del destinatario y observación son opcionales.
Revisar el código de agencia cuando corresponda.

El sistema normaliza teléfonos pegados con `+56`, espacios y símbolos,
homogeneiza nombres y elimina acentos operativos. Revisar los valores guardados.
Catálogos permite gestionar remitentes y destinatarios frecuentes; las sugerencias
de formularios no sustituyen revisar los datos del envío.

## Carga masiva

1. Descargar la plantilla vigente desde la pantalla.
2. Completar remitente común y destinatarios por fila; conservar encabezados.
3. Subir Excel, revisar errores y advertencias y corregir/revalidar las filas.
4. Confirmar una sola vez cuando los datos sean válidos.

La revisión previa no inserta envíos; la confirmación los deja pendientes.
Si la confirmación responde con error o se interrumpe, consultar Pendientes antes
de repetirla: el token temporal aún no garantiza idempotencia ante concurrencia
o fallo posterior al commit. No borrar `tmp_cargas/` durante una carga activa.
Los envíos de agencia sin código no podrán generar CSV.

## Pendientes, selección y CSV Starken

En `/envios`, revisar y editar datos antes de seleccionar los pedidos.
Solo puede eliminarse un pendiente sin OF, lote, trazabilidad ni relaciones
operativas. Un envío en proceso o histórico no se elimina desde esa acción.
No intentar liberar un envío borrando datos de lote o de resultado.

Seleccionar explícitamente los envíos y usar Generar CSV Starken:
elegir descarga para carga manual en Starken o envío por correo configurado.
Solo la selección válida pasa a `en_proceso`; se guardan lote, fila, archivo
y fecha de exportación. El CSV se genera en CP1252 con punto y coma;
`OBSERVACION_CLIENTE` recibe la observación del envío.

Se intenta guardar copia local del CSV, pero un fallo de esa copia no garantiza
cancelar el lote. Conservar el archivo descargado y verificar En proceso antes
de repetir una acción. El correo del CSV ocurre después de registrar el lote:
un error de correo no devuelve automáticamente los pedidos a pendientes.

## En proceso e importación OF

En `/en_proceso`, identificar el lote original y obtener su respuesta Starken.
Cargar el archivo correspondiente manualmente o usar búsqueda asistida en
`/of_correo`. La lectura IMAP requiere configuración real y no se prueba
durante desarrollo aislado.

El procesador común valida filas, correspondencia y OF duplicadas antes de
aplicar resultados. Normaliza números provenientes de Excel para evitar `.0`.
Los resultados OK pasan a Histórico y registran fecha OF; los errores necesitan
revisión. No interpretar un procesamiento válido como confirmación de que todas
las filas fueron exitosas.

La pantalla `/of_exito/<lote>` muestra total, OK, errores y primera/última OF
copiables. Ese rango ayuda a trabajar en Starken, pero no acredita retiro físico.
Al procesar OF se intenta enviar respaldo interno; confirmar un fallo de respaldo
sin repetir automáticamente la importación ni generar otro lote.

## Cancelación de lotes

La cancelación valida y bloquea primero las filas del lote. Para un lote permitido,
devuelve sus envíos en proceso a pendientes y limpia las asociaciones legacy
correspondientes. No equivale a anular una OF en Starken.

Si hay un solo resultado H2H ambiguo, se rechaza el lote completo sin limpiar
su evidencia. No usar cancelación como mecanismo de reintento tras ese error.

## Protecciones H2H

Un resultado `ERROR` cuyo detalle contiene la palabra `H2H` se considera
ambiguo, sin distinguir mayúsculas. Por ejemplo,
`Error al enviar fila X a servicio H2H` **no confirma que no se creó una OF**.

Las Fases 1.1 y 1.1.1 bloquean cancelación del lote ambiguo, reimportación que
sustituya su resultado, generación de otro CSV con ese antecedente y eliminación
individual con trazabilidad. Se conservan detalles y asociaciones originales.
Los errores normales sin ese antecedente no se clasifican todos como H2H.

Ante un bloqueo:

1. Conservar lote, fila, archivo y detalle originales.
2. Verificar el caso con el responsable operativo y la plataforma Starken.
3. No cambiar estados ni borrar evidencia para forzar el reintento.

No existe aún pantalla ni servicio funcional de conciliación manual o autorización
de sucesor. Las nuevas tablas persistentes no habilitan ese procedimiento.
Ver [Estado del proyecto](ESTADO_PROYECTO.md).

## Retiros V2

Desde Operación, abrir `/operacion/retiros`. La cola muestra envíos con OF,
fecha OF, punto de retiro local activo, sin anulación ni retiro vigente.
Academia queda fuera del retiro local; estar en Histórico no basta para aparecer.

Buscar por OF, remitente o destinatario; revisar selección, cantidad y bultos.
Registrar fecha/hora efectiva, responsable y observación y confirmar el retiro
físico una sola vez. Se conserva una asociación por envío con snapshot de bultos.
Si otro operador ya retiró un envío, la operación se rechaza y debe recargarse
la cola; no completar el resto suponiendo que el primer intento quedó parcial.

El servicio de anulación de retiros conserva asociaciones históricas, pero no
hay interfaz actual para ejecutarlo. No manipular asociaciones a mano.
Registrar retiro no activa por sí solo el motor de Avisos V2.

## Avisos legacy

Después del retiro físico, abrir Avisos, revisar lote/funcionarios y enviar
cuando corresponda. Este momento es una decisión del operador: el flujo legacy
no exige automáticamente el registro de retiro V2.

El funcionario recibe resumen con Excel; un destinatario con correo registrado
puede recibir su aviso. Cancelar avisos marca pendientes como cancelados;
no cancela lote, envío ni OF y no borra mensajes enviados.

**Fallo parcial:** varios mensajes pueden haber sido aceptados aunque la base
mantenga el aviso pendiente. Antes de repetir, revisar los envíos aceptados con
el responsable; no asumir que pendiente significa que no salió ningún correo.
Aceptación SMTP/API tampoco confirma entrega final.

Avisos V2 dispone de persistencia y motor probado, pero no está conectado a
esta pantalla. No activar ambos flujos sobre los mismos pedidos.

## Histórico

En `/historico`, filtrar por mes/fechas, OF, remitente, destinatario y estado
vigente/anulado; revisar detalle, exportar resultados o descargar seleccionados.

Anular seleccionados exige motivo y conserva registro, responsable y fecha.
El sistema envía respaldo antes de confirmar: el correo del sistema recibe el
conjunto y cada remitente solo sus propios registros. Si falla el respaldo,
no se confirma la anulación.

La eliminación de seleccionados o filtrados es física y exige la clave configurada
y respaldo por correo previo. No usarla como limpieza de pruebas sobre datos reales.
Las relaciones protegidas pueden impedir el borrado. Un Excel de respaldo
operativo no sustituye un respaldo completo y restaurable de la base.

Los correos y el commit no son atómicos: un mensaje puede salir y luego fallar
la operación o un envío posterior. Confirmar estado en la base mediante los
procedimientos autorizados antes de repetir. Reportes, PDF de incidencias y
panel Admin no forman parte de la interfaz actual.
