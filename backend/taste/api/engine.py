"""Everything the API computes with: catalogues and shared traits (reloaded when a domain's
genome is switched), the profile store, per-user models (cached on the user's ratings), and
shelf scanning."""

import logging
import threading
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Callable

import numpy as np

from taste.api import schemas
from taste.model import TRAITS_FILE, Catalog, Genome, TraitSpace, UserModel, available_domains, genomes
from taste.model import openlibrary
from taste.model.genomes import load as load_genome
from taste.model.llm import LLMError
from taste.model.shelf import Spine, location, match_spines, ollama_vision, rank_matches, read_spines
from taste.settings import get_settings
from taste.storage import SqlProfileStore

Reader = Callable[[bytes], list[Spine]]  # photo -> spines

log = logging.getLogger("taste.api")


def default_reader(image: bytes) -> list[Spine]:
    """Claude when ANTHROPIC_API_KEY is set (one request per photo), else the local Ollama model."""
    if get_settings().anthropic_api_key:
        from taste.model.claude_vision import claude_vision
        return claude_vision(image)
    return ollama_vision(image)


class Engine:
    def __init__(self, store: SqlProfileStore | None = None, reader: Reader = default_reader,
                 cache_size: int = 32,
                 genome: dict[str, str] | None = None, releases: list[Path] | None = None,
                 domains: list[str] | None = None):
        """`domains`: which to serve (default: TASTE_DOMAINS, books only). `genome`: the genome
        each uses (default: TASTE_<DOMAIN>_GENOME). `releases`: BookGenome release folders to
        offer (default: TASTE_BOOK_GENOME_PATHS)."""
        self.releases = releases
        settings = get_settings()
        domains = [d for d in (domains or settings.domains) if d in available_domains()]
        start = {d: (genome or {}).get(d) or getattr(settings, f"{d}_genome", "default") for d in domains}
        self.cats: dict[str, Catalog] = {d: load_genome(self.genome_info(d, g)) for d, g in start.items()}
        self.traits = self._traits(self.cats)
        if store is None:
            if not settings.database_url:
                raise RuntimeError("Set TASTE_DATABASE_URL (Postgres) in .env: see README, Accounts.")
            store = SqlProfileStore(settings.database_url)
        self.store = store
        self.reader = reader
        self._models: OrderedDict = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()

    # --- genomes --------------------------------------------------------------------------

    def genomes(self, domain: str) -> dict[str, Genome]:
        return genomes(domain, releases=self.releases)

    def genome_info(self, domain: str, name: str) -> Genome:
        options = self.genomes(domain)
        if name not in options:
            raise KeyError(f"No genome {name!r} for {domain}; have {', '.join(options) or 'none'}")
        return options[name]

    @staticmethod
    def _traits(cats: dict[str, Catalog]) -> TraitSpace | None:
        return TraitSpace(cats) if TRAITS_FILE.exists() and len(cats) > 1 else None

    def switch_genome(self, domain: str, name: str) -> Catalog:
        """Rebuild `domain`'s catalogue from another genome, and everything built on it.
        Global to the server: every user sees the switch. Ratings are untouched. Not exposed by
        the API for now (the app always uses TASTE_BOOK_GENOME)."""
        cat = load_genome(self.genome_info(domain, name))
        cats = {**self.cats, domain: cat}
        traits = self._traits(cats)
        with self._lock:
            self.cats, self.traits = cats, traits
            self._models.clear()
        return cat

    # --- models ---------------------------------------------------------------------------

    def models(self, ratings: dict[str, int]) -> dict[str, UserModel]:
        """One model per domain, with taste carried over between them. Fitting takes ~100 ms, so
        models are cached on the ratings themselves (paging and searching reuse them)."""
        key = tuple(sorted(ratings.items()))
        cats, traits = self.cats, self.traits  # one consistent set, even if a switch lands meanwhile
        with self._lock:
            if key in self._models:
                self._models.move_to_end(key)
                return self._models[key]
        models = {d: UserModel(c, ratings, prior=traits.prior(d, ratings) if traits else None)
                  for d, c in cats.items()}
        with self._lock:
            if self.cats is not cats:  # switched while fitting: don't cache models of the old genome
                return models
            self._models[key] = models
            while len(self._models) > self._cache_size:
                self._models.popitem(last=False)
        return models

    def source(self, domain: str, ratings: dict[str, int]) -> str:
        """Where carried-over taste comes from for this domain, e.g. "films"."""
        rated = self.traits.rated_domains(ratings) if self.traits else []
        return " & ".join(self.cats[d].name.lower() for d in rated if d != domain)

    # --- item cards -----------------------------------------------------------------------

    def card(self, model: UserModel, i: int, scores: np.ndarray, quality: float,
             where: str | None = None) -> schemas.ItemCard:
        cat, ex = model.cat, model.explain(i, quality, scores=scores)
        # With no ratings in this domain everything is carried over, so marking it says nothing.
        carried = ex.transferred_tags if len(model.rows) else set()
        year = cat.items["year"].iat[i]
        return schemas.ItemCard(
            key=cat.key(i), label=cat.label(i), title=cat.items["title"].iat[i],
            year=None if year != year else int(year),  # NaN != NaN
            creator=cat.creator(i), genres=cat.genres(i), series=cat.series[i] or None,
            score=round(ex.score, 3), percentile=round(ex.percentile, 1), rated=ex.rated,
            because=[schemas.Because(tag=t, from_other_domain=t in carried) for t, _ in ex.for_tags[:3]]
            if len(model.rows) or model.prior.any() else [],
            location=where, cover_url=openlibrary.cover(cat.items, i),
        )

    def cards(self, model: UserModel, rows, quality: float, **kwargs) -> list[schemas.ItemCard]:
        scores = model.scores(quality)
        return [self.card(model, int(i), scores, quality, **kwargs) for i in rows]

    # --- shelf scans ----------------------------------------------------------------------

    def scan_shelf(self, user: str, image: bytes, photo_name: str) -> None:
        """Read a shelf photo and save it as the user's scan, replacing the last one. Raises
        LLMError (written for the user) if the photo can't be read."""
        try:
            spines = read_spines(image, self.reader)
        except LLMError:
            raise
        except Exception:  # anything else stays in the log
            log.exception("shelf scan failed")
            raise LLMError("Something went wrong reading the photo; try again.") from None
        self.store.save_scan(user, uuid.uuid4().hex, photo_name, spines, image)

    def scan(self, user: str, quality: float) -> schemas.ShelfScan:
        saved = self.store.scan(user)
        return self._scan_results(user, saved, quality) if saved else schemas.ShelfScan(status="none")

    def _scan_results(self, user: str, saved, quality: float) -> schemas.ShelfScan:
        books = self.cats["book"]
        model = self.models(self.store.ratings(user))["book"]
        matches = match_spines(saved.spines, books)
        where = {m.row: location(m.spine.where) for m in matches if m.row is not None}
        rows = rank_matches(matches, model, quality)
        scores = model.scores(quality)
        return schemas.ShelfScan(
            status="done", photo_name=saved.photo_name, scanned=saved.scanned,
            books=[self.card(model, int(i), scores, quality, where=where.get(int(i))) for i in rows],
            unmatched=[schemas.Spine(title=m.spine.title, author=m.spine.author) for m in matches if m.row is None],
        )
