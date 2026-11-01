"""HTTP routes. Thin: validate, call the engine or model, shape the response."""

from typing import Annotated, Literal

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, Request, Response, UploadFile

from taste.api import schemas
from taste.api.engine import Engine
from taste.model.describe import taste_brief
from taste.model import openlibrary
from taste.model.llm import LLMError
from taste.model.user_model import TagClaim, claims

router = APIRouter()

# User names become file names in the JSON store: keep them simple.
User = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")]
Quality = Annotated[float, Query(ge=0, le=1, description="Weight on general quality; 0 = pure taste match")]


def engine(request: Request) -> Engine:
    return request.app.state.engine


E = Annotated[Engine, Depends(engine)]


def catalog_or_404(e: Engine, domain: str):
    if domain not in e.cats:
        raise HTTPException(404, f"No such domain: {domain}")
    return e.cats[domain]


def row_or_404(cat, key: str) -> int:
    if key not in cat.row:
        raise HTTPException(404, f"No such item: {key}")
    return cat.row[key]


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.get("/domains")
def domains(e: E) -> list[schemas.Domain]:
    return [schemas.Domain(id=d, name=c.name, items=len(c), genome=c.genome) for d, c in e.cats.items()]


# --- genomes ----------------------------------------------------------------------------------

def genomes_out(e: Engine, domain: str) -> schemas.Genomes:
    cat = catalog_or_404(e, domain)
    traits = e.traits
    return schemas.Genomes(
        domain=domain, active=cat.genome, items=len(cat), tags=len(cat.tags), linked=cat.linked,
        traits=len(traits) if traits and domain in traits.domains else 0,
        options=[schemas.GenomeOption(name=g.name, kind=g.kind, description=g.description)
                 for g in e.genomes(domain).values()],
    )


@router.get("/genomes")
def list_genomes(e: E) -> list[schemas.Genomes]:
    """Each domain's available genomes and the active one."""
    return [genomes_out(e, d) for d in e.cats]


@router.put("/genomes/{domain}")
def switch_genome(domain: str, body: schemas.GenomeIn, e: E) -> schemas.Genomes:
    """Rebuild a domain's catalogue from another genome, for every user (a testing switch).
    Ratings stay saved; items the genome lacks don't appear until you switch back."""
    catalog_or_404(e, domain)
    try:
        e.switch_genome(domain, body.genome)
    except KeyError as err:
        raise HTTPException(404, err.args[0])
    return genomes_out(e, domain)


@router.get("/profiles")
def profiles(e: E) -> list[str]:
    return e.store.users()


@router.get("/profiles/{user}")
def summary(user: User, e: E) -> list[schemas.DomainSummary]:
    models = e.models(e.store.ratings(user))
    return [schemas.DomainSummary(domain=d, name=m.cat.name, rated=len(m.rows), confidence=m.confidence())
            for d, m in models.items()]


# --- browsing ---------------------------------------------------------------------------------

@router.get("/profiles/{user}/{domain}/items")
def items(user: User, domain: str, e: E, mode: Literal["for_you", "rate"] = "for_you",
          q: str = "", page: Annotated[int, Query(ge=1)] = 1,
          page_size: Annotated[int, Query(ge=1, le=100)] = 25, quality: Quality = 0.1,
          tags: Annotated[list[str], Query(max_length=10)] = []) -> schemas.ItemPage:
    """For you: unrated items, best match first. Rate: what rating would teach the profile most.
    A search (q) covers the whole catalogue, rated items included. Each volume of a series is its own item.
    With tags, the order is tag_match × the item's percentile in the mode's own order: a soft AND,
    so what comes first both has the tags and is high on your list."""
    cat = catalog_or_404(e, domain)
    if unknown := [t for t in tags if t not in cat.tags]:
        raise HTTPException(422, f"No such tag in {domain}: {', '.join(unknown)}")
    ratings = e.store.ratings(user)
    model = e.models(ratings)[domain]
    hits = cat.search(q.strip()) if q.strip() else None
    pool = model.ranked(quality, rows=hits) if mode == "for_you" else model.teaching_order(rows=hits)
    match = cat.tag_match(tags) if tags else None
    if match is not None:
        percentile = 1 - np.arange(len(pool)) / max(len(pool) - 1, 1)  # 1 for the mode's top item, 0 for its last
        pool = pool[np.argsort(-match[pool] * percentile, kind="stable")]
    start = (page - 1) * page_size
    shown = pool[start:start + page_size]
    cards = e.cards(model, shown, quality)
    if match is not None:
        cards = [c.model_copy(update={"tag_match": round(float(match[i]), 3)}) for c, i in zip(cards, shown)]
    return schemas.ItemPage(items=cards, total=len(pool), page=page, page_size=page_size,
                            source=e.source(domain, ratings))


@router.get("/domains/{domain}/tags")
def tags(domain: str, e: E) -> list[str]:
    """The active genome's tags for a domain, alphabetical: what the list can be filtered by."""
    return sorted(catalog_or_404(e, domain).tags, key=str.lower)


@router.get("/profiles/{user}/{domain}/items/{key}")
def item(user: User, domain: str, key: str, e: E, quality: Quality = 0.1,
         related: Annotated[int, Query(ge=0, le=50)] = 10) -> schemas.ItemDetail:
    """An item's page: card, distinctive tags, the score breakdown, and the most similar items."""
    cat = catalog_or_404(e, domain)
    i = row_or_404(cat, key)
    model = e.models(e.store.ratings(user))[domain]
    similar, similarity = cat.similar(i)[:related], cat.similarity(i)
    return schemas.ItemDetail(
        card=e.cards(model, [i], quality)[0],
        distinctive=[schemas.TagStrength(tag=t, score=round(s, 3), average=round(a, 3))
                     for t, s, a in cat.distinctive(i)],
        explanation=explanation(user, domain, key, e, quality),
        related=[c.model_copy(update={"similarity": round(float(similarity[r]), 3)})
                 for c, r in zip(e.cards(model, similar, quality), similar)],
        book=openlibrary.info(cat.items.iloc[i]),
    )


@router.get("/profiles/{user}/{domain}/items/{key}/explanation")
def explanation(user: User, domain: str, key: str, e: E, quality: Quality = 0.1) -> schemas.Explanation:
    """Why an item scores what it does: the score popover."""
    cat = catalog_or_404(e, domain)
    model = e.models(e.store.ratings(user))[domain]
    ex = model.explain(row_or_404(cat, key), quality)
    tags = lambda pairs: [schemas.TagContribution(tag=t, contribution=round(c, 4),
                                                  from_other_domain=t in ex.transferred_tags) for t, c in pairs]
    return schemas.Explanation(key=key, label=ex.item, score=ex.score, percentile=ex.percentile, rated=ex.rated,
                               quality_part=ex.quality_part, transferred_part=ex.transferred_part,
                               pulling_up=tags(ex.for_tags), pushing_down=tags(ex.against_tags))


@router.get("/profiles/{user}/{domain}/rated")
def rated(user: User, domain: str, e: E, quality: Quality = 0.1) -> list[schemas.ItemCard]:
    """The user's rated items: likes, then mehs, then dislikes."""
    catalog_or_404(e, domain)
    model = e.models(e.store.ratings(user))[domain]
    return e.cards(model, model.rated_order(), quality)


# --- ratings ----------------------------------------------------------------------------------

def check_key(e: Engine, key: str) -> None:
    domain = key.split(":", 1)[0]
    row_or_404(catalog_or_404(e, domain), key)


@router.put("/profiles/{user}/ratings/{key}")
def rate(user: User, key: str, body: schemas.RatingIn, e: E) -> schemas.Ratings:
    check_key(e, key)
    return schemas.Ratings(ratings=e.store.set_rating(user, key, body.value))


@router.delete("/profiles/{user}/ratings/{key}")
def unrate(user: User, key: str, e: E) -> schemas.Ratings:
    check_key(e, key)
    return schemas.Ratings(ratings=e.store.clear_rating(user, key))


# --- profile ----------------------------------------------------------------------------------

def to_claims(pos: list[TagClaim], neg: list[TagClaim]) -> schemas.Claims:
    one = lambda c: schemas.Claim(
        tag=c.tag, weight=round(c.weight, 4),
        supporting=[schemas.Evidence(item=x.item, rating=x.rating, domain=x.domain) for x in c.supporting],
        contradicting=[schemas.Evidence(item=x.item, rating=x.rating, domain=x.domain) for x in c.contradicting])
    return schemas.Claims(respond_to=[one(c) for c in pos], push_back_on=[one(c) for c in neg])


@router.get("/profiles/{user}/profile")
def profile(user: User, e: E) -> schemas.Profile:
    """What the model has inferred: traits shared across domains, then each domain's own taste."""
    ratings = e.store.ratings(user)
    models = e.models(ratings)
    return schemas.Profile(
        user=user,
        shared=to_claims(*e.traits.profile(ratings)) if e.traits else None,
        domains=[schemas.DomainProfile(domain=d, name=m.cat.name, rated=len(m.rows), confidence=m.confidence(),
                                       claims=to_claims(*m.profile())) for d, m in models.items()],
    )


def description_out(d, ratings: dict[str, int]) -> schemas.Description:
    return schemas.Description(text=d.text, created=d.created, stale=d.ratings != ratings)


@router.get("/profiles/{user}/description")
def get_description(user: User, e: E) -> schemas.Description | None:
    d = e.store.description(user)
    return description_out(d, e.store.ratings(user)) if d else None


@router.post("/profiles/{user}/description")
def new_description(user: User, e: E) -> schemas.Description:
    """Write a new Describe Me (takes ~30 s on a local model) and save it."""
    ratings = e.store.ratings(user)
    if not ratings:
        raise HTTPException(409, "Rate something first.")
    from taste.model.describe import describe
    try:
        text = describe(taste_brief(e.models(ratings), e.traits, ratings), chat=e.chat)
    except LLMError as err:
        raise HTTPException(503, str(err))
    return description_out(e.store.save_description(user, text, ratings), ratings)


# --- shelf scan -------------------------------------------------------------------------------

@router.post("/profiles/{user}/shelf-scans", status_code=202)
async def start_scan(user: User, e: E, photo: UploadFile = File(...)) -> schemas.ShelfScan:
    """Start reading a shelf photo. Poll GET .../shelf-scan for progress and results."""
    if "book" not in e.cats:
        raise HTTPException(404, "Shelf scan needs the book catalogue.")
    image = await photo.read()
    if not image:
        raise HTTPException(422, "Empty photo.")
    e.start_scan(user, image, photo.filename or "photo")
    return schemas.ShelfScan(status="running", progress=schemas.ScanProgress(done=0, total=0))


@router.get("/profiles/{user}/shelf-scan")
def get_scan(user: User, e: E, quality: Quality = 0.1) -> schemas.ShelfScan:
    """The latest scan: running with progress, failed with an error, or done with ranked books."""
    return e.scan(user, quality)


@router.get("/profiles/{user}/shelf-scan/image", responses={200: {"content": {"image/jpeg": {}}}})
def scan_image(user: User, e: E) -> Response:
    image = e.store.scan_image(user)
    if image is None:
        raise HTTPException(404, "No scan yet.")
    return Response(image, media_type="image/jpeg")
