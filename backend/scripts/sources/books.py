"""Book source adapter: the source zip's JSON lines + scores -> data/book/ in the common format.

It also ships a book-tag -> film-tag correspondence, written as data/traits.json: the shared
trait vocabulary that lets taste learnt in one domain transfer to the other.
"""

import json
import re

import numpy as np
import pandas as pd

from sources.common import DATA, Source, quality, write_domain

URL_ENV = "TASTE_BOOK_URL"
SCORES = "scores/glmer.csv"  # same algorithm family as the film relevance scores, for comparable scales
# Titles carry their series: "Morning Star (Red Rising, #3)", "X (Harry Bosch, #3; Bosch Universe, #3)".
SERIES = re.compile(r"\((?P<series>[^()#;]+?),\s*#(?P<index>\d+(?:\.\d+)?)(?P<range>-)?[^()]*\)\s*$")


def series(titles: pd.Series) -> pd.DataFrame:
    """series name and position from each title; "" / NaN when it isn't in a series.
    Omnibus editions ("#1-3") belong to the series but have no single position."""
    out = titles.str.extract(SERIES)
    index = pd.to_numeric(out["index"]).where(out["range"].isna())
    return pd.DataFrame({"series": out["series"].fillna("").str.strip(), "series_index": index})


def build(src: Source) -> None:
    print("Reading tag relevances...")
    tags = pd.read_json(src.open("raw/tags.json"), lines=True).sort_values("id")["tag"].tolist()
    scores = pd.read_csv(src.open(SCORES))
    relevance = scores.pivot(index="item_id", columns="tag", values="score")[tags]

    print("Reading ratings...")
    ratings = pd.read_json(src.open("raw/ratings.json"), lines=True, dtype={"rating": "int8"})
    stats = ratings.groupby("item_id")["rating"].agg(n_ratings="count", mean_rating="mean")

    meta = pd.read_json(src.open("raw/metadata.json"), lines=True).set_index("item_id")
    items = meta.loc[relevance.index, ["title", "year", "authors"]].join(stats)
    items["creator"] = items.pop("authors").str.replace(r"\s+", " ", regex=True).str.strip()
    items["year"] = pd.to_numeric(items["year"], errors="coerce").where(lambda y: y > 0).astype("Int64")
    items[["n_ratings", "mean_rating"]] = items[["n_ratings", "mean_rating"]].fillna(
        {"n_ratings": 0, "mean_rating": ratings["rating"].mean()})
    items[["series", "series_index"]] = series(items["title"])
    items["quality"] = quality(items["n_ratings"], items["mean_rating"], ratings["rating"].mean())
    items = items.reset_index().rename(columns={"item_id": "id"})
    write_domain("book", items, tags, relevance.to_numpy(dtype=np.float32))

    matching = pd.read_csv(src.open("matching.csv")).dropna()
    traits = [{"film": f, "book": b} for f, b in zip(matching["movie_tag"], matching["book_tag"])]
    (DATA / "traits.json").write_text(json.dumps({"traits": traits}, indent=0), encoding="utf-8")
    print(f"Wrote {len(traits)} shared traits to {DATA / 'traits.json'}")
