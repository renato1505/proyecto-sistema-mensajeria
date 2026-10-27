# Arquitectura de Mensajería V2

Descripción del código de la rama `refactor/v2-foundation`, no del estado de
un servicio remoto. El contexto y pendientes están en
[Estado del proyecto](ESTADO_PROYECTO.md).

## Capas y módulos activos

Flask registra rutas desde [main.py](../main.py). Jinja renderiza las vistas;
CSS y JavaScript viven en [static](../static/). SQLAlchemy declarativo comparte
una única `Base.metadata` en [database/modelos.py](../database/modelos.py).
Alembic usa esa metadata sin importar la aplicación.

| Capa | Responsabilidad |
| --- | --- |
| [config](../config/) | Variables de entorno y logs rotativos |
| [database](../database/) | Conexión, modelos y helper de esquema legacy |
| [routes/paginas.py](../routes/paginas.py) | Inicio, pendientes, proceso y entrada de operación |
| [routes/envios.py](../routes/envios.py) | Alta, edición y eliminación protegida de envíos |
| [routes/carga_masiva.py](../routes/carga_masiva.py) | Plantilla, revisión y confirmación Excel |
| [routes/catalogos.py](../routes/catalogos.py), [catalogos_ajax.py](../routes/catalogos_ajax.py) | Catálogos y autocompletados |
| [routes/starken_lotes.py](../routes/starken_lotes.py) | CSV, OF manual/correo, éxito y cancelación de lote |
| [routes/retiros.py](../routes/retiros.py) | Cola elegible y confirmación de retiro físico |
| [routes/historico.py](../routes/historico.py), [historico_ajax.py](../routes/historico_ajax.py) | Consultas, exportaciones, anulación y eliminación respaldada |
| [routes/avisos.py](../routes/avisos.py) | Interfaz de avisos legacy |
| [routes/auth.py](../routes/auth.py), [configuracion.py](../routes/configuracion.py) | Login, sesión, cambio de clave y consulta de cuenta |
| [services](../services/) | Reglas de negocio, persistencia y transportes |
| [utils](../utils/) | Texto, validación, CSRF y fechas de Chile |

No existen rutas activas de Admin o Reportes ni una matriz vigente de permisos
por áreas. Los modelos legacy de áreas, excepciones y recuperación conservados
en metadata no equivalen a interfaces disponibles y no deben eliminarse sin
auditar datos y relaciones.

## Flujo y proyecciones legacy

1. Registro individual o masivo produce `Envio.e_estado=pendiente`.
2. Una selección explícita validada y bloqueada genera CSV y lote.
3. El envío pasa a `en_proceso`, guardando lote, fila y archivo original.
4. El procesamiento OF valida correspondencia y aplica resultados. Los OK pasan
   a `historico`; `e_fecha_of` refleja el procesamiento OK.
5. El retiro físico se registra separadamente; estar en Histórico no lo acredita.
6. El operador gestiona avisos legacy y consultas históricas.

`e_estado_correo` distingue pendiente, descargado, enviado y error del CSV.
`e_aviso_funcionario_estado` distingue pendiente, enviado y cancelado de avisos.
`e_anulado` marca anulación; no representa borrado.
Estas proyecciones legacy no constituyen el futuro historial de intentos.

## Servicios y reglas compartidas

[services/lotes.py](../services/lotes.py) valida IDs seleccionados, estado,
anulación, antecedentes H2H y códigos de agencia antes de preparar un lote.
[services/starken.py](../services/starken.py) genera CSV de 54 columnas,
separador punto y coma y codificación CP1252, con contratos específicos Starken.
La observación se envía en `OBSERVACION_CLIENTE`.

[services/of_processor.py](../services/of_processor.py) centraliza importación
manual y desde correo. Exige correspondencia de filas y detecta duplicados OF.
Un resultado `ERROR` con la palabra `H2H`, sin distinguir mayúsculas,
se trata como ambiguo; no implica inexistencia de OF. No se clasifica cualquier
error ni basta la ausencia de número. Cancelación, reimportación y nuevo CSV
bloquean la pérdida de ese antecedente; un lote mixto ambiguo bloquea la cancelación
completa. Ver [Operación](OPERACION.md#protecciones-h2h).

[services/retiros.py](../services/retiros.py) deriva elegibilidad desde OF,
fecha OF, punto local activo, ausencia de anulación y de retiro vigente.
Usa locks PostgreSQL e índice único parcial como barrera final.
Una asociación conserva un snapshot de bultos por envío, no una fila por bulto.
La anulación de retiro existe como servicio, sin interfaz operativa actual.

[services/avisos.py](../services/avisos.py) es el flujo de avisos conectado a
las rutas. [services/avisos_v2.py](../services/avisos_v2.py),
[motor_avisos_v2.py](../services/motor_avisos_v2.py) y
[proveedor_avisos.py](../services/proveedor_avisos.py) implementan sincronización,
claim y resultados persistentes V2, todavía sin integración con esa interfaz.
No retirar legacy ni activar ambos motores sobre los mismos envíos.

[services/email_client.py](../services/email_client.py) centraliza Gmail SMTP,
Brevo API y Brevo SMTP. Aceptación del proveedor no prueba entrega.
Las plantillas están en [services/email_templates.py](../services/email_templates.py).
[services/correo_of.py](../services/correo_of.py) realiza lectura IMAP asistida.
No existe integración HTTP H2H que genere OF directamente desde esta aplicación.

## Persistencia H2H aditiva

`IntentoOF`, `RegistroOF`, `ConciliacionH2H` y `MovimientoEnvio` tienen
tablas nuevas sin backfill y todavía desacopladas de rutas operativas.
Se pueden conservar distintas OF en distintos intentos del mismo envío.
No se implementaron devoluciones, redespachos ni conciliación manual.

Los snapshots y movimientos se conservan mediante hooks ORM; FK, UNIQUE y CHECK
protegen asociaciones y unicidad en base. Los hooks no protegen SQL directo o
bulk updates/deletes. El contrato detallado y sus límites están en
[Migraciones, Fase 1.2B](MIGRACIONES.md#fase-12b-persistencia-of-y-conciliaciones-h2h).

Todos los campos de un `IntentoOF` persistido, incluido estado, permanecen
inmutables por ORM. Por ello el ciclo de vida aún requiere diseño de transiciones
explícitas o entidad de estado separada antes de integrar respuestas y sucesores.
No usar SQL directo para eludir las guardas.

## Seguridad, normalización y arranque

Login contra `usuarios_sistema` con hash Werkzeug; sesiones con timeout, CSRF
global en métodos de escritura y bloqueo de intentos en memoria por usuario/IP.
No hay recuperación web ni permisos por rol activos.
[services/auditoria.py](../services/auditoria.py) conserva el registro de
acciones implementadas, sin panel Admin de consulta/exportación.
Consultar [Autenticación](AUTENTICACION_V2.md).

[utils/texto.py](../utils/texto.py) y [utils/validaciones.py](../utils/validaciones.py)
normalizan texto, OF Excel y teléfonos. La normalización operativa elimina
acentos y homogeneiza nombres y correos; no garantiza conservar literalmente
todo el texto ingresado. `utils/fechas.py` centraliza `America/Santiago`;
no se deducen ni reescriben fechas históricas para corregir UTC por suposición.

**Importar `main.py` escribe:** ejecuta `create_all()`,
`asegurar_columnas_operativas()` y `normalizar_datos_operativos()`.
Esta última puede fusionar/eliminar remitentes duplicados y modificar registros.
Alembic no se ejecuta por ese import y su versión puede quedar desalineada.
Ver [Migraciones](MIGRACIONES.md) antes de intervenir una base existente.

## Límites y mantenimiento futuro

El correo externo no comparte transacción con la base. Legacy puede enviar
parcialmente y conservar flags pendientes; el reintento puede duplicar avisos.
La carga masiva tampoco dispone todavía de un consumo transaccional de token.
Los lotes usan un identificador temporal con precisión de segundos.

Las vistas tienen consultas que cargan conjuntos completos antes de agrupar o
paginar; medir antes de optimizar. Historico y Catálogos mantienen JavaScript
inline susceptible de extracción futura. Mantener el estilo de los assets
actuales, sin prescribir el archivo retirado `portal_theme.css`.
No mezclar esas refactorizaciones con cambios documentales.
