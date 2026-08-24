import argparse
import getpass
import logging
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from sqlalchemy.engine import make_url  # noqa: E402

from config.settings import DATABASE_URL  # noqa: E402
from database.conexion import SessionLocal  # noqa: E402
from services.usuarios import cambiar_clave_propia, obtener_usuario_por_nombre  # noqa: E402


CODIGO_OK = 0
CODIGO_ERROR = 1
CODIGO_VALIDACION = 2
logger = logging.getLogger(__name__)


def nombre_destino(database_url):
    url = make_url(database_url)
    return f"{url.host or 'local'}/{url.database or ':memory:'}"


def descripcion_destino(database_url):
    url = make_url(database_url)
    host = url.host or "local"
    return f"{url.drivername}://{host}/{url.database or ':memory:'}"


def ejecutar_reset(usuario, clave_nueva, confirmar_clave, session_factory=SessionLocal):
    usuario = (usuario or "").strip().lower()
    if not usuario:
        return CODIGO_VALIDACION
    if clave_nueva != confirmar_clave:
        return CODIGO_VALIDACION
    if not clave_nueva or len(clave_nueva) < 6:
        return CODIGO_VALIDACION

    db = session_factory()
    try:
        usuario_db = obtener_usuario_por_nombre(db, usuario)
        if not usuario_db:
            db.rollback()
            return CODIGO_VALIDACION

        cambiar_clave_propia(usuario_db, clave_nueva)
        db.commit()
        return CODIGO_OK
    except Exception:
        db.rollback()
        logger.exception("No se pudo completar el reset administrativo de clave.")
        return CODIGO_ERROR
    finally:
        db.close()


def construir_parser():
    parser = argparse.ArgumentParser(description="Restablece la clave de un usuario existente.")
    parser.add_argument("--usuario", help="Nombre del usuario en usuarios_sistema.")
    parser.add_argument(
        "--confirmar-destino",
        help="Destino exacto host/base mostrado por el script.",
    )
    return parser


def main(argv=None):
    args = construir_parser().parse_args(argv)
    usuario = (args.usuario or input("Usuario: ")).strip().lower()
    destino = nombre_destino(DATABASE_URL)

    print(f"Destino de base de datos: {descripcion_destino(DATABASE_URL)}")
    confirmacion_destino = args.confirmar_destino or input(f"Escribe '{destino}' para confirmar el destino: ").strip()
    if confirmacion_destino != destino:
        print("Destino no confirmado. No se realizaron cambios.", file=sys.stderr)
        return CODIGO_VALIDACION

    clave_nueva = getpass.getpass("Nueva contrasena: ")
    confirmar_clave = getpass.getpass("Confirmar nueva contrasena: ")
    codigo = ejecutar_reset(usuario, clave_nueva, confirmar_clave)

    if codigo == CODIGO_OK:
        print("Contrasena actualizada correctamente.")
    elif codigo == CODIGO_VALIDACION:
        print("No se actualizo la contrasena. Revisa usuario, confirmacion y longitud minima.", file=sys.stderr)
    else:
        print("No se pudo actualizar la contrasena. Revisa los logs tecnicos.", file=sys.stderr)
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
