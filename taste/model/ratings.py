"""The user's ratings: +1 like, 0 meh, -1 dislike, keyed by movieId."""

import json
from pathlib import Path

from taste.model.catalog import DATA

USER_FILE = DATA / "user.json"


def load_ratings(path: Path = USER_FILE) -> dict[int, int]:
    if not path.exists():
        return {}
    return {int(k): v for k, v in json.loads(path.read_text())["ratings"].items()}


def save_ratings(ratings: dict[int, int], path: Path = USER_FILE) -> None:
    path.write_text(json.dumps({"ratings": {str(k): v for k, v in ratings.items()}}, indent=1))


def toggle_rating(ratings: dict[int, int], movie_id: int, value: int) -> None:
    """Set a rating in place; giving the film its current rating again clears it."""
    if ratings.get(movie_id) == value:
        ratings.pop(movie_id)
    else:
        ratings[movie_id] = value
