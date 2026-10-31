# Migraciones de base de datos

## Lectura vigente y condiciones de ejecución

Actualización documental L1, 27 de octubre de 2026. Las decisiones y contratos
técnicos originales se conservan debajo. Las secciones de baseline y etapas
previas expresan su alcance histórico; Retiro V2 ya tiene servicio/interfaz y
Avisos V2 tiene sincronización/motor sin conexión a las rutas legacy.
El estado consolidado está en [Estado del proyecto](ESTADO_PROYECTO.md).

Los bloques Alembic de este documento son referencias para procedimientos
autorizados, no pasos automáticos de onboarding. Verificar el destino antes de
cualquier comando; no usar producción o QA remota para probar. Para SQLite local
usar una base nueva descartable y el entorno sin correo de
[Desarrollo](DESARROLLO.md). Para PostgreSQL, una copia aislada autorizada y
respaldo/restauración comprobados. Tampoco asumir que autogenerate es de lectura:
se conecta a la base configurada y crea un archivo de revisión.

No importar ni arrancar main.py para inspeccionar un esquema: su startup escribe
estructura y normaliza datos. Aplicar/adoptar Alembic antes de arrancar la versión
nueva. El helper create_all() puede crear tablas sin registrar revisión; ante
esa situación auditar y conciliar, nunca hacer stamp ciego. Un downgrade puede
eliminar evidencia. Ningún comando de esta guía autoriza intervenir Render.

## Alcance y decisión técnica

El proyecto usa Alembic directamente, sin Flask-Migrate. Los modelos son
SQLAlchemy declarativo puro y no dependen de Flask-SQLAlchemy, por lo que
Flask-Migrate no aportaría funcionalidad necesaria y agregaría acoplamiento.

Alembic toma `Base.metadata` desde `database/modelos.py` y obtiene la conexión
desde `DATABASE_URL` mediante `config/settings.py`. `alembic.ini` no contiene
credenciales. Importar la aplicación no ejecuta migraciones.

## Diagnóstico del startup legacy

Al importar `main.py` se ejecutan actualmente tres mecanismos:

1. `Base.metadata.create_all(bind=engine)` crea tablas ausentes. No modifica
   tablas existentes ni versiona el cambio.
2. `asegurar_columnas_operativas()` inspecciona tablas y ejecuta `ALTER TABLE`
   para algunas columnas legacy ausentes.
3. `normalizar_datos_operativos()` modifica datos: normaliza texto y correos,
   normaliza OF y puede fusionar/eliminar remitentes duplicados por correo.

Los dos primeros son gestión de esquema. El tercero es una migración de datos
repetida en cada arranque. Ninguno reemplaza un historial de migraciones.

Durante la transición permanecen activos para no romper despliegues existentes.
No deben añadirse nuevas alteraciones a `database/schema.py`. Una vez que todas
las bases estén auditadas y marcadas con el baseline, deben retirarse por fases:

1. desplegar Alembic sin retirar helpers;
2. auditar y hacer stamp controlado en cada entorno existente;
3. mover cualquier cambio pendiente a revisiones Alembic;
4. retirar `asegurar_columnas_operativas()` del startup;
5. convertir la normalización en un comando explícito e idempotente;
6. retirar `Base.metadata.create_all()` del startup productivo, manteniéndolo
   solamente en fixtures locales si resulta útil.

## Baseline

La revisión `20260826_01` representa el esquema PostgreSQL legacy observado en
la copia restaurada, antes de Retiro Starken. Incluye:

- `areas_operativas`
- `auditoria`
- `comunas`
- `destinatarios`
- `envios`
- `evidencias_excepcion`
- `excepciones_envio`
- `movimientos_excepcion`
- `remitentes`
- `solicitudes_recuperacion_clave`
- `usuarios_sistema`

No crea puntos de retiro, retiros, fecha OF ni clasificación Academia. Tampoco
añade FKs, UNIQUE o CHECK deseables que no están representados hoy por el ORM.

Los defaults actuales son mayoritariamente funciones Python. La excepción
formalizada es `envios.e_anulado`, que en PostgreSQL existe como `BOOLEAN NOT
NULL DEFAULT FALSE`; el ORM conserva el default Python y además declara el
`server_default` equivalente.

Las secuencias `nextval('<tabla>_id_seq'::regclass)` de las PK son la
representación normal de PostgreSQL para el autoincremento declarado por el ORM,
no drift de esquema. El auditor las clasifica como equivalencias informativas.

El índice `ix_envios_e_anulado` es deseable en el ORM, pero no existe en el
esquema restaurado. Por eso no se afirma falsamente que pertenece al baseline:
la revisión `20260828_02` lo crea de forma explícita después de adoptar la base
legacy. Una base existente debe marcarse primero en `20260826_01` y luego probar
`upgrade` a la revisión de reconciliación en un entorno aislado.

## Crear una base vacía

Configurar una URL vacía y ejecutar:

```powershell
$env:DATABASE_URL = "sqlite:///C:/ruta/qa_migraciones.db"
alembic upgrade head
alembic current
alembic history
```

En PostgreSQL debe utilizarse una base aislada, nunca producción como primera
prueba. `upgrade head` crea el esquema completo cuando la base está vacía.

## Base existente y `stamp`

`stamp` registra una revisión sin ejecutar su `upgrade`. Solo corresponde cuando
una base existente coincide suficientemente con el baseline.

Procedimiento obligatorio:

1. respaldar PostgreSQL;
2. restaurar el respaldo en una base aislada;
3. ejecutar `scripts/auditar_esquema.py` con credenciales read-only;
4. revisar tablas, columnas, tipos, nullability, PK, FK, índices y UNIQUE;
5. resolver o documentar todas las diferencias críticas;
6. verificar datos y conteos;
7. recién entonces ejecutar sobre la copia:

```powershell
alembic stamp 20260826_01
alembic current
```

El mismo proceso debe repetirse en staging antes de considerar producción.
Nunca ejecutar `stamp` ciegamente: podría declarar aplicada una estructura que
en realidad tiene columnas o constraints diferentes.

Esta fase no autoriza ejecutar `stamp` en producción.

## Auditoría read-only

Uso recomendado sobre una copia PostgreSQL restaurada:

```powershell
$env:AUDIT_DATABASE_URL = "postgresql+psycopg2://usuario_readonly:...@host/base_copia"
python scripts/auditar_esquema.py
```

Salida JSON:

```powershell
python scripts/auditar_esquema.py --json
```

El script informa esquema, diferencias contra `Base.metadata`, estados de
envíos, total y cardinalidad de OF, duplicados sin exponer el valor de la OF,
anulados, distribución de bultos, distribución de códigos de agencia y nulos por
columna de `envios`. No importa `main`, no ejecuta helpers de startup, no
contiene escrituras y en PostgreSQL usa `SET TRANSACTION READ ONLY`.

Usar idealmente un rol que solo tenga `CONNECT`, `USAGE` y `SELECT`. La
protección por permisos es más fuerte que depender solamente del script.

## Crear nuevas revisiones

```powershell
alembic revision --autogenerate -m "descripcion breve"
```

Autogenerate es una propuesta, no una aprobación. Revisar manualmente:

- tablas y columnas afectadas;
- tipos y nullability;
- defaults Python versus `server_default`;
- nombres de índices y constraints;
- operaciones destructivas inesperadas;
- compatibilidad PostgreSQL/SQLite;
- código de downgrade.

No aceptar automáticamente eliminaciones porque una tabla legacy ya no aparezca
en una pantalla.

## Prueba de una migración

Orden recomendado:

1. base SQLite vacía para portabilidad básica;
2. copia PostgreSQL restaurada para comportamiento real;
3. `alembic current` y `history`;
4. `alembic upgrade head`;
5. auditoría metadata/base;
6. reconciliación de conteos y datos;
7. suite automatizada y smoke;
8. staging.

SQLite no reproduce secuencias, locks, tipos PostgreSQL, permisos, concurrencia
ni todas las operaciones `ALTER`. Una prueba SQLite verde no sustituye la prueba
sobre una restauración PostgreSQL.

## Producción, backup y rollback

Procedimiento futuro, sujeto a autorización expresa del destino y ventana:

1. backup PostgreSQL consistente;
2. restauración en base aislada;
3. auditoría;
4. `alembic current` y `alembic history`;
5. upgrade sobre la copia;
6. reconciliación;
7. tests;
8. staging;
9. ventana controlada;
10. `alembic upgrade head` en producción;
11. verificación posterior.

Las primeras migraciones de Retiro serán aditivas. Ante problemas se prefiere
volver a la versión anterior de la aplicación, que ignorará columnas/tablas
nuevas, antes que ejecutar un downgrade destructivo. No eliminar automáticamente
estructuras que ya contengan datos. Ante corrupción, restaurar el backup. Un
downgrade solo se utiliza cuando fue revisado y probado con datos equivalentes.

## Decisiones de diseño Retiro en la etapa inicial (antecedente)

- `MENSAJERIA_LOCAL` será el punto de retiro predeterminado.
- `ACADEMIA` será una clasificación logística separada.
- `ACM` no es un centro de costo corporativo: es un marcador manual legacy.
- La compatibilidad futura comparará `ACM` exactamente después de normalizar;
  nunca mediante substring.
- La clasificación se persistirá en `e_punto_retiro_id`; no se recalculará en
  reportes históricos.
- La primera versión de Retiro se concentrará en `MENSAJERIA_LOCAL`.
- Academia quedará fuera de la cola y métricas del retiro local.
- No se construirá un motor genérico de reglas.

## Reglas confirmadas y deuda operacional

- Los nuevos envíos persisten su punto de retiro. `ACM`, después de `trim` y
  conversión a mayúsculas, clasifica exactamente como `ACADEMIA`; cualquier otro
  valor usa `MENSAJERIA_LOCAL`. No se aplica substring ni se reclasifica el
  histórico existente.
- `e_fecha_of` registra la hora del procesamiento que produjo un resultado
  realmente `OK`. No se deriva de exportación, correo ni nombre de archivo.
- Una respuesta `ERROR ... servicio H2H` no garantiza ausencia de OF. Es deuda
  funcional crítica diseñar el estado de verificación antes de permitir cualquier
  regeneración automática futura.
- La regla operacional confirmada es `e_kilos = e_bultos`, siempre con mínimo 1.
  Su automatización en la interfaz queda para una fase funcional posterior.
- Un retiro físico se representa mediante un `RetiroStarken` y una asociación
  `RetiroEnvio` por envío/OF, nunca por bulto. `re_bultos_snapshot` conserva los
  bultos existentes al confirmar el retiro.
- La BD impide dos asociaciones vigentes para un mismo envío mediante el índice
  parcial `uq_retiro_envios_envio_vigente`. Una asociación no vigente permanece
  como historia y permite una asociación posterior.
- La futura capa de servicio debe rechazar envíos o retiros anulados y, al anular
  un retiro, marcar sus asociaciones como no vigentes. Estas reglas cruzan tablas
  y no se implementan como `CHECK`; tampoco se introducen triggers implícitos en
  esta migración de persistencia.

## Servicio de dominio de retiros

- La elegibilidad se deriva de OF, fecha OF, punto local activo, anulación y
  ausencia de asociación vigente. `e_estado` no es la fuente de verdad.
- La confirmación bloquea los envíos con `SELECT ... FOR UPDATE` en PostgreSQL y
  conserva el índice parcial como barrera final de concurrencia. Toda la operación
  se confirma o revierte como una unidad.
- El código visible tiene formato `RET-YYYYMMDD-NNNNNN`: usa la fecha efectiva
  y el ID autogenerado de `RetiroStarken`. Durante el primer `flush` se utiliza
  un token UUID interno, que se sustituye antes del commit y nunca se presenta.
  No depende de azar visible, `COUNT` ni `MAX`; el `UNIQUE` permanece como defensa.
- `rs_fecha_confirmacion` usa la hora real del sistema. La fecha efectiva permite
  registros retrospectivos y solo rechaza valores con más de 15 minutos hacia el
  futuro, tolerando diferencias menores de reloj o digitación.
- Anular un retiro no borra registros: marca el retiro como anulado y todas sus
  asociaciones vigentes como inactivas dentro de la misma transacción.

## Persistencia de Avisos V2

La revisión `20260829_05` agrega `avisos_envio` sin modificar ni poblar
`envios`. Durante la transición conviven dos representaciones:

```text
Avisos legacy en envios
    -> coexistencia temporal
AvisoEnvio V2
    -> migracion funcional posterior
```

Cada fila V2 representa un aviso lógico independiente de tipo `FUNCIONARIO` o
`DESTINATARIO`. `UNIQUE(envio_id, av_tipo)` evita duplicar el mismo aviso y
`av_clave_idempotencia`, con formato estable `ENVIO-{envio_id}-{tipo}`, aporta
una segunda defensa que no depende de la dirección de correo. El correo previsto
se conserva en `av_correo_snapshot`; cambiar posteriormente el correo del envío
no altera ese destinatario histórico.

Los estados admitidos son:

- `PENDIENTE`: todavía no se inicia un intento;
- `PROCESANDO`: existe un intento en curso;
- `ENVIADO`: el proveedor confirmó la aceptación del correo;
- `ERROR`: el intento falló de forma conocida y podrá reintentarse;
- `INCIERTO`: no puede determinarse con seguridad si el proveedor aceptó el
  correo; no equivale a `ERROR` y requerirá revisión antes de reintentar;
- `CANCELADO`: el aviso lógico no debe procesarse.

`av_intentos` comienza en cero y tiene un `CHECK` que impide valores negativos.
Las fechas de creación, procesamiento y envío son hechos distintos y no se
infieren entre sí. La FK hacia `envios` usa `ON DELETE RESTRICT`, sin cascadas
destructivas.

Esta revisión no conecta el flujo de correo existente a la tabla nueva. Los
campos legacy `e_estado_correo`, `e_aviso_funcionario_estado`,
`e_fecha_envio_correo` y `e_fecha_aviso_funcionario` permanecen intactos. La
creación, claim, reintentos y reconciliación funcional se implementarán en una
fase posterior.

Se crean índices individuales para `envio_id`, `av_estado`, `av_tipo` y
`av_fecha_creacion`. No se agrega todavía un índice compuesto: la forma exacta
de consulta de la futura cola debe medirse antes de duplicar índices de baja
cardinalidad.

### Elegibilidad y sincronización de Avisos V2

La fuente de verdad para crear avisos es el retiro físico vigente: el envío debe
tener OF y fecha OF, no estar anulado y estar asociado mediante un
`RetiroEnvio.re_vigente=true` a un `RetiroStarken` no anulado. El estado textual
del envío, su lote o la OF por sí solos no lo vuelven elegible.

La sincronización crea, como máximo, un aviso `FUNCIONARIO` y uno
`DESTINATARIO` por envío. Captura una sola vez los correos legacy normalizados;
las ejecuciones posteriores no cambian el snapshot, los intentos ni el estado.
Un correo ausente o inválido genera directamente un aviso `CANCELADO`, sin
snapshot ni error artificial. Esta decisión evita tratar un dato faltante como
un fallo transitorio de entrega.

Si desaparece la elegibilidad, solo `PENDIENTE` y `ERROR` pasan a `CANCELADO`.
`PROCESANDO`, `INCIERTO`, `ENVIADO` y `CANCELADO` se conservan para no afirmar
un resultado que la sincronización no conoce. La operación es atómica por envío;
en PostgreSQL bloquea el envío y los `UNIQUE` absorben carreras como defensa
final. Una ejecución masiva confirma cada envío de forma independiente y se
detiene ante un error inesperado, conservando los anteriores ya completados.

La identidad definitiva de `AvisoEnvio` pertenece al envío y al tipo, no al
ciclo de retiro. Se mantiene `UNIQUE(envio_id, av_tipo)`: un retiro posterior
del mismo envío no crea otro aviso y un aviso `CANCELADO` no se reactiva
automáticamente. Cualquier reactivación o reenvío futuro deberá ser una acción
explícita y auditada.

### Motor seguro de Avisos V2

El motor procesa cada `AvisoEnvio` como una unidad independiente. Primero hace
un claim condicional de `PENDIENTE` (o `ERROR` con autorización explícita), lo
cambia a `PROCESANDO`, incrementa `av_intentos`, registra la fecha y confirma la
transacción. Solo después de ese commit llama al proveedor. El resultado se
persiste y confirma en una sesión nueva, por lo que el fallo de un aviso no puede
revertir avisos enviados anteriormente.

`ENVIADO`, `INCIERTO`, `PROCESANDO` y `CANCELADO` no son procesables. Un `ERROR`
solo se reclama mediante reintento explícitamente autorizado. Si antes del claim
el envío perdió elegibilidad o el snapshot ya no es utilizable, `PENDIENTE` o
`ERROR` se cancela sin invocar al proveedor ni incrementar intentos. El destino
del correo siempre es `av_correo_snapshot`; nunca se reconstruye desde el envío.

Un resultado confirmado por el proveedor produce `ENVIADO`; un rechazo que
confirma que no fue aceptado produce `ERROR`; un timeout, corte o resultado
ambiguo produce `INCIERTO`. El `message_id`, cuando existe, prueba aceptación o
identificación del proveedor, no entrega final al destinatario. Los errores se
limitan y sanitizan antes de persistirse.

Existe una ventana inevitable: el proveedor puede aceptar el correo y el proceso
puede morir antes de guardar `ENVIADO`. Sin idempotencia externa no puede
prometerse entrega "exactly once". La garantía es estado persistente, ausencia de
reintento automático para resultados ambiguos y resolución explícita del operador.
Los `PROCESANDO` antiguos solo se detectan; no se resetean automáticamente y deben
tratarse como potencialmente inciertos.

El flujo legacy agrupa varios envíos de un funcionario en un correo. El modelo
V2 procesa por ahora una unidad persistente por aviso/envío; conservar o cambiar
el agrupamiento se resolverá en 3E.5 sin debilitar el claim individual ni crear
doble envío entre los motores legacy y V2.

#### Contrato del cliente de correo

`services.email_client.enviar_mensaje()` sigue siendo el único punto de entrada
y ahora devuelve un `ResultadoEmail` cuando existe aceptación confirmada. Los
consumidores legacy pueden ignorar el retorno y conservan el contrato de recibir
una excepción cuando la aceptación no puede confirmarse.

Los transportes disponibles son:

- `EMAIL_PROVIDER=brevo`: API HTTPS de Brevo. Solo `HTTP 201`, JSON válido y
  `messageId` confirman aceptación; ese identificador puede persistirse en V2.
- `EMAIL_PROVIDER=smtp`: Gmail SMTP. Una respuesta final sin destinatarios
  rechazados confirma aceptación, pero no entrega un ID real del proveedor.
- `EMAIL_PROVIDER=brevo_smtp`: relay SMTP de Brevo, con la misma ausencia de un
  `messageId` confiable en el contrato utilizado.

Los rechazos HTTP 400, 401, 403, 404, 422 y 429 son `ErrorCorreoConfirmado`.
HTTP 5xx, timeout, interrupción, JSON inválido o respuesta exitosa sin
`messageId` son `ResultadoCorreoIncierto`, porque la aceptación no puede
descartarse con seguridad. El adaptador V2 consume estas excepciones tipadas y
no clasifica errores por expresiones regulares.

En Gmail SMTP, el fallback SSL a STARTTLS solo ocurre si el fallo fue anterior a
`send_message()`. Una interrupción durante el envío es incierta y no inicia un
segundo transporte automático. Un error al cerrar después de una respuesta final
de aceptación tampoco provoca reenvío. `messageId` representa aceptación o
identificación del proveedor, nunca entrega final al destinatario.

Esta adaptación no cambia automáticamente el transporte desplegado. Activar
Brevo API en producción mediante `EMAIL_PROVIDER=brevo` es una decisión de
configuración y despliegue separada.


## Fase 1.2B: persistencia OF y conciliaciones H2H

Revision `20261025_06`, posterior a `20260829_05`. Crea exclusivamente
`intentos_of`, `registros_of`, `conciliaciones_h2h` y `movimientos_envio`.
No modifica `envios`, no realiza backfill y no conecta estas tablas al flujo
operativo, a Avisos V2 ni a nuevas pantallas.

- `IntentoOF` conserva envio, secuencia, transportista, lote, fila, archivo y
  predecesor. Las secuencias son positivas y unicas por envio. Un indice parcial
  admite un solo intento ABIERTO o EN_VERIFICACION por envio. Los otros estados
  son CON_OF, SIN_OF_VERIFICADA y CANCELADO. El predecesor debe pertenecer al
  mismo envio y solo admite un sucesor directo.
- `RegistroOF` conserva la OF como texto sin longitud fija ni conversion a entero.
  El ORM recorta espacios exteriores, preserva ceros iniciales y rechaza numeros
  recibidos como enteros. La unicidad es por transportista normalizado y OF;
  tambien hay un solo registro por intento. Una FK compuesta valida envio y
  transportista contra el intento. No se presume todavia un formato numerico
  exclusivo, longitud, ni ambito adicional por cuenta de transporte.
- `ConciliacionH2H` es unica por intento y conserva snapshots originales.
  PENDIENTE no exige observacion ni fecha de verificacion. OF_EXISTENTE y
  OF_INEXISTENTE exigen fecha, operador, metodo y observacion no vacios.
  OF_EXISTENTE requiere un RegistroOF del mismo intento/envio. El metodo
  habitual se identifica como PLATAFORMA_STARKEN, sin afirmar una consulta
  externa automatica. La referencia de respaldo es opcional.
- `ch_intento_sucesor_id` solo se admite en OF_INEXISTENTE y debe apuntar a un
  sucesor directo del mismo envio. Su unicidad permite representar un consumo
  unico. No se implementa aun la accion de autorizacion ni su consumo atomico;
  esa transicion pertenece a la siguiente capa de servicio.
- `MovimientoEnvio` conserva eventos independientes, actor y snapshot JSON.
  La clave de idempotencia es opcional y unica cuando existe. El intento opcional
  debe pertenecer al envio. Los hooks ORM rechazan actualizar o borrar eventos
  y sobrescribir identidad/evidencia original de conciliaciones. SQL directo y
  actualizaciones masivas pueden eludir esos hooks: no se afirma inmutabilidad
  frente a administradores de base de datos ni se agregan triggers implicitos.

Las FK usan RESTRICT. Los snapshots y relaciones no tienen cascadas destructivas.
La fecha de creacion corresponde al registro nuevo, no a una fecha historica
inferida. La deteccion H2H admite NULL cuando no se dispone de esa fecha.

La revision es estatica y no importa modelos actuales al ejecutarse. Las pruebas
usan SQLite aislada con FK habilitadas, upgrade desde 20260829_05, auditoria
contra metadata y comprobacion de que los registros legacy permanecen intactos.
El DDL PostgreSQL se compila sin conexion; no sustituye una prueba autorizada
sobre una base PostgreSQL aislada.

Antes de integrar: definir formato real de OF, reglas de transicion e idempotencia,
consumo de autorizacion, adopcion explicita de registros legacy y prohibicion de
borrado en rutas ante las nuevas relaciones. No reconstruir historial inexistente.
El downgrade elimina las cuatro tablas nuevas: no usarlo con datos operativos
sin un procedimiento revisado. No se autoriza ninguna migracion externa.


### Fase 1.2B.1: conservacion mediante ORM ordinario

No modifica el esquema de `20261025_06` ni agrega migraciones, triggers o
procedimientos. Las restricciones FK, UNIQUE y CHECK siguen siendo las de 1.2B.

Contrato de registros persistidos:

- `IntentoOF`: todos los campos son inmutables por ORM, incluido el estado.
  No se han definido aun transiciones funcionales; no se habilita una edicion
  generica para resolverlas. Todo intento persistido constituye evidencia y no
  se elimina mediante Session.delete().
- `RegistroOF`: identidad, envio, intento, transportista, numero textual, fecha
  y origen son inmutables. No se elimina por ORM, conservando la reserva del numero.
- `ConciliacionH2H`: identidad, asociaciones y snapshot original permanecen
  inmutables. No se elimina por ORM. Mientras es PENDIENTE puede completar sus
  metadatos de verificacion y registrar una resolucion definitiva, sujeta a los
  CHECK existentes. Una resolucion definitiva conserva estado, fecha, operador,
  metodo, justificacion, referencia y registro OF; no vuelve a PENDIENTE.
- `MovimientoEnvio`: se mantienen las guardas ORM contra actualizacion y borrado.

Consumo de autorizacion: NULL en `ch_intento_sucesor_id` significa que no hay un
sucesor registrado como consumidor. Un valor identifica un unico sucesor directo
validado por FK. Solo OF_INEXISTENTE puede registrarlo. Una vez asignado, el ORM
impide limpiarlo o sustituirlo. La existencia de un intento con io_anterior_id no
constituye por si sola el consumo de una autorizacion de conciliacion. La futura
capa de servicio debera crear y vincular el sucesor en la misma transaccion.

Los hooks de actualizacion comparan con la fila persistida y usan FOR UPDATE
cuando el motor lo admite; no dependen de valores viejos disponibles en memoria.
Esto cubre objetos expirados o desactualizados en el flush ORM ordinario. Las
correcciones futuras requieren movimientos explicitos y una politica revisada;
no hay flags para saltarse las guardas ni acciones funcionales nuevas.

Limite de garantias: SQLAlchemy Core, SQL directo y bulk updates/deletes pueden
eludir los hooks. PostgreSQL aplica directamente las FK, UNIQUE y CHECK, pero
estos no garantizan inmutabilidad historica ni consumo irreversible por SQL.
No se afirma proteccion frente a cambios administrativos en la base. SQLite
solo aplica las FK si se habilitan en cada conexion. La concurrencia real de
PostgreSQL requiere una prueba posterior autorizada.

Despliegue futuro: aplicar Alembic antes de arrancar/importar la version nueva.
El create_all() que main.py conserva podria crear tablas sin avanzar la revision;
no resolver esa situacion mediante stamp ciego. No se ejecuto despliegue alguno.

## S2A: validador de lectura y preparación de S2B

Implementación local pendiente de revisión; **S2B no está implementada**.
Las tres llamadas de main.py permanecen intactas y el servicio web no invoca aún
el validador. Los riesgos de startup descritos arriba continúan existiendo.

[database/validacion_esquema.py](../database/validacion_esquema.py) recibe un
Engine explícito y devuelve un ResultadoEsquema con estado, nombre de contrato,
revisiones conocidas y hallazgos estructurados. No importa main, configuración,
conexión global ni metadata de los modelos.

La política está fijada en
[database/contrato_esquema.py](../database/contrato_esquema.py):
el contrato V2 requiere y acepta 20261025_06. Las revisiones anteriores conocidas
son insuficientes; una revisión desconocida o varias filas requieren revisión
manual. No consulta la cabeza Alembic para ampliar permisos automáticamente.
Cada versión futura deberá aprobar sus revisiones compatibles y su estructura;
las revisiones aceptadas no pueden ser anteriores al mínimo del contrato.

Estados del resultado:

- COMPATIBLE: satisface el contrato declarado.
- REVISION_AUSENTE: falta alembic_version.
- REVISION_INSUFICIENTE: revisión conocida anterior al mínimo.
- ESTRUCTURA_INCOMPLETA: faltan tablas o columnas.
- REFERENCIAS_INCOMPLETAS: falta un punto obligatorio o está inactivo.
- REVISION_MANUAL: versión desconocida/múltiple, garantías diferentes,
  referencias incoherentes o error de conexión/reflexión.

Se conservan todos los hallazgos, aunque el estado principal prioriza ausencia
de revisión, revisión insuficiente y falta de estructura. Los valores de revisión
desconocidos y los textos de errores del driver no se reproducen en el resultado.

El snapshot comprueba columnas de las 19 tablas de la versión, unicidades
declaradas, FK con destino/columnas/RESTRICT, los dos índices únicos parciales
de retiro vigente e intento abierto y tres CHECK sencillos: bultos de retiro,
secuencia de intento e intentos de aviso. Además exige MENSAJERIA_LOCAL y ACADEMIA
activos, únicos y con clasificación logística coherente.

La equivalencia de predicados reconoce únicamente las formas pequeñas declaradas
para SQLite/PostgreSQL; una forma no reconocida exige revisión. No es auditoría
completa de tipos, nullability, defaults, todos los CHECK, permisos, triggers,
contenido operativo ni concurrencia. Reflejar una FK SQLite no acredita que cada
conexión tenga activado PRAGMA foreign_keys. PostgreSQL aún requiere verificación
autorizada sobre copia aislada; las pruebas SQLite no certifican ese backend.

La validación abre una conexión propia y revierte su transacción. En PostgreSQL
declara SET TRANSACTION READ ONLY antes de inspeccionar. No hace commit, DDL,
DML, create_all, upgrade, stamp, normalización ni inserción de referencias.
Preferir además un rol con permisos exclusivamente de lectura cuando corresponda.

Una base creada explícitamente desde metadata puede validarse con
contrato_fixture_sqlite(): omite solo el requisito de historial Alembic, conserva
las comprobaciones estructurales y referencias y se rechaza para PostgreSQL.
Es una decisión expresa del fixture, nunca una inferencia desde APP_ENV,
un fallback productivo ni un stamp implícito.

Antes de S2B:

1. Revisar este contrato y comprobarlo sobre una copia PostgreSQL autorizada.
2. Auditar/adoptar el esquema real y sus referencias sin stamp automático.
3. Retirar las tres llamadas legacy y conectar la validación en modo lectura,
   con un error claro si el resultado no es compatible.
4. Mantener la preparación explícita de fixtures y adaptar el ensayo de arranque
   que en S2A neutraliza las llamadas únicamente dentro de su subproceso de prueba.
5. Conservar endpoints, normalización de entradas y lógica operativa; separar
   el mantenimiento histórico en su etapa autorizada.

El aislamiento y sus comandos están en [Desarrollo](DESARROLLO.md).

### S2A.1: comparación conservadora de expresiones

La comparación distingue tokens SQL y conserva los literales exactamente,
incluidos mayúsculas, espacios internos y comillas escapadas. Solo reconoce
las formas pequeñas de IN/ANY, retiro vigente y CHECK declaradas en el contrato,
con diferencias de formato justificadas fuera de los literales.

Una expresión desconocida no equivale ni siquiera a otra cadena desconocida
idéntica: exige revisión manual. No se incorpora un parser SQL general.
Las regresiones verifican índices SQLite reales con literales cambiados y
una forma textual conocida de reflexión PostgreSQL, sin conectarse a PostgreSQL.

La autorización de raíces temporales y subprocesos de pruebas se describe en
[Desarrollo](DESARROLLO.md#s2a1-procedencia-y-puntos-de-entrada-corregidos).
Estas correcciones no conectan el validador al arranque ni implementan S2B.
