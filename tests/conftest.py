import pytest

from taste.model import Catalog, TraitSpace, available_domains


@pytest.fixture(scope="session")
def cats() -> dict[str, Catalog]:
    missing = {"film", "book"} - set(available_domains())
    if missing:
        pytest.skip(f"run scripts/prepare_data.py for: {', '.join(sorted(missing))}")
    return {d: Catalog(d) for d in ("film", "book")}


@pytest.fixture(scope="session")
def traits(cats) -> TraitSpace:
    return TraitSpace(cats)


def find(cat: Catalog, title: str) -> str:
    """Key of the most-rated item whose title is exactly `title` (or starts with "`title` (")."""
    t = cat.items["title"]
    hits = cat.items.index[(t == title) | t.str.startswith(title + " (")]
    assert len(hits), f"not found: {title}"
    return cat.key(int(min(hits, key=lambda i: cat.popularity_rank[i])))
