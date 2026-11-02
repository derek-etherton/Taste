"""Accounts over HTTP: guests, Apple and Google sign-in (their token checks stubbed), sessions as
bearer tokens or cookies, sign-out, account deletion, rate limits, signed photo links."""

import pytest
from fastapi.testclient import TestClient

from conftest import find, make_store
from taste.api import auth
from taste.api.app import create_app
from taste.api.engine import Engine
from taste.settings import get_settings


@pytest.fixture(scope="module")
def engine(tmp_path_factory, cats):  # cats: skips the module if the data isn't prepared
    return Engine(store=make_store(tmp_path_factory.mktemp("db")), genome={"book": "default"})


@pytest.fixture
def app(engine):
    return create_app(engine, auth_per_minute=1000)


@pytest.fixture(autouse=True)
def providers(monkeypatch):
    """Apple and Google vouch for whoever the token names: "apple:<sub>" or "google:<sub>"."""
    monkeypatch.setattr(auth, "verify_apple", lambda t: (t.split(":")[1], f"{t.split(':')[1]}@icloud.com"))
    monkeypatch.setattr(auth, "verify_google", lambda t: (t.split(":")[1], f"{t.split(':')[1]}@gmail.com", "G"))
    monkeypatch.setattr(get_settings(), "dev_login", False)


def bearer(client, token):
    client.headers["Authorization"] = f"Bearer {token}"
    client.cookies.clear()


def test_everything_needs_a_session(app):
    c = TestClient(app)
    for path in ["/me", "/me/summary", "/me/book/items", "/me/profile", "/me/shelf-scan"]:
        assert c.get(path).status_code == 401, path
    bearer(c, "made-up-token")
    assert c.get("/me").status_code == 401
    assert c.get("/health").status_code == 200 and c.get("/domains").status_code == 200  # public


def test_guest_then_apple_keeps_ratings(app, cats):
    c = TestClient(app)
    guest = c.post("/auth/guest").json()
    assert guest["user"]["kind"] == "guest" and guest["user"]["email"] is None
    bearer(c, guest["token"])
    hobbit = find(cats["book"], "The Hobbit")
    c.put(f"/me/ratings/{hobbit}", json={"value": 1})

    member = c.post("/auth/apple", json={"identity_token": "apple:ann", "name": "Ann"}).json()
    assert member["user"] == {"id": guest["user"]["id"], "kind": "member", "email": "ann@icloud.com", "name": "Ann"}
    assert c.get("/me").status_code == 401  # the guest's session ended with the upgrade
    bearer(c, member["token"])
    assert hobbit in {x["key"] for x in c.get("/me/book/rated").json()}


def test_guest_signing_into_an_existing_account_merges(app, cats):
    hobbit, emma = find(cats["book"], "The Hobbit"), find(cats["book"], "Emma")
    phone = TestClient(app)
    bearer(phone, phone.post("/auth/google", json={"id_token": "google:bo"}).json()["token"])
    phone.put(f"/me/ratings/{hobbit}", json={"value": 1})
    account = phone.get("/me").json()["id"]

    laptop = TestClient(app)  # rated as a guest, then signs in to the same Google account
    bearer(laptop, laptop.post("/auth/guest").json()["token"])
    laptop.put(f"/me/ratings/{hobbit}", json={"value": -1})
    laptop.put(f"/me/ratings/{emma}", json={"value": 1})
    signed = laptop.post("/auth/google", json={"id_token": "google:bo"}).json()
    assert signed["user"]["id"] == account
    ratings = {x["key"]: x["rated"] for x in phone.get("/me/book/rated").json()}
    assert ratings == {hobbit: 1, emma: 1}  # the account's own rating won; the new one came over


def test_logout_and_sign_out_everywhere(app):
    c = TestClient(app)
    first = c.post("/auth/google", json={"id_token": "google:cy"}).json()["token"]
    second = c.post("/auth/google", json={"id_token": "google:cy"}).json()["token"]
    bearer(c, first)
    assert c.post("/auth/logout").status_code == 200 and c.get("/me").status_code == 401
    bearer(c, second)
    assert c.get("/me").status_code == 200
    third = c.post("/auth/google", json={"id_token": "google:cy"}).json()["token"]
    bearer(c, third)
    c.post("/auth/logout", params={"everywhere": True})
    bearer(c, second)
    assert c.get("/me").status_code == 401


def test_delete_account(app, engine, cats):
    c = TestClient(app)
    out = c.post("/auth/apple", json={"identity_token": "apple:dee"}).json()
    bearer(c, out["token"])
    c.put(f"/me/ratings/{find(cats['book'], 'Emma')}", json={"value": 1})
    assert c.delete("/me").status_code == 200
    assert c.get("/me").status_code == 401 and engine.store.get_account(out["user"]["id"]) is None
    again = c.post("/auth/apple", json={"identity_token": "apple:dee"}).json()  # starts over, empty
    assert again["user"]["id"] != out["user"]["id"]


def test_web_session_is_an_httponly_cookie(app):
    c = TestClient(app, base_url="https://testserver")  # Secure cookies need https
    r = c.post("/auth/guest")
    cookie = r.headers["set-cookie"]
    assert "taste_session=" in cookie and "HttpOnly" in cookie and "Secure" in cookie and "samesite=lax" in cookie.lower()
    assert c.get("/me").json()["kind"] == "guest"  # the cookie alone signs in
    c.post("/auth/logout")
    assert c.get("/me").status_code == 401


def test_dev_login_is_off_unless_enabled(app, monkeypatch):
    c = TestClient(app)
    assert c.post("/auth/dev", json={"email": "x@example.com"}).status_code == 404
    monkeypatch.setattr(get_settings(), "dev_login", True)
    assert c.post("/auth/dev", json={"email": "X@example.com"}).json()["user"]["email"] == "x@example.com"


def test_unconfigured_provider(app, monkeypatch):
    monkeypatch.undo()  # the real token checks
    monkeypatch.setattr(get_settings(), "apple_client_ids", [])
    assert TestClient(app).post("/auth/apple", json={"identity_token": "x"}).status_code == 503


def test_real_token_check_rejects_garbage(app, monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(get_settings(), "google_client_ids", ["client.apps.googleusercontent.com"])
    assert TestClient(app).post("/auth/google", json={"id_token": "not.a.jwt"}).status_code == 401


def test_sign_in_is_rate_limited(engine):
    c = TestClient(create_app(engine, auth_per_minute=2))
    assert [c.post("/auth/guest").status_code for _ in range(3)] == [200, 200, 429]


def test_photo_links_expire(app):
    c = TestClient(app)
    expired = auth.image_sig("someone", "scan", 1)
    assert c.get("/shelf-images/someone/scan", params={"expires": 1, "sig": expired}).status_code == 403
