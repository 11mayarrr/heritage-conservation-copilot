from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal: sessionmaker | None = None


def init_engine(url: str | None = None):
    global _engine, _SessionLocal
    url = url or get_settings().database_url
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        db_path = url.replace("sqlite:///", "")
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(url, pool_pre_ping=True, **kwargs)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    from app.database import models  # noqa: F401  (register tables)

    Base.metadata.create_all(_engine)
    _add_missing_columns(_engine)
    return _engine


def _add_missing_columns(engine) -> None:
    """create_all() never alters existing tables. Add columns introduced after a
    database was first created, so older local databases keep working."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "walls" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("walls")}
        if "grid" not in cols:
            col_type = "JSONB" if engine.dialect.name == "postgresql" else "JSON"
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE walls ADD COLUMN grid {col_type}"))


def get_db() -> Iterator[Session]:
    if _SessionLocal is None:
        init_engine()
    assert _SessionLocal is not None
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
