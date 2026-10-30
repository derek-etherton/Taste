"""Streamlit PoC: rate films, get recommendations, inspect your profile.

Run: streamlit run taste/view/app.py
"""

import streamlit as st
from st_keyup import st_keyup

from taste.model import Catalog, UserModel, load_ratings, save_ratings
from taste.view.components import FilmList, profile_panel

PAGE = 25

st.set_page_config(page_title="Taste", page_icon="🎞️", layout="wide")


@st.cache_resource
def catalog() -> Catalog:
    return Catalog()


cat = catalog()
if "ratings" not in st.session_state:
    st.session_state.ratings = load_ratings()
ratings: dict[int, int] = st.session_state.ratings

with st.sidebar:
    st.title("🎞️ Taste")
    quality = st.slider("Weight on general quality", 0.0, 1.0, 0.1, 0.05,
                        help="0 = pure taste match. Higher = lean toward films everyone rates well.")
    min_ratings = st.select_slider("Hide films with fewer ratings than", [0, 100, 500, 1000, 5000, 20000], 500)
    model = UserModel(cat, ratings)
    st.caption(model.confidence())
    if ratings and st.button("Reset all ratings"):
        ratings.clear()
        save_ratings(ratings)
        st.rerun()

films = FilmList(cat, model, ratings, quality, min_ratings)
films_tab, profile_tab = st.tabs(["Films", "Profile"])

with films_tab:
    mode = st.segmented_control("List", ["For you", "Rate films"], default="For you",
                                key="mode", label_visibility="collapsed") or "For you"
    query = st_keyup("Search films", placeholder="Start typing a title…", debounce=200, key="q").strip()
    # Search covers the whole catalogue, rated films included, in the current mode's order.
    hits = cat.search(query) if query else None
    if mode == "For you":
        pool = model.ranked(quality, min_ratings, rows=hits)
        if not query and not ratings:
            st.info("Rate a few films. Until then this is just the best-rated films overall.")
    else:
        pool = model.teaching_order(rows=hits)
        if not query:
            st.caption("Well-known films your profile knows least about, spread across different "
                       "kinds of film. Rating these teaches it the most.")
    if len(pool) == 0:
        st.info("No matches.")
    pages = max(1, -(-len(pool) // PAGE))
    # Keyed on mode and query so the page resets whenever either changes.
    page = st.number_input(f"Page (of {pages})", 1, pages, 1, key=f"page-{mode}-{query}") if pages > 1 else 1
    start = (page - 1) * PAGE
    films.rows(pool[start: start + PAGE], "film", first_rank=None if query else start + 1)

    if ratings:
        with st.expander(f"Your ratings ({len(ratings)})"):
            films.rows(model.rated_order(), "mine")

with profile_tab:
    profile_panel(model)
