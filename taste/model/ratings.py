"""User profiles, one file each in data/users/<name>.json: ratings across all domains, plus
the latest Describe Me.

Ratings are +1 like, 0 meh, -1 dislike, keyed "<domain>:<id>". Each save rewrites only its
own section and keeps the rest of the file.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from taste.model.catalog import DATA

USERS = DATA / "users"
MAIN = "main"
LEGACY_FILE = DATA / "user.json"  # the single profile from before there were several


def user_file(name: str, users: Path = USERS) -> Path:
    return users / f"{name}.json"


def list_users(users: Path = USERS) -> list[str]:
    """Profile names, main first. Moves a pre-profiles data/user.json to main.json."""
    users.mkdir(parents=True, exist_ok=True)
    if users == USERS and LEGACY_FILE.exists() and not user_file(MAIN).exists():
        LEGACY_FILE.replace(user_file(MAIN))
    names = sorted(p.stem for p in users.glob("*.json"))
    return [MAIN] + [n for n in names if n != MAIN]


@dataclass
class Description:
    text: str
    ratings: dict[str, int]  # the ratings it was written from
    created: str  # ISO timestamp


def _read(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _update(path: Path, **sections) -> None:
    path.write_text(json.dumps(_read(path) | sections, indent=1))


def load_ratings(path: Path) -> dict[str, int]:
    raw = _read(path).get("ratings", {})
    # Files from before domains existed hold bare film ids.
    return {(f"film:{k}" if k.isdigit() else k): v for k, v in raw.items()}


def save_ratings(ratings: dict[str, int], path: Path) -> None:
    _update(path, ratings=ratings)


def toggle_rating(ratings: dict[str, int], key: str, value: int) -> None:
    """Set a rating in place; giving the item its current rating again clears it."""
    if ratings.get(key) == value:
        ratings.pop(key)
    else:
        ratings[key] = value


def load_description(path: Path) -> Description | None:
    raw = _read(path).get("description")
    return Description(**raw) if raw else None


def save_description(text: str, ratings: dict[str, int], path: Path) -> Description:
    """Store a new description, replacing the previous one."""
    d = Description(text, dict(ratings), datetime.now().isoformat(timespec="seconds"))
    _update(path, description=asdict(d))
    return d
