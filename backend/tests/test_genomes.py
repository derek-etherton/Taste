"""Genomes: reading a BookGenome release, film links derived from its tags, switching at runtime."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from conftest import find
from taste.api.app import create_app
from taste.api.engine import Engine
from taste.model import UserModel, genomes
from taste.model.bookgenome import link, norm_author, norm_title
from taste.model.genomes import load
from taste.model.traits import compose
from taste.storage import JsonProfileStore

# Gutenberg-style titles of books the default catalogue has, and one it doesn't.
BOOKS = [("robinson-crusoe", "The Life and Adventures of Robinson Crusoe", "Daniel Defoe"),
         ("huckleberry-finn", "Adventures of Huckleberry Finn", "Mark Twain"),
         ("hobbit", "The Hobbit; or, There and Back Again", "J. R. R. Tolkien"),
         ("queen-lucia", "Queen Lucia", "E. F. Benson")]
TAGS = {"adventure": ["adventure"], "satire": ["satire"], "comic": ["funny", "humor"],
        "dragons and magic": ["magic", "dragons"], "seafaring": []}


def write_release(path: Path, books=BOOKS, tags=TAGS, seed=0) -> Path:
    path.mkdir(parents=True)
    (path / "genome.json").write_text(json.dumps({"name": path.name, "description": "a test release"}))
    pd.DataFrame([{"book": b, "title": t, "author": a, "words": 1000, "gutenberg_id": 1, "source_file": f"{b}.txt",
                   "scored_on": "2026-10-31", "scored_by": "test"} for b, t, a in books]).to_csv(path / "books.csv", index=False)
    pd.DataFrame({"tag": list(tags), "derived_from": ["|".join(s) for s in tags.values()]}).to_csv(path / "tags.csv", index=False)
    scores = np.random.default_rng(seed).integers(0, 101, (len(books), len(tags))) / 100
    scores[0] = 0  # 0 is a judgement ("no trace"), not missing data
    pd.DataFrame(scores, columns=list(tags)).assign(book=[b for b, _, _ in books])[["book", *tags]].to_csv(
        path / "scores.csv", index=False)
    return path


# --- the connector, without the real data ------------------------------------------------------

def test_normalising():
    assert norm_title("The Hobbit; or, There and Back Again") == norm_title("The Hobbit (Middle-earth, #0)") == "hobbit"
    assert norm_title("Nostromo: A Tale of the Seaboard") == "nostromo"
    assert norm_title("D'Ri and I") == "dri and i"
    assert norm_author("L. M. Montgomery") == norm_author("L.M. Montgomery") == "montgomery"
    assert norm_author("abbé Prévost") == "prevost"
    assert norm_author("Stephen King, Peter Straub") == "king"


def test_link_prefers_exact_then_suffix_and_most_rated():
    base = pd.DataFrame({"title": ["Robinson Crusoe", "The Hobbit", "The Hobbit (Illustrated)", "Emma"],
                         "creator": ["Daniel Defoe", "J.R.R. Tolkien", "J.R.R. Tolkien", "Jane Austen"],
                         "n_ratings": [10, 5, 50, 1]})
    books = pd.DataFrame({"title": ["The Life and Adventures of Robinson Crusoe", "The Hobbit", "The Hobbit", "Emma"],
                          "author": ["Daniel Defoe", "J. R. R. Tolkien", "J. R. R. Tolkien", "Somebody Else"]})
    assert link(books, base) == [0, 2, 1, None]  # each base row once; the author must match


def test_compose_film_links():
    spec = [{"film": "adventure", "book": "adventure"}, {"film": "alcoholism", "book": "alcoholism"},
            {"film": "drinking", "book": "drinking"}, {"film": "gone", "book": "gone"}]
    out = compose(spec, "book", {"adventure": ["adventure"], "drink": ["alcoholism", "drinking"],
                                 "alcoholism": ["drinking", "alcoholism"], "new": []})
    assert {t["book"]: t["film"] for t in out} == {
        "adventure": "adventure",
        "alcoholism": "alcoholism",  # the exact name wins over the earlier-listed source...
        "drink": "drinking",  # ...so this one falls back to its other source
    }  # "new" has no source: book-only; "gone" has no derived tag: dropped


def test_genome_with_no_rating_data(tmp_path):
    """No default book catalogue to link to: every book is new, with neutral quality and weight."""
    release = write_release(tmp_path / "rel")
    data = tmp_path / "data"
    data.mkdir()
    options = genomes("book", data, releases=[release])
    assert list(options) == ["rel"] and options["rel"].kind == "bookgenome"
    cat = load(options["rel"], data)
    assert cat.keys == [f"book:gb-{b}" for b, _, _ in BOOKS] and cat.linked == 0
    assert (cat.quality == 0).all() and (cat.weights == 1).all()
    assert np.allclose(cat.relevance.mean(axis=0), 0, atol=1e-6) and np.isfinite(cat.relevance).all()
    model = UserModel(cat, {cat.keys[1]: 1})
    assert len(model.ranked()) == 3 and len(model.teaching_order()) == 3


# --- the API, with the real data ---------------------------------------------------------------

@pytest.fixture(scope="module")
def release(tmp_path_factory) -> Path:
    return write_release(tmp_path_factory.mktemp("genomes") / "testgenome")


@pytest.fixture(scope="module")
def client(tmp_path_factory, cats, release):  # cats: skips the module if the data isn't prepared
    engine = Engine(store=JsonProfileStore(tmp_path_factory.mktemp("users")), releases=[release],
                    genome={"book": "default"})
    return TestClient(create_app(engine))


def switch(client, genome: str) -> dict:
    r = client.put("/genomes/book", json={"genome": genome})
    assert r.status_code == 200, r.text
    return r.json()


def test_list_and_switch(client, cats):
    book = {g["domain"]: g for g in client.get("/genomes").json()}["book"]
    assert book["active"] == "default" and book["linked"] is None
    names = [o["name"] for o in book["options"]]  # plus whatever is in data/genomes/book/
    assert names[0] == "default" and "testgenome" in names
    assert book["items"] == len(cats["book"]) and book["traits"] == 512

    out = switch(client, "testgenome")
    assert (out["active"], out["items"], out["tags"], out["linked"]) == ("testgenome", 4, 5, 3)
    assert {d["id"]: d["genome"] for d in client.get("/domains").json()}["book"] == "testgenome"
    titles = {c["title"] for c in client.get("/profiles/main/book/items").json()["items"]}
    assert "Queen Lucia" in titles and len(titles) == 4  # every release book, linked or not
    assert client.get("/profiles/main/film/items").status_code == 200  # films still work

    assert client.put("/genomes/book", json={"genome": "nope"}).status_code == 404
    assert client.put("/genomes/music", json={"genome": "default"}).status_code == 404
    switch(client, "default")


def test_derived_film_links(client):
    switch(client, "testgenome")
    traits = client.app.state.engine.traits
    pairs = {(traits.names[i], traits.cats["book"].tags[c]) for i, c in enumerate(traits.cols["book"])}
    assert pairs == {("adventure", "adventure"), ("satire", "satire"), ("funny", "comic"), ("magic", "dragons and magic")}
    assert {g["domain"]: g["traits"] for g in client.get("/genomes").json()} == {"film": 4, "book": 4}
    switch(client, "default")


def test_ratings_survive_round_trip(client, cats):
    huck = find(cats["book"], "The Adventures of Huckleberry Finn")
    rate = lambda key: client.put(f"/profiles/trip/ratings/{key}", json={"value": 1})
    rated = lambda: {c["key"] for c in client.get("/profiles/trip/book/rated").json()}

    assert rate(huck).status_code == 200  # rated in the default genome...
    switch(client, "testgenome")
    assert rated() == {huck}  # ...carries over to the same book in the release
    assert rate("book:gb-queen-lucia").status_code == 200
    assert rated() == {huck, "book:gb-queen-lucia"}

    switch(client, "default")
    assert rated() == {huck}  # Queen Lucia isn't here: hidden, not lost
    assert rate("book:gb-queen-lucia").status_code == 404
    assert "book:gb-queen-lucia" in client.app.state.engine.store.ratings("trip")

    switch(client, "testgenome")
    assert rated() == {huck, "book:gb-queen-lucia"}
    switch(client, "default")
