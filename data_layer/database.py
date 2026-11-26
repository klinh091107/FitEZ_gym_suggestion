"""Database access for user accounts, profiles and saved plans (SQLAlchemy).

DATABASE_URL chooses the database:
  empty                  -> SQLite file fitez.db in the project root (local development)
  sqlite:///some/file.db -> SQLite file (a relative path is relative to the project root)
  postgresql://...       -> PostgreSQL (cloud)

Tables are defined in user_data.py. Profile and plan queries always filter by user_id.
"""

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from .user_data import Base, Plan, Profile, User, utc_now

BASE_DIR = Path(__file__).resolve().parents[1]

# Catch this to handle errors from either database.
DatabaseError = (SQLAlchemyError,)


class DuplicateAccountError(Exception):
    """The username or email is already registered."""


def database_url():
    return os.environ.get("DATABASE_URL", "").strip() or "sqlite:///fitez.db"


def make_engine(url):
    if url.startswith(("postgres://", "postgresql://")):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    elif url.startswith("sqlite:///"):
        path = Path(url.removeprefix("sqlite:///"))
        if not path.is_absolute():
            path = BASE_DIR / path
        url = "sqlite:///" + str(path)
    else:
        raise RuntimeError("DATABASE_URL must start with sqlite:/// or postgresql://")

    is_sqlite = url.startswith("sqlite:")
    engine = create_engine(
        url, pool_pre_ping=True,
        connect_args={"check_same_thread": False, "timeout": 15} if is_sqlite
        else {"connect_timeout": 5},
    )
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


# One engine per URL, so changing DATABASE_URL (the tests do) switches database.
_engines = {}


def get_engine():
    url = database_url()
    if url not in _engines:
        _engines[url] = make_engine(url)
    return _engines[url]


@contextmanager
def session_scope():
    """Open a session, commit on success (roll back on error), then close it."""
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def create_tables():
    """Create any missing tables. Existing tables and data are kept."""
    Base.metadata.create_all(get_engine())


_tables_ready = set()


def ensure_tables():
    """Create the tables once per database. SQLite needs this for a fresh local file."""
    url = database_url()
    if url not in _tables_ready:
        create_tables()
        _tables_ready.add(url)


def create_user(username, email, password_hash):
    """Insert a user and return the new id."""
    ensure_tables()
    try:
        with session_scope() as session:
            user = User(username=username, email=email, password_hash=password_hash)
            session.add(user)
            session.flush()
            return user.id
    except IntegrityError as error:
        raise DuplicateAccountError() from error


def find_user_by_login(login):
    """Find a user by username or email (both are stored in lower case)."""
    ensure_tables()
    with session_scope() as session:
        user = session.scalars(
            select(User).where((User.username == login) | (User.email == login))
        ).first()
        return None if user is None else {
            "id": user.id, "username": user.username, "password_hash": user.password_hash
        }


def find_user_by_id(user_id):
    ensure_tables()
    with session_scope() as session:
        user = session.get(User, user_id)
        return None if user is None else {
            "id": user.id, "username": user.username, "email": user.email
        }


def get_profile(user_id):
    """Return the user's saved profile dictionary, or None."""
    ensure_tables()
    with session_scope() as session:
        profile = session.get(Profile, user_id)
        return None if profile is None else profile.data


def save_profile(user_id, profile):
    """Create or replace the profile. The old plan no longer matches, so delete it."""
    ensure_tables()
    with session_scope() as session:
        row = session.get(Profile, user_id)
        if row is None:
            session.add(Profile(user_id=user_id, data=profile))
        else:
            row.data = profile
        session.execute(delete(Plan).where(Plan.user_id == user_id))


def get_plan(user_id):
    """Return the user's latest saved plan, or None."""
    ensure_tables()
    with session_scope() as session:
        plan = session.get(Plan, user_id)
        return None if plan is None else plan.data


def save_plan(user_id, plan):
    """Keep only the latest plan for each user."""
    ensure_tables()
    with session_scope() as session:
        row = session.get(Plan, user_id)
        if row is None:
            session.add(Plan(user_id=user_id, data=plan))
        else:
            row.data = plan
            row.created_at = utc_now()


if __name__ == "__main__":
    # One-time cloud setup: python -m data_layer.database
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
    create_tables()
    print("Tables are ready (" + get_engine().dialect.name + ").")
