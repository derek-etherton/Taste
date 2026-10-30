# Taste

A prototype of a person-centred recommender across films and books, built on per-item tag relevance scores. Rate items 👍 / 😐 / 👎, then see recommendations, how strongly any item is recommended and why, and the profile the system has inferred about you. Taste learnt in one domain carries over to the other through shared traits.

New to the maths? Start with [docs/how-it-works.md](docs/how-it-works.md), a plain-language walkthrough.

## Run

Two parts, deployed independently:

- `backend/`: Python model, storage and HTTP API (FastAPI).
- `frontend/`: the app for web, Android and iOS (Expo / React Native), talking to the API. See [frontend/README.md](frontend/README.md).

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e "backend[dev]"
cp .env.example .env                                       # then fill in the source URLs (and Ollama settings, if not the defaults)
cd backend
../.venv/Scripts/python scripts/prepare_data.py film       # one-off, writes data/film/
../.venv/Scripts/python scripts/prepare_data.py book       # one-off, writes data/book/ and data/traits.json
../.venv/Scripts/python scripts/seed_profiles.py           # optional: normie and romantic test profiles
../.venv/Scripts/uvicorn taste.api.app:app --reload        # the API; docs at http://localhost:8000/docs
../.venv/Scripts/python -m pytest                          # tests
cd ../frontend && npm install && npm run web               # the app in a browser, against the local API
```

After the one-off setup, `python dev.py` from the repo root starts both the API (port 8000, auto-reloading) and the web app (port 8081). Ctrl+C stops both.

Settings come from the environment or the repo's `.env` (see `backend/taste/settings.py`): `TASTE_DATA_DIR` (default `data/` at the repo root), `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_VISION_MODEL`, `CORS_ORIGINS` (a JSON list).

`data/` is generated locally and not committed. It holds the prepared catalogues, the shared-trait list, and the profiles in `data/users/<name>.json`, each with its ratings and latest Describe Me.

## Using the app

Three tabs: **Discover**, **Shelf scan** and **Profile**. Each starts with the **Profile** choice (`main` is yours; others are for testing) and **Weight on general quality** (how much widely-liked items get a boost).

- **Discover.** Pick Films or Books, then:
  - **For you:** unrated items ranked by how well they match you. The percentile chip opens a breakdown: which tags push the item up or down, how much comes from general quality, and how much carried over from your other domain. Book series show as one entry: the next volume you haven't rated.
  - **Rate films / Rate books:** see below.
  - **Your ratings.** Search covers the whole catalogue. 👍 😐 👎 rate an item; tapping the same one again clears it.
- **Shelf scan.** Photograph a bookshelf, at home or in a shop ("Take photo" on phones; "Choose photo" everywhere). A local vision model finds each shelf row, reads it in pieces (a whole bookcase at once is too much small text for it; about a minute for a full bookcase), the titles are matched to the book catalogue, and the ones we know come back sorted for the current profile. Spines it read but couldn't find are listed too, and each match says roughly where it is on the shelf. Each profile's last scan is saved (in its profile file, with a small copy of the photo) and shown again until you scan another. Needs `ollama pull qwen3-vl:8b-instruct` (the instruct variant: the default tag "thinks" for minutes), or set `OLLAMA_VISION_MODEL`. The catalogue covers about 9,400 popular books, so newer or niche titles won't be found.
- **Rate films / Rate books.** Every unrated item. The 600 best-known come first, ordered by how unsure your profile is about them, i.e. the ratings that would teach it most. The rest follow, best-known first.
- **Profile.** Three views:
  - **Shared traits:** taste that carries across domains.
  - **Films only** and **Books only:** taste each domain adds on top.

  Every claim lists the rated items behind it. **Describe Me** asks a local [Ollama](https://ollama.com) model for a fun four-line "taste horoscope" built from your profile. By default it uses `qwen3:8b` at `http://localhost:11434`; set `OLLAMA_MODEL` / `OLLAMA_URL` in `.env` to change that.

## API

`backend/taste/api/`, FastAPI. Everything is per user under `/profiles/{user}`:

| | |
|---|---|
| `GET /domains`, `GET /profiles`, `GET /profiles/{user}` | catalogues, users, per-domain confidence |
| `GET …/{domain}/items?mode=for_you\|rate&q=&page=&quality=` | a page of item cards (series collapsed) |
| `GET …/{domain}/items/{key}/explanation`, `GET …/{domain}/rated` | why an item scores what it does; your rated items |
| `PUT` / `DELETE …/ratings/{key}` | rate (`{"value": 1\|0\|-1}`) or clear |
| `GET …/profile` | shared traits and each domain's own taste, with evidence |
| `GET` / `POST …/description` | the saved Describe Me / write a new one (~30 s locally) |
| `POST …/shelf-scans` + `GET …/shelf-scan` | start a scan (multipart `photo`), then poll for progress and ranked results |

`backend/scripts/export_openapi.py` writes the spec for the frontend's generated types. `backend/Dockerfile` builds the API image, with `data/` mounted at `/data`.

## Layout

```
backend/          the Python backend (paths below are inside it)
taste/model/      calculations: no UI, no storage
  catalog.py      one domain's items + centred item × tag matrix (common on-disk format)
  user_model.py   per-domain profile fit (Bayesian ridge with an optional prior), scoring,
                  ranking, series collapsing, teaching order, explanations
  traits.py       shared traits across domains: calibration, shared-taste posterior, priors
  describe.py     Describe Me: profile -> text brief -> a four-line taste horoscope from a local LLM
  shelf.py        Shelf scan: photo -> spine titles (vision model) -> catalogue matches -> ranked
  llm.py          the local Ollama client both of those use
taste/storage/    per-user ratings, Describe Me, last shelf scan: ProfileStore + JsonProfileStore
taste/api/        FastAPI: engine (catalogues, cached models, scan jobs), routes, schemas
taste/settings.py settings from the environment / .env
scripts/
  prepare_data.py     prepare_data.py <domain>
  seed_profiles.py    test profiles (normie, romantic) built from lists of titles
  export_openapi.py   the API spec, for the frontend
  scan_photo.py       run Shelf scan on photos from the command line
  sources/            one adapter per source dataset, all writing the common format
tests/            pytest: model, storage and API (no network)
Dockerfile        the API image
docs/             how-it-works.md
```

### Common data format

Each source adapter writes `data/<domain>/`, so nothing in `taste/` knows which dataset an item came from:

| File | Contents |
|---|---|
| `items.csv` | `id, title, year, creator, genres, series, series_index, n_ratings, mean_rating, quality` (creator to series_index may be blank) |
| `tags.json` | tag names, in column order |
| `relevance.npy` | items × tags, each score in [0, 1] |

`data/traits.json` lists the tag correspondences between domains, e.g. `{"film": "dystopia", "book": "dystopia"}`. Adding a domain means writing one adapter and extending the correspondences.

## How it works (short version)

- Each item is a vector of tag relevances, centred on the average consumed item in its domain.
- Your taste in a domain is one signed weight per tag. An item's score is `weights · item + quality_weight · quality`, so every score splits into per-tag contributions.
- The weights are a Bayesian ridge fit to your likes (+1), mehs (0) and dislikes (−1). Rating noise and a typical item's taste signal are given equal variance, so one rating moves predictions about halfway towards it.
- Tags that exist in both domains (512 of them) are **shared traits**. Each is rescaled per domain so that equal values mean equally unusual for a film or for a book.
- The model is two-level: an item's score = shared taste (on shared traits) + domain-specific taste. `SHARE` in `traits.py` (0.5) splits the variance between the two.
- A domain starts from what your other domains' ratings say about shared taste (the prior mean), together with how sure that is (the prior covariance). Its own ratings then correct the prior, but only as far as the prior is unsure. With no books rated, book recommendations come purely from your films.
- **Rate** puts the 600 most-rated items first, ordered by posterior uncertainty and chosen greedily so the picks cover different kinds of item. The rest of the catalogue follows by popularity.

## Known limitations

- **Traits are treated as independent.** Horror, scary and creepy always appear together, so ratings pin down their blend but not each one. As a result, film evidence firms up a given book's prior only a little: 30 horror films cut *The Shining*'s shared uncertainty by about 20%. Next step: consolidate correlated traits into a few latent dimensions.
- **Quality leaks into taste.** Tags like "oscar (best actor)" and "inspirational" track acclaim as much as taste.
- **Source tag noise.** Some single tags are unreliable, e.g. "race" on a racing anime, or "cia" on *The Shining*.
- **Book years** are often the year of a later edition, not first publication.
- **Profiles are local JSON files** with no auth, and shelf-scan jobs live in memory (lost on restart). A database and auth come next.
