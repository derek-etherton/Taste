"""A horror fan who dislikes romcoms should get a horror-ish film profile."""

import pytest

from conftest import find
from taste.model import UserModel

LIKES = ["The Exorcist", "Halloween", "The Thing", "Night of the Living Dead", "The Shining"]
DISLIKES = ["Notting Hill", "Sleepless in Seattle", "Pretty Woman", "You've Got Mail", "The Wedding Singer"]


@pytest.fixture(scope="module")
def model(cats) -> UserModel:
    cat = cats["film"]
    return UserModel(cat, {find(cat, t): 1 for t in LIKES} | {find(cat, t): -1 for t in DISLIKES})


def test_profile_traits(model):
    pos, neg = model.profile(k=10)
    assert {c.tag for c in pos} & {"horror", "scary", "creepy", "gore", "suspense"}
    assert {c.tag for c in neg} & {"romance", "romantic comedy", "romantic", "chick flick"}


def test_profile_evidence_matches_direction(model):
    pos, neg = model.profile(k=10)
    assert all(e.rating == 1 for c in pos for e in c.supporting), "liked-trait evidence must be likes"
    assert all(e.rating == -1 for c in neg for e in c.supporting), "disliked-trait evidence must be dislikes"


def test_recommendations_exclude_rated(model):
    assert not set(model.rows) & {r.row for r in model.recommend(15)}


def test_romcom_ranks_low(cats, model):
    assert model.explain(cats["film"].row[find(cats["film"], "Love Actually")]).percentile < 20


def test_teaching_order_skips_rated(model):
    assert not set(model.rows) & set(model.teaching_order()[:50])


def test_teaching_order_covers_catalogue_best_known_first(cats, model):
    order = model.teaching_order()
    assert sorted(order) == sorted(model.ranked()), "Rate and For you should list the same items"
    rank = cats["film"].popularity_rank[order]
    head = 600 - int((cats["film"].popularity_rank[model.rows] < 600).sum())
    assert (rank[:head] < 600).all() and (rank[head:] >= 600).all()
    assert (rank[head:][1:] > rank[head:][:-1]).all(), "the rest goes best-known first"
