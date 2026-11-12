"""
SQLAlchemy Engine & Session Management.
"""
import os
from typing import Dict, Generator
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
    """Add columns that were introduced after existing databases were created.

    Each ALTER TABLE is concurrency-safe: if it fails (e.g., another startup
    process added the column first), the table is re-inspected and the error is
    suppressed only when the column now exists.
    """
    inspector = inspect(engine)
    plans: Dict[str, Dict[str, str]] = {
        "reader_sessions": {
            "anthropic_api_key": "VARCHAR(512)",
            "openai_api_key": "VARCHAR(512)",
            "gemini_api_key": "VARCHAR(512)",
            "openrouter_api_key": "VARCHAR(512)",
        },
        "documents": {
            "image_url": "VARCHAR(2048)",
            "paywall_detected": "BOOLEAN NOT NULL DEFAULT 0",
        },
    }
    for table_name, additions in plans.items():
        if table_name not in inspector.get_table_names():
            continue
        existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
        for col_name, col_type in additions.items():
            if col_name in existing_cols:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                    )
            except Exception:
                # Another startup may have added the column concurrently; only
                # suppress when a fresh inspection confirms it now exists.
                fresh = {c["name"] for c in inspect(engine).get_columns(table_name)}
                if col_name not in fresh:
                    raise


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
