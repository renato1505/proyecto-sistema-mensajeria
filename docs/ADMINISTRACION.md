# Administracion del Portal

Este documento resume el uso actual del apartado `/admin`.

## Objetivo

El panel de administracion centraliza funciones sensibles del portal:

- usuarios;
- areas operativas;
- seguridad de acceso;
- auditoria de acciones.

La pantalla esta separada en tres secciones internas:

- `Usuarios`: creacion, edicion, estado, clave, areas y eliminacion.
- `Seguridad`: intentos fallidos, bloqueos activos y matriz base de permisos.
- `Auditoria`: trazabilidad filtrable de acciones sensibles.

Por ahora el foco real sigue siendo Mensajeria. Las areas Recepcion y Seguridad quedan preparadas para crecimiento futuro.

## Usuarios

Desde Administracion se puede:

- crear usuarios;
- registrar RUT del usuario;
- asignar area;
- asignar rol `visita`, `usuario`, `supervisor` o `admin`;
- editar nombre, area y rol;
- cambiar clave temporal;
- activar o desactivar;
- eliminar usuarios.

La seccion de usuarios incluye busqueda y filtros por:

- texto libre;
- area;
- rol;
- estado;
- clave temporal;
- usuarios sin ultimo acceso.

Cada tarjeta de usuario muestra el ultimo acceso registrado y la ultima IP detectada. Si el usuario todavia no ha iniciado sesion desde que se activo esta mejora, aparecera como `Sin registro`.

Cada tarjeta tambien tiene acceso a la bitacora del usuario. Esta vista muestra sus ultimos eventos registrados y permite saltar directo a la auditoria filtrada por ese usuario.

Tambien muestra una salud de acceso con etiquetas como:

- `OK`;
- `Clave temporal`;
- `Sin ultimo acceso`;
- `Inactivo`;
- `Admin`.

Cuando se crea un usuario o el administrador cambia su clave, esa clave queda marcada como temporal. En el siguiente ingreso, el usuario debe reemplazarla por una clave propia antes de usar el portal.

Cuando el sistema genera una clave temporal, la alerta permite copiarla rapidamente. Por seguridad, la clave no se puede volver a visualizar despues, porque en base de datos solo queda guardado el hash. Si se pierde, se debe generar una nueva clave temporal.

Recomendacion operativa:

- desactivar usuarios cuando sea una pausa temporal;
- eliminar solo cuando el acceso no deba existir mas;
- mantener siempre al menos un usuario administrador activo.
- entregar claves temporales solo por canales internos controlados.

Protecciones activas:

- no se puede eliminar el ultimo administrador activo;
- no se puede desactivar el ultimo administrador activo;
- no se puede quitar el rol admin al ultimo administrador activo.
- no se puede desactivar el propio usuario en sesion;
- no se puede quitar el propio rol admin en sesion;
- para eliminar un usuario se debe escribir su usuario exacto;
- para desactivar un admin se debe escribir su usuario exacto;
- para quitar rol admin se debe escribir su usuario exacto.

## Areas

Las areas permiten ordenar permisos y menus por modulo.

Actualmente se usan principalmente:

- `administracion`;
- `mensajeria`;
- `recepcion`;
- `seguridad`.

Estas cuatro areas son areas base del portal. El sistema las asegura automaticamente al abrir Administracion y no permite eliminarlas, para evitar que un usuario quede asignado a un modulo sin permisos definidos.

La creacion de nuevas areas usa solo el nombre visible. El codigo interno se genera automaticamente y queda oculto para evitar errores operativos.

Desde `Admin > Usuarios` se puede:

- crear areas;
- editar el nombre visible;
- ver cuantos usuarios tiene asignados;
- eliminar areas sin usuarios asignados.

## Auditoria

La vista de auditoria muestra acciones sensibles registradas en base de datos.

En `Admin > Usuarios` existe un bloque de eventos recientes para revisar rapidamente acciones sensibles sin entrar a la auditoria completa.

Permite filtrar por:

- usuario;
- accion;
- entidad;
- limite de registros.

Tambien permite exportar los registros filtrados a Excel. Cada exportacion queda registrada como `exportar_auditoria`.

Ejemplos de acciones registradas:

- crear usuario;
- editar usuario;
- cambiar clave;
- eliminar usuario;
- anular historico;
- eliminar historico;
- crear reporte;
- cerrar reporte;
- subir evidencia;
- desbloquear login.

## Seguridad

El panel de seguridad muestra intentos fallidos y bloqueos temporales del login.

Regla actual:

- 5 intentos fallidos;
- bloqueo temporal de 10 minutos;
- bloqueo asociado a usuario + IP.

El administrador puede liberar un bloqueo manualmente.

La politica de intentos y duracion puede ajustarse desde `Admin > Seguridad`. Este ajuste aplica al servidor actual; si Render reinicia el proceso, se recomienda verificar la configuracion nuevamente hasta que exista una configuracion persistente en base de datos.

La seccion tambien muestra una bitacora de accesos recientes con:

- login exitoso;
- login fallido;
- login bloqueado.

Estos eventos se guardan en la tabla `auditoria`.

La pantalla principal muestra solo los ultimos accesos para mantener la vista compacta. El detalle completo se abre desde la ventana emergente.

Si un usuario tiene intentos fallidos o bloqueo activo, su tarjeta de usuario lo mostrara en la salud de acceso para que el administrador no tenga que revisar la bitacora manualmente.

Las solicitudes de recuperacion enviadas desde `Olvide mi clave` quedan en una bandeja gestionable dentro de `Admin > Seguridad`.

Para que un usuario pueda solicitar recuperacion de clave, su ficha debe tener RUT registrado. La recuperacion desde el login solicita usuario + RUT, no correo.

Cada solicitud muestra:

- usuario;
- RUT validado;
- IP de origen;
- fecha;
- estado.

Estados internos:

- `Pendiente`: solicitud nueva, visible en Admin > Seguridad;
- `Resuelta`: se genero una clave temporal desde la solicitud;
- `Rechazada`: el administrador descarto la solicitud.

Desde la solicitud el administrador puede:

- generar una clave temporal para el usuario existente.
- rechazar la solicitud si no corresponde.

Cuando se genera una clave temporal desde recuperacion, la clave se muestra una sola vez en la alerta del portal y debe entregarse por un canal interno seguro. No se guarda la clave en auditoria.

Cada solicitud tambien deja trazabilidad en auditoria como `solicitud_recuperacion`. Si el RUT no coincide o el usuario no existe, queda registrado como `solicitud_recuperacion_rechazada`. Las acciones posteriores quedan registradas como `generar_clave_recuperacion` o `rechazar_solicitud_recuperacion`.

## Permisos Por Modulo

Los permisos ya no son solo visuales. La app usa `services/permisos.py` para:

- decidir que opciones se muestran en el menu;
- proteger rutas criticas;
- registrar intentos de acceso sin permiso en auditoria.

Modelo actual:

- rol `admin`: puede acceder a todos los permisos definidos;
- rol `supervisor` en area `mensajeria`: puede operar el flujo completo de Mensajeria, incluyendo acciones criticas;
- rol `usuario` en area `mensajeria`: puede operar el dia a dia, pero no acciones criticas como anular/eliminar historico o gestionar reportes;
- rol `visita` en area `mensajeria`: puede consultar secciones de lectura sin crear, editar, anular ni eliminar;
- areas `recepcion` y `seguridad`: quedan reservadas, sin heredar permisos de Mensajeria;
- permisos denegados quedan registrados como `permiso_denegado`.

Permisos operativos principales:

- `envios.crear`;
- `carga_masiva.gestionar`;
- `pendientes.gestionar`;
- `proceso.gestionar`;
- `historico.ver`;
- `historico.exportar`;
- `historico.anular`;
- `historico.eliminar`;
- `reportes.gestionar`;
- `avisos.gestionar`;
- `catalogos.gestionar`;
- `admin.panel`.

Limitacion actual:

- los intentos fallidos se guardan en memoria del servidor;
- si Render reinicia el servicio, esos intentos se limpian;
- para una etapa mas formal conviene persistirlos en base de datos.

## Checklist Antes De Deploy

Ejecutar localmente:

```powershell
python -m compileall -q routes\admin.py routes\auth.py services\auditoria.py services\recuperacion.py
python -m unittest discover -s tests -p "test_*.py"
python tests\smoke_check.py
```

Luego probar manualmente:

- entrar con usuario admin;
- crear usuario de prueba;
- editar usuario;
- cambiar clave;
- desactivar/activar;
- revisar auditoria;
- provocar intentos fallidos y confirmar bloqueo;
- liberar bloqueo desde Administracion.
