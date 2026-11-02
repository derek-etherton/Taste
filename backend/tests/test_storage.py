"""SqlProfileStore: ratings, Describe Me and shelf scans per user, and the accounts and sessions
behind them. On SQLite, or on Postgres with TASTE_TEST_DATABASE_URL set."""

import io
from datetime import timedelta

import pytest
from PIL import Image
from sqlalchemy import func, select, update

from conftest import make_store
from taste.model.shelf import Spine, Where
from taste.storage.db import Rating, Session, User, utcnow


@pytest.fixture
def store(tmp_path):
    return make_store(tmp_path)


@pytest.fixture
def me(store) -> str:
    return store.create_guest().id


def photo(width: int, height: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


def test_set_and_clear_ratings(store, me):
    assert store.set_rating(me, "film:1", 1) == {"film:1": 1}
    assert store.set_rating(me, "film:1", 0) == {"film:1": 0}
    assert store.set_rating(me, "book:2", -1) == {"film:1": 0, "book:2": -1}
    assert store.clear_rating(me, "film:1") == {"book:2": -1}
    assert store.clear_rating(me, "film:1") == {"book:2": -1}  # clearing twice is fine
    assert store.ratings(me) == {"book:2": -1}
    assert store.ratings(store.create_guest().id) == {}  # profiles don't share anything


def test_description_lives_alongside_ratings(store, me):
    assert store.description(me) is None
    store.set_rating(me, "film:1", 1)
    store.save_description(me, "You're a chaos gremlin.", {"film:1": 1})
    store.set_rating(me, "book:2", -1)  # rating later must not drop the description
    d = store.description(me)
    assert d.text == "You're a chaos gremlin." and d.ratings == {"film:1": 1} and d.created
    store.save_description(me, "You're a goth with a library card.", store.ratings(me))
    assert store.description(me).text == "You're a goth with a library card."  # replaced
    assert store.ratings(me) == {"film:1": 1, "book:2": -1}


def test_scan_persists_with_a_thumbnail(store, me):
    assert store.scan(me) is None and store.scan_image(me) is None
    store.set_rating(me, "book:1", 1)
    spines = [Spine("Dune", "Frank Herbert", Where(1, 3, 0.2)), Spine("Emma")]
    store.save_scan(me, "upload-1", "shelf.jpg", spines, photo(1600, 1200))
    scan = store.scan(me)
    assert scan.id == "upload-1" and scan.photo_name == "shelf.jpg" and scan.scanned
    assert scan.spines == spines and scan.spines[0].where == Where(1, 3, 0.2) and scan.spines[1].where is None
    assert max(Image.open(io.BytesIO(store.scan_image(me))).size) == 800  # thumbnail, not the full photo
    assert store.ratings(me) == {"book:1": 1}  # the rest of the profile is untouched
    store.save_scan(me, "upload-2", "other.jpg", [Spine("Emma")], photo(400, 300))
    assert store.scan(me).id == "upload-2"  # replaced, not appended


# --- accounts and sessions --------------------------------------------------------------------

def test_guest_becomes_member_keeping_everything(store, me):
    store.set_rating(me, "book:1", 1)
    store.save_scan(me, "s1", "shelf.jpg", [Spine("Emma")], photo(100, 100))
    member = store.sign_in("apple", "apple-123", "a@example.com", "Ann", guest=me)
    assert member.id == me and member.kind == "member" and member.email == "a@example.com"
    assert store.ratings(me) == {"book:1": 1} and store.scan(me).id == "s1"
    assert store.sign_in("apple", "apple-123", None, None).id == me  # the same Apple account, next time


def test_guest_merges_into_existing_account(store):
    member = store.sign_in("google", "g-1", "b@example.com", "Bo")
    store.set_rating(member.id, "book:1", 1)
    guest = store.create_guest().id
    store.set_rating(guest, "book:1", -1)  # conflicts: the account's own rating wins
    store.set_rating(guest, "book:2", 1)  # new: carried over
    store.save_scan(guest, "s1", "shelf.jpg", [Spine("Emma")], photo(100, 100))
    assert store.sign_in("google", "g-1", None, None, guest=guest).id == member.id
    assert store.ratings(member.id) == {"book:1": 1, "book:2": 1}
    assert store.scan(member.id).id == "s1"  # the account had none
    assert store.get_account(guest) is None  # the guest is gone


def test_a_member_is_never_merged_away(store):
    a = store.sign_in("google", "g-1", None, None)
    b = store.sign_in("apple", "a-1", None, None, guest=a.id)  # a's session signing into b's identity
    assert b.id != a.id and store.get_account(a.id) is not None


def test_sessions(store, me):
    token = store.new_session(me)
    assert store.session_user(token) == me
    assert store.session_user(token + "x") is None and store.session_user("") is None
    with store.db.begin() as s:  # only a hash is stored, never the token
        assert s.scalar(select(func.count()).where(Session.token_hash == token)) == 0
    other = store.new_session(me)
    store.end_session(token)
    assert store.session_user(token) is None and store.session_user(other) == me
    third = store.new_session(me)
    store.end_session(other, everywhere=True)
    assert store.session_user(third) is None


def test_idle_sessions_expire(store, me):
    token = store.new_session(me)
    with store.db.begin() as s:
        s.execute(update(Session).values(last_used_at=utcnow() - timedelta(days=91)))
    assert store.session_user(token) is None


def test_delete_account_removes_everything(store, me):
    store.set_rating(me, "book:1", 1)
    token = store.new_session(me)
    store.sign_in("dev", "x@example.com", "x@example.com", None, guest=me)
    store.delete_account(me)
    assert store.get_account(me) is None and store.session_user(token) is None
    with store.db.begin() as s:
        assert s.scalar(select(func.count()).select_from(Rating)) == 0
    assert store.sign_in("dev", "x@example.com", None, None).id != me  # the identity went too


def test_clean_up_removes_long_idle_guests(store, me):
    member = store.sign_in("dev", "m@example.com", None, None).id
    with store.db.begin() as s:
        s.execute(update(User).values(last_seen_at=utcnow() - timedelta(days=200)))
    assert store.clean_up() == 1
    assert store.get_account(me) is None and store.get_account(member) is not None
