import os

import pytest

from taste.model import Catalog, TraitSpace, available_domains

os.environ.setdefault("TASTE_ENV", "development")  # the API refuses to start otherwise without TASTE_SECRET


@pytest.fixture(scope="session")
def cats() -> dict[str, Catalog]:
    missing = {"film", "book"} - set(available_domains())
    if missing:
        pytest.skip(f"run scripts/prepare_data.py for: {', '.join(sorted(missing))}")
    return {d: Catalog.load(d) for d in ("film", "book")}


@pytest.fixture(scope="session")
def traits(cats) -> TraitSpace:
    return TraitSpace(cats)


def find(cat: Catalog, title: str) -> str:
    """Key of the most-rated item whose title is exactly `title` (or starts with "`title` (")."""
    t = cat.items["title"]
    hits = cat.items.index[(t == title) | t.str.startswith(title + " (")]
    assert len(hits), f"not found: {title}"
    return cat.key(int(min(hits, key=lambda i: cat.popularity_rank[i])))


def make_store(tmp_path):
    """A fresh, empty database: Postgres when TASTE_TEST_DATABASE_URL is set (its tables are
    dropped and recreated: point it at a throwaway database), else a SQLite file in tmp_path."""

    from taste.storage import SqlProfileStore
    from taste.storage.db import Base, connect

    url = os.environ.get("TASTE_TEST_DATABASE_URL") or f"sqlite:///{(tmp_path / 'taste.sqlite').as_posix()}"
    engine = connect(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return SqlProfileStore(engine)


def sign_in_as_guest(client):
    """Give the test client a new, empty guest profile; returns its user id."""
    client.headers["X-Taste-Client"] = "native"  # the native app gets its token to send as a bearer
    out = client.post("/auth/guest").json()
    client.headers["Authorization"] = f"Bearer {out['token']}"
    client.cookies.clear()  # the bearer header decides who this is
    return out["user"]["id"]
