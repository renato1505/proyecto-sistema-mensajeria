# Migraciones de base de datos

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

Procedimiento futuro:

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

## Decisiones de diseño Retiro todavía no implementadas

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
