from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError("Falta configurar DATABASE_URL en el archivo .env")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)
