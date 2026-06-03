import sys
from pathlib import Path

import pandas as pd
from database.conexion import SessionLocal
from database.modelos import Remitente

if "--confirmar" not in sys.argv:
    print("Este script borra y recarga todos los remitentes.")
    print("Ejecuta: python scripts/cargar_remitentes.py --confirmar")
    raise SystemExit(1)

project_dir = Path(__file__).resolve().parent.parent
archivo = project_dir / "Mensajeria.xlsx"
hoja = "EMP910 - GBL - Employment Info"

df = pd.read_excel(archivo, sheet_name=hoja)
db = SessionLocal()
db.query(Remitente).delete()

for _, fila in df.iterrows():
    nombre = f"{str(fila['First Name']).strip()} {str(fila['Last Name']).strip()}".strip()
    correo = str(fila['Email Address']).strip() if pd.notna(fila['Email Address']) else None
    division = str(fila['HR Division']).strip() if pd.notna(fila['HR Division']) else None
    centro_costo = str(fila['Cost Center ID']).strip() if pd.notna(fila['Cost Center ID']) else None

    nuevo_remitente = Remitente(
        r_nombre=nombre,
        r_correo=correo,
        r_division=division,
        r_centro_costo=centro_costo
    )

    db.add(nuevo_remitente)

db.commit()
db.close()

print("Remitentes cargados correctamente")
