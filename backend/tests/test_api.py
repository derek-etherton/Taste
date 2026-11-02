"""The HTTP API, end to end in-process: a temporary profile store and a stand-in vision model."""

import io
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from conftest import find, make_store, sign_in_as_guest
from taste.api.app import create_app
from taste.api.engine import Engine
from taste.model.llm import LLMError
from taste.model.shelf import Spine, Where

SHELF = [Spine("The Hobbit", "Tolkien", Where(0, 2, 0.2)), Spine("Pride and Prejudice", None, Where(1, 2, 0.8)),
         Spine("A Book Nobody Has Heard Of", "Jo Bloggs", Where(1, 2, 0.5))]


def reader(image):
    return SHELF


@pytest.fixture(scope="module")
def engine(tmp_path_factory, cats):  # cats: skips the module if the data isn't prepared
    return Engine(store=make_store(tmp_path_factory.mktemp("db")), reader=reader,
                  domains=["film", "book"],  # the app serves books only, but the film code stays tested
                  genome={"film": "default", "book": "default"})  # whatever TASTE_*_GENOME says


@pytest.fixture
def client(engine):
    c = TestClient(create_app(engine, auth_per_minute=1000))
    sign_in_as_guest(c)  # every test starts with a new, empty profile
    return c


def photo() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (1200, 900), "white").save(out, format="JPEG")
    return out.getvalue()


def scan(client, data=None, name="shelf.jpg"):
    return client.post("/me/shelf-scans", files={"photo": (name, photo() if data is None else data, "image/jpeg")})


def test_basics(client):
    assert client.get("/health").json() == {"ok": True}
    assert {d["id"] for d in client.get("/domains").json()} == {"film", "book"}
    assert [d["rated"] for d in client.get("/me/summary").json()] == [0, 0]


def test_bad_inputs(client, cats):
    assert client.get("/me/music/items").status_code == 404
    assert client.put("/me/ratings/book:0", json={"value": 1}).status_code == 404
    key = find(cats["book"], "The Hobbit")
    assert client.put(f"/me/ratings/{key}", json={"value": 2}).status_code == 422


def test_rating_changes_recommendations(client, cats):
    book = cats["book"]
    before = [c["key"] for c in client.get("/me/book/items", params={"page_size": 10}).json()["items"]]
    for t in ["The Hobbit", "A Game of Thrones", "The Name of the Wind"]:
        assert client.put(f"/me/ratings/{find(book, t)}", json={"value": 1}).status_code == 200
    page = client.get("/me/book/items", params={"page_size": 10}).json()
    after = [c["key"] for c in page["items"]]
    assert after != before and page["total"] > 1000 and page["page_size"] == 10
    assert not {find(book, t) for t in ["The Hobbit", "A Game of Thrones"]} & set(after)  # rated ones excluded
    assert all(c["because"] for c in page["items"])
    rated = client.get("/me/book/rated").json()
    assert len(rated) == 3 and all(c["rated"] == 1 for c in rated)
    ratings = client.delete(f"/me/ratings/{find(book, 'The Hobbit')}").json()["ratings"]
    assert len(ratings) == 2


def test_search_rate_mode_and_paging(client):
    found = client.get("/me/book/items", params={"q": "hobbit"}).json()
    assert any(c["title"] == "The Hobbit" for c in found["items"])
    p1 = client.get("/me/book/items", params={"mode": "rate", "page_size": 5}).json()
    p2 = client.get("/me/book/items", params={"mode": "rate", "page_size": 5, "page": 2}).json()
    assert len(p1["items"]) == 5 and not {c["key"] for c in p1["items"]} & {c["key"] for c in p2["items"]}


def test_series_volumes_listed_separately(client):
    items = client.get("/me/book/items", params={"page_size": 100}).json()["items"]
    scores = [c["score"] for c in items]
    assert scores == sorted(scores, reverse=True)  # in score order, series and all
    hunger = client.get("/me/book/items", params={"q": "hunger games"}).json()["items"]
    assert len([c for c in hunger if c["series"] == "The Hunger Games"]) >= 3


def test_explanation(client, cats):
    key = find(cats["film"], "The Shining")
    client.put(f"/me/ratings/{find(cats['film'], 'Halloween')}", json={"value": 1})
    ex = client.get(f"/me/film/items/{key}/explanation").json()
    assert ex["key"] == key and 0 <= ex["percentile"] <= 100 and ex["pulling_up"]
    cards = client.get("/me/film/items", params={"page_size": 10}).json()["items"]
    scores = [c["score"] for c in cards]
    assert scores == sorted(scores, reverse=True) and scores[0] > 0  # For you: best predicted rating first


def test_item_page(client, cats):
    key = find(cats["book"], "Harry Potter and the Sorcerer's Stone")
    page = client.get(f"/me/book/items/{key}").json()
    assert page["card"]["key"] == key and page["explanation"]["key"] == key
    tags = page["distinctive"]
    assert "wizards" in {t["tag"] for t in tags} and all(t["score"] > t["average"] for t in tags)
    related = page["related"]
    assert len(related) == 10 and key not in {c["key"] for c in related}
    sims = [c["similarity"] for c in related]
    assert sims == sorted(sims, reverse=True) and 0 < sims[-1] <= sims[0] < 1  # most similar first
    assert all(c["key"].startswith("book:") for c in related)
    assert any(c["series"] == "Harry Potter" for c in related)  # its own series counts like any other book
    assert client.get("/me/book/items/book:0").status_code == 404
    assert client.get("/me/film/items/film:0/explanation").status_code == 404


def test_profile(client, cats):
    for t in ["The Exorcist", "Halloween", "The Thing"]:
        client.put(f"/me/ratings/{find(cats['film'], t)}", json={"value": 1})
    p = client.get("/me/profile").json()
    assert p["shared"]["respond_to"] and [d["domain"] for d in p["domains"]] == ["film", "book"]
    assert p["domains"][0]["rated"] == 3 and p["domains"][0]["claims"]["respond_to"]


def test_shelf_scan(client, cats):
    assert client.get("/me/shelf-scan").json()["status"] == "none"
    assert client.get("/me/shelf-scan").json().get("image_url") is None
    r = scan(client)  # one request: it answers with the results
    assert r.status_code == 200
    result = r.json()
    assert result["status"] == "done" and result["photo_name"] == "shelf.jpg"
    assert {b["title"] for b in result["books"]} == {"The Hobbit", "Pride and Prejudice"}
    hobbit = next(b for b in result["books"] if b["title"] == "The Hobbit")
    assert hobbit["location"] == "Top shelf, on the left"
    assert [s["title"] for s in result["unmatched"]] == ["A Book Nobody Has Heard Of"]
    saved = client.get("/me/shelf-scan").json()  # and it's kept
    assert saved["books"] == result["books"]
    image = client.get(saved["image_url"])  # a signed link: works without the session
    assert image.headers["content-type"] == "image/jpeg"
    anonymous = TestClient(client.app)
    assert anonymous.get(saved["image_url"]).status_code == 200
    assert anonymous.get(saved["image_url"].replace("sig=", "sig=0")).status_code == 403
    # Results are ranked for whoever asks: the saved readings, re-ranked on their ratings.
    client.put(f"/me/ratings/{find(cats['book'], 'Emma')}", json={"value": 1})
    assert client.get("/me/shelf-scan").json()["books"][0]["title"] == "Pride and Prejudice"


def test_failed_scan_keeps_the_last_good_one(client, engine):
    assert scan(client).status_code == 200

    def broken(image):
        raise LLMError("Ollama doesn't have qwen3-vl:8b-instruct")

    engine.reader = broken
    try:
        r = scan(client, name="other.jpg")
        assert r.status_code == 422 and "qwen3-vl" in r.json()["detail"]
        saved = client.get("/me/shelf-scan").json()
        assert saved["photo_name"] == "shelf.jpg" and saved["books"]  # the previous scan is still there
    finally:
        engine.reader = reader


def test_tag_filter(client, cats):
    tags = client.get("/domains/book/tags").json()
    assert "wizards" in tags and tags == sorted(tags, key=str.lower)
    page = client.get("/me/book/items", params={"tags": ["wizards", "dark"], "page_size": 50}).json()
    cards = page["items"]
    plain = client.get("/me/book/items", params={"page_size": 50}).json()["items"]
    assert min(c["tag_match"] for c in cards[:10]) > 0.5  # wizardly and dark...
    assert min(c["percentile"] for c in cards[:10]) > 50  # ...and high on your list
    assert {c["key"] for c in cards} != {c["key"] for c in plain}
    assert page["total"] > 1000  # it orders the list, it doesn't shrink it
    assert client.get("/me/book/items").json()["items"][0]["tag_match"] is None
    assert client.get("/me/book/items", params={"tags": ["nope"]}).status_code == 422


def test_item_page_book_info(client, cats):
    hobbit = client.get(f"/me/book/items/{find(cats['book'], 'The Hobbit')}").json()
    if "ol_work" not in cats["book"].items:
        assert hobbit["book"] is None  # scripts/openlibrary.py hasn't been run
        return
    book = hobbit["book"]
    assert book["first_published"] == 1937 and hobbit["card"]["year"] == 1937 and "Tolkien" in book["authors"][0]["name"]
    assert book["url"].startswith("https://openlibrary.org/works/") and book["subjects"]
    assert hobbit["card"]["cover_url"] == book["cover_url"]  # lists show the cover too
    page = client.get("/me/book/items", params={"page_size": 50}).json()["items"]
    assert sum(bool(c["cover_url"]) for c in page) > 30  # most: about 90% of books have one
    assert client.get(f"/me/film/items/{find(cats['film'], 'Halloween')}").json()["book"] is None


def test_books_only_by_default(tmp_path, cats):
    """The app serves books only, from TASTE_BOOK_GENOME (truegenome): no films, no genome switch."""
    engine = Engine(store=make_store(tmp_path), reader=reader, genome={"book": "default"})
    c = TestClient(create_app(engine))
    sign_in_as_guest(c)
    assert [d["id"] for d in c.get("/domains").json()] == ["book"]
    assert c.get("/me/film/items").status_code == 404
    assert c.get("/genomes").status_code == 404 and c.put("/genomes/book", json={"genome": "x"}).status_code in (404, 405)
    assert c.get("/me/profile").json()["shared"] is None  # nothing carries over with one domain


def test_shelf_scans_run_side_by_side(engine):
    """People's scans don't queue behind each other: both readers are in flight at once."""
    both = threading.Barrier(2, timeout=5)

    def slow(image):
        both.wait()  # breaks (and the scan fails) unless the other scan is running too
        return SHELF

    engine.reader = slow
    try:
        with TestClient(create_app(engine, auth_per_minute=1000)) as app:  # one event loop, as in production
            tokens = [app.post("/auth/guest", headers={"X-Taste-Client": "native"}).json()["token"] for _ in range(2)]
            with ThreadPoolExecutor(2) as people:
                codes = list(people.map(lambda t: app.post(
                    "/me/shelf-scans", headers={"Authorization": f"Bearer {t}"},
                    files={"photo": ("s.jpg", photo(), "image/jpeg")}).status_code, tokens))
        assert codes == [200, 200]
    finally:
        engine.reader = reader


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")  # the point of the test
def test_shelf_scan_limits(client):
    big = io.BytesIO()
    Image.new("1", (7000, 7000)).save(big, format="PNG")  # 49 MP: a tiny file that decodes huge
    assert scan(client, b"x" * (15 * 1024 * 1024 + 1)).status_code == 413
    assert scan(client, b"not a photo").status_code == 422
    assert "too large" in scan(client, big.getvalue()).json()["detail"]
    for _ in range(5):
        assert scan(client).status_code == 200
    r = scan(client)
    assert r.status_code == 429 and "5 shelves an hour" in r.json()["detail"]


def test_parallel_uploads_cant_pass_the_hourly_limit(engine):
    """Photos over 1 MB are spooled to disk, so reading them lets other requests run; the limit is
    checked and the scan logged after that, with nothing in between."""
    noise = io.BytesIO()
    Image.frombytes("RGB", (1000, 800), os.urandom(1000 * 800 * 3)).save(noise, format="PNG")  # ~2.4 MB
    with TestClient(create_app(engine, auth_per_minute=1000)) as app:
        token = app.post("/auth/guest", headers={"X-Taste-Client": "native"}).json()["token"]
        upload = lambda _: app.post("/me/shelf-scans", headers={"Authorization": f"Bearer {token}"},
                                    files={"photo": ("s.png", noise.getvalue(), "image/png")}).status_code
        with ThreadPoolExecutor(12) as people:
            codes = list(people.map(upload, range(12)))
    assert sorted(codes) == [200] * 5 + [429] * 7


def test_failed_scan_hides_internal_errors(client, engine):
    def broken(image):
        raise RuntimeError("psycopg.OperationalError: connection to /var/run/secret failed")

    engine.reader = broken
    try:
        detail = scan(client).json()["detail"]
        assert "psycopg" not in detail and "try again" in detail
    finally:
        engine.reader = reader
