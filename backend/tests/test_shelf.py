"""Shelf scan: reading (stubbed, no network), matching to the catalogue, and ranking."""

import io
import json

import pytest
from PIL import Image

import taste.model.shelf as shelf
from conftest import find
from taste.model import UserModel
from taste.model.llm import LLMError
from taste.model.shelf import Spine, match_spines, normalise, parse_spines, rank_matches, read_spines


def matched(cat, *spines):
    return [cat.label(m.row) if m.row is not None else None for m in match_spines(list(spines), cat)]


def test_normalise():
    assert normalise("The Hunger Games (The Hunger Games, #1)") == "hunger games"
    assert normalise("Pride & Prejudice") == "pride and prejudice"
    assert normalise("Ender's Game") == "enders game"


def test_matches_despite_ocr_noise(cats):
    book = cats["book"]
    labels = matched(book, Spine("MORNING STAR", "PIERCE BROWN"), Spine("Evicted"), Spine("Orxy and Crake"),
                     Spine("Hunger Games"), Spine("Pride & Prejudice", "Austen"))
    assert labels[0].startswith("Morning Star (Red Rising")  # caps, series bracket
    assert labels[1].startswith("Evicted: Poverty and Profit")  # subtitle left off the spine
    assert labels[2].startswith("Oryx and Crake")  # typo
    assert labels[3].startswith("The Hunger Games (The Hunger Games, #1)")  # missing article
    assert labels[4].startswith("Pride and Prejudice")


def test_author_breaks_ties_and_sinks_fuzzy_titles(cats):
    book = cats["book"]
    assert book.creator(match_spines([Spine("The Road", "Cormac McCarthy")], book)[0].row) == "Cormac McCarthy"
    assert matched(book, Spine("The Shining", "Jane Austen"))[0].startswith("The Shining")  # exact title survives
    assert matched(book, Spine("The Shinning", "Jane Austen")) == [None]  # fuzzy title + wrong author doesn't


def test_swapped_title_and_author(cats):
    assert matched(cats["book"], Spine("Orson Scott Card", "Ender's Game"))[0].startswith("Ender's Game")


def test_unknown_books_stay_unmatched(cats):
    assert matched(cats["book"], Spine("A Small Press Debut Nobody Has Heard Of", "Jo Bloggs")) == [None]


def test_each_book_matched_once(cats):
    book = cats["book"]
    rows = [m.row for m in match_spines([Spine("The Shining"), Spine("The Shining")], book)]
    assert rows[0] is not None and rows[0] != rows[1]


def test_rank_follows_the_profile(cats, traits):
    book = cats["book"]
    likes = {find(book, t): 1 for t in ["The Hobbit", "A Game of Thrones", "The Name of the Wind"]}
    model = UserModel(book, likes, prior=traits.prior("book", likes))
    matches = match_spines([Spine("Me Before You"), Spine("The Way of Kings"), Spine("Gone Girl")], book)
    ranked = rank_matches(matches, model)
    assert sorted(ranked) == sorted(m.row for m in matches)
    assert list(ranked) == list(model.ranked(rows=[m.row for m in matches]))
    assert book.label(ranked[0]).startswith("The Way of Kings")  # the fantasy fan's pick


def test_parse_spines_is_tolerant():
    assert parse_spines('{"books": [{"title": "Dune", "author": null}, {"title": " ", "author": "x"}]}') == \
        [Spine("Dune")]
    assert parse_spines('Sure! [{"title": "Dune", "author": "Frank Herbert"}]') == [Spine("Dune", "Frank Herbert")]
    with pytest.raises(LLMError):
        parse_spines("I can't see any books.")


def test_read_spines_drops_duplicates():
    reader = lambda image: [Spine("Dune"), Spine("DUNE", "Herbert"), Spine("Emma")]
    assert read_spines(b"", reader) == [Spine("Dune"), Spine("Emma")]


def photo(width: int, height: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


def test_reads_each_shelf_row_in_pieces():
    """Rows are located on an overview, then each wide row is read in overlapping pieces."""
    calls = []

    def chat(prompt, image, schema, options):
        calls.append((schema, image.size))
        if schema is shelf.ROWS_SCHEMA:
            return json.dumps({"rows": [{"bbox_2d": [0, 100, 1000, 200]}, {"bbox_2d": [0, 500, 1000, 600]}]})
        return json.dumps({"books": [{"title": f"Book {len(calls)}", "author": None}]})

    progress = []
    spines = shelf.ollama_vision(photo(3000, 4000), progress=lambda d, n: progress.append((d, n)), chat=chat)
    overview, reads = calls[0], calls[1:]
    assert overview[0] is shelf.ROWS_SCHEMA and max(overview[1]) == shelf.MAX_SIDE
    assert len(reads) >= 4  # two rows, each 3000 x ~520 px, cut into several pieces
    assert all(w / h <= shelf.PIECE_ASPECT * 1.25 for _, (w, h) in reads)
    assert len(spines) == len(reads) and progress[-1] == (len(reads), len(reads))


def test_no_rows_found_reads_whole_photo():
    def chat(prompt, image, schema, options):
        return '{"rows": []}' if schema is shelf.ROWS_SCHEMA else '{"books": [{"title": "Dune", "author": null}]}'

    assert shelf.ollama_vision(photo(800, 600), chat=chat) == [Spine("Dune")]


def test_truncated_reply_keeps_complete_entries():
    reply = '{"books": [{"title": "Dune", "author": null}, {"title": "Emma", "author": "Jane Austen"}, {"title": "Th'
    assert parse_spines(reply) == [Spine("Dune"), Spine("Emma", "Jane Austen")]


def test_author_read_as_title_is_dropped():
    assert parse_spines('{"books": [{"title": "STEPHEN KING", "author": "Stephen King"}]}') == []


def test_location_in_words():
    from taste.model.shelf import Where, location
    assert location(Where(0, 5, 0.1)) == "Top shelf, on the left"
    assert location(Where(1, 5, 0.5)) == "2nd shelf from the top, in the middle"
    assert location(Where(4, 5, 0.9)) == "Bottom shelf, on the right"
    assert location(Where(0, 1, 0.5)) == "In the middle"  # one shelf (or none found): side only
    assert location(None) == ""


def test_spines_remember_their_shelf_and_side():
    def chat(prompt, image, schema, options):
        if schema is shelf.ROWS_SCHEMA:
            return json.dumps({"rows": [{"bbox_2d": [0, 100, 1000, 200]}, {"bbox_2d": [0, 500, 1000, 600]}]})
        return json.dumps({"books": [{"title": "Left", "author": None}, {"title": "Right", "author": None}]})

    spines = shelf.ollama_vision(photo(1200, 1600), chat=chat)
    top = [s for s in spines if s.where.row == 0]
    assert {s.where.rows for s in spines} == {2} and top and len(top) < len(spines)
    assert top[0].where.x < 0.5 < top[-1].where.x  # first read in a row is leftmost
