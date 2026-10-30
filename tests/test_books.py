"""Books on their own: a fantasy fan who dislikes romance."""

import pytest

from conftest import find
from taste.model import UserModel

LIKES = ["The Hobbit", "A Game of Thrones", "The Name of the Wind", "The Final Empire", "The Way of Kings"]
DISLIKES = ["Fifty Shades of Grey", "The Notebook", "Twilight", "Me Before You", "Pride and Prejudice"]


@pytest.fixture(scope="module")
def model(cats) -> UserModel:
    cat = cats["book"]
    return UserModel(cat, {find(cat, t): 1 for t in LIKES} | {find(cat, t): -1 for t in DISLIKES})


def test_profile_traits(model):
    pos, neg = model.profile(k=10)
    assert {c.tag for c in pos} & {"fantasy", "epic fantasy", "high fantasy", "magic", "dragons"}
    assert {c.tag for c in neg} & {"romance", "romantic", "love story", "chick lit"}


def test_recommendations_lean_fantasy(cats, model):
    recs = model.recommend(20)
    assert not set(model.rows) & {r.row for r in recs}
    fantasy = cats["book"].tags.index("fantasy")
    assert sum(cats["book"].relevance[r.row, fantasy] > 0 for r in recs) >= 15


def test_collapse_series_one_entry_each(cats, model):
    book = cats["book"]
    rows, more = model.collapse_series(model.ranked())
    names = [book.series[i] for i in rows if book.series[i]]
    assert len(names) == len(set(names)), "a series appears twice"
    assert len(rows) < len(model.ranked())
    assert all(book.series[i] for i in more)


def test_collapse_series_shows_next_unread(cats):
    """Rate the first Hunger Games book and the series entry moves on to #2."""
    book = cats["book"]
    first = find(book, "The Hunger Games")
    assert book.series[book.row[first]] == "The Hunger Games"
    hg = [i for i in range(len(book)) if book.series[i] == "The Hunger Games"]
    shown = lambda m: [i for i in m.collapse_series(m.ranked())[0] if book.series[i] == "The Hunger Games"]
    assert book.series_index[shown(UserModel(book, {}))[0]] == 1
    after = shown(UserModel(book, {first: 1}))
    assert len(after) == 1 and book.series_index[after[0]] == 2, [book.label(i) for i in hg]
