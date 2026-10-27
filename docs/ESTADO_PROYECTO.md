# Estado del proyecto

Corte documental: **27 de octubre de 2026**.
Rama de trabajo: `refactor/v2-foundation`.
Base consolidada: `e7cf93e4ebf318ac11d5d9158a769840ca173412`.
Este documento describe el repositorio; no verifica el estado remoto de Render.

## Propósito y continuidad

Mensajería es el módulo activo del Portal Operativo interno. Nació para reducir
digitación desde correos/Excel, errores de copia, pérdida de OF y avisos manuales
por funcionario. Se mantiene ajustado al flujo del equipo: recepción física,
preparación Starken, impresión de etiquetas, retiro y comunicación posterior.

Principios que se conservan: claridad operativa, trazabilidad, respaldo antes
de eliminar, validación y normalización compartidas, cambios pequeños y respeto
por decisiones de negocio existentes. El contexto de uso real reportado en los
documentos antiguos no certifica que la rama actual esté desplegada.

Para continuar: leer [README](../README.md), este estado,
[Arquitectura](ARQUITECTURA.md), [Operación](OPERACION.md) y
[Migraciones](MIGRACIONES.md); revisar Git antes de modificar archivos.
No tocar `.env`, datos reales, infraestructura, commit o push sin autorización.

## Consolidado

| Fase | Resultado |
| --- | --- |
| 1.1 y 1.1.1 | Bloqueo de pérdida/regeneración ante H2H ambiguo; eliminación individual limitada a pendientes sin trazabilidad |
| 1.2B | Persistencia aditiva de intentos OF, registros OF, conciliaciones H2H y movimientos |
| 1.2B.1 | Preservación histórica por ORM ordinario y vínculo de sucesor no borrable/sustituible una vez consumido |

Commit de 1.1/1.1.1: `819b5d46fb7da40e27a8717827b7a9ddfa5651f9`.
Commit de 1.2B/1.2B.1:
`e7cf93e4ebf318ac11d5d9158a769840ca173412`.

Última ejecución registrada: **273 pruebas aprobadas**, incluidas 50 de
persistencia/migración añadidas en 1.2B y 1.2B.1.
También se registraron compileall y `git diff --check` satisfactorios.
No se repiten esos tests ni se ejecuta la aplicación durante L1 documental.

Retiros V2 cuenta con modelo, servicio y pantalla de confirmación.
Avisos V2 cuenta con persistencia, sincronización, motor y adaptador probados,
sin integración con las rutas de avisos legacy.

## Decisiones técnicas vigentes

- La integración actual con Starken intercambia CSV/Excel y correo asistido;
  no existe cliente HTTP H2H de generación automática de OF.
- La observación Starken va en `OBSERVACION_CLIENTE`; el CSV mantiene CP1252,
  punto y coma y el contrato de columnas del servicio.
- Un error H2H puede ocultar una OF creada: no regenerar por ausencia de número.
  La detección conservadora requiere resultado ERROR y palabra H2H.
- La fecha OF refleja procesamiento OK, no exportación ni correo.
- La clasificación de retiro usa `ACM` exacto normalizado para Academia;
  no es centro de costo corporativo ni regla por substring. El histórico no
  se reclasifica retrospectivamente por inferencia.
- Retiro representa un hecho físico con una asociación por envío y snapshot de
  bultos. La regla de negocio kilos igual a bultos, mínimo uno, no debe anunciarse
  como automatizada en todos los formularios.
- Los avisos a funcionarios se gestionan después del retiro por decisión operativa;
  el flujo legacy no exige automáticamente el retiro persistido.
- Fechas nuevas usan `utils/fechas.py` y `America/Santiago`; no corregir
  fechas antiguas masivamente suponiendo su zona original.
- La normalización de textos, tildes, nombres, OF Excel y teléfonos se comparte;
  debe evaluarse conservación literal si aparecen exigencias legales/auditoría.
- La anulación conserva el envío; la eliminación histórica física sigue existiendo
  con clave y respaldo, y necesita una política futura más sólida.
- Login únicamente desde base con hash Werkzeug; Admin, Reportes, recuperación
  web, Recepción y Seguridad no son módulos operativos actuales.
- Conservar modelos/tablas legacy y migraciones hasta auditar sus datos y vínculos.
  Ausencia de pantalla no demuestra que una tabla esté vacía.
- Mantener estilo corporativo claro, tarjetas suaves y acentos dorados usando
  assets actuales; no reinstalar módulos o CSS retirados por una guía antigua.

Los contratos detallados de FK/UNIQUE/CHECK, Avisos V2 y H2H permanecen en
[Migraciones](MIGRACIONES.md); no se sustituyen por este resumen.

## Pendiente antes de integrar intentos OF

**Fase 1.2C no iniciada por esta limpieza.** Debe definir ciclo de vida y servicios
transaccionales, adopción explícita de datos legacy y coordinación de rutas.

Hoy `IntentoOF` es totalmente inmutable por ORM, incluido `io_estado`.
Un intento abierto no puede cerrarse por una edición ordinaria; el índice de
un intento abierto por envío impide abrir otro sin resolver ese ciclo.
Definir transiciones explícitas controladas con movimientos, o una entidad
separada de estado, antes de implementar procesamiento/confirmación.
No eludir hooks con SQL o bulk updates.

`ch_intento_sucesor_id=NULL` significa sin consumidor registrado.
Un valor identifica el sucesor directo del mismo envío; solo una resolución
OF_INEXISTENTE puede registrarlo. Por ORM no se limpia ni sustituye.
Crear sucesor y vincular consumo exige una misma transacción y control de
concurrencia en el futuro servicio; la FK por sí sola no implementa autorización.

La conciliación manual H2H, su operador/método/justificación y las acciones de
reintento no tienen todavía interfaz o servicio funcional.
No inventar historial ni hacer backfill como efecto de integración.

## Otros pendientes

- Integrar Avisos V2 y decidir agrupamiento sin doble envío junto a legacy.
  No reintentar automáticamente INCIERTO ni PROCESANDO abandonado.
- Mejoras del Histórico, incidencias, devoluciones y redespachos con movimientos
  explícitos; no se anuncian como implementados.
- Formalizar respaldo/restauración integral de base y evidencias.
- Retirar gradualmente DDL y normalización del startup tras adoptar Alembic.
- Resolver idempotencia de carga masiva y consistencia de correo/commit legacy.
- Persistir bloqueo de login y revisar concurrencia/observabilidad.
- Medir consultas de listas antes de paginar/refactorizar; extraer JS inline de
  Histórico y Catálogos en cambios independientes.
- La posible expansión a otras áreas, indicadores o administración futura
  requiere diseño y autorización propios, sin reactivar el backlog Admin antiguo.

## Riesgos y límites de evidencia

- Importar `main.py` crea tablas, agrega columnas y normaliza datos; puede
  fusionar/eliminar remitentes. Arrancar no es una auditoría de lectura.
- `create_all()` no avanza Alembic; aplicar/adoptar esquema antes del nuevo
  startup. No hacer `stamp` para ocultar diferencias.
- Hooks ORM no impiden Core, SQL directo ni bulk updates/deletes.
- SQLite aislada prueba integridad básica y preservación; no prueba locks,
  permisos o concurrencia PostgreSQL. El DDL compilado no equivale a ejecución.
- Correo aceptado no prueba entrega. Legacy puede enviar parcialmente y dejar
  flags pendientes; anulación/eliminación también separan correo y commit.
- El clonador cloud legacy no es respaldo integral y puede escribir aun en
  diagnóstico. No usarlo en onboarding ni recuperación.
- Identificadores de lote basados en segundos y cargas de listas completas son
  límites conocidos; no se corrigen en L1.
- No se consultó producción/QA ni se certificó proveedor, rama desplegada o
  automatización remota durante esta actualización.

## Limpieza L1

Actualiza diez documentos activos y conserva nueve originales históricos.
Fusiona onboarding, Git y calidad en Desarrollo/QA; continuidad y traspaso en
este documento; preserva íntegramente los antecedentes y las decisiones técnicas.
No modifica código, modelos, scripts, migraciones, datos ni configuración.
Queda pendiente de revisión, sin commit ni push.

## Archivo documental

Los siguientes originales se conservan con aviso histórico; sus instrucciones
pueden citar funciones retiradas y comandos peligrosos. No ejecutarlos como guía
vigente. Las rutas citadas como texto dentro de ellos corresponden a su época.

| Original conservado | Uso actual |
| --- | --- |
| [CALIDAD.md](historico/CALIDAD.md) | Controles trasladados a Desarrollo y QA |
| [GITHUB.md](historico/GITHUB.md) | Custodia y revisión Git trasladadas a Desarrollo |
| [MIGRACION_PC.md](historico/MIGRACION_PC.md) | Onboarding sustituido por Desarrollo |
| [CONTINUIDAD_PROYECTO.md](historico/CONTINUIDAD_PROYECTO.md) | Contexto vigente integrado aquí |
| [TRASPASO_NUEVO_CHAT.md](historico/TRASPASO_NUEVO_CHAT.md) | Historia, principios y pendientes reconciliados aquí |
| [ADMINISTRACION.md](historico/ADMINISTRACION.md) | Antecedente de módulos retirados, no instrucciones de acceso actual |
| [INFORME_IMPLEMENTACION.md](historico/INFORME_IMPLEMENTACION.md) | Informe de junio de 2026, contexto y beneficios originales |
| [REVISION_CALIDAD_2026-06.md](historico/REVISION_CALIDAD_2026-06.md) | Evaluación histórica de riesgos y decisiones |
| [REVISION_MANTENIBILIDAD_2026-07.md](historico/REVISION_MANTENIBILIDAD_2026-07.md) | Decisiones y verificaciones de julio de 2026 |
