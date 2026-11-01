"""JsonProfileStore: one JSON file per user; each save touches only its own section."""

import io
import json

import pytest
from PIL import Image

from taste.model.shelf import Spine, Where
from taste.storage import JsonProfileStore


@pytest.fixture
def store(tmp_path):
    return JsonProfileStore(tmp_path)


def photo(width: int, height: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


def test_users_put_main_first(store):
    assert store.users() == ["main"]  # always offered, created on first save
    for name in ["romantic", "normie", "main"]:
        store.set_rating(name, "film:1", 1)
    assert store.users() == ["main", "normie", "romantic"]


def test_set_and_clear_ratings(store):
    assert store.set_rating("main", "film:1", 1) == {"film:1": 1}
    assert store.set_rating("main", "film:1", 0) == {"film:1": 0}
    assert store.set_rating("main", "book:2", -1) == {"film:1": 0, "book:2": -1}
    assert store.clear_rating("main", "film:1") == {"book:2": -1}
    assert store.clear_rating("main", "film:1") == {"book:2": -1}  # clearing twice is fine
    assert store.ratings("main") == {"book:2": -1}
    assert store.ratings("nobody") == {}


def test_bare_ids_migrate_to_film(store):
    store.root.joinpath("old.json").write_text(json.dumps({"ratings": {"123": 1, "book:9": -1}}))
    assert store.ratings("old") == {"film:123": 1, "book:9": -1}


def test_description_lives_alongside_ratings(store):
    assert store.description("main") is None
    store.set_rating("main", "film:1", 1)
    store.save_description("main", "You're a chaos gremlin.", {"film:1": 1})
    store.set_rating("main", "book:2", -1)  # rating later must not drop the description
    d = store.description("main")
    assert d.text == "You're a chaos gremlin." and d.ratings == {"film:1": 1} and d.created
    store.save_description("main", "You're a goth with a library card.", store.ratings("main"))
    assert store.description("main").text == "You're a goth with a library card."  # replaced
    assert store.ratings("main") == {"film:1": 1, "book:2": -1}


def test_scan_persists_with_a_thumbnail(store):
    assert store.scan("main") is None and store.scan_image("main") is None
    store.set_rating("main", "book:1", 1)
    spines = [Spine("Dune", "Frank Herbert", Where(1, 3, 0.2)), Spine("Emma")]
    store.save_scan("main", "upload-1", "shelf.jpg", spines, photo(1600, 1200))
    scan = store.scan("main")
    assert scan.id == "upload-1" and scan.photo_name == "shelf.jpg" and scan.scanned
    assert scan.spines == spines and scan.spines[0].where == Where(1, 3, 0.2) and scan.spines[1].where is None
    assert max(Image.open(io.BytesIO(store.scan_image("main"))).size) == 800  # thumbnail, not the full photo
    assert store.ratings("main") == {"book:1": 1}  # the rest of the profile is untouched
    store.save_scan("main", "upload-2", "other.jpg", [Spine("Emma")], photo(400, 300))
    assert store.scan("main").id == "upload-2"  # replaced, not appended
