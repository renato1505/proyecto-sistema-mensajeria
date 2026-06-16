# Revision de calidad - Junio 2026

## Resumen ejecutivo

El sistema ya cumple una funcion operativa real: reemplaza un flujo manual basado en correos y planillas, reduce digitacion repetitiva, mantiene historico, genera CSV Starken, procesa OF, avisa por correo y respalda eliminaciones.

La prioridad actual no es agregar muchas funciones nuevas, sino consolidar estabilidad, mantenibilidad y trazabilidad antes de expandir el Portal Operativo a otras areas.

## Fortalezas actuales

- Flujo de Mensajeria completo desde solicitud hasta historico.
- Carga individual y masiva.
- Validacion de archivos OF antes de aplicar cambios.
- Historico filtrable, exportable, anulable y eliminable con respaldo.
- Correos diferenciados para funcionarios, destinatarios, respaldo interno y eliminacion.
- Pantalla de exito post OF con rango de OF copiable.
- Login interno sin registro publico.
- CSRF global en formularios.
- Hora centralizada en zona `America/Santiago`.
- Documentacion operativa y tecnica existente.

## Riesgos y deuda tecnica

### Alta prioridad

- No hay migraciones formales versionadas. `database/schema.py` cubre columnas operativas, pero a futuro conviene Alembic.
- No existe auditoria dedicada para acciones criticas como anular, eliminar, cancelar avisos o procesar OF.
- El envio de correos depende de Gmail SMTP/IMAP. Funciona, pero en cloud puede ser menos robusto que un proveedor transaccional.
- El sistema aun no tiene timeout de sesion por inactividad.

### Prioridad media

- Algunas rutas concentran varias responsabilidades, especialmente `routes/starken_lotes.py` y `services/avisos.py`.
- La documentacion debe mantenerse sincronizada despues de cada cambio grande.
- Falta cobertura unitaria de validaciones, generacion CSV y procesamiento OF.
- El modulo Mensajeria ya esta maduro, pero la expansion a Recepcion/Seguridad requiere separar menus y permisos por modulo.

### Prioridad baja

- CSS esta separado por pantalla, lo que facilita trabajo visual, pero algunos patrones se repiten.
- Los respaldos locales en cloud son temporales; esto esta controlado porque lo critico se respalda por correo/base, pero debe mantenerse claro.

## Recomendaciones inmediatas

1. Crear pruebas unitarias para:
   - normalizacion de telefono;
   - validacion OF;
   - generacion CSV Starken;
   - agrupacion/envio de avisos;
   - filtros de historico.
2. Agregar auditoria en base de datos:
   - usuario;
   - accion;
   - lote/envio;
   - fecha Chile;
   - detalle.
3. Implementar timeout de sesion por inactividad.
4. Evaluar proveedor transaccional para correos si el volumen crece.
5. Mantener `.env.example` sin secretos y documentar cada variable nueva.
6. Antes de expandir a otros modulos, definir estructura de navegacion y permisos por area.

## Criterio de calidad para futuros cambios

- Todo cambio debe probarse localmente antes de push/deploy.
- Al tocar correos, probar HTML sin enviar y luego con una prueba real controlada.
- Al tocar historico, validar que eliminacion no borre sin respaldo.
- Al tocar OF, validar que no se rompa el bloqueo por filas/lote/duplicados.
- Al tocar UI, revisar header, mobile y que los textos no se corten.

## Estado recomendado antes de subir a produccion

Ejecutar:

```powershell
python -m compileall -q main.py config database routes services scripts tests
python tests\smoke_check.py
```

Luego probar manualmente:

- crear envio individual;
- generar CSV;
- procesar OF;
- revisar pantalla de exito;
- enviar/cancelar avisos;
- anular registro historico;
- eliminar registro de prueba con respaldo por correo.
