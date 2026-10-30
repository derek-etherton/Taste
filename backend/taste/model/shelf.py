"""Shelf scan: read book spines off a photo, find them in the catalogue, rank them for you.

    photo --reader--> [Spine(title, author)] --match_spines--> [Match(row | None)]
          --UserModel.ranked--> best for this profile first

A reader is any callable image bytes -> spines, so the vision model is swappable: the
default asks a local Ollama vision model; a Claude reader can drop in with the same prompt
and schema. Matching is fuzzy on titles (OCR is imperfect), with the author as a tiebreak.
"""

import base64
import io
import json
import re
from dataclasses import dataclass, field, replace
from typing import Callable

from PIL import Image, ImageOps
from rapidfuzz import fuzz, process

from taste.settings import get_settings
from taste.model.catalog import Catalog
from taste.model.llm import LLMError, ollama_chat

MAX_SIDE = 1600  # px; the overview used to find shelf rows is downscaled to this
PIECE_HEIGHT = 320  # px; each piece of a row is scaled to about this height so spine text is legible
PIECE_ASPECT = 3.2  # max width:height of a piece; wider rows are cut into overlapping pieces
MATCH_THRESHOLD = 85  # 0-100; below this a spine counts as not in the catalogue

# Small vision models loop ("The Art of War", "The Art of War", ...) on a crowded image at
# temperature 0; a little randomness, a repeat penalty and a token cap stop that.
READ_OPTIONS = {"temperature": 0.3, "repeat_penalty": 1.15, "repeat_last_n": 256,
                "num_ctx": 8192, "num_predict": 1024}

ROWS_PROMPT = """Locate every horizontal row of books in this image (one per shelf). Return each \
row as bbox_2d [x1, y1, x2, y2] in coordinates from 0 to 1000, top row first."""

ROWS_SCHEMA = {
    "type": "object",
    "properties": {"rows": {"type": "array", "items": {
        "type": "object",
        "properties": {"bbox_2d": {"type": "array", "items": {"type": "integer"}}},
        "required": ["bbox_2d"],
    }}},
    "required": ["rows"],
}

PROMPT = """This photo shows books on a shelf. List every book whose title you can read on its \
spine or cover, in order from left to right.
For each give the title exactly as printed (without series numbers) and the author's name if \
it's visible, otherwise null. Skip books whose title you can't read; don't guess."""

SCHEMA = {
    "type": "object",
    "properties": {"books": {"type": "array", "items": {
        "type": "object",
        "properties": {"title": {"type": "string"}, "author": {"type": ["string", "null"]}},
        "required": ["title", "author"],
    }}},
    "required": ["books"],
}


@dataclass(frozen=True)
class Where:
    """Roughly where a spine was read: which shelf row, and how far along it."""
    row: int  # 0 = top shelf
    rows: int  # shelf rows found in the photo
    x: float  # 0 = left edge of the photo, 1 = right edge


@dataclass(frozen=True)
class Spine:
    title: str
    author: str | None = None
    where: Where | None = field(default=None, compare=False)


@dataclass
class Match:
    spine: Spine
    row: int | None  # catalogue row, or None if not found
    confidence: float  # 0-100+


Reader = Callable[[bytes], list[Spine]]


def load_image(image_bytes: bytes) -> Image.Image:
    """Upright RGB image (phone photos carry their rotation in EXIF)."""
    return ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")


def encode(image: Image.Image) -> str:
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90)
    return base64.b64encode(out.getvalue()).decode()


def prepare_image(image_bytes: bytes, max_side: int = MAX_SIDE) -> str:
    """Upright, downscaled JPEG as base64."""
    image = load_image(image_bytes)
    image.thumbnail((max_side, max_side))
    return encode(image)


def parse_spines(reply: str) -> list[Spine]:
    """Spines from the model's JSON reply. Tolerant of a bare list, extra text around it, and
    a reply cut off mid-list (the complete entries are kept)."""
    match = re.search(r"[\[{].*[\]}]", reply, flags=re.DOTALL)
    try:
        data = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        entries = re.findall(r'\{\s*"title"\s*:\s*"([^"]*)"\s*,\s*"author"\s*:\s*(null|"[^"]*")\s*\}', reply)
        data = [{"title": t, "author": None if a == "null" else a.strip('"')} for t, a in entries] or None
    if data is None:
        raise LLMError("The vision model's reply couldn't be read as a list of books.")
    books = data.get("books", []) if isinstance(data, dict) else data
    out = []
    for b in books:
        title = str(b.get("title") or "").strip() if isinstance(b, dict) else ""
        author = (b.get("author") or "").strip() or None if isinstance(b, dict) else None
        if title and (not author or normalise(title) != normalise(author)):  # an author's name read as a title
            out.append(Spine(title, author))
    return out


def shelf_rows(overview: Image.Image, chat) -> list[tuple[float, float, float, float]]:
    """Each row of books as a (x1, y1, x2, y2) fraction of the image, top first; [] if none found."""
    reply = chat(ROWS_PROMPT, overview, ROWS_SCHEMA, {"temperature": 0, "num_ctx": 8192, "num_predict": 600})
    try:
        rows = json.loads(reply)["rows"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []
    boxes = []
    for r in rows:
        box = r.get("bbox_2d") if isinstance(r, dict) else None
        if isinstance(box, list) and len(box) == 4:
            x1, y1, x2, y2 = (min(max(v / 1000, 0.0), 1.0) for v in box)
            if x2 - x1 > 0.05 and y2 - y1 > 0.02:
                boxes.append((x1, y1, x2, y2))
    return sorted(boxes, key=lambda b: b[1])


def pieces(image: Image.Image, row: tuple[float, float, float, float], pad: float = 0.15,
           overlap: float = 0.08) -> list[tuple[Image.Image, float, float]]:
    """A row cut into overlapping pieces no wider than PIECE_ASPECT, each scaled to PIECE_HEIGHT,
    with the left and right edge of each as a fraction of the photo's width."""
    w, h = image.size
    x1, y1, x2, y2 = row[0] * w, row[1] * h, row[2] * w, row[3] * h
    grow = (y2 - y1) * pad  # rows are found on a small overview; leave room for tall spines
    y1, y2 = max(0.0, y1 - grow), min(float(h), y2 + grow)
    n = max(1, round((x2 - x1) / ((y2 - y1) * PIECE_ASPECT)))
    step = (x2 - x1) / n
    out = []
    for i in range(n):
        left = max(x1, x1 + i * step - step * overlap)
        right = min(x2, x1 + (i + 1) * step + step * overlap)
        piece = image.crop((int(left), int(y1), int(right), int(y2)))
        scale = PIECE_HEIGHT / piece.height
        if scale > 1:  # only enlarge; big photos are already sharp enough
            piece = piece.resize((round(piece.width * min(scale, 3)), round(piece.height * min(scale, 3))),
                                 Image.LANCZOS)
        out.append((piece, left / w, right / w))
    return out


def _ollama(prompt: str, image: Image.Image, schema: dict, options: dict) -> str:
    model = get_settings().ollama_vision_model
    message = {"role": "user", "content": prompt, "images": [encode(image)]}
    return ollama_chat([message], model, format=schema, options=options, timeout=300)


def ollama_vision(image_bytes: bytes, progress: Callable[[int, int], None] | None = None,
                  chat=_ollama) -> list[Spine]:
    """Read spines with a local vision model: find the shelf rows, then read each row in pieces
    (a whole bookcase at once is too much small text for it). progress(done, total) is called
    as pieces finish. Each spine records roughly where it was: its shelf row, and a position
    along the row from its order within the piece (the model reads left to right)."""
    image = load_image(image_bytes)
    overview = image.copy()
    overview.thumbnail((MAX_SIDE, MAX_SIDE))
    rows = shelf_rows(overview, chat)
    found = len(rows)
    todo = [(r, p) for r, row in enumerate(rows or [(0.0, 0.0, 1.0, 1.0)]) for p in pieces(image, row)]
    spines = []
    for i, (r, (piece, left, right)) in enumerate(todo):
        if progress:
            progress(i, len(todo))
        read = parse_spines(chat(PROMPT, piece, SCHEMA, READ_OPTIONS))
        for j, s in enumerate(read):
            x = left + (right - left) * (j + 0.5) / len(read)
            spines.append(replace(s, where=Where(r, found, x)))
    if progress:
        progress(len(todo), len(todo))
    return spines


ORDINALS = ["top", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]


def location(where: Where | None) -> str:
    """Where to look, in words: "2nd shelf from the top, on the left". Rough by design."""
    if where is None:
        return ""
    side = "on the left" if where.x < 1 / 3 else "in the middle" if where.x < 2 / 3 else "on the right"
    if where.rows <= 1:
        return side.capitalize()
    if where.row == 0:
        shelf = "Top shelf"
    elif where.row == where.rows - 1:
        shelf = "Bottom shelf"
    else:
        shelf = f"{ORDINALS[where.row] if where.row < len(ORDINALS) else f'{where.row + 1}th'} shelf from the top"
    return f"{shelf}, {side}"


def read_spines(image_bytes: bytes, reader: Reader = ollama_vision) -> list[Spine]:
    """Spines in the photo, without duplicates."""
    seen, out = set(), []
    for s in reader(image_bytes):
        key = normalise(s.title)
        if key and key not in seen:
            seen.add(key)
            out.append(s)
    return out


ARTICLES = re.compile(r"^(the|a|an) ")


def normalise(text: str) -> str:
    """Lowercase words only: no brackets (series, alternate titles), punctuation or leading article."""
    text = re.sub(r"\([^()]*\)", " ", text.lower())
    text = re.sub(r"[^\w\s]", " ", text.replace("&", " and ").replace("'", ""))
    return ARTICLES.sub("", " ".join(text.split()))


_index: dict[int, tuple[list[str], list[str]]] = {}


def _titles(cat: Catalog) -> tuple[list[str], list[str]]:
    """Normalised full titles and main titles (before any subtitle), cached per catalogue."""
    if id(cat) not in _index:
        full = [normalise(t) for t in cat.items["title"]]
        main = [normalise(t.split(":")[0]) for t in cat.items["title"]]
        _index[id(cat)] = (full, main)
    return _index[id(cat)]


def candidates(spine: Spine, cat: Catalog, limit: int = 10) -> list[tuple[int, float]]:
    """(row, confidence) for the closest catalogue titles, best first.

    Title similarity is token_sort_ratio against the full title or the main title (spines
    often leave off subtitles), whichever is closer. A matching author adds a little and a
    clearly different one takes some away, enough to sink a fuzzy title but not an exact one
    (vision models misread authors more than titles). The reading is also tried with title
    and author swapped, which vision models often do. Popularity breaks ties."""
    full, main = _titles(cat)
    scores: dict[int, float] = {}
    readings = [(spine.title, spine.author)] + ([(spine.author, spine.title)] if spine.author else [])
    for title, author in readings:
        query = normalise(title)
        if not query:
            continue
        found: dict[int, float] = {}
        for choices in (full, main):
            for _, score, row in process.extract(query, choices, scorer=fuzz.token_sort_ratio, limit=limit):
                found[row] = max(found.get(row, 0.0), score)
        if author:
            for row in found:
                agree = fuzz.token_set_ratio(normalise(author), normalise(cat.creator(row)))  # "KING" ~ "Stephen King"
                found[row] += 10 if agree >= 80 else -12 if agree < 50 else 0
        for row, score in found.items():
            scores[row] = max(scores.get(row, 0.0), score)
    return sorted(scores.items(), key=lambda rs: (-rs[1], cat.popularity_rank[rs[0]]))


def match_spines(spines: list[Spine], cat: Catalog, threshold: float = MATCH_THRESHOLD) -> list[Match]:
    """Each spine's catalogue book (or None), in spine order. A book is matched at most once:
    the most confident spine claims it and the others fall back to their next candidate."""
    options = [[c for c in candidates(s, cat) if c[1] >= threshold] for s in spines]
    order = sorted(range(len(spines)), key=lambda i: -(options[i][0][1] if options[i] else 0))
    taken, found = set(), {}
    for i in order:
        pick = next(((row, conf) for row, conf in options[i] if row not in taken), None)
        if pick:
            taken.add(pick[0])
            found[i] = pick
    return [Match(s, *found.get(i, (None, 0.0))) for i, s in enumerate(spines)]


def rank_matches(matches: list[Match], model, quality: float = 0.1):
    """Catalogue rows of the matched books, best for this profile first."""
    rows = list(dict.fromkeys(m.row for m in matches if m.row is not None))
    return model.ranked(quality, rows=rows)
