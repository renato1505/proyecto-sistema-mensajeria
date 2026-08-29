# Demo operativa V2

La demo es un sandbox local descartable. Usa modelos, generación de lotes/CSV y
procesamiento OF reales, pero todos sus datos y archivos son ficticios y quedan
bajo `%TEMP%\mensajeria-v2-demo`.

## Inicio y limpieza

Desde la raíz del repositorio:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
.\scripts\run_demo.ps1 -Clean
.\scripts\run_demo.ps1 -Seed
```

Ejemplo del equipo local actual:

```powershell
cd "C:\Users\Renato\Desktop\Proyecto Sistema de Gestion de Mensajería\sistema_mensajeria"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
.\scripts\run_demo.ps1 -Clean
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
