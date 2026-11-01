"""A domain's catalogue: item metadata plus the centred item × tag relevance matrix.

Every source adapter (scripts/sources/) writes the same files to data/<domain>/:
  items.csv      id, title, year, creator, genres, series, series_index,
                 n_ratings, mean_rating, quality   (creator..series_index may be blank)
  tags.json      tag names, in relevance-column order
  relevance.npy  float32, items × tags, each score in [0, 1]
so nothing here knows which dataset an item came from. Other genomes for a domain (e.g. a
BookGenome release) are read by their own connector into the same shape: see genomes.py.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from taste.model.openlibrary import enrich
from taste.settings import get_settings

DATA = get_settings().data_dir
DOMAINS = {"film": "Films", "book": "Books"}  # domain -> display name


class Catalog:
    def __init__(self, domain: str, items: pd.DataFrame, tags: list[str], relevance: np.ndarray, *,
                 genome: str = "default", weights: np.ndarray | None = None,
                 derived_from: dict[str, list[str]] | None = None, linked: int | None = None):
        """`weights` say how much each item counts when centring (default: its rating count;
        uniform if nobody rated anything). `derived_from` maps each tag to the tags of the
        domain's default genome it was made from, for genomes with their own tag set; None
        means the tags are the default ones. `linked`: items matched to the default genome."""
        self.domain, self.genome = domain, genome
        self.name = DOMAINS.get(domain, domain.title())
        self.items = items.reset_index(drop=True)
        self.items["id"] = self.items["id"].astype(str)
        self.tags = list(tags)
        self.derived_from, self.linked = derived_from, linked
        n_ratings = self.items["n_ratings"].to_numpy(dtype=np.float64)
        if weights is None:
            weights = n_ratings
        self.weights = np.asarray(weights, dtype=np.float64)
        if not self.weights.sum() > 0:
            self.weights = np.ones(len(self.items))
        # Centre on the average *consumed* item, so a vector says how unusual an item is on
        # each tag rather than how relevant the tag is in absolute terms.
        self.center = np.average(relevance, axis=0, weights=self.weights).astype(np.float32)
        self.relevance = (relevance - self.center).astype(np.float32)  # raw score = relevance + center
        self.norms = np.linalg.norm(self.relevance, axis=1)
        self.quality = self.items["quality"].to_numpy(dtype=np.float32)
        for col in ("series", "series_index"):  # optional: older or series-less sources
            if col not in self.items:
                self.items[col] = ""
        self.series = self.items["series"].to_numpy(dtype=object)
        self.series_index = pd.to_numeric(self.items["series_index"], errors="coerce").to_numpy(dtype=np.float64)
        self.keys = [f"{domain}:{i}" for i in self.items["id"]]
        self.row = {k: i for i, k in enumerate(self.keys)}
        # 0 = most-rated item; filters use this so thresholds mean the same in every domain.
        self.popularity_rank = np.empty(len(self.items), dtype=int)
        self.popularity_rank[np.argsort(-n_ratings, kind="stable")] = np.arange(len(self.items))
        self.labels = [
            f"{t} ({int(y)})" if pd.notna(y) else t
            for t, y in zip(self.items["title"], self.items["year"])
        ]

    @classmethod
    def load(cls, domain: str, data_dir: Path = DATA, src: Path | None = None, genome: str = "default") -> "Catalog":
        """A catalogue in the common format, from data/<domain>/ unless `src` says otherwise."""
        src = src or data_dir / domain
        return cls(domain, read_items(src),
                   json.loads((src / "tags.json").read_text(encoding="utf-8")),
                   np.load(src / "relevance.npy"), genome=genome)

    def __len__(self) -> int:
        return len(self.items)

    def label(self, i: int) -> str:
        return self.labels[i]

    def key(self, i: int) -> str:
        return self.keys[i]

    def creator(self, i: int) -> str:
        return self.items["creator"].iat[i]

    def genres(self, i: int) -> list[str]:
        g = self.items["genres"].iat[i]
        return g.split("|") if g else []

    def similarity(self, i: int) -> np.ndarray:
        """Each row's similarity to row i, from -1 to 1: cosine similarity of the centred tag
        vectors, so two items match on what sets them apart, not on what every item has."""
        return self.relevance @ self.relevance[i] / np.maximum(self.norms * self.norms[i], 1e-9)

    def similar(self, i: int) -> np.ndarray:
        """Every other row, most similar to row i first."""
        sim = self.similarity(i)
        sim[i] = -np.inf
        return np.argsort(-sim, kind="stable")[:-1]

    def tag_match(self, tags: list[str]) -> np.ndarray:
        """How strongly each row has all the given tags: the mean of its raw scores (0 to 1)."""
        cols = [self.tags.index(t) for t in tags]
        return self.relevance[:, cols].mean(axis=1) + self.center[cols].mean()

    def distinctive(self, i: int, k: int = 10) -> list[tuple[str, float, float]]:
        """The k tags row i has most above the catalogue's average: (tag, its score, average)."""
        top = np.argsort(-self.relevance[i], kind="stable")[:k]
        return [(self.tags[t], float(self.relevance[i, t] + self.center[t]), float(self.center[t]))
                for t in top if self.relevance[i, t] > 0]

    def search(self, query: str) -> np.ndarray:
        """Rows whose title or creator contains the query (case-insensitive), most-rated first."""
        match = self.items["title"].str.contains(query, case=False, regex=False) | self.items[
            "creator"
        ].str.contains(query, case=False, regex=False)
        hits = np.flatnonzero(match.to_numpy())
        return hits[np.argsort(self.popularity_rank[hits])]


def read_items(src: Path) -> pd.DataFrame:
    """items.csv, with Open Library metadata joined on if the folder has it (see openlibrary.py)."""
    return enrich(pd.read_csv(src / "items.csv", keep_default_na=False, na_values={"year": [""]},
                              dtype={"goodreads_id": str}), src)
