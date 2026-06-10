from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError("Falta configurar DATABASE_URL en el archivo .env")

database_url = DATABASE_URL
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine)
