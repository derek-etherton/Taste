"""Create test profiles in data/users/ from lists of titles.

    python scripts/seed_profiles.py            # creates any that don't exist yet
    python scripts/seed_profiles.py --force    # overwrites them (their ratings and description)

Titles are matched exactly, ignoring a trailing bracket ("(Series, #1)", an alternate
title), most-rated first.
"""

import argparse

from taste.model import Catalog
from taste.storage import JsonProfileStore

# profile -> domain -> rating -> titles
PROFILES = {
    "normie": {
        "film": {
            1: ["Titanic", "Avatar", "The Avengers", "Forrest Gump", "The Lion King", "Shrek",
                "Finding Nemo", "Jurassic Park", "Pirates of the Caribbean: The Curse of the Black Pearl",
                "Frozen", "The Dark Knight", "Toy Story"],
            0: ["Inception", "The Shawshank Redemption"],
            -1: ["2001: A Space Odyssey", "Mulholland Drive", "Eraserhead", "Synecdoche, New York",
                 "The Seventh Seal", "Stalker"],
        },
        "book": {
            1: ["Harry Potter and the Sorcerer's Stone", "The Da Vinci Code", "The Hunger Games",
                "Gone Girl", "The Fault in Our Stars", "Twilight"],
            -1: ["Ulysses", "Moby-Dick or, The Whale", "Infinite Jest", "Gravity's Rainbow"],
        },
    },
    "romantic": {
        "film": {
            1: ["The Notebook", "Pride & Prejudice", "Before Sunrise", "Notting Hill",
                "When Harry Met Sally...", "Titanic", "Amelie", "La La Land", "Love Actually",
                "Sense and Sensibility", "Casablanca", "Eternal Sunshine of the Spotless Mind"],
            0: ["The Princess Bride"],
            -1: ["Saw", "The Texas Chainsaw Massacre", "Die Hard", "Mad Max: Fury Road",
                 "First Blood", "The Human Centipede"],
        },
        "book": {
            1: ["Pride and Prejudice", "Me Before You", "The Notebook", "Outlander", "Jane Eyre",
                "Persuasion", "The Time Traveler's Wife"],
            -1: ["It", "American Psycho", "Blood Meridian, or the Evening Redness in the West"],
        },
    },
}


def find(cat: Catalog, title: str) -> str | None:
    t = cat.items["title"]
    base = t.str.replace(r"\s*\([^()]*\)$", "", regex=True)  # drop "(Series, #1)" or an alternate title
    hits = cat.items.index[(t == title) | (base == title)]
    return cat.key(int(min(hits, key=lambda i: cat.popularity_rank[i]))) if len(hits) else None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="overwrite existing test profiles")
    args = p.parse_args()
    cats = {d: Catalog.load(d) for d in {d for spec in PROFILES.values() for d in spec}}
    store = JsonProfileStore()
    for name, spec in PROFILES.items():
        if name in store.users() and not args.force:
            print(f"{name}: exists, skipped (use --force to overwrite)")
            continue
        ratings, missing = {}, []
        for domain, by_rating in spec.items():
            for value, titles in by_rating.items():
                for title in titles:
                    key = find(cats[domain], title)
                    if key:
                        ratings[key] = value
                    else:
                        missing.append(f"{domain}: {title}")
        for f in store.root.glob(f"{name}.*"):  # a fresh profile: no old description or scan
            f.unlink()
        for key, value in ratings.items():
            store.set_rating(name, key, value)
        print(f"{name}: {len(ratings)} ratings" + (f"; not found: {missing}" if missing else ""))


if __name__ == "__main__":
    main()
