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

S2A incorpora [el bootstrap de pruebas](../tests/entorno_aislado.py), invocado
antes de configuración, conexión o aplicación por los módulos unittest.
No requiere un `.env` de desarrollo preparado: fija valores ficticios, correo
deshabilitado y SQLite en memoria o dentro de una raíz temporal nueva.
No abre ni modifica `.env`; el cargador legacy de configuración sigue pudiendo
leerlo al importar la aplicación, con las variables críticas ya fijadas.

Usar una consola dedicada desde la raíz. Si el proceso hereda PostgreSQL, otra
base, una SQLite fuera de la raíz de pruebas o indicadores de producción, el
bootstrap rechaza la ejecución antes de importar la aplicación. No reutilizar
la SQLite de trabajo ni resolver el rechazo copiando credenciales.

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_validacion_esquema tests.test_entorno_aislado
if ($LASTEXITCODE -ne 0) { throw "Las pruebas S2A fallaron" }
.\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
if ($LASTEXITCODE -ne 0) { throw "La suite fallo" }
.\venv\Scripts\python.exe -m compileall -q main.py config database routes services scripts tests migrations
if ($LASTEXITCODE -ne 0) { throw "compileall fallo" }
git diff --check
if ($LASTEXITCODE -ne 0) { throw "El diff contiene errores de formato" }
```

Se bloquean DNS y conexiones de sockets, SQLite fuera de la raíz temporal y
conexiones SQLAlchemy de otros motores. Un acceso inesperado interrumpe unittest;
no se transforma en éxito de un transporte simulado.
Los subprocesos Python heredan las barreras mediante un `sitecustomize` generado
en la raíz temporal y abortan si el bootstrap falla.

Es aislamiento para los procesos Python y las dependencias actuales, no un sandbox
del sistema operativo frente a código arbitrario, ejecutables nativos o un
subproceso que elimine deliberadamente sus barreras. Revisar cualquier nuevo
punto de entrada. No guardar estado o código operativo en la raíz temporal.

Los fixtures pueden crear tablas y datos ficticios explícitamente.
[fixtures_app.py](../tests/fixtures_app.py) prepara la base global antes de
importar `main.app`; las pruebas que la utilizan no dependen de su creación
implícita. Las pruebas Alembic migran exclusivamente sus archivos SQLite
temporales; no son una autorización para migraciones externas.

La referencia previa a S2A es 273 pruebas aprobadas. Las nuevas pruebas cubren
compatibilidad y ausencia de reparaciones, barreras de aislamiento y preparación
de S2B. No usar el orden de importación de tests como protección de una URL real.


### S2A.1: procedencia y puntos de entrada corregidos

Cada ejecución principal crea una raíz nueva y rechaza cualquier SQLite de archivo
recibida por variables heredadas. No se abre una base para decidir si es de pruebas.
Una raíz heredada, aunque tenga el prefijo esperado, se rechaza sin autorización.

Los hijos se lanzan mediante `ejecutar_python_aislado()`. El principal conserva
un manifiesto de sesión y emite un permiso aleatorio de un solo uso, con caducidad
de 120 segundos, ligado a sesión, raíz, padre y URL SQLite exacta.
El hijo verifica esa relación antes de instalar el entorno y consume el permiso.
No puede reutilizarlo, cambiar de raíz o cambiar de destino.
Los subprocesos de Alembic usan este mismo lanzador y solo sus fixtures temporales.

En Windows se contempla el redirector de Python del venv: si el padre inmediato
es ese intermediario, se comprueban su ejecutable completo y su padre real mediante
consultas de lectura del sistema. Ante una identidad indeterminada se aborta.

El nonce de entorno por sí solo no autoriza acceso: se contrasta con el manifiesto,
el permiso existente y el proceso padre. Este protocolo evita adopciones accidentales;
no ofrece garantía criptográfica absoluta frente a código hostil del mismo usuario
que pueda modificar archivos, memoria o el lanzador. No es un sandbox del sistema.

Los módulos unittest preparan `sys.path` antes de importar el bootstrap.
Se preservan descubrimiento, ejecución por módulo y los formatos directos:

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_flujo_critico_unit
.\venv\Scripts\python.exe -m unittest tests.test_email_client_unit
.\venv\Scripts\python.exe tests/test_flujo_critico_unit.py
.\venv\Scripts\python.exe tests/test_email_client_unit.py
```

No restaurar la protección de hijos copiando solo `MENSAJERIA_TEST_ROOT` o una URL
a otro proceso. El lanzador debe emitir su propio permiso para cada hijo.

## Smoke y arranque

[tests/smoke_check.py](../tests/smoke_check.py) instala el mismo aislamiento antes
de importar configuración o aplicación y utiliza el fixture explícito.
Desactiva login únicamente en su proceso, por lo que no prueba autenticación.

```powershell
.\venv\Scripts\python.exe tests/smoke_check.py
if ($LASTEXITCODE -ne 0) { throw "El smoke fallo" }
```

Sigue escribiendo en su base temporal: prepara tablas/referencias y el arranque
legacy aún ejecuta las tres llamadas automáticas. No es una auditoría de lectura
ni valida un despliegue. No ofrecer una URL operativa al smoke.

S2A no conecta el validador al arranque ni retira llamadas de `main.py`.
Para explorar la interfaz, seguir la [demo](DEMO_OPERATIVA_V2.md).
Ejecutar `python main.py` conserva sus efectos legacy y requiere verificar el
destino; no sustituye una adopción Alembic. Ver el
[contrato de lectura S2A](MIGRACIONES.md#s2a-validador-de-lectura-y-preparación-de-s2b).

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
