"""Shared traits: the tags that mean the same thing in more than one domain.

data/traits.json lists correspondences, one per trait, e.g. {"film": "dystopia", "book":
"dystopia"}. Each domain's relevance scores come from its own pipeline, so their spreads
differ (book scores are about half as spread out as film scores). Each trait is rescaled
per domain to a shared unit: the geometric mean of its spread across domains. That makes
"as unusually X as a typical film/book" line up, while keeping each trait's natural
importance. (Z-scoring every trait instead let niche tags such as "autism", whose few
strong items sit 15+ spreads out, dominate the profile.)

The model is hierarchical. An item's taste score is z.u + x.d: z its shared-trait features
and u your shared taste, x its own tags and d your taste specific to its domain. A priori
u ~ N(0, I share/lam_u) and d ~ N(0, I (1-share)/lam_d), scaled so a typical item's score
has variance 1/ridge, of which `share` is shared. Ratings have noise variance 1.

A domain's prior is the posterior over u given every *other* domain's ratings (with their
own domain-specific parts integrated out), mapped onto this domain's tags, plus the
domain-specific variance. Its mean is "what your other ratings say"; its covariance is how
sure they are. Traits that many consistent ratings agree on get little variance, so this
domain's ratings can only move them through the domain-specific part: they are stiff.
Traits with little evidence keep the full variance and give way to the first rating here.
"""

import json
from pathlib import Path

import numpy as np

from taste.model.catalog import DATA, Catalog
from taste.model.user_model import Prior, TagClaim, claims, ridge_lambda

TRAITS_FILE = DATA / "traits.json"
SHARE = 0.5  # default: half of a typical item's taste variance is shared across domains


class TraitSpace:
    def __init__(self, catalogs: dict[str, Catalog], path: Path = TRAITS_FILE):
        self.cats = catalogs
        spec = json.loads(path.read_text(encoding="utf-8"))["traits"]
        # Keep traits whose tag exists in every loaded domain the spec covers.
        spec = [t for t in spec if all(d not in t or t[d] in c.tags for d, c in catalogs.items())]
        self.domains = [d for d in catalogs if spec and all(d in t for t in spec)]
        self.names = [next(iter(t.values())) for t in spec]
        self.cols, spread = {}, {}
        for d in self.domains:
            cat = catalogs[d]
            index = {tag: j for j, tag in enumerate(cat.tags)}
            cols = np.array([index[t[d]] for t in spec])
            w = cat.items["n_ratings"].to_numpy(dtype=np.float64)
            # Columns are already centred on the weighted mean, so this is the weighted std.
            var = np.average(cat.relevance[:, cols].astype(np.float64) ** 2, axis=0, weights=w)
            self.cols[d], spread[d] = cols, np.sqrt(np.maximum(var, 1e-12))
        unit = np.exp(np.mean([np.log(s) for s in spread.values()], axis=0)) if spread else 1.0
        self.scale = {d: s / unit for d, s in spread.items()}  # features = relevance / scale
        # Mean squared norm of an item's trait features, for the prior on u.
        norms = [np.mean(np.einsum("ij,ij->i", Z, Z))
                 for Z in (self.features(d, np.arange(len(catalogs[d]))) for d in self.domains)]
        self.z_norm = float(np.mean(norms)) if norms else 1.0

    def __len__(self) -> int:
        return len(self.names)

    def features(self, domain: str, rows) -> np.ndarray:
        return self.cats[domain].relevance[np.asarray(rows)][:, self.cols[domain]] / self.scale[domain]

    def _rated(self, ratings: dict[str, int], domains, share: float, ridge: float):
        """Rated items in `domains`: trait features Z, ratings y, labels, domains, and the
        covariance their domain-specific parts add to the ratings (block-diagonal)."""
        Z, y, labels, doms, blocks = [], [], [], [], []
        for d in domains:
            cat = self.cats[d]
            rows = [cat.row[k] for k in ratings if k in cat.row]
            if rows:
                X = cat.relevance[rows].astype(np.float64)
                Z.append(self.features(d, rows))
                y += [ratings[cat.key(r)] for r in rows]
                labels += [cat.label(r) for r in rows]
                doms += [d] * len(rows)
                blocks.append((1 - share) / ridge_lambda(cat.relevance, rows, ridge) * (X @ X.T))
        own = np.zeros((len(y), len(y)))
        i = 0
        for b in blocks:
            own[i:i + len(b), i:i + len(b)] = b
            i += len(b)
        Z = np.vstack(Z) if Z else np.zeros((0, len(self)))
        return Z, np.array(y, dtype=np.float64), labels, doms, own

    def posterior(self, ratings: dict[str, int], domains=None, share: float = SHARE,
                  ridge: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
        """Mean and covariance of shared taste u given the ratings in `domains` (default all)."""
        Z, y, _, _, own = self._rated(ratings, self.domains if domains is None else domains, share, ridge)
        A = ridge * self.z_norm / share * np.eye(len(self))  # prior precision of u
        if len(y) == 0:
            return np.zeros(len(self)), np.linalg.inv(A)
        # Each rating = z.u + (domain-specific part + noise); the latter has covariance own + I.
        WZ = np.linalg.solve(own + np.eye(len(y)), Z)
        cov = np.linalg.inv(A + Z.T @ WZ)
        return cov @ (WZ.T @ y), cov

    def prior(self, domain: str, ratings: dict[str, int], share: float = SHARE,
              ridge: float = 1.0) -> Prior | None:
        """Prior on `domain`'s tag weights from every other domain's ratings (None if share is 0)."""
        if domain not in self.domains or share <= 0:
            return None
        share = min(share, 0.95)  # keep some room for domain-specific taste
        mean_u, cov_u = self.posterior(ratings, [d for d in self.domains if d != domain], share, ridge)
        cat, cols, scale = self.cats[domain], self.cols[domain], self.scale[domain]
        mean = np.zeros(len(cat.tags))
        mean[cols] = mean_u / scale  # so relevance @ mean == features @ mean_u
        rows = [cat.row[k] for k in ratings if k in cat.row]
        cov = np.eye(len(cat.tags)) * (1 - share) / ridge_lambda(cat.relevance, rows, ridge)
        cov[np.ix_(cols, cols)] += cov_u / np.outer(scale, scale)
        return Prior(mean, cov)

    def profile(self, ratings: dict[str, int], k: int = 15, evidence: int = 3,
                share: float = SHARE) -> tuple[list[TagClaim], list[TagClaim]]:
        """Strongest shared traits across all domains, with evidence from any of them."""
        share = min(max(share, 0.05), 0.95)
        Z, y, labels, doms, _ = self._rated(ratings, self.domains, share, 1.0)
        if len(y) == 0:
            return [], []
        return claims(self.names, self.posterior(ratings, share=share)[0], Z, y, labels, doms, k, evidence)

    def rated_domains(self, ratings: dict[str, int]) -> list[str]:
        return [d for d in self.domains if any(k in self.cats[d].row for k in ratings)]
