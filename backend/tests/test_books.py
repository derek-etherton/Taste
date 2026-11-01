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
