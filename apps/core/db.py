"""
Database session management and utilities.
Uses SQLModel (SQLAlchemy + Pydantic) for type-safe ORM.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlmodel import SQLModel, Session, create_engine as sqlmodel_create_engine

from apps.core.config import get_settings
import apps.core.models  # noqa: F401 - Import to register models with SQLModel


# Engine instance (created lazily)
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
            echo=False,
        )
    return _engine


def get_session_factory():
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        from sqlmodel import Session as SQLModelSession
        _SessionLocal = lambda: SQLModelSession(get_engine())
    return _SessionLocal


def init_db():
    """Initialize the database schema.

    In production, use migrations (infra/migrations/*.sql).
    For development, this creates tables based on SQLModel metadata.
    """
    # Models are imported at module level
    SQLModel.metadata.create_all(get_engine())


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a database session with automatic cleanup.

    Usage:
        with get_session() as session:
            results = session.exec(select(App)).all()
    """
    SessionFactory = get_session_factory()
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
