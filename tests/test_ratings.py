import json

from taste.model import load_ratings, save_ratings, toggle_rating


def test_toggle_rating():
    r = {}
    toggle_rating(r, "film:1", 1)
    assert r == {"film:1": 1}
    toggle_rating(r, "film:1", 0)
    assert r == {"film:1": 0}
    toggle_rating(r, "film:1", 0)
    assert r == {}


def test_bare_ids_migrate_to_film(tmp_path):
    path = tmp_path / "user.json"
    path.write_text(json.dumps({"ratings": {"123": 1, "book:9": -1}}))
    assert load_ratings(path) == {"film:123": 1, "book:9": -1}
    save_ratings(load_ratings(path), path)
    assert load_ratings(path) == {"film:123": 1, "book:9": -1}
