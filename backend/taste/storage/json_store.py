"""ProfileStore on JSON files: data/users/<name>.json per user, plus <name>.shelf.jpg for the
last scan's thumbnail. Each save rewrites only its own section of the file."""

import io
import json
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from taste.model.shelf import Spine, Where, load_image
from taste.settings import get_settings
from taste.storage.base import Description, ShelfScan

MAIN = "main"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class JsonProfileStore:
    def __init__(self, root: Path | None = None):
        data = get_settings().data_dir
        self.root = root or data / "users"
        self._lock = threading.Lock()  # the API serves requests on several threads
        legacy = data / "user.json"  # the single profile from before there were several
        if root is None and legacy.exists() and not self._file(MAIN).exists():
            self.root.mkdir(parents=True, exist_ok=True)
            legacy.replace(self._file(MAIN))

    def _file(self, user: str) -> Path:
        return self.root / f"{user}.json"

    def _image(self, user: str) -> Path:
        return self.root / f"{user}.shelf.jpg"

    def _read(self, user: str) -> dict:
        path = self._file(user)
        return json.loads(path.read_text()) if path.exists() else {}

    def _update(self, user: str, **sections) -> None:
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            self._file(user).write_text(json.dumps(self._read(user) | sections, indent=1))

    def users(self) -> list[str]:
        names = sorted(p.stem for p in self.root.glob("*.json")) if self.root.exists() else []
        return [MAIN] + [n for n in names if n != MAIN]

    def ratings(self, user: str) -> dict[str, int]:
        raw = self._read(user).get("ratings", {})
        # Files from before domains existed hold bare film ids.
        return {(f"film:{k}" if k.isdigit() else k): v for k, v in raw.items()}

    def set_rating(self, user: str, key: str, value: int) -> dict[str, int]:
        ratings = self.ratings(user) | {key: value}
        self._update(user, ratings=ratings)
        return ratings

    def clear_rating(self, user: str, key: str) -> dict[str, int]:
        ratings = self.ratings(user)
        if ratings.pop(key, None) is not None:
            self._update(user, ratings=ratings)
        return ratings

    def description(self, user: str) -> Description | None:
        raw = self._read(user).get("description")
        return Description(**raw) if raw else None

    def save_description(self, user: str, text: str, ratings: dict[str, int]) -> Description:
        d = Description(text, dict(ratings), now())
        self._update(user, description=asdict(d))
        return d

    def scan(self, user: str) -> ShelfScan | None:
        raw = self._read(user).get("shelf_scan")
        if not raw:
            return None
        spines = [Spine(s["title"], s.get("author"), Where(**s["where"]) if s.get("where") else None)
                  for s in raw["spines"]]
        return ShelfScan(raw["id"], raw["photo_name"], raw["scanned"], spines)

    def save_scan(self, user: str, scan_id: str, photo_name: str, spines: list[Spine],
                  image: bytes) -> ShelfScan:
        thumb = load_image(image)
        thumb.thumbnail((800, 800))
        self.root.mkdir(parents=True, exist_ok=True)
        thumb.save(self._image(user), format="JPEG", quality=85)
        scan = ShelfScan(scan_id, photo_name, now(), spines)
        self._update(user, shelf_scan={
            "id": scan.id, "photo_name": photo_name, "scanned": scan.scanned,
            "spines": [{"title": s.title, "author": s.author, "where": asdict(s.where) if s.where else None}
                       for s in spines],
        })
        return scan

    def scan_image(self, user: str) -> bytes | None:
        path = self._image(user)
        return path.read_bytes() if path.exists() else None
