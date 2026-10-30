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


def test_description_persists_alongside_ratings(tmp_path):
    from taste.model import load_description, save_description
    path = tmp_path / "user.json"
    assert load_description(path) is None
    save_ratings({"film:1": 1}, path)
    save_description("You're a chaos gremlin.", {"film:1": 1}, path)
    save_ratings({"film:1": 1, "book:2": -1}, path)  # rating later must not drop the description
    d = load_description(path)
    assert d.text == "You're a chaos gremlin." and d.ratings == {"film:1": 1} and d.created
    assert load_ratings(path) == {"film:1": 1, "book:2": -1}
    save_description("You're a goth with a library card.", load_ratings(path), path)
    assert load_description(path).text == "You're a goth with a library card."  # replaced, not appended
    assert load_ratings(path) == {"film:1": 1, "book:2": -1}
