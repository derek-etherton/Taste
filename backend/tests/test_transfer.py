"""Shared traits: film taste should carry over to books, and only through the prior."""

import re

import numpy as np
import pytest

from conftest import find
from taste.model import UserModel

HORROR_FILMS = ["The Exorcist", "Halloween", "The Thing", "Night of the Living Dead", "The Shining",
                "Alien", "Psycho", "The Texas Chainsaw Massacre"]


def _norm(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s*\(.*\)\s*$", "", title.lower())).strip()


def test_adaptations_closer_than_random(cats, traits):
    """Films and books with the same title (mostly adaptations) should share traits."""
    film, book = cats["film"], cats["book"]
    by_title = {}
    for i in np.argsort(-film.popularity_rank):  # most-rated last, so it wins
        by_title[_norm(film.items["title"].iat[i])] = int(i)
    pairs = [(by_title[k], j) for j, t in enumerate(book.items["title"])
             if len(k := _norm(t)) > 6 and k in by_title]
    assert len(pairs) > 500
    F = traits.features("film", [p[0] for p in pairs])
    B = traits.features("book", [p[1] for p in pairs])
    cos = lambda X, Y: (X * Y).sum(1) / np.linalg.norm(X, axis=1) / np.linalg.norm(Y, axis=1)
    matched = cos(F, B)
    shuffled = cos(F, B[np.random.default_rng(0).permutation(len(B))])
    auc = (matched[:, None] > shuffled[None, :]).mean()
    assert auc > 0.8, auc


@pytest.fixture(scope="module")
def horror(cats):
    return {find(cats["film"], t): 1 for t in HORROR_FILMS}


def test_horror_films_recommend_horror_books(cats, traits, horror):
    book = cats["book"]
    model = UserModel(book, horror, prior=traits.prior("book", horror))
    assert model.explain(book.row[find(book, "The Shining")]).percentile > 90
    horror_tag = book.tags.index("horror")
    recs = model.recommend(20)
    assert sum(book.relevance[r.row, horror_tag] > 0 for r in recs) >= 12
    assert all(r.transferred_part != 0 for r in recs)


def test_no_transfer_is_quality_order(cats, traits, horror):
    book = cats["book"]
    off = UserModel(book, horror, prior=traits.prior("book", horror, share=0.0))
    plain = UserModel(book, {})
    assert np.array_equal(off.ranked()[:50], plain.ranked()[:50])


def test_prior_excludes_own_domain(cats, traits, horror):
    """A domain's prior comes only from other domains' ratings."""
    assert not traits.prior("film", horror).mean.any()


def test_own_ratings_override_prior(cats, traits, horror):
    book = cats["book"]
    shining = find(book, "The Shining")
    ratings = horror | {shining: -1}
    model = UserModel(book, ratings, prior=traits.prior("book", ratings))
    before = UserModel(book, horror, prior=traits.prior("book", horror))
    carrie = book.row[find(book, "Carrie")]
    assert model.scores(0.1)[carrie] < before.scores(0.1)[carrie]


def test_shared_traits_agree_with_film_profile(cats, traits, horror):
    """With only film ratings, the shared profile should be the film profile's shared part,
    not a few niche tags that one rated film happens to have in the extreme."""
    film_pos, _ = UserModel(cats["film"], horror).profile(k=25)
    shared_pos, _ = traits.profile(horror, k=10)
    overlap = {c.tag for c in shared_pos} & {c.tag for c in film_pos}
    assert len(overlap) >= 6, (sorted(c.tag for c in shared_pos), overlap)


def test_film_evidence_makes_book_prior_surer(cats, traits):
    """More consistent film ratings -> less prior uncertainty about a related book, but never
    below the domain-specific part, which no amount of film evidence can pin down."""
    film, book = cats["film"], cats["book"]
    x = book.relevance[book.row[find(book, "The Shining")]].astype(np.float64)
    horror = film.tags.index("horror")
    pool = np.flatnonzero(film.popularity_rank < 3000)
    scary = pool[np.argsort(-film.relevance[pool, horror])]
    variances = []
    for n in [0, 8, 30, 100]:
        prior = traits.prior("book", {film.key(int(i)): 1 for i in scary[:n]})
        variances.append(x @ prior.cov @ x)
    assert all(a > b for a, b in zip(variances, variances[1:])), variances
    floor = 0.5 * (x @ x) / (np.mean(np.einsum("ij,ij->i", book.relevance, book.relevance)))
    assert variances[-1] > floor, (variances, floor)


def test_isotropic_prior_matches_plain_ridge(cats):
    """A prior covariance of I/lam must reproduce the plain ridge fit exactly."""
    from taste.model import Prior
    film = cats["film"]
    ratings = {find(film, t): 1 for t in HORROR_FILMS[:4]} | {find(film, "Notting Hill"): -1}
    plain = UserModel(film, ratings)
    same = UserModel(film, ratings, prior=Prior(np.zeros(len(film.tags)), np.eye(len(film.tags)) / plain.lam))
    assert np.allclose(plain.weights, same.weights)
    assert np.array_equal(plain.teaching_order()[:30], same.teaching_order()[:30])
