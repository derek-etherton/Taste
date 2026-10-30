"""Helpers shared by the source adapters: .env, download, quality, and the common output format."""

import json
import os
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import truststore

from taste.model import DATA

truststore.inject_into_ssl()  # use the OS certificate store for HTTPS downloads

RAW = DATA / "raw"
SHRINK = 50  # pseudo-ratings pulling an item's mean toward the global mean
COLUMNS = ["id", "title", "year", "creator", "genres", "series", "series_index",
           "n_ratings", "mean_rating", "quality"]


def load_env(path: Path = DATA.parent / ".env") -> None:
    """Minimal .env reader: KEY=value lines; real environment variables win."""
    if path.exists():
        for line in path.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())


class Source:
    """A downloaded source zip, read in place (some hold gigabytes we never need extracted)."""

    def __init__(self, url: str, name: str):
        dest = RAW / name
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / "source.zip"
        if not path.exists():
            print(f"Downloading {name} source dataset...")
            urllib.request.urlretrieve(url, dest / "source.zip.part")
            (dest / "source.zip.part").replace(path)
        self.zip = zipfile.ZipFile(path)

    def open(self, name: str):
        """A member by file name or trailing path (e.g. "raw/tags.json"), wherever it sits."""
        hits = [n for n in self.zip.namelist()
                if (n == name or n.endswith("/" + name)) and not n.startswith("__MACOSX")]
        assert len(hits) == 1, f"{name}: {hits}"
        return self.zip.open(hits[0])


def quality(n_ratings: pd.Series, mean_rating: pd.Series, global_mean: float) -> pd.Series:
    """Bayesian-shrunk mean rating, z-scored within the domain."""
    shrunk = (n_ratings * mean_rating + SHRINK * global_mean) / (n_ratings + SHRINK)
    return (shrunk - shrunk.mean()) / shrunk.std()


def write_domain(domain: str, items: pd.DataFrame, tags: list[str], relevance: np.ndarray) -> None:
    assert len(items) == relevance.shape[0] and len(tags) == relevance.shape[1]
    out = DATA / domain
    out.mkdir(parents=True, exist_ok=True)
    items = items.copy()
    for col, empty in [("creator", ""), ("genres", ""), ("series", ""), ("series_index", None)]:
        if col not in items:
            items[col] = empty
    items[COLUMNS].to_csv(out / "items.csv", index=False)
    (out / "tags.json").write_text(json.dumps(tags), encoding="utf-8")
    np.save(out / "relevance.npy", relevance.astype(np.float32))
    print(f"Wrote {relevance.shape[0]} {domain}s x {relevance.shape[1]} tags to {out}")
