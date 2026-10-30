"""The film catalogue: metadata plus the centred film × tag relevance matrix."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"


class Catalog:
    def __init__(self, data_dir: Path = DATA):
        self.films = pd.read_csv(data_dir / "films.csv")
        # Source titles read "Exorcist, The"; put the article back in front.
        self.films["title"] = self.films["title"].str.replace(
            r"^(.*), (The|A|An)$", r"\2 \1", regex=True
        )
        self.tags = json.loads((data_dir / "tags.json").read_text())
        genome = np.load(data_dir / "genome.npy")
        # Centre on the average *watched* film, so a vector says how unusual a
        # film is on each tag rather than how relevant the tag is in absolute terms.
        weights = self.films["n_ratings"].to_numpy(dtype=np.float64)
        self.genome = (genome - np.average(genome, axis=0, weights=weights)).astype(np.float32)
        self.quality = self.films["quality"].to_numpy(dtype=np.float32)
        self.row = {mid: i for i, mid in enumerate(self.films["movieId"])}
        self.labels = [
            f"{t} ({int(y)})" if pd.notna(y) else t
            for t, y in zip(self.films["title"], self.films["year"])
        ]

    def label(self, i: int) -> str:
        return self.labels[i]

    def movie_id(self, i: int) -> int:
        return int(self.films["movieId"].iat[i])

    def genres(self, i: int) -> list[str]:
        return self.films["genres"].iat[i].split("|")

    def search(self, query: str) -> np.ndarray:
        """Rows whose title contains the query (case-insensitive), most-rated first."""
        hits = self.films[self.films["title"].str.contains(query, case=False, regex=False)]
        return hits.sort_values("n_ratings", ascending=False).index.to_numpy()
