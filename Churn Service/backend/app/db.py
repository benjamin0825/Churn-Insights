"""Database engine and session handling (SQLite)."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal: sessionmaker | None = None


def init_engine(url: str | None = None):
    """(Re)create the engine; tests call this with a temporary database."""
    global _engine, _SessionLocal
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(url or settings.database_url, connect_args={"check_same_thread": False})

    @event.listens_for(_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")  # readers don't block the job worker's writes
        cursor.close()

    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(_engine)
    _add_missing_columns(_engine)
    _seed_plans()
    return _engine


# Columns added after the first release. create_all() never alters existing tables, so add them here.
_NEW_COLUMNS = {
    "organizations": {"plan": "VARCHAR(40) NOT NULL DEFAULT 'starter'", "status": "VARCHAR(20) NOT NULL DEFAULT 'active'"},
    "users": {"is_admin": "BOOLEAN NOT NULL DEFAULT 0", "is_active": "BOOLEAN NOT NULL DEFAULT 1"},
}


def _add_missing_columns(engine) -> None:
    existing = inspect(engine)
    with engine.begin() as conn:
        for table, columns in _NEW_COLUMNS.items():
            have = {c["name"] for c in existing.get_columns(table)}
            for name, ddl in columns.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


DEFAULT_PLANS = [
    {"key": "starter", "name": "Starter", "monthly_price": 0, "sort_order": 1,
     "blurb": "Ideal for trying the product with demo data or forecasting churn for a small customer base.",
     "limits": ["Up to 1,000 customers", "Quick model training"],
     "features": ["Subscription metrics dashboard", "8-week churn forecast", "Reasons for every prediction",
                  "Customer risk list", "CSV upload templates"]},
    {"key": "growth", "name": "Growth", "monthly_price": 99, "sort_order": 2, "popular": True,
     "blurb": "Ideal for teams running retention campaigns every month and tracking how they pay off.",
     "limits": ["Up to 25,000 customers", "Standard and thorough training"],
     "features": ["Retention campaign planner", "Profit curve and ROI", "CSV export of target lists",
                  "Saved campaigns", "Drift monitoring", "Model comparison"]},
    {"key": "scale", "name": "Scale", "monthly_price": 299, "sort_order": 3,
     "blurb": "Ideal for larger customer bases that need full control over models and monitoring.",
     "limits": ["Unlimited customers", "All training modes"],
     "features": ["Model registry with rollback", "Drift checks per region", "API access", "Priority support"]},
]


def _seed_plans() -> None:
    from .models import Plan

    with _SessionLocal() as db:
        if db.query(Plan).count() == 0:
            db.add_all(Plan(**p) for p in DEFAULT_PLANS)
            db.commit()


def session_factory() -> sessionmaker:
    if _SessionLocal is None:
        init_engine()
    return _SessionLocal


def get_db() -> Iterator[Session]:
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()
