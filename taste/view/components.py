"""Reusable Streamlit pieces: item rows, rating buttons, score breakdown, profile."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from taste.model import (Catalog, Explanation, TagClaim, TraitSpace, UserModel, load_description, save_description,
                         save_ratings, toggle_rating)
from taste.model.describe import DescribeError, describe, taste_brief
from taste.model.llm import LLMError
from taste.model.shelf import match_spines, ollama_vision, rank_matches, read_spines

ICON = {1: "👍", 0: "😐", -1: "👎"}
DOMAIN_ICON = {"film": "🎬", "book": "📚"}
BUTTONS = [(1, "up"), (0, "meh"), (-1, "down")]


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def fmt_tags(tags: list[tuple[str, float]], transferred: set[str] = frozenset(), source: str = "") -> str:
    """Tag names; those mostly carried over from other domains are marked, e.g. "dark (from films)"."""
    return ", ".join(f"{t} <i>(from {source})</i>" if t in transferred else t for t, _ in tags) or "—"


def _rate(ratings: dict[str, int], key: str, value: int, path: Path) -> None:
    toggle_rating(ratings, key, value)
    save_ratings(ratings, path)


def rating_buttons(ratings: dict[str, int], key: str, widget_key: str, path: Path) -> None:
    current = ratings.get(key)
    for col, (value, name) in zip(st.columns(3), BUTTONS):
        col.button(ICON[value], key=f"{widget_key}-{name}", type="primary" if current == value else "secondary",
                   on_click=_rate, args=(ratings, key, value, path), use_container_width=True,
                   help="Meh: tried it, neither loved nor hated it" if value == 0 else None)


def score_breakdown(ex: Explanation, source: str) -> None:
    """Why an item scores what it does: shown inside its row's popover."""
    a, b, c, d = st.columns(4)
    a.metric("Percentile", f"{ex.percentile:.1f}",
             help="Share of unrated items (in the current pool) this one beats.")
    b.metric("Score", f"{ex.score:+.3f}")
    c.metric("…from quality", f"{ex.quality_part:+.3f}")
    d.metric(f"…from your {source or 'other ratings'}", f"{ex.transferred_part:+.3f}",
             help="The part of the taste score carried over from your ratings in other domains.")
    left, right = st.columns(2)
    left.markdown("**Pulling it up**")
    left.dataframe(pd.DataFrame(ex.for_tags, columns=["tag", "contribution"]), hide_index=True)
    right.markdown("**Pushing it down**")
    right.dataframe(pd.DataFrame(ex.against_tags, columns=["tag", "contribution"]), hide_index=True)


@dataclass
class ItemList:
    """Renders lists of one domain's items against one model and set of knob values."""

    cat: Catalog
    model: UserModel
    ratings: dict[str, int]
    path: Path  # the profile file ratings are saved to
    quality: float
    source: str = ""  # where transferred taste comes from, e.g. "films"; "" if none

    def rows(self, rows, key: str, first_rank: int | None = None, more: dict[int, int] | None = None) -> None:
        """One row per item (catalogue row indices), numbered from first_rank if given.
        `more` maps a row to how many other volumes of its series it stands in for."""
        more = more or {}
        scores = self.model.scores(self.quality)
        personal = len(self.model.rows) or self.model.prior.any()
        for n, i in enumerate(rows):
            i = int(i)
            item = self.cat.key(i)
            ex = self.model.explain(i, self.quality, scores=scores)
            name, fit, buttons = st.columns([6, 1.3, 1.8])
            rank = f"{first_rank + n}. " if first_rank is not None else ""
            details = [self.cat.creator(i), " · ".join(self.cat.genres(i))]
            if i in more:
                details.append(f"+{more[i]} more in {self.cat.series[i]}")
            if personal:
                # With no ratings here everything is transferred; the list's banner already says so.
                marked = ex.transferred_tags if len(self.model.rows) else set()
                details.append("because: " + fmt_tags(ex.for_tags[:3], marked, self.source))
            name.markdown(f"**{rank}{self.cat.label(i)}**  \n"
                          f"<small>{' · '.join(d for d in details if d)}</small>",
                          unsafe_allow_html=True)
            with fit.popover(f"{ordinal(round(ex.percentile))} pct", use_container_width=True,
                             help="How recommended this is for you. Click for why."):
                score_breakdown(ex, self.source)
            with buttons:
                rating_buttons(self.ratings, item, f"{key}-{item}", self.path)


def claim_list(pos: list[TagClaim], neg: list[TagClaim], empty: str) -> None:
    if not pos and not neg:
        st.info(empty)
        return
    top = max(abs(c.weight) for c in pos + neg)
    items = lambda es: "; ".join(f"{ICON[e.rating]} {DOMAIN_ICON.get(e.domain, '')} {e.item}" for e in es)
    for col, title, claims in zip(st.columns(2), ["You respond to", "You push back on"], [pos, neg]):
        with col:
            st.subheader(title)
            for c in claims:
                st.markdown(f"**{c.tag}**")
                st.progress(min(1.0, abs(c.weight) / top))
                lines = []
                if c.supporting:
                    lines.append("for: " + items(c.supporting))
                if c.contradicting:
                    lines.append("against: " + items(c.contradicting))
                st.caption("  \n".join(lines))


EVIDENCE_NOTE = ("Evidence lists only items that clearly have the trait. **for**: rated the way the "
                 "trait points. **against**: rated the other way, or meh.")


def describe_me(models: dict[str, UserModel], traits: TraitSpace | None, ratings: dict[str, int],
                path: Path) -> None:
    """The Describe Me button, and your saved description (kept until a new one is written)."""
    if st.button("Describe Me", disabled=not ratings,
                 help="A fun four-line taste horoscope, written by a local AI model. Press again for a new one."):
        with st.spinner("Writing your description…"):
            try:
                save_description(describe(taste_brief(models, traits, ratings)), ratings, path)
            except DescribeError as e:
                st.error(str(e))  # a failed attempt keeps the previous description
    saved = load_description(path)
    if saved:
        st.info(saved.text)
        note = f"Written {saved.created.replace('T', ' at ')}"
        if saved.ratings != ratings:
            note += ". Your ratings have changed since; press Describe Me for a fresh one."
        st.caption(note)


def shelf_scan(items: ItemList) -> None:
    """Photograph a bookshelf: the books on it that we know, best for this profile first."""
    st.caption("Snap or upload a photo of a bookshelf, at home or in a shop. We read the spines and "
               "sort the books we know by how much you'd like them.")
    photo = st.file_uploader("Shelf photo", type=["jpg", "jpeg", "png", "webp"], key="shelf-photo",
                             label_visibility="collapsed")
    if photo is None:
        return
    # Readings are cached per photo, so switching profile just re-ranks the same shelf.
    scans = st.session_state.setdefault("shelf_scans", {})
    picture, results = st.columns([1, 3])
    picture.image(photo, use_container_width=True)
    with results:
        if photo.file_id not in scans:
            bar = st.progress(0.0, text="Finding the shelves…")

            def progress(done: int, total: int) -> None:
                bar.progress(done / total, text=f"Reading the spines: part {min(done + 1, total)} of {total}…")

            try:
                spines = read_spines(photo.getvalue(), lambda image: ollama_vision(image, progress=progress))
            except LLMError as e:
                bar.empty()
                st.error(str(e))
                return
            bar.empty()
            scans[photo.file_id] = match_spines(spines, items.cat)
        matches = scans[photo.file_id]
        if not matches:
            st.warning("Couldn't read any titles in this photo. Try a closer, sharper shot of the spines.")
            return
        ranked = rank_matches(matches, items.model, items.quality)
        st.markdown(f"**On this shelf, best for you first** · {len(ranked)} of {len(matches)} "
                    "books recognised")
        missing = [m.spine for m in matches if m.row is None]
        if missing:
            with st.expander(f"Read but not in our catalogue ({len(missing)})"):
                st.markdown("\n".join(f"- {s.title}" + (f" · {s.author}" if s.author else "") for s in missing))
    items.rows(ranked, "shelf", first_rank=1)
