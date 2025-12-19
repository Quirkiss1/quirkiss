from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

database_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/dronedelivery_db")
env_file_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_file_path):
    try:
        with open(env_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key == "DATABASE_URL":
                        database_url = value
                        break
    except Exception as e:
        print(f"Предупреждение: не удалось прочитать .env файл: {e}")

settings = type('Settings', (), {'database_url': database_url})()
try:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        connect_args={"connect_timeout": 5}
    )
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✅ Подключение к базе данных успешно")
except Exception as e:
    print(f"⚠️  Предупреждение: не удалось подключиться к базе данных: {e}")
    print("⚠️  Убедитесь, что:")
    print("   1. PostgreSQL запущен")
    print("   2. База данных создана: запустите ./create_db.sh")
    print("      или вручную: CREATE DATABASE dronedelivery_db;")
    print("   3. DATABASE_URL в backend/.env файле правильный")
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        connect_args={"connect_timeout": 5}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


