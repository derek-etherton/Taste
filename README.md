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
../.venv/Scripts/python -m pip install -e ".[data]"        # optional, then: Open Library metadata (see below)
../.venv/Scripts/python scripts/openlibrary.py
../.venv/Scripts/python scripts/seed_profiles.py           # optional: normie and romantic test profiles
../.venv/Scripts/uvicorn taste.api.app:app --reload        # the API; docs at http://localhost:8000/docs
../.venv/Scripts/python -m pytest                          # tests
cd ../frontend && npm install && npm run web               # the app in a browser, against the local API
```

After the one-off setup, `python dev.py` from the repo root starts both the API (port 8000, auto-reloading) and the web app (port 8081). Ctrl+C stops both.

Settings come from the environment or the repo's `.env` (see `backend/taste/settings.py`): `TASTE_DATA_DIR` (default `data/` at the repo root), `TASTE_DOMAINS` (default `["book"]`), `TASTE_BOOK_GENOME` (default `truegenome`), `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_VISION_MODEL`, `CORS_ORIGINS` (a JSON list).

**Books only, for now.** The app and API serve books from the `truegenome` BookGenome release (`data/genomes/book/truegenome/`), for one profile (`main`). The film catalogue, taste carried over between films and books, other profiles and the genome switch are all still in the backend (and tested); `TASTE_DOMAINS=["film","book"]` brings films back to the API.

`data/` is generated locally and not committed. It holds the prepared catalogues, the shared-trait list, and the profiles in `data/users/<name>.json`, each with its ratings and latest Describe Me.

## Using the app

Three tabs: **Discover**, **Shelf scan** and **Profile**.

- **Discover:** unrated books ranked by how well they match you. The score chip opens a breakdown: which tags push the book up or down. Tap a title for the book's page: cover, first-publication year, description, subjects, why it scores what it does, and similar books. Search covers the whole catalogue, and **Filter by tags** puts books that have the chosen tags *and* rank high for you first. The thumbs-up, minus and thumbs-down buttons rate a book (like, meh, dislike); tapping the current one again clears it.
- **Shelf scan.** Photograph a bookshelf, at home or in a shop ("Take Photo" opens the camera on phones, including phone browsers; desktop browsers show only "Choose Photo"). A local vision model finds each shelf row and reads it in pieces (a whole bookcase at once is too much small text for it; about a minute for a full bookcase). The titles are matched to the catalogue, and the ones we know come back sorted for you. Spines it read but couldn't find are listed too, and each match says roughly where it is on the shelf. Your last scan is saved (in your profile file, with a small copy of the photo) and shown again until you scan another. Needs `ollama pull qwen3-vl:8b-instruct` (the instruct variant: the default tag "thinks" for minutes), or set `OLLAMA_VISION_MODEL`. The catalogue covers about 9,400 popular books, so newer or niche titles won't be found.
- **Profile.** Two tabs. **Taste**: your taste in books as an infographic: how you've rated (liked, meh, disliked), your 3 books (the best matches among books you liked or haven't read; a summary of your taste, not just recommendations), a one-line summary, and a butterfly chart of the ten tags you're most into against the ten you're least into, by how much each moves your scores (hover or tap a bar for its weight and the books you rated its way that have most of it). **Ratings**: the books you've rated.

Scores in the app are pure taste match: it sends `quality=0`, so other readers' ratings don't count (the truegenome release won't carry them for every book). The API still takes `quality` (default 0.1).

## API

`backend/taste/api/`, FastAPI. Everything is per user under `/profiles/{user}`:

| | |
|---|---|
| `GET /domains`, `GET /profiles`, `GET /profiles/{user}` | catalogues, users, per-domain confidence |
| `GET /domains/{domain}/tags` | the active genome's tags, to filter by |
| `GET …/{domain}/items?mode=for_you\|rate&q=&page=&quality=&tags=` | a page of item cards; with `tags` (repeatable), sorted by `tag_match` × the item's percentile in the mode's own order (has the tags *and* is high on your list) |
| `GET …/{domain}/items/{key}` | an item's page: card, distinctive tags, score breakdown, most similar items, and for books what Open Library knows (`book`) |
| `GET …/{domain}/items/{key}/explanation`, `GET …/{domain}/rated` | why an item scores what it does; your rated items |
| `PUT` / `DELETE …/ratings/{key}` | rate (`{"value": 1\|0\|-1}`) or clear |
| `GET …/profile` | shared traits and each domain's own taste, with evidence |
| `POST …/shelf-scans` + `GET …/shelf-scan` | start a scan (multipart `photo`), then poll for progress and ranked results |

`backend/scripts/export_openapi.py` writes the spec for the frontend's generated types. `backend/Dockerfile` builds the API image, with `data/` mounted at `/data`.

## Layout

```
backend/          the Python backend (paths below are inside it)
taste/model/      calculations: no UI, no storage
  catalog.py      one domain's items + centred item × tag matrix (common on-disk format)
  genomes.py      which genomes each domain has (default + data/genomes/<domain>/*) and loading one
  bookgenome.py   connector for BookGenome releases: links books to the default catalogue
  openlibrary.py  joins data/book/openlibrary.csv onto the books when a catalogue is read
  user_model.py   per-domain profile fit (Bayesian ridge with an optional prior), scoring,
                  ranking, teaching order, explanations
  traits.py       shared traits across domains: calibration, shared-taste posterior, priors
  describe.py     Describe Me (not in the API for now): profile -> text brief -> a taste horoscope from a local LLM
  shelf.py        Shelf scan: photo -> spine titles (vision model) -> catalogue matches -> ranked
  llm.py          the local Ollama client both of those use
taste/storage/    per-user ratings, Describe Me, last shelf scan: ProfileStore + JsonProfileStore
taste/api/        FastAPI: engine (catalogues, cached models, scan jobs), routes, schemas
taste/settings.py settings from the environment / .env
scripts/
  prepare_data.py     prepare_data.py <domain>
  openlibrary.py      refresh the books' Open Library metadata from the newest monthly dump
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
| `items.csv` | `id, title, year, creator, genres, series, series_index, n_ratings, mean_rating, quality` (creator to series_index may be blank); books add `goodreads_id` |
| `tags.json` | tag names, in column order |
| `relevance.npy` | items × tags, each score in [0, 1] |

`data/traits.json` lists the tag correspondences between domains, e.g. `{"film": "dystopia", "book": "dystopia"}`. Adding a domain means writing one adapter and extending the correspondences.

### Genomes

`data/<domain>/` is a domain's `default` genome. `TASTE_<DOMAIN>_GENOME` picks the one the server uses (books: `truegenome`). The engine can also switch at runtime (`Engine.switch_genome`, not exposed by the API for now). Genomes it can use:

- `data/genomes/<domain>/<name>/` in the common format, or for books a [BookGenome](../BookGenome) release folder;
- BookGenome release folders used in place, listed in `TASTE_BOOK_GENOME_PATHS` (a JSON list of paths).

A BookGenome release's books are linked to the default catalogue by title and author surname (subtitles, punctuation and "The" ignored), so they keep its IDs, and your ratings; the rest get `book:gb-<release id>` and average quality. Every release book counts equally when centring. Its tags inherit film links from the default tags they were derived from (`tags.csv`), preferring a same-named one; new tags stay book-only. Items missing from the active genome don't appear, but their ratings stay saved.

### Open Library

`backend/scripts/openlibrary.py` matches the books to [Open Library](https://openlibrary.org) works and keeps their metadata. It matches by the source's Goodreads ID (on Open Library editions), and otherwise by main title and author surname. Merged works are followed through Open Library's redirects. It writes three files to `data/book/`:

| File | Contents |
|---|---|
| `openlibrary.duckdb` | our own copy of everything about the matched books: works, all their editions, authors, series, Open Library's ratings and reading log, for later features |
| `openlibrary.csv` | what the app uses, one row per matched book: work ID, first-publication year (the earliest plausible edition year; the dataset's year is often a reprint's), series, description, first sentence, subjects, places, people, times, authors with dates, pages, original language, cover, ISBN, links, and Open Library's own rating and reader counts (stored, not yet used in scoring) |
| `openlibrary.json` | which dump it was built from, and match counts |

When a catalogue is read, the first-publication year replaces `year`, and Open Library's series fills in books whose title doesn't name one. The item page shows the rest.

Open Library publishes full dumps monthly, about two days after month end (archive.org collection `ol_exports`). The script only downloads when a newer dump is out, so it is safe to schedule weekly, e.g. with Windows Task Scheduler running `.venv/Scripts/python scripts/openlibrary.py` from `backend/`, or cron. Restart the API afterwards. A refresh needs about 20 GB of disk while it runs (the works, editions and authors dumps), deleted afterwards unless `--keep-raw`. `--force` rebuilds from the same dump, and `--dump YYYY-MM-DD` picks one. Set `TASTE_OPENLIBRARY_CONTACT` to put a contact in the User-Agent, as Open Library asks. On licensing, Open Library says the Internet Archive asserts no new copyright over the database. It doesn't name a licence.

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
