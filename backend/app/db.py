from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_engine(settings.db_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def apply_schema():
    """Apply schema.sql idempotently at startup."""
    import pathlib

    schema_path = pathlib.Path(__file__).resolve().parent.parent / "design" / "schema.sql"
    if not schema_path.exists():
        print(f"[schema] not found at {schema_path}, skipping")
        return
    ddl = schema_path.read_text()
    with engine.begin() as conn:
        conn.execute(text(ddl))
    print(f"[schema] applied {schema_path.name}")


def ensure_extension():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))