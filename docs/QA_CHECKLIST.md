# Checklist QA

Aplicar sobre entorno local descartable y datos ficticios. No es autorización
para probar en producción, QA remota, enviar correos o generar OF reales.

## Verificación técnica

- [ ] Revisar rama, cambios locales y alcance de la tarea.
- [ ] Configurar el bloque de aislamiento de [Desarrollo](DESARROLLO.md#pruebas-con-destino-explícito-y-descartable) antes de importar código.
- [ ] Ejecutar con Python del venv la suite completa:
  `python -m unittest discover -s tests -p "test_*.py"`.
- [ ] Ejecutar `python -m compileall -q main.py config database routes services scripts tests migrations`.
- [ ] Ejecutar `git diff --check` y revisar `git status --short --branch`.
- [ ] Si corresponde smoke, hacerlo solo con el entorno aislado documentado.
  Importa `main.py`, puede escribir esquema/datos y desactiva el login.
- [ ] Confirmar que `.env`, bases, logs, cargas temporales, respaldos y
  `.vscode/` no se incluyan accidentalmente.

Última ejecución registrada antes de L1: **273 pruebas aprobadas**.
L1 solo cambia documentación; no se vuelve a ejecutar aplicación, suite o migración.

## Login y seguridad

- [ ] Usar una cuenta ficticia en `usuarios_sistema` con hash Werkzeug.
- [ ] Confirmar formulario de login con `LOGIN_REQUIRED=1`, acceso correcto y
  rechazo de clave inválida o usuario inactivo.
- [ ] Verificar bloqueo al quinto fallo por usuario/IP y timeout de sesión.
  Los bloqueos no persisten entre procesos/reinicios.
- [ ] Verificar cierre de sesión por POST y cambio de clave propia.
- [ ] Comprobar rechazo de escritura sin CSRF y validación con CSRF.
- [ ] Confirmar `/admin` y `/reportes` retirados (404).
- [ ] No asumir roles, desbloqueo Admin ni recuperación web disponibles.
  El reset externo requiere autorización y destino verificado.

## Envíos, catálogos y carga masiva

- [ ] Crear envío manual ficticio con teléfono `+56`, RUT `0`, correo y
  observación opcionales; verificar normalización y región de comuna.
- [ ] Revisar autocompletados y alta/edición de catálogos con datos válidos e inválidos.
- [ ] Editar pendiente antes de exportar.
- [ ] Eliminar un pendiente sin trazabilidad; rechazar proceso/histórico,
  OF, lote o relaciones operativas sin modificar datos.
- [ ] Descargar plantilla Excel, revisar remitente común y filas.
- [ ] Validar correos, teléfonos, observación y errores corregibles.
- [ ] Confirmar una vez y revisar pedidos creados; no asumir idempotencia si
  se repite token o falla la eliminación del temporal.
- [ ] Verificar bloqueo de CSV para agencia sin código.

## Lotes y OF, solo simulación local

- [ ] Generar CSV únicamente para IDs elegidos, manteniendo otros pendientes.
- [ ] Revisar rechazo de IDs vacíos, repetidos, inexistentes o ya no pendientes.
- [ ] Comprobar separador, CP1252, columnas Starken y `OBSERVACION_CLIENTE`.
- [ ] Procesar respuesta OF ficticia correspondiente al lote, rechazo de
  desajustes de filas y OF duplicadas y normalización de `.0`.
- [ ] Verificar OK, Histórico, fecha OF y resumen primera/última OF.
- [ ] Cancelar lote válido y verificar funcionamiento ordinario.
- [ ] Reproducir H2H ambiguo: cancelar lote mixto debe rechazar todo sin cambios.
- [ ] Rechazar reimportación que sobrescriba H2H y CSV posterior con antecedente.
- [ ] Confirmar conservación exacta de detalle, lote, archivo, fila y asociaciones.
- [ ] No ampliar la clasificación H2H a todos los errores.

No subir archivos demo a Starken ni usar Buscar OF en correo con una cuenta real.
Las simulaciones disponibles están en [Demo operativa](DEMO_OPERATIVA_V2.md).

## Retiros V2

- [ ] Verificar elegibilidad por OF/fecha OF/punto local activo, sin anulación
  ni asociación vigente; excluir Academia.
- [ ] Buscar, paginar y revisar selecciones y suma de bultos.
- [ ] Confirmar retiro con fecha efectiva, responsable y observación.
- [ ] Comprobar una asociación por envío y snapshot de bultos.
- [ ] Rechazar selección que perdió elegibilidad sin retiro parcial.
- [ ] La anulación de retiro se verifica a nivel de servicio; no inventar botón UI.

## Histórico y avisos

- [ ] Probar filtros, detalle y exportaciones con datos ficticios.
- [ ] Con dobles de correo, comprobar motivo/responsable/fecha de anulación y
  que cada remitente reciba solo sus registros.
- [ ] Simular fallo de respaldo: no debe confirmar anulación/eliminación.
- [ ] Verificar clave de eliminación y relaciones que impidan borrado.
- [ ] Probar avisos legacy con correo destinatario opcional y cancelación.
- [ ] Revisar el escenario conocido de fallo parcial: puede haber mensajes
  aceptados y flags pendientes; no marcar ese riesgo como resuelto.
- [ ] No activar motor V2 junto a legacy para comprobar la misma operación.

Las acciones dependientes de correo se prueban con mocks/transportes ficticios.
El script `tests/test_correo.py` con `--confirmar` envía correo real: queda
fuera de este checklist local y requiere otra autorización y destinatarios
controlados. IMAP y transporte externo también se validan por separado.

## Persistencia H2H y migraciones

- [ ] Revisar las 50 pruebas añadidas en 1.2B/1.2B.1: asociaciones, FK,
  secuencias, unicidad, snapshots, consumo irreversible por ORM y rollback.
- [ ] Conservar múltiples OF legítimas en distintos intentos de un envío.
- [ ] Revisar inmutabilidad ORM de IntentoOF/RegistroOF/MovimientoEnvio y
  resolución definitiva de ConciliacionH2H.
- [ ] Recordar que Core/SQL/bulk eluden hooks; no afirmar protección equivalente.
- [ ] Fixtures SQLite activan FK y prueban upgrade/downgrade/datos legacy.
  No ejecutar manualmente migraciones sobre el entorno operativo para hacer QA.
- [ ] Registrar como pendiente concurrencia y locks en PostgreSQL aislada autorizada.
  Compilar DDL PostgreSQL no prueba un servidor real.

## Documentación e interfaz

- [ ] Revisar enlaces y rutas citadas; actualizar [Estado](ESTADO_PROYECTO.md)
  si cambian fases, verificaciones o contratos.
- [ ] Mantener [Operación](OPERACION.md), [Arquitectura](ARQUITECTURA.md) y
  [Migraciones](MIGRACIONES.md) consistentes con el código.
- [ ] Revisar navegación móvil, tablas, modales, errores y portapapeles.
- [ ] Conservar estilo corporativo claro y acentos dorados con assets existentes.
- [ ] No agregar comprobaciones de módulos retirados como funcionalidades activas.

La aprobación de QA local no autoriza despliegue. Ver
[Despliegue cloud](DESPLIEGUE_CLOUD.md) y sus condiciones previas.
