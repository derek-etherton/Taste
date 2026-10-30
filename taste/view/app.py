"""Streamlit prototype: rate films and books, get recommendations, inspect your profile.

Run: streamlit run taste/view/app.py
"""

import streamlit as st
from st_keyup import st_keyup

from taste.model import (TRAITS_FILE, Catalog, TraitSpace, UserModel, available_domains, list_users, load_ratings,
                         user_file)
from taste.view.components import DOMAIN_ICON, EVIDENCE_NOTE, ItemList, claim_list, describe_me, shelf_scan

PAGE = 25

st.set_page_config(page_title="Taste", page_icon="🎬", layout="wide")


@st.cache_resource
def catalogs() -> dict[str, Catalog]:
    return {d: Catalog(d) for d in available_domains()}


@st.cache_resource
def trait_space() -> TraitSpace | None:
    return TraitSpace(catalogs()) if TRAITS_FILE.exists() and len(catalogs()) > 1 else None


cats, traits = catalogs(), trait_space()

with st.sidebar:
    st.title("Taste")
    user = st.selectbox("Profile", list_users(), key="user",
                        help="Each profile has its own ratings and description, in data/users/<name>.json.")
    path = user_file(user)
    # Ratings live in session state per profile, so switching back keeps edits made this session.
    profiles = st.session_state.setdefault("profiles", {})
    if user not in profiles:
        profiles[user] = load_ratings(path)
    ratings: dict[str, int] = profiles[user]
    domain = st.segmented_control(
        "Domain", list(cats), default=list(cats)[0], key="domain", label_visibility="collapsed",
        format_func=lambda d: f"{DOMAIN_ICON.get(d, '')} {cats[d].name}") or list(cats)[0]
    quality = st.slider("Weight on general quality", 0.0, 1.0, 0.1, 0.05,
                        help="0 = pure taste match. Higher = lean toward items everyone rates well.")
    models = {d: UserModel(c, ratings, prior=traits.prior(d, ratings) if traits else None)
              for d, c in cats.items()}
    for d, m in models.items():
        st.caption(f"{DOMAIN_ICON.get(d, '')} {m.confidence()}")



def item_list(d: str) -> ItemList:
    others = [cats[o].name.lower() for o in (traits.rated_domains(ratings) if traits else []) if o != d]
    return ItemList(cats[d], models[d], ratings, path, quality, source=" & ".join(others))


cat, model, items = cats[domain], models[domain], item_list(domain)
shelf = "book" in cats  # Shelf scan reads book spines, whichever domain is selected
tabs = st.tabs([cat.name] + (["Shelf scan"] if shelf else []) + ["Profile"])
list_tab, profile_tab = tabs[0], tabs[-1]

with list_tab:
    mode = st.segmented_control("List", ["For you", f"Rate {cat.name.lower()}"], default="For you",
                                key=f"mode-{domain}", label_visibility="collapsed") or "For you"
    query = st_keyup(f"Search {cat.name.lower()}", placeholder="Start typing a title or name…",
                     debounce=200, key=f"q-{domain}").strip()
    # Search covers the whole catalogue, rated items included, in the current mode's order.
    hits = cat.search(query) if query else None
    if mode == "For you":
        pool = model.ranked(quality, rows=hits)
        if not query and not len(model.rows) and not items.source:
            st.info(f"Rate a few {cat.name.lower()}. Until then this is just the best-rated overall.")
    else:
        pool = model.teaching_order(rows=hits)
        if not query:
            st.caption(f"Well-known {cat.name.lower()} your profile knows least about, spread across "
                       "different kinds. Rating these teaches it the most.")
    # One entry per series: the next volume you haven't rated, ranked by the series' best match.
    pool, more = model.collapse_series(pool)
    if len(pool) == 0:
        st.info("No matches.")
    pages = max(1, -(-len(pool) // PAGE))
    # Keyed on domain, mode and query so the page resets whenever any of them changes.
    page = (st.number_input(f"Page (of {pages})", 1, pages, 1, key=f"page-{user}-{domain}-{mode}-{query}")
            if pages > 1 else 1)
    start = (page - 1) * PAGE
    items.rows(pool[start: start + PAGE], domain, first_rank=None if query else start + 1, more=more)

    if len(model.rows):
        with st.expander(f"Your ratings ({len(model.rows)})"):
            items.rows(model.rated_order(), f"mine-{domain}")

if shelf:
    with tabs[1]:
        shelf_scan(item_list("book"), path)

with profile_tab:
    describe_me(models, traits, ratings, path)
    st.caption(EVIDENCE_NOTE)
    names = (["Shared traits"] if traits else []) + [f"{cats[d].name} only" for d in cats]
    sections = st.tabs(names)
    if traits:
        with sections[0]:
            st.caption(f"Traits that mean the same across {' and '.join(c.name.lower() for c in cats.values())}, "
                       "fit on all your ratings. This is what carries over between domains.")
            claim_list(*traits.profile(ratings), "No ratings yet.")
    for section, (d, m) in zip(sections[1 if traits else 0:], models.items()):
        with section:
            st.caption(m.confidence() + (". Taste learnt from these ratings alone, on top of what "
                                         "carried over from other domains." if traits else ""))
            claim_list(*m.profile(), f"No {cats[d].name.lower()} rated yet.")
