"""Model layer: data, ratings storage and the user taste model. No UI code here."""

from taste.model.catalog import DATA, Catalog
from taste.model.ratings import USER_FILE, load_ratings, save_ratings, toggle_rating
from taste.model.user_model import TEACH_MIN_RATINGS, Explanation, TagClaim, UserModel

__all__ = [
    "DATA", "Catalog",
    "USER_FILE", "load_ratings", "save_ratings", "toggle_rating",
    "TEACH_MIN_RATINGS", "Explanation", "TagClaim", "UserModel",
]
