"""
SQLAlchemy Engine & Session Management.
"""
import os
from typing import Generator
from sqlalchemy import create_engine, Engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from app.config import get_settings
from app.db.models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine(database_url: str | None = None) -> Engine:
    global _engine
    url = database_url or get_settings().database_url
    if url.startswith("sqlite:///"):
        db_path = url.replace("sqlite:///", "", 1)
        if db_path and db_path != ":memory:":
            parent = os.path.dirname(os.path.abspath(db_path))
            if parent:
                os.makedirs(parent, exist_ok=True)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    if database_url is not None or _engine is None:
        engine = create_engine(url, connect_args=connect_args, future=True)
        if database_url is None:
            _engine = engine
        return engine
    return _engine


def _migrate_schema(engine: Engine) -> None:
    """Add columns that were introduced after existing databases were created."""
    inspector = inspect(engine)
    for table_name in inspector.get_table_names():
        if table_name == "reader_sessions":
            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
            additions = {
                "anthropic_api_key": "VARCHAR(512)",
                "openai_api_key": "VARCHAR(512)",
                "gemini_api_key": "VARCHAR(512)",
                "openrouter_api_key": "VARCHAR(512)",
            }
            with engine.begin() as conn:
                for col_name, col_type in additions.items():
                    if col_name not in existing_cols:
                        conn.execute(
                            text(f'ALTER TABLE reader_sessions ADD COLUMN {col_name} {col_type}')
                        )
        elif table_name == "documents":
            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
            if "image_url" not in existing_cols:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN image_url VARCHAR(2048)"))


def init_db(engine: Engine | None = None) -> Engine:
    target_engine = engine or get_engine()
    Base.metadata.create_all(bind=target_engine)
    _migrate_schema(target_engine)
    return target_engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    global _SessionLocal
    if engine is not None:
        return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    SessionFactory = get_session_factory()
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()
