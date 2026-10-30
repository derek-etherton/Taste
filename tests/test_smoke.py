"""Sanity check: a horror fan who dislikes romcoms should get a horror-ish profile."""

import pytest

from taste.model import Catalog, UserModel, toggle_rating

LIKES = ["The Exorcist", "Halloween", "The Thing", "Night of the Living Dead", "The Shining"]
DISLIKES = ["Notting Hill", "Sleepless in Seattle", "Pretty Woman", "You've Got Mail", "The Wedding Singer"]


@pytest.fixture(scope="module")
def cat() -> Catalog:
    return Catalog()


def find(cat: Catalog, title: str) -> int:
    hits = cat.films[cat.films["title"] == title]
    assert not hits.empty, f"not found: {title}"
    return int(hits.sort_values("n_ratings").iloc[-1]["movieId"])


@pytest.fixture(scope="module")
def model(cat: Catalog) -> UserModel:
    ratings = {find(cat, t): 1 for t in LIKES} | {find(cat, t): -1 for t in DISLIKES}
    return UserModel(cat, ratings)


def test_profile_traits(model: UserModel):
    pos, neg = model.profile(k=10)
    assert {c.tag for c in pos} & {"horror", "scary", "creepy", "gore", "suspense"}
    assert {c.tag for c in neg} & {"romance", "romantic comedy", "romantic", "chick flick"}


def test_profile_evidence_matches_direction(model: UserModel):
    pos, neg = model.profile(k=10)
    assert all(r == 1 for c in pos for _, r in c.supporting), "liked-trait evidence must be likes"
    assert all(r == -1 for c in neg for _, r in c.supporting), "disliked-trait evidence must be dislikes"


def test_recommendations_exclude_rated(model: UserModel):
    recs = model.recommend(15)
    assert not set(model.rows) & {r.row for r in recs}


def test_romcom_ranks_low(cat: Catalog, model: UserModel):
    assert model.explain(cat.row[find(cat, "Love Actually")]).percentile < 20


def test_teaching_order_skips_rated(model: UserModel):
    assert not set(model.rows) & set(model.teaching_order()[:50])


def test_toggle_rating():
    r = {}
    toggle_rating(r, 1, 1)
    assert r == {1: 1}
    toggle_rating(r, 1, 0)
    assert r == {1: 0}
    toggle_rating(r, 1, 0)
    assert r == {}
