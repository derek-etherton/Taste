"""A domain's catalogue: item metadata plus the centred item × tag relevance matrix.

Every source adapter (scripts/sources/) writes the same files to data/<domain>/:
  items.csv      id, title, year, creator, genres, series, series_index,
                 n_ratings, mean_rating, quality   (creator..series_index may be blank)
  tags.json      tag names, in relevance-column order
  relevance.npy  float32, items × tags, each score in [0, 1]
so nothing here knows which dataset an item came from.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from taste.settings import get_settings

DATA = get_settings().data_dir
DOMAINS = {"film": "Films", "book": "Books"}  # domain -> display name


def available_domains(data_dir: Path = DATA) -> list[str]:
    return [d for d in DOMAINS if (data_dir / d / "items.csv").exists()]


class Catalog:
    def __init__(self, domain: str, data_dir: Path = DATA):
        src = data_dir / domain
        self.domain = domain
        self.name = DOMAINS.get(domain, domain.title())
        self.items = pd.read_csv(src / "items.csv", keep_default_na=False, na_values={"year": [""]})
        self.tags = json.loads((src / "tags.json").read_text(encoding="utf-8"))
        relevance = np.load(src / "relevance.npy")
        # Centre on the average *consumed* item, so a vector says how unusual an item
        # is on each tag rather than how relevant the tag is in absolute terms.
        weights = self.items["n_ratings"].to_numpy(dtype=np.float64)
        self.relevance = (relevance - np.average(relevance, axis=0, weights=weights)).astype(np.float32)
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
        self.popularity_rank[np.argsort(-weights, kind="stable")] = np.arange(len(self.items))
        self.labels = [
            f"{t} ({int(y)})" if pd.notna(y) else t
            for t, y in zip(self.items["title"], self.items["year"])
        ]

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

    def search(self, query: str) -> np.ndarray:
        """Rows whose title or creator contains the query (case-insensitive), most-rated first."""
        match = self.items["title"].str.contains(query, case=False, regex=False) | self.items[
            "creator"
        ].str.contains(query, case=False, regex=False)
        hits = np.flatnonzero(match.to_numpy())
        return hits[np.argsort(self.popularity_rank[hits])]
