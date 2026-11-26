"""Database tables. This file is the only schema, for both SQLite and PostgreSQL."""

from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Plain JSON on SQLite, JSONB on PostgreSQL. Reads return a dictionary on both.
JsonData = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Usernames and emails are always stored in lower case (see auth.clean_login).
        CheckConstraint("username = lower(username)"),
        CheckConstraint("email = lower(email)"),
        {"sqlite_autoincrement": True},  # ids are never reused
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)  # never the plain password
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Profile(Base):
    """One training profile per user (body details, goals, equipment, preferences)."""
    __tablename__ = "profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[dict] = mapped_column(JsonData)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Plan(Base):
    """The latest generated plan per user (today's picks and the weekly schedule)."""
    __tablename__ = "plans"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[dict] = mapped_column(JsonData)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
