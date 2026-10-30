"""Model layer: data, ratings storage and the user taste model. No UI code here."""

from taste.model.catalog import DATA, DOMAINS, Catalog, available_domains
from taste.model.ratings import (USERS, Description, list_users, load_description, load_ratings, save_description,
                                 save_ratings, toggle_rating, user_file)
from taste.model.traits import SHARE, TRAITS_FILE, TraitSpace
from taste.model.user_model import TEACH_POOL, Evidence, Explanation, Prior, TagClaim, UserModel

__all__ = [
    "DATA", "DOMAINS", "Catalog", "available_domains",
    "USERS", "Description", "list_users", "load_description", "load_ratings", "save_description", "save_ratings",
    "toggle_rating", "user_file",
    "SHARE", "TRAITS_FILE", "TraitSpace",
    "TEACH_POOL", "Evidence", "Explanation", "Prior", "TagClaim", "UserModel",
]
