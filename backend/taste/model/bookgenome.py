"""Connector for BookGenome releases: books scored by an LLM that read the whole text.

A release folder holds genome.json, books.csv (book, title, author, ...), tags.csv (tag,
derived_from: the original book-genome tags it was made from, |-separated) and scores.csv
(book × tag, every score in [0, 1]; 0 means "looked, no trace", not missing).

Each release book is linked to the default book catalogue by title and author, so it keeps
that catalogue's ID (and so the user's ratings), year, genres, series and rating stats.
Books the default catalogue lacks get `gb-<release id>` and neutral quality. Every book in
the release counts equally when centring: the release is a hand-picked set, and most of it
has no reader ratings to weight by.
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["id", "title", "year", "creator", "genres", "series", "series_index",
           "n_ratings", "mean_rating", "quality"]


def is_release(path: Path) -> bool:
    return all((path / f).exists() for f in ("genome.json", "books.csv", "tags.csv", "scores.csv"))


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def norm_title(title: str) -> str:
    """Main title only: no subtitle ("X: A Tale"), alternative title ("X; Or, Y"), series
    note ("X (Series, #1)"), punctuation or leading article."""
    t = re.split(r"\s*[:;(\[]|\s+-{1,2}\s+", _ascii(title))[0]
    t = re.sub(r"[^a-z0-9 ]+", "", t.replace("&", " and ").replace("'", "").replace("-", " "))
    return re.sub(r"^(the|a|an) ", "", " ".join(t.split()))


def norm_author(author: str) -> str:
    """Surname of the first author: "L. M. Montgomery", "L.M. Montgomery" -> "montgomery"."""
    words = re.sub(r"[^a-z ]+", " ", _ascii(author.split(",")[0])).split()
    return words[-1] if words else ""


def link(books: pd.DataFrame, base: pd.DataFrame) -> list[int | None]:
    """For each release book, the row of the same book in `base` (an items table), or None.
    Same main title and author surname; failing that, one title ending with the other
    ("The Life and Adventures of Robinson Crusoe"). The most-rated edition wins, and no
    base row is linked twice."""
    titles = base["title"].map(norm_title)
    authors = base["creator"].map(norm_author)
    rated = base["n_ratings"].to_numpy(dtype=np.float64)
    by_author: dict[str, list[int]] = {}
    for i, a in enumerate(authors):
        by_author.setdefault(a, []).append(i)
    out, taken = [], set()
    for title, author in zip(books["title"], books["author"]):
        t, rows = norm_title(title), [i for i in by_author.get(norm_author(author), []) if i not in taken]
        hits = [i for i in rows if titles.iat[i] == t]
        if not hits:
            hits = [i for i in rows if _suffix(titles.iat[i], t)]
        best = max(hits, key=lambda i: rated[i]) if hits else None
        taken.add(best)
        out.append(best)
    return out


def _suffix(a: str, b: str) -> bool:
    short, long = sorted((a, b), key=len)
    return len(short.split()) >= 2 and long.endswith(" " + short)


@dataclass
class Release:
    name: str
    description: str
    items: pd.DataFrame  # the common items.csv columns, in books.csv order
    tags: list[str]
    relevance: np.ndarray  # books × tags, float32
    derived_from: dict[str, list[str]]  # tag -> original book-genome tags (empty if new)
    linked: int  # books matched to the base catalogue


def read_release(path: Path, base: pd.DataFrame | None = None) -> Release:
    """Read a release, linking its books to `base` (the default book items) if given."""
    meta = json.loads((path / "genome.json").read_text(encoding="utf-8"))
    books = pd.read_csv(path / "books.csv", dtype=str, keep_default_na=False, encoding="utf-8")
    tag_rows = pd.read_csv(path / "tags.csv", dtype=str, keep_default_na=False, encoding="utf-8")
    tags = tag_rows["tag"].tolist()
    derived = {t: [s for s in d.split("|") if s] for t, d in zip(tag_rows["tag"], tag_rows["derived_from"])}
    scores = pd.read_csv(path / "scores.csv", encoding="utf-8").set_index("book")
    missing_books = set(books["book"]) - set(scores.index)
    missing_tags = set(tags) - set(scores.columns)
    if missing_books or missing_tags:
        raise ValueError(f"{path}: scores.csv lacks books {sorted(missing_books)[:5]} / tags {sorted(missing_tags)[:5]}")
    relevance = scores.loc[books["book"], tags].to_numpy(dtype=np.float32)
    if np.isnan(relevance).any():
        raise ValueError(f"{path}: scores.csv has blank scores")

    rows = link(books, base) if base is not None and len(base) else [None] * len(books)
    extra = [c for c in base.columns if c not in COLUMNS] if base is not None else []  # e.g. Open Library's
    columns = COLUMNS + extra
    items = []
    for (_, b), r in zip(books.iterrows(), rows):
        if r is None:  # not in the default catalogue: nobody's rated it, so average quality
            items.append({"id": f"gb-{b['book']}", "title": b["title"], "year": np.nan, "creator": b["author"],
                          "genres": "", "series": "", "series_index": "",
                          "n_ratings": 0, "mean_rating": np.nan, "quality": 0.0} | dict.fromkeys(extra, ""))
        else:
            items.append(base.iloc[r].reindex(columns, fill_value="").to_dict())
    return Release(
        name=path.name, description=meta.get("description", ""),
        items=pd.DataFrame(items, columns=columns), tags=tags, relevance=np.clip(relevance, 0, 1),
        derived_from=derived, linked=sum(r is not None for r in rows),
    )
