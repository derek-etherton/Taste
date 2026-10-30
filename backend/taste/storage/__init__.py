"""Storage: per-user ratings, Describe Me and the last shelf scan, behind one interface."""

from taste.storage.base import Description, ProfileStore, ShelfScan
from taste.storage.json_store import MAIN, JsonProfileStore

__all__ = ["Description", "ProfileStore", "ShelfScan", "MAIN", "JsonProfileStore"]
