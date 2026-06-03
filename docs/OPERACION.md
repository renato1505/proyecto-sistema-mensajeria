# Procedimiento operativo

Este documento resume el uso diario del Sistema de Gestion de Mensajeria.

## 1. Registrar envio

1. Entrar a `Nuevo envio`.
2. Completar remitente, destinatario, direccion, comuna, telefono, tipo de envio, bultos y kilos.
3. Usar RUT `0` cuando el destinatario no entregue RUT.
4. Guardar el envio.

El envio queda en estado `pendiente` para revision.

## 2. Revisar pendientes

1. Entrar a `Pendientes`.
2. Revisar datos de cada envio.
3. Editar cualquier error antes de generar el archivo Starken.
4. Eliminar solo si el envio no corresponde.

## 3. Generar archivo Starken

1. En `Pendientes`, presionar `Generar y enviar CSV`.
2. El sistema genera un lote, guarda respaldo local y envia el CSV por correo.
3. Los envios pasan a `En proceso`.

No repetir esta accion si no hay claridad sobre el estado del correo o del lote.

## 4. Cargar respuesta OF

1. Subir en Starken el archivo CSV recibido por correo.
2. Descargar desde Starken el archivo Excel con resultado OF.
3. Entrar a `En proceso`.
4. Subir el Excel en el lote correspondiente.

Si las filas, estados u ordenes de flete no coinciden, el sistema bloquea el procesamiento.

## 5. Historico

Los envios con resultado `OK` pasan al historico.

Desde `Historico` se puede:

- Filtrar por mes, OF, remitente, destinatario o fechas.
- Exportar resultados filtrados.
- Descargar registros seleccionados.
- Eliminar registros filtrados con clave de eliminacion.

Cuando se elimina historico, primero se genera un respaldo Excel en `respaldos_historico`.

## 6. Pruebas manuales

La prueba de correo envia un email real. Ejecutarla solo cuando se quiera validar Gmail:

```powershell
python tests\test_correo.py --confirmar
```

