"""ProfileStore on the database (db.py), plus the accounts behind it: guests, members, their
sign-in identities and sessions.

A user is identified by an opaque id, never a name. A session token is 32 random bytes handed
to the device once; the database keeps only its sha256, so a leaked database or backup can't
sign anyone in.
"""

import hashlib
import io
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from taste.model.shelf import Spine, Where, load_image
from taste.storage.base import Description, ShelfScan
from taste.storage.db import DescriptionRow, Identity, Rating, ScanLog, Session, ShelfScanRow, User, connect, utcnow

SESSION_IDLE = timedelta(days=90)  # a session unused this long has expired
TOUCH_EVERY = timedelta(hours=1)  # how often a session's last use is written back
GUEST_IDLE = timedelta(days=180)  # guests unseen this long are deleted by clean_up()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def aware(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)  # SQLite hands back naive datetimes


@dataclass
class Account:
    id: str
    kind: str  # "guest" or "member"
    email: str | None
    name: str | None


def account(u: User) -> Account:
    return Account(u.id, u.kind, u.email, u.name)


class SqlProfileStore:
    def __init__(self, url_or_engine: str | Engine):
        self.engine = connect(url_or_engine) if isinstance(url_or_engine, str) else url_or_engine
        self.db = sessionmaker(self.engine, expire_on_commit=False)

    # --- ratings, Describe Me, shelf scan (the ProfileStore protocol) -----------------------

    def _upsert(self, table, values: dict):
        """Insert a row, or overwrite the one with the same primary key, in one statement: two
        requests writing the same row at once (two scans, a double tap) can't both try to insert."""
        dialect = postgresql if self.engine.dialect.name == "postgresql" else sqlite
        keys = [c.name for c in table.__table__.primary_key]
        insert = dialect.insert(table).values(**values)
        return insert.on_conflict_do_update(index_elements=keys,
                                            set_={k: v for k, v in values.items() if k not in keys})

    def ratings(self, user: str) -> dict[str, int]:
        with self.db() as s:
            return dict(s.execute(select(Rating.item_key, Rating.value).where(Rating.user_id == user)).all())

    def set_rating(self, user: str, key: str, value: int) -> dict[str, int]:
        with self.db.begin() as s:
            s.execute(self._upsert(Rating, dict(user_id=user, item_key=key, value=value, updated_at=utcnow())))
        return self.ratings(user)

    def clear_rating(self, user: str, key: str) -> dict[str, int]:
        with self.db.begin() as s:
            s.execute(delete(Rating).where(Rating.user_id == user, Rating.item_key == key))
        return self.ratings(user)

    def description(self, user: str) -> Description | None:
        with self.db() as s:
            row = s.get(DescriptionRow, user)
            return Description(row.text, dict(row.ratings), row.created) if row else None

    def save_description(self, user: str, text: str, ratings: dict[str, int]) -> Description:
        d = Description(text, dict(ratings), now_iso())
        with self.db.begin() as s:
            s.merge(DescriptionRow(user_id=user, text=d.text, ratings=d.ratings, created=d.created))
        return d

    def scan(self, user: str) -> ShelfScan | None:
        with self.db() as s:
            row = s.get(ShelfScanRow, user)
            if not row:
                return None
            spines = [Spine(x["title"], x.get("author"), Where(**x["where"]) if x.get("where") else None)
                      for x in row.spines]
            return ShelfScan(row.id, row.photo_name, row.scanned, spines)

    def save_scan(self, user: str, scan_id: str, photo_name: str, spines: list[Spine],
                  image: bytes) -> ShelfScan:
        thumb = load_image(image)
        thumb.thumbnail((800, 800))
        out = io.BytesIO()
        thumb.save(out, format="JPEG", quality=85)
        photo_name = photo_name[:255]  # the client names the file
        scan = ShelfScan(scan_id, photo_name, now_iso(), spines)
        stored = [{"title": x.title, "author": x.author, "where": asdict(x.where) if x.where else None} for x in spines]
        with self.db.begin() as s:
            s.execute(self._upsert(ShelfScanRow, dict(user_id=user, id=scan_id, photo_name=photo_name,
                                                      scanned=scan.scanned, spines=stored, image=out.getvalue())))
        return scan

    def log_scan(self, user: str) -> None:
        """Note that the user started a scan (for the hourly limit)."""
        with self.db.begin() as s:
            s.add(ScanLog(user_id=user))

    def scans_since(self, user: str, since: datetime) -> list[datetime]:
        """When the user started scans since `since`, oldest first."""
        with self.db() as s:
            rows = s.scalars(select(ScanLog.created_at).where(ScanLog.user_id == user, ScanLog.created_at >= since)
                             .order_by(ScanLog.created_at))
            return [aware(t) for t in rows]

    def scan_image(self, user: str) -> bytes | None:
        with self.db() as s:
            return s.scalar(select(ShelfScanRow.image).where(ShelfScanRow.user_id == user))

    # --- accounts ---------------------------------------------------------------------------

    def create_guest(self) -> Account:
        with self.db.begin() as s:
            u = User(kind="guest")
            s.add(u)
            s.flush()
            return account(u)

    def get_account(self, user: str) -> Account | None:
        with self.db() as s:
            u = s.get(User, user)
            return account(u) if u else None

    def sign_in(self, provider: str, subject: str, email: str | None, name: str | None,
                guest: str | None = None) -> Account:
        """The member for this Apple/Google identity, creating it if new. With a guest's id
        (from the session the request came with): a new identity turns that guest into the
        member, keeping its data; an identity that already has an account takes the guest's
        ratings it doesn't have yet (its own win), the guest's shelf scan if it has none, and
        the guest is deleted."""
        with self.db.begin() as s:
            ident = s.get(Identity, (provider, subject))
            g = s.get(User, guest) if guest else None
            g = g if g and g.kind == "guest" else None
            if ident is None:
                u = g or User(kind="member")
                u.kind = "member"
                u.email, u.name = email or u.email, name or u.name
                s.add(u)
                s.flush()
                s.add(Identity(provider=provider, subject=subject, user_id=u.id, email=email))
                return account(u)
            u = s.get(User, ident.user_id)
            if email and not u.email:
                u.email = email
            if name and not u.name:
                u.name = name
            if g and g.id != u.id:
                mine = set(s.scalars(select(Rating.item_key).where(Rating.user_id == u.id)))
                for r in s.scalars(select(Rating).where(Rating.user_id == g.id)):
                    if r.item_key not in mine:
                        s.add(Rating(user_id=u.id, item_key=r.item_key, value=r.value))
                if s.get(ShelfScanRow, u.id) is None:
                    s.execute(update(ShelfScanRow).where(ShelfScanRow.user_id == g.id).values(user_id=u.id))
                s.flush()
                s.delete(g)
            return account(u)

    def delete_account(self, user: str) -> None:
        """The user and everything they own (ratings, scan, identities, sessions)."""
        with self.db.begin() as s:
            s.execute(delete(User).where(User.id == user))

    # --- sessions ---------------------------------------------------------------------------

    def new_session(self, user: str) -> str:
        """A fresh session token for the user. Returned once; only its hash is kept."""
        token = secrets.token_urlsafe(32)
        with self.db.begin() as s:
            s.add(Session(token_hash=hash_token(token), user_id=user))
        return token

    def session_user(self, token: str) -> str | None:
        """The user a token signs in, or None if it's unknown or expired. Each use extends the
        session (written back at most hourly)."""
        h = hash_token(token)
        with self.db.begin() as s:
            row = s.get(Session, h)
            if row is None:
                return None
            now = utcnow()
            if now - aware(row.last_used_at) > SESSION_IDLE:
                s.delete(row)
                return None
            if now - aware(row.last_used_at) > TOUCH_EVERY:
                row.last_used_at = now
                s.execute(update(User).where(User.id == row.user_id).values(last_seen_at=now))
            return row.user_id

    def end_session(self, token: str, everywhere: bool = False) -> None:
        with self.db.begin() as s:
            row = s.get(Session, hash_token(token))
            if row is None:
                return
            if everywhere:
                s.execute(delete(Session).where(Session.user_id == row.user_id))
            else:
                s.delete(row)

    def clean_up(self) -> int:
        """Delete guests unseen for GUEST_IDLE and sessions idle past SESSION_IDLE; returns the
        number of guests removed. Run it daily (scripts/clean_up.py)."""
        now = utcnow()
        with self.db.begin() as s:
            s.execute(delete(Session).where(Session.last_used_at < now - SESSION_IDLE))
            s.execute(delete(ScanLog).where(ScanLog.created_at < now - timedelta(days=1)))
            return s.execute(delete(User).where(User.kind == "guest", User.last_seen_at < now - GUEST_IDLE)).rowcount
