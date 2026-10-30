"""Model layer: catalogues and the taste maths. No UI or storage code here."""

from taste.model.catalog import DATA, DOMAINS, Catalog, available_domains
from taste.model.traits import SHARE, TRAITS_FILE, TraitSpace
from taste.model.user_model import TEACH_POOL, Evidence, Explanation, Prior, TagClaim, UserModel

__all__ = [
    "DATA", "DOMAINS", "Catalog", "available_domains",
    "SHARE", "TRAITS_FILE", "TraitSpace",
    "TEACH_POOL", "Evidence", "Explanation", "Prior", "TagClaim", "UserModel",
]
