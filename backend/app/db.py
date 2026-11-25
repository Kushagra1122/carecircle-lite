import os
import time
from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://carecircle:carecircle@localhost:5432/carecircle",
)


class UtcDateTime(TypeDecorator):
    """Store instants as UTC.

    SQLite drops timezone offsets, so values are written as UTC and read back
    as UTC. Postgres keeps them as timestamptz. Callers can pass either.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if url in {"sqlite://", "sqlite:///:memory:"}:
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True)


engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    attempts = 1 if os.getenv("TESTING") else 30
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            Base.metadata.create_all(bind=engine)
            last_error = None
            break
        except Exception as exc:  # database may still be starting
            last_error = exc
            time.sleep(0.5)
    if last_error is not None:
        raise last_error
    if os.getenv("TESTING"):
        return
    from app.seed import seed_if_empty

    with SessionLocal() as db:
        seed_if_empty(db)
