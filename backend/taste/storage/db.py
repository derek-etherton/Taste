"""The database schema: users (guests and members), their sign-in identities and sessions, and
each user's ratings, latest shelf scan and Describe Me. Postgres in development and production
(TASTE_DATABASE_URL); tests may use a SQLite file. Changes go through Alembic (backend/migrations).

Everything a user owns is deleted with them (ON DELETE CASCADE): deleting an account is one
statement.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, LargeBinary, SmallInteger, String, Text, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


def owner() -> Mapped[str]:
    """A column holding the owning user's id; the row goes when the user does."""
    return mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind: Mapped[str] = mapped_column(String(10))  # "guest" or "member"
    email: Mapped[str | None] = mapped_column(String(320))
    name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)  # guest clean-up


class Identity(Base):
    """A way to sign in as a member: an Apple or Google account (or "dev", locally)."""
    __tablename__ = "identities"
    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), primary_key=True)  # the provider's stable user id
    user_id: Mapped[str] = owner()
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Session(Base):
    """A signed-in device. Only the token's sha256 is stored, so the table can't sign anyone in."""
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = owner()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Rating(Base):
    __tablename__ = "ratings"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    item_key: Mapped[str] = mapped_column(String(64), primary_key=True)  # "<domain>:<id>"
    value: Mapped[int] = mapped_column(SmallInteger)  # +1 like, 0 meh, -1 dislike
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ShelfScanRow(Base):
    """A user's last shelf scan: the spine readings and an 800px JPEG of the photo."""
    __tablename__ = "shelf_scans"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    id: Mapped[str] = mapped_column(String(32))
    photo_name: Mapped[str] = mapped_column(String(255))
    scanned: Mapped[str] = mapped_column(String(32))  # ISO timestamp
    spines: Mapped[list] = mapped_column(JSONType)
    image: Mapped[bytes] = mapped_column(LargeBinary)


class DescriptionRow(Base):
    """The latest Describe Me reading (not in the app for now)."""
    __tablename__ = "descriptions"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    ratings: Mapped[dict] = mapped_column(JSONType)
    created: Mapped[str] = mapped_column(String(32))


def connect(url: str) -> Engine:
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":  # SQLite only enforces foreign keys (and cascades) when asked
        event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    return engine
