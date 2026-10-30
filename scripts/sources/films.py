"""Film source adapter: the source zip's CSVs -> data/film/ in the common format."""

import re
import numpy as np
import pandas as pd

from sources.common import Source, quality, write_domain

URL_ENV = "TASTE_FILM_URL"


def split_title(title: str) -> tuple[str, int | None]:
    m = re.match(r"^(.*?)\s*\((\d{4})\)\s*$", title)
    title, year = (m.group(1), int(m.group(2))) if m else (title, None)
    # Source titles read "Exorcist, The"; put the article back in front.
    return re.sub(r"^(.*), (The|A|An)$", r"\2 \1", title), year


def build(src: Source) -> None:
    print("Reading tag relevances...")
    tags = pd.read_csv(src.open("genome-tags.csv")).sort_values("tagId")
    scores = pd.read_csv(src.open("genome-scores.csv"))
    relevance = scores.pivot(index="movieId", columns="tagId", values="relevance")
    relevance = relevance[tags["tagId"]]  # column order == tags.json order

    print("Reading ratings (this takes a minute)...")
    ratings = pd.read_csv(src.open("ratings.csv"), usecols=["movieId", "rating"])
    stats = ratings.groupby("movieId")["rating"].agg(n_ratings="count", mean_rating="mean")

    items = pd.read_csv(src.open("movies.csv")).set_index("movieId").loc[relevance.index].join(stats)
    items[["title", "year"]] = items["title"].apply(lambda t: pd.Series(split_title(t)))
    items["year"] = items["year"].astype("Int64")
    items["genres"] = items["genres"].replace("(no genres listed)", "")
    items["quality"] = quality(items["n_ratings"], items["mean_rating"], ratings["rating"].mean())
    items = items.reset_index().rename(columns={"movieId": "id"})
    write_domain("film", items, tags["tag"].tolist(), relevance.to_numpy(dtype=np.float32))
