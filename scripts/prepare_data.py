"""One-off data prep: download the source dataset zip and compact it into data/.

The source URL is not kept in the repo: set TASTE_DATA_URL in .env (see .env.example),
the environment, or pass it as an argument.
"""

import argparse
import json
import os
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import truststore

from taste.model import DATA

truststore.inject_into_ssl()  # use the OS certificate store for the HTTPS download

RAW = DATA / "raw"
SHRINK = 50  # pseudo-ratings pulling a film's mean toward the global mean


def load_env(path: Path = DATA.parent / ".env") -> None:
    """Minimal .env reader: KEY=value lines; real environment variables win."""
    if path.exists():
        for line in path.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())


def download(url: str) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    zip_path = RAW / "source.zip"
    if not zip_path.exists():
        print("Downloading source dataset (~250 MB)...")
        urllib.request.urlretrieve(url, zip_path)
    with zipfile.ZipFile(zip_path) as z:
        top = z.namelist()[0].split("/")[0]  # the zip holds one top-level folder
        if not (RAW / top).exists():
            print("Extracting...")
            z.extractall(RAW)
    return RAW / top


def split_title(title: str) -> tuple[str, int | None]:
    m = re.match(r"^(.*?)\s*\((\d{4})\)\s*$", title)
    return (m.group(1), int(m.group(2))) if m else (title, None)


def main(url: str, keep_raw: bool) -> None:
    src = download(url)

    print("Reading tag relevances...")
    tags = pd.read_csv(src / "genome-tags.csv").sort_values("tagId")
    scores = pd.read_csv(src / "genome-scores.csv")
    genome = scores.pivot(index="movieId", columns="tagId", values="relevance")
    genome = genome[tags["tagId"]]  # column order == tags.json order

    print("Reading ratings (this takes a minute)...")
    ratings = pd.read_csv(src / "ratings.csv", usecols=["movieId", "rating"])
    stats = ratings.groupby("movieId")["rating"].agg(n_ratings="count", mean_rating="mean")
    global_mean = ratings["rating"].mean()

    films = pd.read_csv(src / "movies.csv").set_index("movieId").loc[genome.index]
    films = films.join(stats)
    films[["title", "year"]] = films["title"].apply(lambda t: pd.Series(split_title(t)))
    shrunk = (films["n_ratings"] * films["mean_rating"] + SHRINK * global_mean) / (
        films["n_ratings"] + SHRINK
    )
    films["quality"] = (shrunk - shrunk.mean()) / shrunk.std()

    DATA.mkdir(exist_ok=True)
    np.save(DATA / "genome.npy", genome.to_numpy(dtype=np.float32))
    films.reset_index()[
        ["movieId", "title", "year", "genres", "n_ratings", "mean_rating", "quality"]
    ].to_csv(DATA / "films.csv", index=False)
    (DATA / "tags.json").write_text(json.dumps(tags["tag"].tolist()))
    print(f"Wrote {genome.shape[0]} films x {genome.shape[1]} tags to {DATA}")

    if not keep_raw:
        shutil.rmtree(RAW)


if __name__ == "__main__":
    load_env()
    p = argparse.ArgumentParser()
    p.add_argument("url", nargs="?", default=os.environ.get("TASTE_DATA_URL"), help="source dataset zip")
    p.add_argument("--keep-raw", action="store_true", help="keep the downloaded zip/csvs")
    args = p.parse_args()
    if not args.url:
        p.error("set TASTE_DATA_URL in .env or pass the source dataset URL")
    main(args.url, args.keep_raw)
