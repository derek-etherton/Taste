"""Reusable Streamlit pieces: film rows, rating buttons, score breakdown, profile."""

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from taste.model import Catalog, Explanation, UserModel, save_ratings, toggle_rating

ICON = {1: "👍", 0: "😐", -1: "👎"}
BUTTONS = [(1, "up"), (0, "meh"), (-1, "down")]


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def fmt_tags(tags: list[tuple[str, float]]) -> str:
    return ", ".join(t for t, _ in tags) or "—"


def _rate(ratings: dict[int, int], movie_id: int, value: int) -> None:
    toggle_rating(ratings, movie_id, value)
    save_ratings(ratings)


def rating_buttons(ratings: dict[int, int], movie_id: int, key: str) -> None:
    current = ratings.get(movie_id)
    for col, (value, name) in zip(st.columns(3), BUTTONS):
        col.button(ICON[value], key=f"{key}-{name}", type="primary" if current == value else "secondary",
                   on_click=_rate, args=(ratings, movie_id, value), use_container_width=True,
                   help="Meh: seen it, neither loved nor hated it" if value == 0 else None)


def score_breakdown(ex: Explanation) -> None:
    """Why a film scores what it does: shown inside its row's popover."""
    a, b, c = st.columns(3)
    a.metric("Percentile", f"{ex.percentile:.1f}",
             help="Share of unrated films (in the current pool) this one beats.")
    b.metric("Score", f"{ex.score:+.3f}")
    c.metric("…of which quality", f"{ex.quality_part:+.3f}")
    left, right = st.columns(2)
    left.markdown("**Pulling it up**")
    left.dataframe(pd.DataFrame(ex.for_tags, columns=["tag", "contribution"]), hide_index=True)
    right.markdown("**Pushing it down**")
    right.dataframe(pd.DataFrame(ex.against_tags, columns=["tag", "contribution"]), hide_index=True)


@dataclass
class FilmList:
    """Renders lists of films against one model and set of knob values."""

    cat: Catalog
    model: UserModel
    ratings: dict[int, int]
    quality: float
    min_ratings: int

    def rows(self, rows, key: str, first_rank: int | None = None) -> None:
        """One row per film (catalogue row indices), numbered from first_rank if given."""
        scores = self.model.scores(self.quality)
        for n, i in enumerate(rows):
            i = int(i)
            mid = self.cat.movie_id(i)
            ex = self.model.explain(i, self.quality, self.min_ratings, scores=scores)
            name, fit, buttons = st.columns([6, 1.3, 1.8])
            rank = f"{first_rank + n}. " if first_rank is not None else ""
            because = f" · because: {fmt_tags(ex.for_tags[:3])}" if self.ratings else ""
            name.markdown(f"**{rank}{self.cat.label(i)}**  \n"
                          f"<small>{' · '.join(self.cat.genres(i))}{because}</small>",
                          unsafe_allow_html=True)
            with fit.popover(f"{ordinal(round(ex.percentile))} pct", use_container_width=True,
                             help="How recommended this film is for you. Click for why."):
                score_breakdown(ex)
            with buttons:
                rating_buttons(self.ratings, mid, f"{key}-{mid}")


def profile_panel(model: UserModel) -> None:
    st.caption(model.confidence())
    st.caption("Evidence lists only films that clearly have the trait. **for**: rated the way the "
               "trait points. **against**: rated the other way, or meh.")
    pos, neg = model.profile()
    if not pos and not neg:
        st.info("No profile yet: rate some films.")
    top = max([abs(c.weight) for c in pos + neg] or [1])
    films = lambda fs: "; ".join(f"{ICON[r]} {f}" for f, r in fs)
    for col, title, claims in zip(st.columns(2), ["You respond to", "You push back on"], [pos, neg]):
        with col:
            st.subheader(title)
            for c in claims:
                st.markdown(f"**{c.tag}**")
                st.progress(min(1.0, abs(c.weight) / top))
                lines = []
                if c.supporting:
                    lines.append("for: " + films(c.supporting))
                if c.contradicting:
                    lines.append("against: " + films(c.contradicting))
                st.caption("  \n".join(lines))
