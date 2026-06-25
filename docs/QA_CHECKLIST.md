# Checklist QA Del Portal

Este checklist se debe ejecutar antes de subir una version nueva a Render.

## Checks Tecnicos

Desde la carpeta `sistema_mensajeria`:

```powershell
python -m compileall -q main.py config database routes services scripts tests
python -m unittest discover -s tests -p "test_*.py"
python tests\smoke_check.py
```

Resultado esperado:

- tests unitarios en `OK`;
- rutas principales con codigo `200`;
- POST sin CSRF bloqueado con `400`;
- POST con CSRF permitido;
- validaciones negativas respondiendo como corresponde.

## Login Y Seguridad

- Entrar con usuario admin.
- Entrar con usuario de Mensajeria.
- Confirmar que un usuario normal no ve Administracion.
- Confirmar que Admin no ve el menu operativo de Mensajeria como flujo principal.
- Probar clave incorrecta hasta generar bloqueo.
- Confirmar que el bloqueo aparece en Admin > Seguridad.
- Liberar bloqueo desde Admin.
- Crear solicitud de recuperacion con usuario + RUT correcto.
- Rechazar una solicitud.
- Generar clave temporal desde una solicitud.
- Ingresar con clave temporal y confirmar redireccion a cambio de clave.

## Administracion

- Confirmar que en `/admin` no aparece el boton superior de notificaciones.
- Crear usuario con RUT.
- Editar nombre, RUT, area y rol.
- Cambiar clave temporal.
- Desactivar y activar usuario.
- Intentar eliminar/desactivar el ultimo admin activo y confirmar bloqueo.
- Crear area solo con nombre.
- Editar area.
- Intentar eliminar area con usuarios asignados.
- Revisar auditoria filtrando por usuario, accion y entidad.
- Exportar auditoria.

## Mensajeria

- Entrar a `Envios` y confirmar que permite elegir entre envio manual y carga masiva.
- Crear envio individual.
- Pegar telefono con `+56`, espacios o simbolos y confirmar normalizacion.
- Crear envio con correo destinatario opcional.
- Crear envio con observacion.
- Confirmar que comuna completa region.
- Editar envio pendiente.
- Generar CSV Starken descargado.
- Generar CSV Starken enviado por correo si aplica.

## Carga Masiva

- Descargar plantilla.
- Cargar archivo con remitente comun.
- Cargar destinatarios con telefono en distintos formatos.
- Confirmar que correo destinatario y observacion se leen.
- Confirmar que observacion no rompe H2H por puntos/comas.
- Confirmar que regiones se completan desde comuna cuando aplica.
- Confirmar que filas con error se pueden revisar/editar.

## Proceso OF

- Cargar archivo OF.
- Confirmar que OF no queda con `.0`.
- Confirmar paso correcto a historico.
- Confirmar pantalla de exito con primera y ultima OF.
- Click en primera/ultima OF debe copiar al portapapeles.
- Ir a avisos desde pantalla de exito.

## Historico

- Filtrar por OF.
- Filtrar por remitente.
- Filtrar por destinatario.
- Filtrar por fecha/mes.
- Filtrar por vigentes/anulados.
- Ver detalle.
- Descargar seleccionado.
- Anular seleccionados con motivo.
- Confirmar que anular envia respaldo al correo del sistema y al remitente correspondiente.
- Confirmar que el correo de anulacion muestra el responsable que realizo la gestion.
- Confirmar que si se anulan registros de varios remitentes, cada remitente recibe solo sus propios registros.
- Confirmar marca visual de OF anulada.
- Eliminar seleccionados con respaldo.
- Eliminar filtrados con respaldo.
- Confirmar que el correo de eliminacion de historico muestra el responsable.

## Avisos

- Enviar aviso a funcionario.
- Confirmar saludo con primer nombre.
- Confirmar adjunto Excel.
- Enviar aviso a destinatario cuando exista correo.
- Confirmar que no se envia a destinatario sin correo.
- Cancelar/omitir aviso.
- Confirmar que no reaparece como pendiente si ya fue gestionado.

## Reportes Y Excepciones

- Crear reporte desde OF historica.
- Intentar crear segundo reporte vigente sobre la misma OF y confirmar que abre el existente.
- Agregar movimiento.
- Agregar evidencia.
- Confirmar que vuelve al mismo reporte despues de guardar.
- Descargar PDF.
- Cerrar reporte con resultado y OF de retorno opcional.
- Anular reporte con motivo y confirmar que queda visible como anulado.
- Anular reporte y confirmar responsable en auditoria.
- Eliminar reporte con motivo y confirmar envio de respaldo PDF antes de borrar.
- Confirmar que el correo de eliminacion de reporte muestra el responsable.
- Confirmar marca del reporte en historico.
- Filtrar reportes por vigente/resuelto/todos.
- Buscar reportes por OF o destinatario.

## Documentacion

- Revisar header en ancho movil y confirmar que la barra de navegacion se desliza horizontalmente sin cortar opciones.
- Confirmar que `static/css/portal_theme.css` mantiene la estetica comun del portal sin romper estilos locales.
- Confirmar que las pantallas principales respetan el estilo oficial del inicio: hero claro, tarjetas blancas, acento dorado, tablas limpias y modales coherentes.
- Actualizar `docs/CONTINUIDAD_PROYECTO.md` con cambios funcionales relevantes.
- Actualizar `docs/ADMINISTRACION.md` si se modifican usuarios, roles, seguridad o auditoria.
- Actualizar `docs/OPERACION.md` si cambia el flujo operativo de Mensajeria.
- Actualizar novedades visibles del portal si corresponde a una version publicada.
