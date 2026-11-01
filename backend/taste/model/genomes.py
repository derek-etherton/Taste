"""Genomes: which item × tag scores a domain's catalogue is built from.

Each domain has a `default` genome, data/<domain>/ in the common format (catalog.py), and
may have more, picked by name at startup (TASTE_<DOMAIN>_GENOME) or switched at runtime:
  data/genomes/<domain>/<name>/   in the common format, or a BookGenome release (books)
  TASTE_BOOK_GENOME_PATHS         BookGenome release folders used in place, e.g.
                                  '["D:/BookGenome/data/release/truegenome-2026-10-31"]'
Items keep their IDs across genomes wherever they can be linked, so ratings carry over;
items a genome lacks just don't appear while it's active.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from taste.model import bookgenome
from taste.model.catalog import DATA, DOMAINS, Catalog, read_items
from taste.settings import get_settings

DEFAULT = "default"


@dataclass(frozen=True)
class Genome:
    name: str
    domain: str
    kind: str  # "common" (the common format) or "bookgenome" (a BookGenome release)
    path: Path
    description: str = ""


def genomes(domain: str, data_dir: Path = DATA, releases: list[Path] | None = None) -> dict[str, Genome]:
    """The genomes available for `domain`, by name, default first. `releases`: BookGenome
    release folders to offer besides those under data/genomes/book/ (default: from settings)."""
    out: dict[str, Genome] = {}
    if (data_dir / domain / "items.csv").exists():
        out[DEFAULT] = Genome(DEFAULT, domain, "common", data_dir / domain, "the catalogue's own tag scores")
    folders = sorted(p for p in (data_dir / "genomes" / domain).glob("*") if p.is_dir())
    if domain == "book":
        folders += [Path(p) for p in (get_settings().book_genome_paths if releases is None else releases)]
    for path in folders:
        if (path / "items.csv").exists():
            out.setdefault(path.name, Genome(path.name, domain, "common", path))
        elif domain == "book" and bookgenome.is_release(path):
            meta = json.loads((path / "genome.json").read_text(encoding="utf-8"))
            out.setdefault(path.name, Genome(path.name, domain, "bookgenome", path, meta.get("description", "")))
    return out


def available_domains(data_dir: Path = DATA) -> list[str]:
    return [d for d in DOMAINS if genomes(d, data_dir)]


def load(genome: Genome, data_dir: Path = DATA) -> Catalog:
    """The catalogue for a genome."""
    if genome.kind == "common":
        return Catalog.load(genome.domain, src=genome.path, genome=genome.name)
    base_dir = data_dir / genome.domain
    base = read_items(base_dir) if (base_dir / "items.csv").exists() else None
    r = bookgenome.read_release(genome.path, base)
    return Catalog(genome.domain, r.items, r.tags, r.relevance, genome=genome.name,
                   weights=[1.0] * len(r.items), derived_from=r.derived_from, linked=r.linked)
