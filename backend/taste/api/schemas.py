"""Request and response bodies. These define the OpenAPI spec the frontend's types are generated from."""

from typing import Literal

from pydantic import BaseModel, Field


class Domain(BaseModel):
    id: str  # "film", "book"
    name: str  # "Films", "Books"
    items: int


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
    more_in_series: int = 0  # other volumes of the series folded into this card
    percentile: float  # share of unrated items this one beats
    rated: Literal[-1, 0, 1] | None
    because: list[Because]
    location: str | None = None  # shelf scan only: roughly where it is on the shelf


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


class Description(BaseModel):
    text: str
    created: str
    stale: bool  # ratings have changed since it was written


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
