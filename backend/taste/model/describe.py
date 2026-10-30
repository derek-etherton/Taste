"""Describe Me: a playful four-line "taste horoscope", written by an LLM from your profile.

The LLM never sees the maths. taste_brief() turns what the model has inferred (shared
traits, each domain's own taste, and the items you rated) into a short text brief;
describe() asks a local Ollama model to write it up. Keeping the brief separate makes it
testable and lets you see exactly what the LLM was told.
"""

import re
from typing import Callable

from taste.settings import get_settings
from taste.model.llm import LLMError, ollama_chat
from taste.model.traits import TraitSpace
from taste.model.user_model import TagClaim, UserModel

DescribeError = LLMError

SYSTEM = """Below is what a recommender has worked out about someone's taste in films and \
books. Turn it into a taste horoscope: a fun, cheeky reading they'd screenshot and send to \
friends. Be playful, a little mystical and over the top, but true to them underneath.

Write four short sentences, each under 18 words:
1. "You're a" plus an inventive archetype that's half flattering, half teasing (e.g. a feral \
romantic, an apocalypse tourist, a chaos gremlin, a goth with a library card). Make it \
specific to them; never a plain genre label like "sci-fi fan".
2. What they love, as a vivid picture of the kind of story or moment that gets them, not a list.
3. An omen about what they can't stand.
4. A prophecy about what's coming for them next, linking their films and books.

Rules:
- Never name a film, book, author or director. The titles below are only there so you can \
read their taste.
- Exaggerate for fun, but every claim must come from the information given.
- Everyday words with personality, not critic-speak. Each sentence should surprise; avoid \
stock horoscope phrases. Never use: gravitate, drawn to, resonate, explore, nuanced, \
cerebral, tapestry, undercurrents, narratives, complex, journey, sacred, holy, scripture, \
texts, soul, your nose, the stars, soft spot, swept away.
- Teasing is fine; cruel or crude is not.
- No em dashes or en dashes. Use commas, colons or full stops instead.
- Never mention ratings, tags, traits, profiles or the recommender. Some trait names are \
noise: ignore any that don't fit the titles.
- Reply with the reading only."""
# No example reading: the model copied any example's structure line for line.

Chat = Callable[[list[dict]], str]  # messages -> reply text


def _claims(title: str, pos: list[TagClaim], neg: list[TagClaim], k: int) -> list[str]:
    def line(c: TagClaim) -> str:
        ev = ", ".join(e.item for e in c.supporting[:2])
        return f"- {c.tag}" + (f" (e.g. {ev})" if ev else "")

    out = [f"{title}:"]
    if pos:
        out += ["  Drawn to:"] + ["  " + line(c) for c in pos[:k]]
    if neg:
        out += ["  Steers away from:"] + ["  " + line(c) for c in neg[:k]]
    return out if len(out) > 1 else []


def taste_brief(models: dict[str, UserModel], traits: TraitSpace | None, ratings: dict[str, int],
                k: int = 8, titles: int = 15) -> str:
    """What the model has inferred about you, as text for the LLM."""
    lines = []
    for m in models.values():
        name = m.cat.name.lower()
        lines.append(f"{m.cat.name}: {m.confidence()}.")
        for label, value in [("Liked", 1), ("Meh", 0), ("Disliked", -1)]:
            rows = [int(i) for i, y in zip(m.rows, m.y) if y == value]
            if rows:
                shown = "; ".join(m.cat.label(i) for i in rows[:titles])
                more = f" (and {len(rows) - titles} more)" if len(rows) > titles else ""
                lines.append(f"  {label} {name}: {shown}{more}")
    if traits:
        lines += [""] + _claims("Taste that carries across films and books", *traits.profile(ratings, k=k), k)
    for m in models.values():
        own = _claims(f"Taste specific to {m.cat.name.lower()}", *m.profile(k=k), k)
        lines += [""] + own if own else []
    return "\n".join(lines).strip()


def default_chat(messages: list[dict]) -> str:
    # A higher temperature keeps the readings playful and different on each press.
    return ollama_chat(messages, get_settings().ollama_model, options={"temperature": 1.0})


def describe(brief: str, chat: Chat = default_chat) -> str:
    """Three sentences about the person behind `brief`. Raises DescribeError on failure."""
    reply = chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": brief}])
    # Some models still emit their reasoning inline; keep only the answer.
    text = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
    text = re.sub(r"\s*[—–]\s*", ", ", text)  # in case a dash slips past the prompt
    if not text:
        raise DescribeError("The model returned no text.")
    return text
