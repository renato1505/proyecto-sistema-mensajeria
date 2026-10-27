# Desarrollo local

Guía vigente para recuperar el proyecto en otro equipo, trabajar con datos
ficticios y revisar cambios. Consolida las instrucciones útiles de Calidad,
GitHub y Migración de PC; sus originales se conservan en
[el archivo documental](ESTADO_PROYECTO.md#archivo-documental).

## Instalación en un equipo nuevo

Clonar el repositorio autorizado y situarse en su raíz, donde están
[main.py](../main.py) y [requirements.txt](../requirements.txt).
No hay que entrar en una subcarpeta `sistema_mensajeria`.

```powershell
git clone https://github.com/renato1505/proyecto-sistema-mensajeria.git
cd proyecto-sistema-mensajeria
git switch refactor/v2-foundation
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python --version
git status --short --branch
```

La última ejecución registrada utilizó Python 3.14 del entorno virtual.
Recrear `venv` en cada equipo; no copiarlo desde otro notebook.
Si el repositorio ya existe, revisar cambios locales y rama antes de actualizarlo;
no usar un pull que descarte o mezcle trabajo sin revisión.

No hace falta recuperar credenciales productivas ni instalar PostgreSQL para
las pruebas SQLite y la demo. Respaldos y evidencias reales requieren un
procedimiento de custodia separado; no copiarlos al repositorio para probar.

## Configuración local y precedencia

[config/settings.py](../config/settings.py) carga `.env` desde la raíz con
`os.environ.setdefault`: las variables ya presentes en el proceso prevalecen.
Activar el venv no aísla las variables del equipo ni neutraliza una URL heredada.

Si falta `.env`, usar [.env.example](../.env.example) solo como referencia.
No copiar secretos ni completar valores reales. Para una base local descartable,
usar exclusivamente una URL SQLite con ruta local y datos ficticios.
La demo configura su propia base, usuario y rutas temporales.

Valores locales mínimos recomendados:

| Variable | Valor o criterio local |
| --- | --- |
| `DATABASE_URL` | SQLite local descartable; nunca Render, producción ni QA |
| `APP_ENV`, `FLASK_ENV` | `development` o `test` |
| `RENDER` | `false` |
| `SECRET_KEY` | Valor exclusivo de demo/desarrollo, sin reutilizar secretos |
| `LOGIN_REQUIRED` | `1`, necesario para renderizar el formulario de login |
| `FLASK_DEBUG` | `0` |
| `SESSION_TIMEOUT_MINUTES` | `30` |
| `EMAIL_PROVIDER` | `disabled` |
| `CORREO_EMISOR`, destinos Starken y respaldo | Direcciones ficticias `.invalid` |
| Credenciales SMTP/Brevo | Sentinelas locales inutilizables, sin secretos |
| `OF_IMAP_HOST`, `OF_IMAP_PORT` | `127.0.0.1`, `0` |
| `LOGS_DIR`, `RESPALDOS_LOTES_DIR` | Directorios locales descartables |

`disabled` es deliberadamente un proveedor no admitido: un intento de correo
falla; no simula una entrega exitosa. El puerto IMAP cero evita considerar
configurada la lectura. No probar correo real ni añadir credenciales para
hacer pasar una validación local.

El login consulta únicamente `usuarios_sistema` y exige hash Werkzeug.
Una base vacía no incluye un usuario automáticamente. Usar la demo para disponer
de una cuenta ficticia; `APP_USERS` y `APP_ACCESS_PASSWORD` no habilitan acceso.
Ver [Autenticación](AUTENTICACION_V2.md).

## Pruebas con destino explícito y descartable

En una consola PowerShell dedicada, desde la raíz y antes de importar módulos,
configurar este entorno. No ejecutarlo contra una base que deba conservarse.
El bloque crea una carpeta temporal nueva y no lee el contenido de `.env`.

```powershell
$validacionRoot = Join-Path $env:TEMP ("mensajeria-validacion-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $validacionRoot | Out-Null
$validacionSqlite = (Join-Path $validacionRoot "validacion.sqlite3").Replace("\", "/")
$env:DATABASE_URL = "sqlite:///$validacionSqlite"
$env:APP_ENV = "test"
$env:FLASK_ENV = "test"
$env:RENDER = "false"
$env:FLASK_DEBUG = "0"
$env:SECRET_KEY = "solo-validacion-local-no-productiva"
$env:LOGIN_REQUIRED = "1"
$env:SESSION_TIMEOUT_MINUTES = "30"
$env:EMAIL_PROVIDER = "disabled"
$env:CORREO_EMISOR = "sistema@demo.invalid"
$env:CORREO_DESTINO_STARKEN = "starken@demo.invalid"
$env:CORREO_RESPALDO_MENSAJERIA = "respaldo@demo.invalid"
$env:CORREO_CLAVE_APP = "LOCAL_DISABLED"
$env:BREVO_API_KEY = "LOCAL_DISABLED"
$env:BREVO_SMTP_LOGIN = "LOCAL_DISABLED"
$env:BREVO_SMTP_PASSWORD = "LOCAL_DISABLED"
$env:OF_IMAP_HOST = "127.0.0.1"
$env:OF_IMAP_PORT = "0"
$env:CLAVE_ELIMINACION_HISTORICO = "solo-datos-ficticios"
$env:LOGS_DIR = Join-Path $validacionRoot "logs"
$env:RESPALDOS_LOTES_DIR = Join-Path $validacionRoot "respaldos_lotes"
if ($env:DATABASE_URL -notlike "sqlite:///*") { throw "Se requiere SQLite local" }
.\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
if ($LASTEXITCODE -ne 0) { throw "La suite fallo" }
.\venv\Scripts\python.exe -m compileall -q main.py config database routes services scripts tests migrations
if ($LASTEXITCODE -ne 0) { throw "compileall fallo" }
git diff --check
if ($LASTEXITCODE -ne 0) { throw "El diff contiene errores de formato" }
```

Los sentinelas de credenciales son no vacíos porque asignar una cadena vacía
puede quitar una variable en Windows PowerShell y permitir que `.env` la reponga.
Este bloque configura aislamiento local; no es una barrera de red para código
arbitrario. Revisar cambios de tests, fixtures y transportes antes de ejecutar
una suite modificada. Los tests usan SQLite en memoria o archivos temporales y
dobles de servicios; las pruebas Alembic migran únicamente sus fixtures locales.

El valor de referencia es 273 tests aprobados, no una promesa sobre futuras
modificaciones. No usar una selección de tests o su orden de importación como
única defensa frente a una URL real.

## Smoke y arranque

[tests/smoke_check.py](../tests/smoke_check.py) importa `main.py` y desactiva el
login dentro de su proceso. No prueba autenticación y no es de solo lectura:
el import ejecuta `create_all()`, helpers de columnas y normalización.
Puede alterar datos aun cuando las peticiones del smoke sean consultas o
validaciones negativas.

Solo después de configurar el entorno descartable anterior, en esa misma consola:

```powershell
.\venv\Scripts\python.exe tests/smoke_check.py
if ($LASTEXITCODE -ne 0) { throw "El smoke fallo" }
```

No incluir el smoke en una auditoría exclusivamente de lectura.
Para explorar la interfaz, seguir la [demo](DEMO_OPERATIVA_V2.md).
Ejecutar `python main.py` solo después de verificar el destino local; no es un
mecanismo de adopción Alembic ni un paso inocuo para recuperar una base existente.

## Esquema y scripts

Las migraciones formales están descritas en [Migraciones](MIGRACIONES.md).
No ejecutar scripts de mantenimiento como parte automática de instalar o hacer QA.

| Archivo | Alcance y precaución |
| --- | --- |
| [scripts/auditar_esquema.py](../scripts/auditar_esquema.py) | Auditoría de esquema; usa `AUDIT_DATABASE_URL` o el destino configurado. Solo con destino verificado y permisos de lectura |
| [scripts/aplicar_indices.py](../scripts/aplicar_indices.py) | Escribe índices; revisar adopción legacy/Alembic antes de usar |
| [scripts/cargar_comunas.py](../scripts/cargar_comunas.py) | Borra y recarga catálogo; `--confirmar` autoriza destrucción, no demuestra que el destino sea correcto |
| [scripts/cargar_remitentes.py](../scripts/cargar_remitentes.py) | Borra y recarga catálogo desde un Excel externo; no es un seed local general |
| [scripts/normalizar_remitentes.py](../scripts/normalizar_remitentes.py) | Escribe normalizaciones; requiere revisión de destino y datos |
| [scripts/migrar_bd_cloud.py](../scripts/migrar_bd_cloud.py) | Herramienta legacy parcial; no usar como respaldo o restauración integral V2 |
| [scripts/reset_password.py](../scripts/reset_password.py) | Administración externa de clave de un usuario existente; seguir el procedimiento autorizado de autenticación |

`migrar_bd_cloud.py` solo clona Comuna, Remitente, Destinatario y Envio.
Su `create_all()` de destino ocurre incluso sin `--confirmar`.
`--reemplazar-destino` borra datos del destino y su respaldo de origen no
respalda íntegramente la base V2 ni el destino. No ejecutarlo para diagnosticar
o recuperar datos; diseñar y probar por separado un respaldo/restauración completo.

## Git y custodia

Antes de preparar un commit:

```powershell
git branch --show-current
git status --short --branch
git diff --stat
git diff --check
git check-ignore .env
git ls-files .env
git diff --cached --name-only
```

`.env` debe estar ignorado y no aparecer como archivo versionado. Revisar
también bases locales, Excel reales, logs, respaldos, `venv/`, cargas temporales
y evidencias. `.vscode/` puede aparecer como no versionado; no incluirlo por
accidente. Preparar archivos explícitos, revisar el diff preparado y obtener la
autorización correspondiente antes de commit o push; evitar `git add .`.

La rama de trabajo actual es `refactor/v2-foundation`; no renombrarla a
`main`, fusionar ni desplegar como parte del onboarding. Un push puede activar
automatizaciones externas según su configuración: no asumir que publicar es
equivalente a desplegar, ni que nunca despliega.

Mantener repositorio privado y acceso limitado. No pegar secretos en commits,
issues o documentación. Si se publica un secreto, revocarlo y rotarlo; borrar el
archivo en el siguiente commit no elimina su exposición del historial.
