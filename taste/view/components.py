"""Reusable Streamlit pieces: item rows, rating buttons, score breakdown, profile."""

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from taste.model import Catalog, Explanation, TagClaim, UserModel, save_ratings, toggle_rating

ICON = {1: "👍", 0: "😐", -1: "👎"}
DOMAIN_ICON = {"film": "🎬", "book": "📚"}
BUTTONS = [(1, "up"), (0, "meh"), (-1, "down")]


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def fmt_tags(tags: list[tuple[str, float]], transferred: set[str] = frozenset(), source: str = "") -> str:
    """Tag names; those mostly carried over from other domains are marked, e.g. "dark (from films)"."""
    return ", ".join(f"{t} <i>(from {source})</i>" if t in transferred else t for t, _ in tags) or "—"


def _rate(ratings: dict[str, int], key: str, value: int) -> None:
    toggle_rating(ratings, key, value)
    save_ratings(ratings)


def rating_buttons(ratings: dict[str, int], key: str, widget_key: str) -> None:
    current = ratings.get(key)
    for col, (value, name) in zip(st.columns(3), BUTTONS):
        col.button(ICON[value], key=f"{widget_key}-{name}", type="primary" if current == value else "secondary",
                   on_click=_rate, args=(ratings, key, value), use_container_width=True,
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
                rating_buttons(self.ratings, item, f"{key}-{item}")


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
