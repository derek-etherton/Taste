"""Open Library: matching a tiny synthetic dump, and joining the result onto a catalogue."""

import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from taste.model.openlibrary import enrich, info, plain

duckdb = pytest.importorskip("duckdb")  # the data extra: pip install -e ".[data]"
from sources.openlibrary import build, file_name, first_published  # noqa: E402

DATE = "2026-09-30"


def write(dump: Path, kind: str, lines: list) -> None:
    with gzip.open(dump / file_name(DATE, kind), "wt", encoding="utf-8") as f:
        for line in lines:
            if isinstance(line, dict):  # a record: type, key, revision, last_modified, JSON
                line = [line["type"]["key"], line["key"], "1", "2026-09-01T00:00:00", json.dumps(line)]
            f.write("\t".join(line) + "\n")


def rec(kind: str, key: str, **fields) -> dict:
    return {"type": {"key": f"/type/{kind}"}, "key": key, **fields}


@pytest.fixture
def dump(tmp_path) -> Path:
    d = tmp_path / "dump"
    d.mkdir()
    write(d, "works", [
        rec("work", "/works/OL1W", title="The Hobbit", authors=[{"author": {"key": "/authors/OL1A"}}],
            first_publish_date="January 1938", subjects=["Fantasy fiction", "series:Middle_earth"],
            subject_places=["Middle-earth"], description={"type": "/type/text", "value": "A hobbit goes there."},
            excerpts=[{"excerpt": "In a hole in the ground...", "comment": "first sentence"}], covers=[-1, 42],
            links=[{"title": "Wikipedia", "url": "https://en.wikipedia.org/wiki/The_Hobbit"}]),
        rec("work", "/works/OL2W", title="Emma", authors=[{"author": {"key": "/authors/OL2A"}}],
            series=[{"series": {"key": "/series/OL1L"}, "position": "3"}]),
        rec("work", "/works/OL3W", title="Emma", authors=[{"author": {"key": "/authors/OL3A"}}]),  # wrong author
        rec("work", "/works/OL5W", title="Unrelated", authors=[]),
    ])
    write(d, "editions", [
        rec("edition", "/books/OL1M", works=[{"key": "/works/OL9W"}], publish_date="September 21, 1937",
            identifiers={"goodreads": ["5907"]}, number_of_pages=310, languages=[{"key": "/languages/eng"}],
            isbn_13=["9780261102217"]),
        rec("edition", "/books/OL2M", works=[{"key": "/works/OL1W"}], publish_date="1066",  # a typo
            number_of_pages=300),
        rec("edition", "/books/OL3M", works=[{"key": "/works/OL2W"}], publish_date="1815",
            translated_from=[{"key": "/languages/fre"}]),
        rec("edition", "/books/OL4M", works=[{"key": "/works/OL5W"}], publish_date="2000"),
    ])
    write(d, "authors", [
        rec("author", "/authors/OL1A", name="J.R.R. Tolkien", birth_date="3 January 1892",
            remote_ids={"wikidata": "Q892"}),
        rec("author", "/authors/OL2A", name="Jane Austen"),
        rec("author", "/authors/OL3A", name="Somebody Else"),
    ])
    write(d, "redirects", [{"type": {"key": "/type/redirect"}, "key": "/works/OL9W", "location": "/works/OL1W"}])
    write(d, "other", [rec("series", "/series/OL1L", name="Austen Novels")])
    write(d, "ratings", [["/works/OL1W", "\\N", "5", "2020-01-01"], ["/works/OL1W", "\\N", "4", "2021-01-01"]])
    write(d, "reading-log", [["/works/OL1W", "\\N", "Already Read", "2020-01-01"],
                             ["/works/OL1W", "\\N", "Want to Read", "2020-01-01"]])
    return d


ITEMS = pd.DataFrame({"id": ["10", "20", "30"], "title": ["The Hobbit (Middle-earth, #0)", "Emma", "Nowhere"],
                      "creator": ["J.R.R. Tolkien", "Jane Austen", "Nobody"], "goodreads_id": ["5907", "1", "2"]})


def test_build(dump, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    s = build(ITEMS, dump, DATE, out)
    assert (s["matched"], s["by"], s["dump"]) == (2, {"goodreads": 1, "title": 1}, DATE)
    rows = pd.read_csv(out / "openlibrary.csv", dtype=str, keep_default_na=False).set_index("id")
    hobbit, emma = rows.loc["10"], rows.loc["20"]
    assert hobbit["ol_work"] == "OL1W" and hobbit["match"] == "goodreads"  # via the redirect OL9W -> OL1W
    assert hobbit["first_published"] == "1937"  # earliest edition; not the work's 1938, not the 1066 typo
    assert (hobbit["pages"], hobbit["isbn13"], hobbit["cover_id"]) == ("305", "9780261102217", "42")
    assert hobbit["subjects"] == "Fantasy fiction" and hobbit["ol_series"] == "Middle earth"
    assert hobbit["first_sentence"].startswith("In a hole") and hobbit["author_wikidata"] == "Q892"
    assert (hobbit["ol_ratings"], hobbit["ol_rating_mean"], hobbit["ol_readers"], hobbit["ol_want"]) == (
        "2", "4.5", "1", "1")
    assert emma["ol_work"] == "OL2W" and emma["match"] == "title"  # same title, right author
    assert (emma["ol_series"], emma["ol_series_index"], emma["original_language"]) == ("Austen Novels", "3", "fre")
    con = duckdb.connect(str(out / "openlibrary.duckdb"), read_only=True)  # our own copy, for later
    assert con.execute("SELECT count(*) FROM editions").fetchone()[0] == 3
    assert {t for (t,) in con.execute("SHOW TABLES").fetchall()} >= {
        "works", "editions", "authors", "series", "ratings", "reading_log", "meta"}


def test_first_published_ignores_typos():
    eds = [{"publish_date": "1066"}, {"publish_date": "c1990"}, {"publish_date": "3000"}]
    assert first_published({}, eds, 2026) == 1990
    lone = [{"publish_date": "1724"}, {"publish_date": "2012"}, {"publish_date": "2013"}]  # a modern novel
    assert first_published({}, lone, 2026) == 2012
    assert first_published({}, [{"publish_date": d} for d in ("1880", "1888", "1900")], 2026) == 1880
    twice = [{"publish_date": d} for d in ("1724", "1724", "2012", "2012")]
    assert first_published({}, twice, 2026) == 2012
    assert first_published({}, [{"publish_date": "1880"}, {"publish_date": "1950"}], 2026, born=1900) == 1950


def test_enrich_and_info(tmp_path):
    items = pd.DataFrame({"id": [1, 2, 3], "title": ["A", "B", "C"], "year": [2000.0, 2001.0, 2011.0],
                          "series": ["", "S", ""], "series_index": [float("nan"), 1.0, float("nan")]})
    assert enrich(items, tmp_path) is items  # no openlibrary.csv: unchanged
    pd.DataFrame([{"id": "1", "ol_work": "OL1W", "first_published": "1937", "ol_series": "Middle earth",
                   "ol_series_index": "2", "cover_id": "42", "authors": "Tolkien|Baynes", "author_birth": "1892|",
                   "author_death": "1973|", "subjects": "Fantasy|Dragons", "pages": "305",
                   "links": "Wikipedia=https://w.org/H"},
                  {"id": "3", "ol_work": "OL3W", "first_published": "2012"}]).to_csv(tmp_path / "openlibrary.csv", index=False)
    out = enrich(items, tmp_path)
    assert list(out["year"]) == [1937, 2001, 2011]  # never later than the dataset's edition
    assert list(out["series"]) == ["Middle earth", "S", ""]
    assert float(out["series_index"].iat[0]) == 2 and out["ol_work"].iat[1] == ""
    book = info(out.iloc[0])
    assert book["cover_url"].endswith("/42-M.jpg") and book["url"].endswith("/works/OL1W")
    assert book["authors"] == [{"name": "Tolkien", "birth": "1892", "death": "1973"},
                               {"name": "Baynes", "birth": None, "death": None}]
    assert book["subjects"] == ["Fantasy", "Dragons"] and book["pages"] == 305
    assert book["links"] == [{"title": "Wikipedia", "url": "https://w.org/H"}]
    assert info(out.iloc[1]) is None


def test_title_match_needs_the_same_author(dump, tmp_path):
    """Same title and surname, different first name: not the same book."""
    out = tmp_path / "out"
    out.mkdir()
    items = pd.DataFrame({"id": ["1"], "title": ["Emma"], "creator": ["Sarah Austen"], "goodreads_id": [""]})
    assert build(items, dump, DATE, out)["matched"] == 0


def test_plain_description():
    md = r"From [wikipedia](https://w.org/X):" + "\n\n" + r"Crime (IPA: \[prʲɪ\]) is **a novel**, serialised in 1866.[1](https://x)"
    assert plain(md) == "From wikipedia:\n\nCrime (IPA: [prʲɪ]) is a novel, serialised in 1866."
