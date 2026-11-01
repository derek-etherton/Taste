"""Request and response bodies. These define the OpenAPI spec the frontend's types are generated from."""

from typing import Literal

from pydantic import BaseModel, Field


class Domain(BaseModel):
    id: str  # "book" (and "film", with TASTE_DOMAINS)
    name: str  # "Films", "Books"
    items: int
    genome: str  # the active genome, e.g. "default"


class Because(BaseModel):
    tag: str
    from_other_domain: bool  # mostly carried over from ratings in another domain


class ItemCard(BaseModel):
    key: str  # "<domain>:<id>"; what ratings are keyed by
    label: str  # title with year, for display
    title: str
    year: int | None
    creator: str
    genres: list[str]
    series: str | None
    score: float  # predicted rating: about +1 like, 0 meh, -1 dislike (taste, plus the quality part)
    percentile: float  # share of unrated items this one beats
    rated: Literal[-1, 0, 1] | None
    because: list[Because]
    location: str | None = None  # shelf scan only: roughly where it is on the shelf
    similarity: float | None = None  # item pages' related items only: to the page's item, -1 to 1
    tag_match: float | None = None  # lists filtered by tags only: how strongly it has them, 0 to 1
    cover_url: str | None = None  # books with an Open Library cover


class ItemPage(BaseModel):
    items: list[ItemCard]
    total: int
    page: int
    page_size: int
    source: str  # where carried-over taste comes from, e.g. "films" ("" if none)


class TagContribution(BaseModel):
    tag: str
    contribution: float
    from_other_domain: bool


class Explanation(BaseModel):
    key: str
    label: str
    score: float
    percentile: float
    rated: Literal[-1, 0, 1] | None
    quality_part: float
    transferred_part: float  # carried over from other domains
    pulling_up: list[TagContribution]
    pushing_down: list[TagContribution]


class Evidence(BaseModel):
    item: str
    rating: Literal[-1, 0, 1]
    domain: str


class Claim(BaseModel):
    tag: str
    weight: float
    supporting: list[Evidence]
    contradicting: list[Evidence]


class Claims(BaseModel):
    respond_to: list[Claim]
    push_back_on: list[Claim]


class TagStrength(BaseModel):
    tag: str
    score: float  # how much the item has the tag, 0 to 1
    average: float  # the catalogue's average on the tag (weighted like the centring)


class Author(BaseModel):
    name: str
    birth: str | None  # as Open Library has it: "3 January 1892", "1892", ...
    death: str | None


class Link(BaseModel):
    title: str
    url: str


class BookInfo(BaseModel):
    """What Open Library knows about a book (see scripts/openlibrary.py)."""
    ol_work: str  # e.g. "OL27448W"
    url: str  # its Open Library page
    cover_url: str | None
    first_published: int | None  # earliest edition's year
    pages: int | None  # typical length across editions
    original_language: str | None  # MARC code, e.g. "eng", "fre", "rus"
    description: str | None
    first_sentence: str | None
    subjects: list[str]
    places: list[str]
    people: list[str]  # characters, or the real people a book is about
    times: list[str]
    authors: list[Author]
    links: list[Link]  # e.g. Wikipedia


class ItemDetail(BaseModel):
    """One item's page: its card, what sets it apart, why it scores what it does, and similar items."""
    card: ItemCard
    distinctive: list[TagStrength]  # the tags it has most above average, strongest first
    explanation: Explanation
    related: list[ItemCard]  # most similar items first, each with its similarity
    book: BookInfo | None = None  # books matched to Open Library only


class DomainSummary(BaseModel):
    domain: str
    name: str
    rated: int
    confidence: str  # e.g. "based on 30 films (20 liked, 3 meh, 7 disliked): reasonable confidence"


class DomainProfile(DomainSummary):
    claims: Claims  # taste learnt in this domain on top of what carried over


class Profile(BaseModel):
    user: str
    shared: Claims | None  # traits that carry across domains (None with a single domain)
    domains: list[DomainProfile]


class RatingIn(BaseModel):
    value: Literal[-1, 0, 1] = Field(description="1 like, 0 meh, -1 dislike")


class Ratings(BaseModel):
    ratings: dict[str, int]


class Spine(BaseModel):
    title: str
    author: str | None


class ScanProgress(BaseModel):
    done: int
    total: int


class ShelfScan(BaseModel):
    status: Literal["none", "running", "done", "failed"]
    progress: ScanProgress | None = None  # while running
    error: str | None = None  # when failed
    photo_name: str | None = None
    scanned: str | None = None
    books: list[ItemCard] = []  # recognised books, best for this user first, with locations
    unmatched: list[Spine] = []  # read but not in the catalogue
