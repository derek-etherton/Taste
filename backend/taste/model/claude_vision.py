"""Shelf scan's reader on Claude (Sonnet 5.5 by default): one request per photo.

Unlike the small local model (shelf.ollama_vision), Claude reads a whole bookcase at once at up to
2576 px on the long edge, with coordinates in that image's pixels, so there's no need to find
the shelf rows and read them piece by piece. A JSON schema (structured outputs) guarantees the
reply parses.

    TASTE_SHELF_MODEL   default claude-sonnet-5-5
    TASTE_SHELF_EFFORT  default medium: reading spines is perception, not deep reasoning
"""

import base64
import io
import json
from typing import Callable

import anthropic

from taste.model.llm import LLMError
from taste.model.shelf import Spine, Where, load_image, normalise
from taste.settings import get_settings

MAX_SIDE = 2576  # px on the long edge: the most detail the model takes in

PROMPT = """This photo shows books on shelves, at home or in a shop. List every book whose title \
you can read on its spine or cover.

For each book give:
- title: exactly as printed, without series names or numbers;
- author: the author's name if it's visible, otherwise null;
- shelf: which shelf it's on, counting from the top (1 is the top shelf);
- x: the horizontal centre of the book in the image, in pixels from the left edge.

Also give shelves: how many shelves of books the photo shows. Skip books whose title you can't \
read; don't guess."""

SCHEMA = {
    "type": "object",
    "properties": {
        "shelves": {"type": "integer"},
        "books": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "author": {"type": ["string", "null"]},
                "shelf": {"type": "integer"},
                "x": {"type": "integer"},
            },
            "required": ["title", "author", "shelf", "x"],
            "additionalProperties": False,
        }},
    },
    "required": ["shelves", "books"],
    "additionalProperties": False,
}


def client() -> anthropic.Anthropic:
    key = get_settings().anthropic_api_key
    if not key:
        raise LLMError("Shelf scan needs ANTHROPIC_API_KEY in .env.")
    return anthropic.Anthropic(api_key=key)


def jpeg(image_bytes: bytes) -> tuple[str, int]:
    """The photo upright and at most MAX_SIDE on the long edge, as base64 JPEG, and its width."""
    image = load_image(image_bytes)
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90)
    return base64.b64encode(out.getvalue()).decode(), image.width


def claude_vision(image_bytes: bytes, progress: Callable[[int, int], None] | None = None,
                  claude: anthropic.Anthropic | None = None) -> list[Spine]:
    """Spines read off a shelf photo, each with roughly where it is (shelf row and position)."""
    settings = get_settings()
    data, width = jpeg(image_bytes)
    if progress:
        progress(0, 1)
    try:
        response = (claude or client()).beta.messages.create(
            model=settings.shelf_model,
            max_tokens=16000,
            output_config={"effort": settings.shelf_effort, "format": {"type": "json_schema", "schema": SCHEMA}},
            # On a safety decline, retry on a fallback model rather than fail (Claude API only).
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
                {"type": "text", "text": PROMPT},
            ]}],
        )
    except anthropic.AuthenticationError:
        raise LLMError("The Anthropic API key was refused; check ANTHROPIC_API_KEY in .env.") from None
    except anthropic.RateLimitError:
        raise LLMError("Claude is busy (rate limited); try the scan again in a minute.") from None
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude returned an error ({e.status_code}): {e.message}") from None
    except anthropic.APIConnectionError:
        raise LLMError("Couldn't reach the Claude API; check the internet connection.") from None
    if response.stop_reason == "refusal":
        raise LLMError("Claude declined to read this photo.")
    if response.stop_reason == "max_tokens":
        raise LLMError("Too many books in one photo; try a photo of fewer shelves.")
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        reply = json.loads(text)
    except json.JSONDecodeError:
        raise LLMError("Claude's reply couldn't be read as a list of books.") from None
    if progress:
        progress(1, 1)
    return spines(reply, width)


def spines(reply: dict, width: int) -> list[Spine]:
    """The reply as spines: shelf 1 (top) becomes row 0, and x a fraction of the photo's width."""
    books = reply.get("books", [])
    shelves = max([1, int(reply.get("shelves") or 0), *(int(b.get("shelf") or 1) for b in books)])
    out = []
    for b in books:
        title = str(b.get("title") or "").strip()
        author = (str(b.get("author") or "").strip()) or None
        if not title or (author and normalise(title) == normalise(author)):  # an author's name read as a title
            continue
        row = min(max(int(b.get("shelf") or 1), 1), shelves) - 1
        x = min(max(float(b.get("x") or 0) / max(width, 1), 0.0), 1.0)
        out.append(Spine(title, author, Where(row, shelves, x)))
    return out
