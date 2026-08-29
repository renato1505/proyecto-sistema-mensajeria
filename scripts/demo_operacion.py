import argparse
import os
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from config.settings import DATABASE_URL  # noqa: E402
from database.conexion import SessionLocal  # noqa: E402
from services.demo_starken import (  # noqa: E402
    ESCENARIOS_OF_DEMO,
    ejecutar_escenario_demo,
    raiz_demo_permitida,
)


def main():
    parser = argparse.ArgumentParser(description="Ejecuta un escenario Starken exclusivamente demo")
    parser.add_argument("--cantidad", type=int, default=10)
    parser.add_argument("--escenario", choices=sorted(ESCENARIOS_OF_DEMO), default="TODOS_OK")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        resultado = ejecutar_escenario_demo(
            db,
            DATABASE_URL,
            os.getenv("APP_ENV"),
            os.getenv("RENDER"),
            args.cantidad,
            args.escenario,
            raiz_demo_permitida(),
        )
    finally:
        db.close()
    print(f"Lote demo: {resultado['lote']['lote']}")
    print(f"CSV: {resultado['lote']['ruta_csv']}")
    print(f"OF: {resultado['of']['ruta_of']}")
    print(f"Resultado: OK={resultado['of']['total_ok']} ERROR={resultado['of']['total_error']}")


if __name__ == "__main__":
    main()
