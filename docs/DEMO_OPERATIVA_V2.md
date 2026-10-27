# Demo operativa V2

La demo es un sandbox local descartable. Usa modelos, generación de lotes/CSV y
procesamiento OF reales, pero todos sus datos y archivos son ficticios y quedan
bajo `%TEMP%\mensajeria-v2-demo`.

## Inicio y limpieza

Usar una consola dedicada sin variables PostgreSQL/productivas. El script se
contrasta en [scripts/run_demo.ps1](../scripts/run_demo.ps1); configura SQLite,
correo bloqueado y datos ficticios antes de importar la app. No necesita secretos
reales. Ver [Desarrollo](DESARROLLO.md) para crear el venv y las dependencias.

Desde la raíz del repositorio:

```powershell
.\venv\Scripts\Activate.ps1
.\scripts\run_demo.ps1 -Seed
```

Credenciales deliberadamente no productivas:

```text
usuario: demo
contraseña: Demo1234!
```

`-Clean` solo puede eliminar el directorio fijo de demo dentro de `%TEMP%`. Si
una SQLite antigua informa columnas ausentes como `envios.e_fecha_of`, ejecutar
primero `-Clean`; `create_all` no actualiza tablas existentes.

## Escenarios Starken/OF

Es posible preparar datos adicionales y procesar una respuesta OF antes de
iniciar la aplicación:

```powershell
.\scripts\run_demo.ps1 -Scenario TODOS_OK -Cantidad 10
.\scripts\run_demo.ps1 -Scenario UNO_ERROR -Cantidad 5
.\scripts\run_demo.ps1 -Scenario MIXTO -Cantidad 10
.\scripts\run_demo.ps1 -Scenario H2H_AMBIGUO -Cantidad 5
```

Para preparar y validar sin levantar el servidor:

```powershell
.\scripts\run_demo.ps1 -Clean
.\scripts\run_demo.ps1 -Seed -Scenario TODOS_OK -Cantidad 10 -NoStart
```

La cantidad permitida es 1 a 50. El simulador crea pendientes, llama al mismo
servicio usado por `/generar_excel`, guarda el CSV CP1252 real, genera un Excel
con las columnas reales de respuesta OF y lo entrega a `procesar_archivo_of()`.

Los archivos quedan exclusivamente en:

```text
%TEMP%\mensajeria-v2-demo\starken\
```

Las OF correctas usan el rango numérico ficticio reservado desde
`900000000000`; nunca deben enviarse fuera de la demo.

## Aislamiento

El script y el simulador abortan ante PostgreSQL, `RENDER=true`, un `APP_ENV`
productivo, SQLite en memoria o una base fuera del directorio demo. SMTP, Brevo
e IMAP se configuran con proveedores inválidos, puerto local cero y correos
`.invalid`. Producción no importa módulos demo.

`H2H_AMBIGUO` reproduce el texto `Error al enviar fila X a servicio H2H`. Este
error no garantiza ausencia de OF y el simulador no intenta regenerar envíos.

## Alcance y límites

El startup demo usa create_all() e importa main.py: escribe y normaliza su base
descartable; no es una prueba read-only ni valida la adopción Alembic. El smoke
se documenta por separado en [Desarrollo](DESARROLLO.md#smoke-y-arranque).

Para limpiar, detener antes el servidor y confirmar que se desea perder todo
el entorno demo fijo, incluidos datos y archivos de ensayos anteriores:

```powershell
.\scripts\run_demo.ps1 -Clean
```

No usar -Clean como requisito rutinario: es destructivo dentro del directorio
demo. Los escenarios generan archivos/OF ficticias locales, nunca una solicitud
real al transportista. No subir sus CSV ni sus OF a plataformas externas.

La demo no implementa conciliación manual, transición de estados de IntentoOF
ni integración de Avisos V2. Un escenario H2H no autoriza regeneración.
