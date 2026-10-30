"""User taste model over a film × tag relevance matrix.

A film is a vector of ~1,128 tag relevances. A user's profile is one signed
weight per tag, fit by ridge regression on their likes (+1), mehs (0) and
dislikes (-1). A meh shrinks the weights on that film's distinctive traits.
Scoring a film is a dot product, so every recommendation decomposes into
per-tag contributions and every profile weight traces back to rated films.
"""

from dataclasses import dataclass, field

import numpy as np

from taste.model.catalog import Catalog

TEACH_MIN_RATINGS = 10_000  # widely enough rated that you have likely seen it


@dataclass
class TagClaim:
    tag: str
    weight: float
    supporting: list[tuple[str, int]] = field(default_factory=list)  # (film, your rating)
    contradicting: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class Explanation:
    row: int
    film: str
    score: float
    percentile: float  # among unrated films in the candidate pool
    rated: int | None  # the user's rating, if they already rated it
    quality_part: float
    for_tags: list[tuple[str, float]]
    against_tags: list[tuple[str, float]]


class UserModel:
    def __init__(self, catalog: Catalog, ratings: dict[int, int], ridge: float = 1.0):
        self.cat = catalog
        self.ratings = {m: y for m, y in ratings.items() if m in catalog.row}
        self.rows = np.array([catalog.row[m] for m in self.ratings], dtype=int)
        self.y = np.array(list(self.ratings.values()), dtype=np.float64)
        self.weights = self._fit(ridge)

    def _fit(self, ridge: float) -> np.ndarray:
        if len(self.rows) == 0:
            self.lam = ridge * float(np.mean(np.einsum("ij,ij->i", self.cat.genome, self.cat.genome)))
            return np.zeros(len(self.cat.tags))
        X = self.cat.genome[self.rows].astype(np.float64)
        K = X @ X.T
        # Ridge in dual form: n x n solve, cheap for a handful of ratings.
        # The penalty is relative to the average squared film norm so it is scale-free.
        self.lam = ridge * np.trace(K) / len(K)
        alpha = np.linalg.solve(K + self.lam * np.eye(len(K)), self.y)
        return X.T @ alpha

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
            return "no ratings yet"
        level = "low" if n < 10 else "medium" if n < 30 else "reasonable"
        return (f"based on {n} films ({self.n_likes} liked, {self.n_meh} meh, "
                f"{self.n_dislikes} disliked): {level} confidence")

    def scores(self, quality: float) -> np.ndarray:
        return self.cat.genome @ self.weights.astype(np.float32) + quality * self.cat.quality

    def _pool(self, min_ratings: int) -> np.ndarray:
        mask = self.cat.films["n_ratings"].to_numpy() >= min_ratings
        mask[self.rows] = False
        return mask

    def rated_order(self) -> np.ndarray:
        """Rated film rows: likes, then mehs, then dislikes, alphabetical within each."""
        titles = np.array([self.cat.label(int(i)) for i in self.rows])
        return self.rows[np.lexsort((titles, -self.y))]

    def ranked(self, quality: float = 0.1, min_ratings: int = 500, rows=None) -> np.ndarray:
        """Film rows best-first: the given rows, or by default every unrated film in the pool."""
        s = self.scores(quality)
        rows = np.flatnonzero(self._pool(min_ratings)) if rows is None else np.asarray(rows)
        return rows[np.argsort(-s[rows], kind="stable")]

    def teaching_order(self, min_ratings: int = TEACH_MIN_RATINGS, rows=None, greedy: int = 100) -> np.ndarray:
        """Film rows ordered by how much rating them would teach the profile.

        Only films many people have seen are candidates (min_ratings), so you can actually
        answer. Among those, the value is x'A^-1 x: the ridge model read as Bayesian regression
        (A = X'X + lam*I), i.e. how uncertain the profile still is in that film's direction.
        High for films unlike anything rated so far. It doesn't depend on the answer, so the
        first `greedy` films are picked one at a time, each assuming the earlier picks were
        rated. That spreads them across different parts of taste instead of asking about ten
        near-identical films.
        """
        rows = np.flatnonzero(self._pool(min_ratings)) if rows is None else np.asarray(rows)
        if len(rows) == 0:
            return rows
        G = self.cat.genome[rows].astype(np.float64)
        lam = self.lam
        if len(self.rows):
            X = self.cat.genome[self.rows].astype(np.float64)
            M = np.linalg.inv(X @ X.T + lam * np.eye(len(X)))
            S = (np.eye(G.shape[1]) - X.T @ M @ X) / lam  # A^-1 via the dual, cheap for small n
            KG = G @ X.T
            v = (np.einsum("ij,ij->i", G, G) - np.einsum("ij,ij->i", KG @ M, KG)) / lam
        else:
            S = np.eye(G.shape[1]) / lam
            v = np.einsum("ij,ij->i", G, G) / lam

        order, left = [], np.ones(len(rows), dtype=bool)
        for _ in range(min(greedy, len(rows))):
            j = int(np.argmax(np.where(left, v, -np.inf)))
            order.append(j)
            left[j] = False
            u = S @ G[j]
            d = 1.0 + G[j] @ u
            S -= np.outer(u, u) / d  # Sherman-Morrison: as if film j had been rated
            v = np.maximum(v - (G @ u) ** 2 / d, 0.0)
        rest = np.flatnonzero(left)
        rest = rest[np.argsort(-v[rest], kind="stable")]
        return rows[np.concatenate([order, rest]).astype(int)]

    def recommend(self, n: int = 20, quality: float = 0.1, min_ratings: int = 500) -> list[Explanation]:
        s = self.scores(quality)
        top = self.ranked(quality, min_ratings)[:n]
        return [self.explain(int(i), quality, min_ratings, scores=s) for i in top]

    def explain(
        self, i: int, quality: float = 0.1, min_ratings: int = 500, k: int = 5, scores=None
    ) -> Explanation:
        s = self.scores(quality) if scores is None else scores
        pool = s[self._pool(min_ratings)]
        contrib = self.weights * self.cat.genome[i]
        order = np.argsort(contrib)
        tag = self.cat.tags
        return Explanation(
            row=i,
            film=self.cat.label(i),
            score=float(s[i]),
            percentile=float((pool < s[i]).mean() * 100) if len(pool) else 0.0,
            rated=self.ratings.get(self.cat.movie_id(i)),
            quality_part=float(quality * self.cat.quality[i]),
            for_tags=[(tag[t], float(contrib[t])) for t in order[::-1][:k] if contrib[t] > 0],
            against_tags=[(tag[t], float(contrib[t])) for t in order[:k] if contrib[t] < 0],
        )

    def profile(self, k: int = 15, evidence: int = 3) -> tuple[list[TagClaim], list[TagClaim]]:
        """Strongest positive and negative tag weights, each with the rated films behind it."""
        if len(self.rows) == 0:
            return [], []
        order = np.argsort(self.weights)

        def claim(t: int) -> TagClaim:
            # Evidence is films that clearly have the trait (above a typical film), strongest
            # first: rated in the weight's direction -> supporting; rated the other way or
            # meh'd -> contradicting. Liking a film that merely lacks a trait says little to a
            # person, so it isn't listed (the linear model does still use it, weakly).
            g = self.cat.genome[self.rows, t]
            agrees = self.y * np.sign(self.weights[t])  # +1 supports, -1 contradicts, 0 meh
            has = np.flatnonzero(g > 0)
            has = has[np.argsort(-g[has])]
            labels = lambda js: [(self.cat.label(int(self.rows[j])), int(self.y[j])) for j in js]
            return TagClaim(
                tag=self.cat.tags[t],
                weight=float(self.weights[t]),
                supporting=labels([j for j in has if agrees[j] > 0][:evidence]),
                contradicting=labels([j for j in has if agrees[j] <= 0][:evidence]),
            )

        pos = [claim(t) for t in order[::-1][:k] if self.weights[t] > 0]
        neg = [claim(t) for t in order[:k] if self.weights[t] < 0]
        return pos, neg
