"""What gets stored per user, and the interface any storage backend implements.

The model layer never touches storage; the API reads and writes through a ProfileStore,
keyed by user id. SqlProfileStore (sql_store.py) is the implementation.
"""

from dataclasses import dataclass
from typing import Protocol

from taste.model.shelf import Spine


@dataclass
class Description:
    """The latest Describe Me reading."""
    text: str
    ratings: dict[str, int]  # the ratings it was written from
    created: str  # ISO timestamp


@dataclass
class ShelfScan:
    """A user's last shelf scan. Only the readings are stored: matching and ranking are
    redone on load, so they follow the catalogue and the user's current ratings."""
    id: str  # identifies the upload it came from
    photo_name: str
    scanned: str  # ISO timestamp
    spines: list[Spine]


class ProfileStore(Protocol):
    def ratings(self, user: str) -> dict[str, int]:
        """Ratings keyed "<domain>:<id>": +1 like, 0 meh, -1 dislike."""

    def set_rating(self, user: str, key: str, value: int) -> dict[str, int]:
        """Set one rating; returns all of the user's ratings."""

    def clear_rating(self, user: str, key: str) -> dict[str, int]:
        """Remove one rating (no-op if absent); returns all of the user's ratings."""

    def description(self, user: str) -> Description | None: ...

    def save_description(self, user: str, text: str, ratings: dict[str, int]) -> Description:
        """Store a new Describe Me, replacing the previous."""

    def scan(self, user: str) -> ShelfScan | None: ...

    def save_scan(self, user: str, scan_id: str, photo_name: str, spines: list[Spine],
                  image: bytes) -> ShelfScan:
        """Store a scan as the user's last one (with a thumbnail of the photo), replacing the previous."""

    def scan_image(self, user: str) -> bytes | None:
        """The last scan's thumbnail as JPEG bytes."""
