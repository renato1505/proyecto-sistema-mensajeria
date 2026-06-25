# Procedimiento operativo

Este documento resume el uso diario del modulo de Mensajeria dentro del Portal Operativo.

## 1. Registrar envio

1. Entrar a `Envios`.
2. Elegir `Envio manual`.
3. Completar remitente, destinatario, direccion, comuna, telefono, tipo de envio, bultos y kilos.
4. Usar RUT `0` cuando el destinatario no entregue RUT.
5. Guardar el envio.

El envio queda en estado `pendiente` para revision.

El sistema normaliza automaticamente:

- telefonos pegados con espacios, simbolos o `+56`;
- nombres con mayusculas/minusculas inconsistentes;
- acentos en nombres y datos operativos para evitar duplicados funcionales.

## 1.1 Registrar carga masiva

1. Entrar a `Envios`.
2. Elegir `Envio masivo`.
3. Descargar la plantilla si se requiere.
4. Completar remitente comun y filas de destinatarios.
5. Subir el archivo y revisar advertencias/errores.
6. Confirmar la carga solo cuando todas las filas relevantes esten correctas.

La carga masiva no modifica pendientes hasta confirmar la revision. Si hay datos faltantes o telefonos invalidos, se corrigen antes de guardar.

## 2. Revisar pendientes

1. Entrar a `Pendientes`.
2. Revisar datos de cada envio.
3. Editar cualquier error antes de generar el archivo Starken.
4. Eliminar solo si el envio no corresponde.

## 3. Generar archivo Starken

1. En `Pendientes`, presionar `Generar CSV Starken`.
2. El sistema muestra una ventana con dos opciones:
   - `Descargar CSV`: usar cuando se subira el archivo directamente al sistema Starken.
   - `Enviar por correo`: usar cuando el CSV debe enviarse por correo.
3. El sistema genera un lote, guarda respaldo local y mueve los envios a `En proceso`.

No repetir esta accion si no hay claridad sobre el estado del lote.

## 4. Cargar respuesta OF

1. Subir en Starken el archivo CSV descargado o enviado por correo.
2. Esperar la respuesta OF.
3. Entrar a `En proceso`.
4. Usar carga OF manual o `Buscar OF en correo`.
5. Procesar el archivo OF correspondiente al lote.

Si las filas, estados u ordenes de flete no coinciden, el sistema bloquea el procesamiento.

Si la OF viene desde Excel con formato numerico, el sistema limpia automaticamente sufijos como `.0`.

Cuando el archivo OF se procesa correctamente, el sistema muestra una pantalla de exito con:

- total de envios del lote;
- cantidad OK;
- cantidad con error;
- primera OF;
- ultima OF.

La primera y ultima OF se pueden copiar haciendo clic sobre cada numero. Esta pantalla ayuda a imprimir etiquetas en Starken usando rango desde/hasta.

## 5. Avisos y respaldo

Al procesar OF:

- El sistema intenta enviar respaldo completo del lote a Mensajeria.
- Los envios OK pasan al historico.
- Los avisos a funcionarios y destinatarios quedan pendientes.

Cuando Starken ya haya retirado los pedidos:

1. Entrar a `Avisos`.
2. Abrir el lote pendiente.
3. Seleccionar funcionarios.
4. Enviar correos.

Al enviar avisos:

- El funcionario recibe un correo resumen con Excel adjunto.
- El destinatario recibe un correo formal si el envio tiene correo destinatario registrado.
- Los avisos enviados dejan de aparecer como pendientes.

Si el lote no debe ser avisado, usar `Cancelar avisos`. Esto marca el lote como cancelado para que no vuelva a aparecer en la lista de avisos pendientes.

## 6. Historico

Los envios con resultado `OK` pasan al historico.

Desde `Historico` se puede:

- Filtrar por mes, OF, remitente, destinatario o fechas.
- Filtrar por estado OF: vigentes o anuladas.
- Exportar resultados filtrados.
- Descargar registros seleccionados.
- Anular registros seleccionados con motivo.
- Eliminar registros seleccionados con clave de eliminacion.
- Eliminar registros filtrados con clave de eliminacion.

Cuando se elimina historico en cloud, primero se envia un respaldo Excel por correo a Mensajeria. El respaldo indica fecha, filtros aplicados y responsable de la eliminacion. Si el correo de respaldo falla, no se eliminan registros.

La anulacion no elimina el registro. Marca la OF como anulada, guarda motivo/fecha/responsable y envia respaldo Excel antes de confirmar. El correo del sistema recibe el respaldo completo y cada remitente recibe solo sus propios registros anulados. Si el correo de respaldo falla, no se anulan registros.

## 6.1 Reportes y excepciones

Los reportes permiten documentar incidencias posteriores al despacho. Al eliminar un reporte, el sistema exige motivo, genera PDF de respaldo y envia correo antes de borrar el caso. El correo y la auditoria muestran el responsable que realizo la eliminacion.

## 7. Pruebas manuales

La prueba de correo envia un email real. Ejecutarla solo cuando se quiera validar Gmail:

```powershell
python tests\test_correo.py --confirmar
```
