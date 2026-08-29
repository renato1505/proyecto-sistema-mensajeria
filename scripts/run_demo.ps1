param(
    [switch]$Seed,
    [switch]$Clean,
    [switch]$NoStart,
    [ValidateSet("TODOS_OK", "UNO_ERROR", "MIXTO", "H2H_AMBIGUO")]
    [string]$Scenario,
    [ValidateRange(1, 50)]
    [int]$Cantidad = 10
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DemoRoot = [System.IO.Path]::GetFullPath((Join-Path $env:TEMP "mensajeria-v2-demo"))
$TempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$DemoDatabase = Join-Path $DemoRoot "mensajeria_demo.sqlite3"
$DemoLogs = Join-Path $DemoRoot "logs"
$DemoBackups = Join-Path $DemoRoot "respaldos_lotes"
$DemoStarken = Join-Path $DemoRoot "starken"
$DemoUrl = "http://127.0.0.1:5000"

function Test-ProductionEnvironment {
    $renderValue = [string]$env:RENDER
    $appEnvironment = [string]$env:APP_ENV
    $databaseUrl = [string]$env:DATABASE_URL

    if ($renderValue.Trim().ToLowerInvariant() -eq "true") {
        throw "Abortado: RENDER=true no es compatible con MODO DEMO LOCAL."
    }

    if ($appEnvironment.Trim().ToLowerInvariant() -in @("production", "produccion", "prod")) {
        throw "Abortado: APP_ENV indica un entorno productivo."
    }

    if ($databaseUrl -match "^postgres(?:ql)?(?:\+[^:]+)?://") {
        throw "Abortado: DATABASE_URL apunta a PostgreSQL. Abre una consola limpia para ejecutar el demo."
    }
}

function Remove-DemoEnvironment {
    if (-not $DemoRoot.StartsWith($TempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Se rechazo la limpieza: la ruta demo no esta dentro de TEMP."
    }

    if (Test-Path -LiteralPath $DemoRoot) {
        Remove-Item -LiteralPath $DemoRoot -Recurse -Force
        Write-Host "Entorno demo eliminado: $DemoRoot" -ForegroundColor Green
    } else {
        Write-Host "No existe un entorno demo para eliminar: $DemoRoot" -ForegroundColor Yellow
    }
}

Test-ProductionEnvironment

if ($Clean) {
    Remove-DemoEnvironment
    exit 0
}

Set-Location -LiteralPath $ProjectRoot

New-Item -ItemType Directory -Path $DemoRoot -Force | Out-Null
New-Item -ItemType Directory -Path $DemoLogs -Force | Out-Null
New-Item -ItemType Directory -Path $DemoBackups -Force | Out-Null
New-Item -ItemType Directory -Path $DemoStarken -Force | Out-Null

$SitePackages = Join-Path $ProjectRoot "venv\Lib\site-packages"
if (Test-Path -LiteralPath $SitePackages) {
    $env:PYTHONPATH = $SitePackages
}

$PythonCandidates = @(
    (Join-Path $ProjectRoot "venv\Scripts\python.exe"),
    (Join-Path $env:TEMP "codex-python-3.14.3\python.exe")
)

$Python = $null
foreach ($Candidate in $PythonCandidates) {
    if (-not (Test-Path -LiteralPath $Candidate)) {
        continue
    }

    try {
        & $Candidate -c "import flask, sqlalchemy, werkzeug" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $Python = $Candidate
            break
        }
    } catch {
        continue
    }
}

if (-not $Python) {
    throw (
        "No se encontro un Python funcional. Se revisaron el venv del repositorio y " +
        "$env:TEMP\codex-python-3.14.3\python.exe."
    )
}

$SqlitePath = $DemoDatabase.Replace("\", "/")
$env:DATABASE_URL = "sqlite:///$SqlitePath"
$env:APP_ENV = "test"
$env:RENDER = "false"
$env:FLASK_DEBUG = "0"
$env:LOGIN_REQUIRED = "1"
$env:SECRET_KEY = "demo-local-secret-no-productiva"
$env:SESSION_TIMEOUT_MINUTES = "60"
$env:RESPALDOS_LOTES_DIR = $DemoBackups
$env:LOGS_DIR = $DemoLogs

# Valores deliberadamente inutilizables. El proveedor invalido bloquea SMTP/Brevo
# y el puerto IMAP cero hace que la lectura de correo figure como no configurada.
$env:EMAIL_PROVIDER = "disabled"
$env:CORREO_EMISOR = "demo@invalid.example"
$env:CORREO_CLAVE_APP = "DEMO_DISABLED"
$env:CORREO_DESTINO_STARKEN = "starken@invalid.example"
$env:CORREO_RESPALDO_MENSAJERIA = "mensajeria@invalid.example"
$env:BREVO_API_KEY = "DEMO_DISABLED"
$env:BREVO_SMTP_LOGIN = "DEMO_DISABLED"
$env:BREVO_SMTP_PASSWORD = "DEMO_DISABLED"
$env:OF_IMAP_HOST = "127.0.0.1"
$env:OF_IMAP_PORT = "0"
$env:OF_CORREO_FILTRO_REMITENTE = ""
$env:OF_CORREO_FILTRO_TEXTO = ""

if ($env:DATABASE_URL -notmatch "^sqlite:///") {
    throw "Abortado: el entorno demo no quedo configurado con SQLite."
}

$SetupDemo = @'
from werkzeug.security import generate_password_hash
from sqlalchemy import inspect
from datetime import timedelta

from database.conexion import SessionLocal, engine
from database.modelos import Base, Envio, PuntoRetiro, UsuarioSistema
from services.demo_starken import (
    crear_lote_demo,
    generar_envios_ficticios,
    procesar_respuesta_of_demo,
    raiz_demo_permitida,
)
from services.puntos_retiro import (
    PUNTO_ACADEMIA,
    PUNTO_MENSAJERIA_LOCAL,
    asignar_punto_retiro_nuevo_envio,
)
from utils.fechas import ahora_chile

tablas_existentes = set(inspect(engine).get_table_names())
if "envios" in tablas_existentes:
    columnas_envios = {item["name"] for item in inspect(engine).get_columns("envios")}
    requeridas = {"e_fecha_of", "e_punto_retiro_id"}
    faltantes = sorted(requeridas - columnas_envios)
    if faltantes:
        raise RuntimeError(
            "SQLite demo incompatible; faltan columnas "
            f"{', '.join(faltantes)}. Ejecuta .\\scripts\\run_demo.ps1 -Clean"
        )

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    puntos_demo = [
        (PUNTO_MENSAJERIA_LOCAL, "Mensajeria local", True, True),
        (PUNTO_ACADEMIA, "Academia", False, False),
    ]
    for codigo, nombre, es_local, incluir_metricas in puntos_demo:
        if db.query(PuntoRetiro).filter(PuntoRetiro.pr_codigo == codigo).first() is None:
            db.add(PuntoRetiro(
                pr_codigo=codigo,
                pr_nombre=nombre,
                pr_es_local=es_local,
                pr_incluir_metricas_locales=incluir_metricas,
                pr_activo=True,
            ))
    db.flush()

    usuario = (
        db.query(UsuarioSistema)
        .filter(UsuarioSistema.u_usuario == "demo")
        .first()
    )
    if usuario is None:
        db.add(
            UsuarioSistema(
                u_usuario="demo",
                u_nombre="Operador Demo Local",
                u_rut="11111111-1",
                u_clave_hash=generate_password_hash("Demo1234!"),
                u_area="mensajeria",
                u_rol="usuario",
                u_activo=True,
                u_debe_cambiar_clave=False,
            )
        )

    if __import__("os").environ.get("DEMO_SEED") == "1":
        existe_seed = (
            db.query(Envio)
            .filter(Envio.e_destinatario == "Destinatario Ficticio 001")
            .first()
        )
        if existe_seed is None:
            envios_demo = generar_envios_ficticios(db, 10, incluir_academia=True)
            incompleto = Envio(
                e_remitente="Funcionario Demo QA Incompleto",
                e_correo_remitente="funcionario@demo.invalid",
                e_division="DPGP",
                e_centro_costo="DEMO-QA",
                e_destinatario="Agencia Ficticia Incompleta",
                e_rut_destinatario="0",
                e_direccion="Avenida Ficticia 999",
                e_comuna="Santiago",
                e_region="Metropolitana",
                e_telefono_destinatario="56999999999",
                e_correo_destinatario="incompleto@demo.invalid",
                e_tipo_envio="Agencia",
                e_codigo_agencia=None,
                e_bultos=1,
                e_kilos=1,
                e_estado="pendiente",
                e_anulado=False,
            )
            asignar_punto_retiro_nuevo_envio(db, incompleto)
            db.add(incompleto)
            db.commit()
            lote_seed = crear_lote_demo(
                db,
                [envios_demo[0].id, envios_demo[1].id],
                raiz_demo_permitida(),
                fecha_actual=ahora_chile() - timedelta(minutes=1),
            )
            procesar_respuesta_of_demo(
                db,
                lote_seed["lote"],
                "UNO_ERROR",
                raiz_demo_permitida(),
            )

    db.commit()
finally:
    db.close()
'@

$env:DEMO_SEED = if ($Seed) { "1" } else { "0" }
$SetupDemoEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($SetupDemo))
& $Python -c "import base64; exec(base64.b64decode('$SetupDemoEncoded'))"
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo preparar SQLite demo. Si esta desactualizada, ejecuta -Clean."
}

if ($Scenario) {
    & $Python scripts/demo_operacion.py --cantidad $Cantidad --escenario $Scenario
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo ejecutar el escenario Starken demo."
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "                 MODO DEMO LOCAL" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "URL:        $DemoUrl"
Write-Host "Usuario:    demo"
Write-Host "Contrasena: Demo1234!"
Write-Host "Base:       $DemoDatabase"
Write-Host "Logs:       $DemoLogs"
Write-Host "Respaldos:  $DemoBackups"
Write-Host "Starken:    $DemoStarken"
Write-Host "Correo:     DESHABILITADO"
Write-Host "Python:     $Python"
Write-Host ""
Write-Host "Detener servidor: Ctrl+C"
Write-Host "Eliminar demo:    .\scripts\run_demo.ps1 -Clean"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($NoStart) {
    Write-Host "Demo preparada sin iniciar servidor (-NoStart)." -ForegroundColor Green
    exit 0
}

$BrowserCommand = @"
for (`$intento = 0; `$intento -lt 30; `$intento++) {
    try {
        Invoke-WebRequest -Uri '$DemoUrl' -UseBasicParsing -TimeoutSec 1 | Out-Null
        Start-Process '$DemoUrl'
        exit 0
    } catch {
        Start-Sleep -Milliseconds 500
    }
}
"@
$EncodedBrowserCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($BrowserCommand))
Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-EncodedCommand",
    $EncodedBrowserCommand
) | Out-Null

& $Python -c "from main import app; app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)"
