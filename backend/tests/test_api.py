"""The HTTP API, end to end in-process: a temporary profile store, stand-in vision model and chat."""

import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from conftest import find
from taste.api.app import create_app
from taste.api.engine import Engine
from taste.model.llm import LLMError
from taste.model.shelf import Spine, Where
from taste.storage import JsonProfileStore

SHELF = [Spine("The Hobbit", "Tolkien", Where(0, 2, 0.2)), Spine("Pride and Prejudice", None, Where(1, 2, 0.8)),
         Spine("A Book Nobody Has Heard Of", "Jo Bloggs", Where(1, 2, 0.5))]


def reader(image, progress):
    progress(0, 2)
    progress(2, 2)
    return SHELF


def chat(messages):
    return "You're a hobbit with a library card."


@pytest.fixture(scope="module")
def engine(tmp_path_factory, cats):  # cats: skips the module if the data isn't prepared
    return Engine(store=JsonProfileStore(tmp_path_factory.mktemp("users")), reader=reader, chat=chat)


@pytest.fixture
def client(engine):
    for f in engine.store.root.glob("*"):  # every test starts with empty profiles
        f.unlink()
    engine.jobs.clear()
    return TestClient(create_app(engine))


def photo() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (1200, 900), "white").save(out, format="JPEG")
    return out.getvalue()


def test_basics(client):
    assert client.get("/health").json() == {"ok": True}
    assert {d["id"] for d in client.get("/domains").json()} == {"film", "book"}
    assert client.get("/profiles").json() == ["main"]
    assert [d["rated"] for d in client.get("/profiles/main").json()] == [0, 0]


def test_bad_inputs(client, cats):
    assert client.get("/profiles/main/music/items").status_code == 404
    assert client.get("/profiles/Bad.Name/book/items").status_code == 422  # user names become file names
    assert client.put("/profiles/main/ratings/book:0", json={"value": 1}).status_code == 404
    key = find(cats["book"], "The Hobbit")
    assert client.put(f"/profiles/main/ratings/{key}", json={"value": 2}).status_code == 422


def test_rating_changes_recommendations(client, cats):
    book = cats["book"]
    before = [c["key"] for c in client.get("/profiles/main/book/items", params={"page_size": 10}).json()["items"]]
    for t in ["The Hobbit", "A Game of Thrones", "The Name of the Wind"]:
        assert client.put(f"/profiles/main/ratings/{find(book, t)}", json={"value": 1}).status_code == 200
    page = client.get("/profiles/main/book/items", params={"page_size": 10}).json()
    after = [c["key"] for c in page["items"]]
    assert after != before and page["total"] > 1000 and page["page_size"] == 10
    assert not {find(book, t) for t in ["The Hobbit", "A Game of Thrones"]} & set(after)  # rated ones excluded
    assert all(c["because"] for c in page["items"])
    rated = client.get("/profiles/main/book/rated").json()
    assert len(rated) == 3 and all(c["rated"] == 1 for c in rated)
    ratings = client.delete(f"/profiles/main/ratings/{find(book, 'The Hobbit')}").json()["ratings"]
    assert len(ratings) == 2


def test_search_rate_mode_and_paging(client):
    found = client.get("/profiles/main/book/items", params={"q": "hobbit"}).json()
    assert any(c["title"] == "The Hobbit" for c in found["items"])
    p1 = client.get("/profiles/main/book/items", params={"mode": "rate", "page_size": 5}).json()
    p2 = client.get("/profiles/main/book/items", params={"mode": "rate", "page_size": 5, "page": 2}).json()
    assert len(p1["items"]) == 5 and not {c["key"] for c in p1["items"]} & {c["key"] for c in p2["items"]}


def test_series_collapse(client):
    items = client.get("/profiles/main/book/items", params={"q": "hunger games"}).json()["items"]
    hunger = [c for c in items if c["series"] == "The Hunger Games"]
    assert len(hunger) == 1 and hunger[0]["more_in_series"] >= 2


def test_explanation(client, cats):
    key = find(cats["film"], "The Shining")
    client.put(f"/profiles/main/ratings/{find(cats['film'], 'Halloween')}", json={"value": 1})
    ex = client.get(f"/profiles/main/film/items/{key}/explanation").json()
    assert ex["key"] == key and 0 <= ex["percentile"] <= 100 and ex["pulling_up"]
    assert client.get("/profiles/main/film/items/film:0/explanation").status_code == 404


def test_profile(client, cats):
    for t in ["The Exorcist", "Halloween", "The Thing"]:
        client.put(f"/profiles/main/ratings/{find(cats['film'], t)}", json={"value": 1})
    p = client.get("/profiles/main/profile").json()
    assert p["shared"]["respond_to"] and [d["domain"] for d in p["domains"]] == ["film", "book"]
    assert p["domains"][0]["rated"] == 3 and p["domains"][0]["claims"]["respond_to"]


def test_describe_me(client, engine, cats):
    assert client.get("/profiles/main/description").json() is None
    assert client.post("/profiles/main/description").status_code == 409  # nothing rated yet
    client.put(f"/profiles/main/ratings/{find(cats['book'], 'The Hobbit')}", json={"value": 1})
    d = client.post("/profiles/main/description").json()
    assert d["text"] == "You're a hobbit with a library card." and not d["stale"]
    client.put(f"/profiles/main/ratings/{find(cats['book'], 'Emma')}", json={"value": -1})
    assert client.get("/profiles/main/description").json()["stale"]

    def broken(messages):
        raise LLMError("Couldn't reach Ollama")

    engine.chat = broken
    try:
        r = client.post("/profiles/main/description")
        assert r.status_code == 503 and "Ollama" in r.json()["detail"]
    finally:
        engine.chat = chat


def poll(client, user="main"):
    for _ in range(100):
        scan = client.get(f"/profiles/{user}/shelf-scan").json()
        if scan["status"] != "running":
            return scan
        time.sleep(0.05)
    raise AssertionError("scan never finished")


def test_shelf_scan(client, cats):
    assert client.get("/profiles/main/shelf-scan").json()["status"] == "none"
    assert client.get("/profiles/main/shelf-scan/image").status_code == 404
    r = client.post("/profiles/main/shelf-scans", files={"photo": ("shelf.jpg", photo(), "image/jpeg")})
    assert r.status_code == 202 and r.json()["status"] == "running"
    scan = poll(client)
    assert scan["status"] == "done" and scan["photo_name"] == "shelf.jpg"
    assert {b["title"] for b in scan["books"]} == {"The Hobbit", "Pride and Prejudice"}
    hobbit = next(b for b in scan["books"] if b["title"] == "The Hobbit")
    assert hobbit["location"] == "Top shelf, on the left"
    assert [s["title"] for s in scan["unmatched"]] == ["A Book Nobody Has Heard Of"]
    assert client.get("/profiles/main/shelf-scan/image").headers["content-type"] == "image/jpeg"
    # Results are ranked for whoever asks: the saved readings, re-ranked on their ratings.
    client.put(f"/profiles/main/ratings/{find(cats['book'], 'Emma')}", json={"value": 1})
    assert poll(client)["books"][0]["title"] == "Pride and Prejudice"


def test_failed_scan_keeps_the_last_good_one(client, engine):
    client.post("/profiles/main/shelf-scans", files={"photo": ("shelf.jpg", photo(), "image/jpeg")})
    assert poll(client)["status"] == "done"

    def broken(image, progress):
        raise LLMError("Ollama doesn't have qwen3-vl:8b-instruct")

    engine.reader = broken
    try:
        client.post("/profiles/main/shelf-scans", files={"photo": ("other.jpg", photo(), "image/jpeg")})
        scan = poll(client)
        assert scan["status"] == "failed" and "qwen3-vl" in scan["error"]
        assert scan["photo_name"] == "shelf.jpg" and scan["books"]  # the previous scan is still shown
    finally:
        engine.reader = reader
