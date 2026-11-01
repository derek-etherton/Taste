"""User taste model for one domain, over its item × tag relevance matrix.

An item is a vector of tag relevances. A user's profile is one signed weight per
tag, fit by ridge regression on their likes (+1), mehs (0) and dislikes (-1). A meh
shrinks the weights on that item's distinctive traits. Scoring an item is a dot
product, so every recommendation decomposes into per-tag contributions and every
profile weight traces back to rated items.

Read as Bayesian regression (rating noise variance 1), ridge is a Gaussian prior on the
weights. By default it is N(0, I/lam): lam is set so a typical item's score has prior
variance 1/ridge, i.e. one rating moves the profile about halfway toward it. A Prior from
traits.py replaces it with what other domains imply: a mean (transferred taste) and a
covariance (how sure that is, per direction). The posterior mean is then
    w = mean + C X' (X C X' + I)^-1 (y - X mean)
so ratings here only fit what the prior gets wrong, and only as far as the prior is unsure.
"""

from dataclasses import dataclass, field

import numpy as np

from taste.model.catalog import Catalog

TEACH_POOL = 600  # the most-rated items: widely enough known that you have likely tried them


@dataclass
class Prior:
    mean: np.ndarray  # tag weights
    cov: np.ndarray  # tags x tags


def ridge_lambda(R: np.ndarray, rows, ridge: float = 1.0) -> float:
    """Prior precision per tag: ridge x mean squared norm of the rated items (or of all items
    if none are rated), so that a typical item's score has prior variance 1/ridge."""
    X = R[np.asarray(rows, dtype=int)] if len(rows) else R
    return ridge * float(np.mean(np.einsum("ij,ij->i", X, X)))


@dataclass
class Evidence:
    item: str  # label
    rating: int
    domain: str


@dataclass
class TagClaim:
    tag: str
    weight: float
    supporting: list[Evidence] = field(default_factory=list)
    contradicting: list[Evidence] = field(default_factory=list)


@dataclass
class Explanation:
    row: int
    item: str
    score: float
    percentile: float  # among unrated items in the candidate pool
    rated: int | None  # the user's rating, if they already rated it
    quality_part: float
    transferred_part: float  # from the prior, i.e. ratings in other domains
    for_tags: list[tuple[str, float]]
    against_tags: list[tuple[str, float]]
    transferred_tags: set[str]  # tags whose contribution comes mostly from other domains


class UserModel:
    def __init__(self, catalog: Catalog, ratings: dict[str, int], ridge: float = 1.0,
                 prior: Prior | None = None):
        """ratings may span domains; only this catalogue's items are used."""
        self.cat = catalog
        self.ratings = {k: y for k, y in ratings.items() if k in catalog.row}
        self.rows = np.array([catalog.row[k] for k in self.ratings], dtype=int)
        self.y = np.array(list(self.ratings.values()), dtype=np.float64)
        self.lam = ridge_lambda(catalog.relevance, self.rows, ridge)
        self.prior = np.zeros(len(catalog.tags)) if prior is None else prior.mean
        self.prior_cov = None if prior is None else prior.cov  # None: I / lam
        self.weights = self._fit()

    def _fit(self) -> np.ndarray:
        if len(self.rows) == 0:
            return self.prior.copy()
        X = self.cat.relevance[self.rows].astype(np.float64)
        resid = self.y - X @ self.prior
        # Dual form: an n x n solve, cheap for a handful of ratings.
        if self.prior_cov is None:
            return self.prior + X.T @ np.linalg.solve(X @ X.T + self.lam * np.eye(len(X)), resid)
        CX = self.prior_cov @ X.T
        return self.prior + CX @ np.linalg.solve(X @ CX + np.eye(len(X)), resid)

    def posterior_cov(self) -> np.ndarray:
        """How unsure the profile still is, per direction: C - C X' (X C X' + I)^-1 X C."""
        C = np.eye(len(self.cat.tags)) / self.lam if self.prior_cov is None else self.prior_cov
        if len(self.rows) == 0:
            return C.copy()
        X = self.cat.relevance[self.rows].astype(np.float64)
        CX = C @ X.T
        return C - CX @ np.linalg.solve(X @ CX + np.eye(len(X)), CX.T)

    @property
    def n_likes(self) -> int:
        return int((self.y > 0).sum())

    @property
    def n_dislikes(self) -> int:
        return int((self.y < 0).sum())

    @property
    def n_meh(self) -> int:
        return int((self.y == 0).sum())

    def confidence(self) -> str:
        n = len(self.rows)
        if n == 0:
            return f"no {self.cat.name.lower()} rated yet"
        level = "low" if n < 10 else "medium" if n < 30 else "reasonable"
        return (f"based on {n} {self.cat.name.lower()} ({self.n_likes} liked, {self.n_meh} meh, "
                f"{self.n_dislikes} disliked): {level} confidence")

    def scores(self, quality: float) -> np.ndarray:
        return self.cat.relevance @ self.weights.astype(np.float32) + quality * self.cat.quality

    def _pool(self, top: int | None = None) -> np.ndarray:
        """Unrated items, optionally only among the `top` most-rated."""
        mask = np.ones(len(self.cat), dtype=bool) if top is None else self.cat.popularity_rank < top
        mask[self.rows] = False
        return mask

    def rated_order(self) -> np.ndarray:
        """Rated item rows: likes, then mehs, then dislikes, alphabetical within each."""
        titles = np.array([self.cat.label(int(i)) for i in self.rows])
        return self.rows[np.lexsort((titles, -self.y))]

    def ranked(self, quality: float = 0.1, rows=None) -> np.ndarray:
        """Item rows best-first: the given rows, or by default every unrated item."""
        s = self.scores(quality)
        rows = np.flatnonzero(self._pool()) if rows is None else np.asarray(rows)
        return rows[np.argsort(-s[rows], kind="stable")]

    def teaching_order(self, top: int = TEACH_POOL, rows=None, greedy: int = 100) -> np.ndarray:
        """Item rows ordered by how much rating them would teach the profile.

        By default every unrated item, but the `top` most-rated come first, since those you
        can most likely answer; the rest follow best-known first. When `rows` is given (a
        search), all of them are ordered by value.

        The value is x'Sx with S the posterior covariance: how uncertain the profile still
        is in that item's direction. High for items unlike anything rated so far, and low
        where other domains already pin taste down. It doesn't depend on the answer, so the
        first `greedy` items are picked one at a time, each assuming the earlier picks were
        rated. That spreads them across different parts of taste instead of asking about ten
        near-identical items.
        """
        if rows is None:
            unrated = np.flatnonzero(self._pool())
            known = self.cat.popularity_rank[unrated] < top
            rest = unrated[~known]
            rest = rest[np.argsort(self.cat.popularity_rank[rest], kind="stable")]
            return np.concatenate([self.teaching_order(rows=unrated[known], greedy=greedy), rest])
        rows = np.asarray(rows)
        if len(rows) == 0:
            return rows
        G = self.cat.relevance[rows].astype(np.float64)
        S = self.posterior_cov()
        v = np.einsum("ij,ij->i", G @ S, G)

        order, left = [], np.ones(len(rows), dtype=bool)
        for _ in range(min(greedy, len(rows))):
            j = int(np.argmax(np.where(left, v, -np.inf)))
            order.append(j)
            left[j] = False
            u = S @ G[j]
            d = 1.0 + G[j] @ u
            S -= np.outer(u, u) / d  # Sherman-Morrison: as if item j had been rated
            v = np.maximum(v - (G @ u) ** 2 / d, 0.0)
        rest = np.flatnonzero(left)
        rest = rest[np.argsort(-v[rest], kind="stable")]
        return rows[np.concatenate([order, rest]).astype(int)]

    def recommend(self, n: int = 20, quality: float = 0.1) -> list[Explanation]:
        s = self.scores(quality)
        best = self.ranked(quality)[:n]
        return [self.explain(int(i), quality, scores=s) for i in best]

    def explain(self, i: int, quality: float = 0.1, k: int = 5, scores=None) -> Explanation:
        s = self.scores(quality) if scores is None else scores
        pool = s[self._pool()]
        g = self.cat.relevance[i]
        contrib = self.weights * g
        transferred = self.prior * g
        order = np.argsort(contrib)
        tag = self.cat.tags
        for_t = [t for t in order[::-1][:k] if contrib[t] > 0]
        against_t = [t for t in order[:k] if contrib[t] < 0]
        return Explanation(
            row=i,
            item=self.cat.label(i),
            score=float(s[i]),
            percentile=float((pool < s[i]).mean() * 100) if len(pool) else 0.0,
            rated=self.ratings.get(self.cat.key(i)),
            quality_part=float(quality * self.cat.quality[i]),
            transferred_part=float(transferred.sum()),
            for_tags=[(tag[t], float(contrib[t])) for t in for_t],
            against_tags=[(tag[t], float(contrib[t])) for t in against_t],
            # Mostly transferred: the prior alone accounts for over half the tag's pull.
            transferred_tags={tag[t] for t in for_t + against_t if transferred[t] / contrib[t] > 0.5},
        )

    def profile(self, k: int = 15, evidence: int = 3) -> tuple[list[TagClaim], list[TagClaim]]:
        """Strongest positive and negative tag weights *learnt in this domain* (on top of any
        prior), each with the rated items behind it. TraitSpace.profile shows shared traits."""
        if len(self.rows) == 0:
            return [], []
        labels = [self.cat.label(int(i)) for i in self.rows]
        return claims(self.cat.tags, self.weights - self.prior, self.cat.relevance[self.rows],
                      self.y, labels, [self.cat.domain] * len(self.rows), k, evidence)


def claims(names, weights, G, y, labels, domains, k: int = 15, evidence: int = 3):
    """Top positive and negative weights as TagClaims, with evidence from rated items (G, y).

    Evidence is items that clearly have the trait (above a typical item), strongest first:
    rated in the weight's direction -> supporting; rated the other way or meh'd ->
    contradicting. Liking an item that merely lacks a trait says little to a person, so it
    isn't listed (the linear model does still use it, weakly).
    """
    order = np.argsort(weights)

    def claim(t: int) -> TagClaim:
        g = G[:, t]
        agrees = y * np.sign(weights[t])  # +1 supports, -1 contradicts, 0 meh
        has = np.flatnonzero(g > 0)
        has = has[np.argsort(-g[has])]
        ev = lambda js: [Evidence(labels[j], int(y[j]), domains[j]) for j in js]
        return TagClaim(
            tag=names[t],
            weight=float(weights[t]),
            supporting=ev([j for j in has if agrees[j] > 0][:evidence]),
            contradicting=ev([j for j in has if agrees[j] <= 0][:evidence]),
        )

    pos = [claim(t) for t in order[::-1][:k] if weights[t] > 1e-12]
    neg = [claim(t) for t in order[:k] if weights[t] < -1e-12]
    return pos, neg
