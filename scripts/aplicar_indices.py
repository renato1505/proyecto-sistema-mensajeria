import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from database.conexion import engine


INDICES = [
    "CREATE INDEX IF NOT EXISTS ix_remitentes_r_nombre ON remitentes (r_nombre)",
    "CREATE INDEX IF NOT EXISTS ix_remitentes_r_correo ON remitentes (r_correo)",
    "CREATE INDEX IF NOT EXISTS ix_destinatarios_d_nombre ON destinatarios (d_nombre)",
    "CREATE INDEX IF NOT EXISTS ix_comunas_c_nombre ON comunas (c_nombre)",
    "CREATE INDEX IF NOT EXISTS ix_envios_e_estado ON envios (e_estado)",
    "CREATE INDEX IF NOT EXISTS ix_envios_e_orden_flete ON envios (e_orden_flete)",
    "CREATE INDEX IF NOT EXISTS ix_envios_e_lote ON envios (e_lote)",
    "CREATE INDEX IF NOT EXISTS ix_envios_e_fecha_creacion ON envios (e_fecha_creacion)",
]


def ejecutar():
    with engine.begin() as conn:
        for sql in INDICES:
            conn.execute(text(sql))

    print("Indices aplicados correctamente.")


if __name__ == "__main__":
    ejecutar()
