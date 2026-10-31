"""Aislamiento preventivo para pruebas Python, no sandbox del sistema operativo.

Cada principal crea una raíz nueva. Un hijo solo adopta la sesión mediante un
permiso de un solo uso emitido por su padre, ligado a sesión, raíz y destino.
Ni el prefijo de una carpeta ni un token de entorno bastan por sí solos.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time

_RAIZ = None
_SESION = None
_LISTO = False
_VARIABLES_SESION = ("MENSAJERIA_TEST_ROOT", "MENSAJERIA_TEST_RUN",
                     "MENSAJERIA_TEST_AUTORIZACION")
_URLS_MEMORIA = {"", "sqlite://", "sqlite:///:memory:",
                "sqlite+pysqlite://", "sqlite+pysqlite:///:memory:"}
_VIGENCIA_PERMISO = 120


class DestinoPruebasInvalido(ValueError):
    """Configuración, procedencia o destino no autorizados."""


class AccesoExternoBloqueado(KeyboardInterrupt):
    """Interrumpe unittest aunque el código probado capture Exception."""


def validar_destino_pruebas(url, raiz):
    from sqlalchemy.engine import make_url

    try:
        destino = make_url(url)
        if destino.get_backend_name() != "sqlite" or destino.host:
            raise ValueError()
        base = destino.database
        if base in (None, "", ":memory:"):
            return
        if not Path(base).is_absolute() or not Path(base).resolve().is_relative_to(Path(raiz).resolve()):
            raise ValueError()
    except Exception:
        raise DestinoPruebasInvalido(
            "Las pruebas requieren SQLite en memoria o dentro de su sesión temporal autorizada."
        ) from None


def _leer_json(ruta):
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            raise ValueError()
        return datos
    except Exception:
        raise DestinoPruebasInvalido("No se pudo verificar la procedencia de la sesión de pruebas.") from None


def _escribir_nuevo(ruta, datos):
    descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo)


def _padre_autorizado(esperado, lanzador):
    inmediato = os.getppid()
    if inmediato == esperado:
        return True
    if os.name != "nt":
        return False
    # El redirector python.exe de un venv Windows puede iniciar el intérprete
    # real como nieto. Admitir solo ese único intermediario, verificando tanto
    # su ejecutable completo como su padre mediante consultas al sistema.
    import ctypes
    from ctypes import wintypes

    class Proceso(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
            ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
            ("ppid", wintypes.DWORD), ("priority", wintypes.LONG),
            ("flags", wintypes.DWORD), ("exe", wintypes.WCHAR * 260),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    )
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(Proceso))
    kernel.Process32FirstW.restype = wintypes.BOOL
    kernel.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(Proceso))
    kernel.Process32NextW.restype = wintypes.BOOL

    handle = kernel.OpenProcess(0x1000, False, inmediato)
    if not handle:
        return False
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        longitud = wintypes.DWORD(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(longitud)):
            return False
        if os.path.normcase(str(Path(buffer.value).resolve())) != os.path.normcase(lanzador):
            return False
        snapshot = kernel.CreateToolhelp32Snapshot(0x00000002, 0)
        if snapshot in (None, ctypes.c_void_p(-1).value):
            return False
        try:
            proceso = Proceso()
            proceso.dwSize = ctypes.sizeof(Proceso)
            valido = kernel.Process32FirstW(snapshot, ctypes.byref(proceso))
            while valido:
                if proceso.pid == inmediato:
                    return proceso.ppid == esperado
                valido = kernel.Process32NextW(snapshot, ctypes.byref(proceso))
            return False
        finally:
            kernel.CloseHandle(snapshot)
    finally:
        kernel.CloseHandle(handle)


def _adoptar_sesion():
    """Valida el permiso antes de abrir SQLite o importar la aplicación."""
    token = os.environ.get("MENSAJERIA_TEST_AUTORIZACION", "")
    identificador = os.environ.get("MENSAJERIA_TEST_RUN", "")
    if not re.fullmatch(r"[0-9a-f]{64}", token) or not re.fullmatch(r"[0-9a-f]{64}", identificador):
        raise DestinoPruebasInvalido("Raíz heredada sin autorización de subproceso.")
    try:
        raiz = Path(os.environ["MENSAJERIA_TEST_ROOT"]).resolve(strict=True)
        sesion = _leer_json(raiz / ".sesion-pruebas.json")
        permiso_path = raiz / ".permisos" / (token + ".json")
        permiso = _leer_json(permiso_path)
        url = os.environ.get("DATABASE_URL", "")
        if not (
            raiz.is_dir()
            and sesion["raiz"] == str(raiz)
            and sesion["sesion"] == identificador == permiso["sesion"]
            and sesion["principal"] == permiso["principal"]
            and permiso["raiz"] == str(raiz)
            and _padre_autorizado(permiso["padre"], permiso["lanzador"])
            and permiso["destino"] == url
            and 0 <= time.time() - permiso["creado"] <= _VIGENCIA_PERMISO
        ):
            raise ValueError()
        validar_destino_pruebas(url, raiz)
        # Dos hijos que presenten el mismo permiso no pueden consumirlo ambos.
        # El segundo unlink falla y su bootstrap aborta.
        permiso_path.unlink()
    except Exception:
        raise DestinoPruebasInvalido("Autorización de subproceso inválida o ya consumida.") from None
    os.environ.pop("MENSAJERIA_TEST_AUTORIZACION", None)
    return raiz, sesion, url


def _auditar(evento, argumentos):
    if evento in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}:
        raise AccesoExternoBloqueado("Pruebas aisladas: conexiones de red prohibidas.")
    if evento == "sqlite3.connect":
        base = str(argumentos[0])
        if base != ":memory:" and not Path(base).resolve().is_relative_to(_RAIZ):
            raise AccesoExternoBloqueado("Pruebas aisladas: SQLite fuera de la sesión temporal.")


def _antes_de_conectar(dialecto, _registro, _argumentos, _opciones):
    if dialecto.name != "sqlite":
        raise AccesoExternoBloqueado("Pruebas aisladas: solo se permiten conexiones SQLite.")


def preparar_entorno_pruebas():
    global _RAIZ, _SESION, _LISTO
    if _RAIZ is not None:
        if (not _LISTO or os.environ.get("MENSAJERIA_TEST_ROOT") != str(_RAIZ)
                or os.environ.get("MENSAJERIA_TEST_RUN") != _SESION["sesion"]):
            raise DestinoPruebasInvalido("El contexto de la sesión de pruebas fue alterado.")
        validar_destino_pruebas(os.environ.get("DATABASE_URL", ""), _RAIZ)
        return _RAIZ

    if any(n in sys.modules for n in ("config.settings", "database.conexion", "main")):
        raise DestinoPruebasInvalido("El aislamiento debe configurarse antes de importar la aplicación.")
    if os.environ.get("RENDER", "").strip().lower() == "true" or any(
        os.environ.get(n, "").strip().lower() in {"prod", "production", "produccion"}
        for n in ("APP_ENV", "FLASK_ENV")
    ):
        raise DestinoPruebasInvalido("Se rechaza ejecutar pruebas con indicadores de producción.")

    heredada = any(os.environ.get(n) for n in _VARIABLES_SESION)
    if heredada:
        raiz, sesion, url = _adoptar_sesion()
    else:
        # Un principal jamás adopta un archivo SQLite de las variables heredadas.
        # No se abre la base para averiguar si contiene datos reales.
        if os.environ.get("DATABASE_URL", "") not in _URLS_MEMORIA:
            raise DestinoPruebasInvalido("Un principal nuevo no puede reutilizar una base heredada.")
        raiz = Path(tempfile.mkdtemp(prefix="mensajeria-tests-")).resolve()
        sesion = {"raiz": str(raiz), "sesion": secrets.token_hex(32), "principal": os.getpid()}
        _escribir_nuevo(raiz / ".sesion-pruebas.json", sesion)
        (raiz / ".permisos").mkdir()
        url = "sqlite:///:memory:"

    _RAIZ, _SESION = raiz, sesion
    sys.addaudithook(_auditar)
    os.environ.update({
        "DATABASE_URL": url,
        "APP_ENV": "test", "FLASK_ENV": "test", "RENDER": "false",
        "FLASK_DEBUG": "0", "SECRET_KEY": "solo-pruebas-aisladas",
        "LOGIN_REQUIRED": "1", "SESSION_TIMEOUT_MINUTES": "30",
        "EMAIL_PROVIDER": "disabled", "CORREO_EMISOR": "local@demo.invalid",
        "CORREO_DESTINO_STARKEN": "starken@demo.invalid",
        "CORREO_RESPALDO_MENSAJERIA": "respaldo@demo.invalid",
        "CORREO_CLAVE_APP": "LOCAL_DISABLED", "BREVO_API_KEY": "LOCAL_DISABLED",
        "BREVO_SMTP_LOGIN": "LOCAL_DISABLED", "BREVO_SMTP_PASSWORD": "LOCAL_DISABLED",
        "BREVO_API_URL": "http://127.0.0.1:0/disabled",
        "BREVO_SMTP_HOST": "127.0.0.1", "BREVO_SMTP_PORT": "0",
        "OF_IMAP_HOST": "127.0.0.1", "OF_IMAP_PORT": "0",
        "OF_CORREO_FILTRO_REMITENTE": "LOCAL_DISABLED",
        "OF_CORREO_FILTRO_TEXTO": "LOCAL_DISABLED",
        "CLAVE_ELIMINACION_HISTORICO": "solo-ficticio",
        "LOGS_DIR": str(raiz / "logs"), "RESPALDOS_LOTES_DIR": str(raiz / "respaldos"),
        "MENSAJERIA_TEST_ROOT": str(raiz), "MENSAJERIA_TEST_RUN": sesion["sesion"],
        "TMP": str(raiz), "TEMP": str(raiz),
    })
    tempfile.tempdir = str(raiz)
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    event.listen(Engine, "do_connect", _antes_de_conectar)

    guardia = raiz / "bootstrap"
    if not heredada:
        guardia.mkdir()
        (guardia / "sitecustomize.py").write_text(
            "import os\ntry:\n"
            "    from tests.entorno_aislado import preparar_entorno_pruebas\n"
            "    preparar_entorno_pruebas()\n"
            "except BaseException:\n    os._exit(79)\n",
            encoding="utf-8",
        )
    proyecto = Path(__file__).resolve().parent.parent
    os.environ["PYTHONPATH"] = os.pathsep.join((str(guardia), str(proyecto)))
    _LISTO = True
    return raiz


@contextmanager
def entorno_subproceso_autorizado(env=None):
    """Emite un permiso efímero de un uso para un hijo Python inmediato.

    Vincula padre real, sesión, raíz y URL exacta. No es una frontera de seguridad
    contra código hostil del mismo usuario capaz de modificar memoria/archivos.
    """
    raiz = preparar_entorno_pruebas()
    datos = os.environ.copy() if env is None else dict(env)
    if (datos.get("MENSAJERIA_TEST_ROOT") != str(raiz)
            or datos.get("MENSAJERIA_TEST_RUN") != _SESION["sesion"]
            or datos.get("MENSAJERIA_TEST_AUTORIZACION")):
        raise DestinoPruebasInvalido("El hijo debe pertenecer a la sesión actual.")
    if _leer_json(raiz / ".sesion-pruebas.json") != _SESION:
        raise DestinoPruebasInvalido("La identidad de la sesión fue alterada.")
    url = datos.get("DATABASE_URL", "")
    validar_destino_pruebas(url, raiz)
    token = secrets.token_hex(32)
    ruta = raiz / ".permisos" / (token + ".json")
    _escribir_nuevo(ruta, {
        **_SESION, "padre": os.getpid(), "lanzador": str(Path(sys.executable).resolve()),
        "destino": url, "creado": time.time(),
    })
    datos["MENSAJERIA_TEST_AUTORIZACION"] = token
    # El lanzador fija el bootstrap; no permite omitirlo mediante el env recibido.
    datos["PYTHONPATH"] = os.environ["PYTHONPATH"]
    try:
        yield datos
    finally:
        try:
            ruta.unlink()
        except FileNotFoundError:
            pass


def ejecutar_python_aislado(argumentos, *, env=None, **opciones):
    """Usa siempre el intérprete activo del venv y autorización de un uso."""
    with entorno_subproceso_autorizado(env) as autorizado:
        return subprocess.run([sys.executable, *argumentos], env=autorizado, **opciones)
