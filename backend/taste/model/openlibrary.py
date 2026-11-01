"""Open Library metadata for books: data/book/openlibrary.csv, written by scripts/openlibrary.py.

One row per catalogue item that was matched to an Open Library work. Joined onto the items
when a catalogue is read: the first-publication year replaces the dataset's (an edition's
year, often a reprint) when earlier, and a series is filled in where the title didn't name one.
"""

import re
from pathlib import Path

import pandas as pd

FILE = "openlibrary.csv"
LISTS = ["subjects", "subject_places", "subject_people", "subject_times", "authors", "author_birth",
         "author_death", "links"]  # "|"-separated; links are "title=url"
COVER = "https://covers.openlibrary.org/b/id/{}-{}.jpg"  # cover ID, size: S, M or L
WORK = "https://openlibrary.org/works/{}"


def read(src: Path) -> pd.DataFrame | None:
    path = src / FILE
    if not path.exists():
        return None
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")


def enrich(items: pd.DataFrame, src: Path) -> pd.DataFrame:
    """The items with their Open Library columns, if src has an openlibrary.csv."""
    ol = read(src)
    if ol is None:
        return items
    ol = ol.drop_duplicates("id").set_index("id")
    ol = ol.drop(columns=[c for c in ol.columns if c in items.columns])  # e.g. goodreads_id: the items' own
    out = items.join(ol, on=items["id"].astype(str))
    # The dataset's year is some edition's, so the first edition can't be later: Open Library
    # lacks the first editions of many ebook-first books.
    first = pd.to_numeric(out["first_published"], errors="coerce")
    out["year"] = pd.concat([first, pd.to_numeric(out["year"], errors="coerce")], axis=1).min(axis=1)
    if "series" in out:
        blank = out["series"].fillna("").eq("") & out["ol_series"].fillna("").ne("")
        out["series"] = out["series"].where(~blank, out["ol_series"])
        out["series_index"] = out["series_index"].where(~blank, out["ol_series_index"])  # Catalog parses it
    return out.fillna({c: "" for c in ol.columns})


def plain(text: str) -> str:
    """Open Library descriptions are often Markdown: keep link text (dropping footnote links
    like [1](...)), and drop escapes and emphasis."""
    text = re.sub(r"\[\d+\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!])", r"\1", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def cover(items: pd.DataFrame, i: int, size: str = "M") -> str | None:
    """Row i's cover image (S, M or L), if Open Library has one."""
    cid = items["cover_id"].iat[i] if "cover_id" in items else ""
    return COVER.format(cid, size) if cid else None


def info(row: pd.Series) -> dict | None:
    """What the item page shows about a book, or None if it has no Open Library match."""
    work = row.get("ol_work", "")
    if not work:
        return None
    split = lambda c: [s for s in str(row.get(c, "")).split("|") if s]
    names, births, deaths = split("authors"), str(row.get("author_birth", "")).split("|"), str(
        row.get("author_death", "")).split("|")
    links = [dict(zip(("title", "url"), s.split("=", 1))) for s in split("links") if "=" in s]
    number = lambda c: int(float(row[c])) if str(row.get(c, "")).strip() else None
    return {
        "ol_work": work, "url": WORK.format(work),
        "cover_url": COVER.format(row["cover_id"], "M") if row.get("cover_id") else None,
        "first_published": number("first_published"), "pages": number("pages"),
        "original_language": row.get("original_language") or None,
        "description": plain(row.get("description", "")) or None,
        "first_sentence": plain(row.get("first_sentence", "")) or None,
        "subjects": split("subjects"), "places": split("subject_places"), "people": split("subject_people"),
        "times": split("subject_times"),
        "authors": [{"name": n, "birth": (births[i] if i < len(births) else "") or None,
                     "death": (deaths[i] if i < len(deaths) else "") or None} for i, n in enumerate(names)],
        "links": links,
    }
