"""The user's ratings across all domains: +1 like, 0 meh, -1 dislike, keyed "<domain>:<id>"."""

import json
from pathlib import Path

from taste.model.catalog import DATA

USER_FILE = DATA / "user.json"


def load_ratings(path: Path = USER_FILE) -> dict[str, int]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())["ratings"]
    # Files from before domains existed hold bare film ids.
    return {(f"film:{k}" if k.isdigit() else k): v for k, v in raw.items()}


def save_ratings(ratings: dict[str, int], path: Path = USER_FILE) -> None:
    path.write_text(json.dumps({"ratings": ratings}, indent=1))


def toggle_rating(ratings: dict[str, int], key: str, value: int) -> None:
    """Set a rating in place; giving the item its current rating again clears it."""
    if ratings.get(key) == value:
        ratings.pop(key)
    else:
        ratings[key] = value
