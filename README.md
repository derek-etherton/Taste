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
cp .env.example .env                                       # then fill in the source URLs, TASTE_DATABASE_URL, ...
cd backend
../.venv/Scripts/python scripts/prepare_data.py film       # one-off, writes data/film/
../.venv/Scripts/python scripts/prepare_data.py book       # one-off, writes data/book/ and data/traits.json
../.venv/Scripts/python -m pip install -e ".[data]"        # optional, then: Open Library metadata (see below)
../.venv/Scripts/python scripts/openlibrary.py
../.venv/Scripts/alembic upgrade head                      # create/upgrade the database tables (see Accounts)
../.venv/Scripts/uvicorn taste.api.app:app --reload        # the API; docs at http://localhost:8000/docs
../.venv/Scripts/python -m pytest                          # tests
cd ../frontend && npm install && npm run web               # the app in a browser, against the local API
```

After the one-off setup, `python dev.py` from the repo root starts both the API (port 8000, auto-reloading) and the web app (port 8081), and, with `TASTE_PG_BIN` set, the local Postgres (applying migrations first). Ctrl+C stops everything.

Settings come from the environment or the repo's `.env` (see `backend/taste/settings.py`): `TASTE_DATA_DIR` (default `data/` at the repo root), `TASTE_DOMAINS` (default `["book"]`), `TASTE_BOOK_GENOME` (default `truegenome`), `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_VISION_MODEL`, `CORS_ORIGINS` (a JSON list of the web app's origins; default `["http://localhost:8081"]`), and the account settings below.

**Books only, for now.** The app and API serve books from the `truegenome` BookGenome release (`data/genomes/book/truegenome/`). The film catalogue, taste carried over between films and books, other profiles and the genome switch are all still in the backend (and tested); `TASTE_DOMAINS=["film","book"]` brings films back to the API.

`data/` is generated locally and not committed. It holds the prepared catalogues and the shared-trait list (and, locally, the Postgres data in `data/pg`). Profiles live in the database.

## Accounts

People sign in with **Apple** (iOS) or **Google**, or tap **Continue without an account**. That makes a guest: a real but anonymous profile, kept by this device's session. A guest who signs in later keeps their ratings. If the Apple or Google account already has a profile, the guest's ratings merge into it, with the account's own ratings winning.

- **Sessions:** a random 256-bit token. The database stores only its sha256.
  - **Phones** keep the token in the iOS Keychain or Android Keystore (`expo-secure-store`) and send it as `Authorization: Bearer`.
  - **The web app** gets it as an HttpOnly, Secure, SameSite=Lax cookie that page scripts can't read. So in production the API and the web app must share a site (e.g. `taste.app` and `api.taste.app`), with that origin in `CORS_ORIGINS`.
  - Sessions expire after 90 days unused. Signing in ends the session the request came with. Sign Out ends one session; `POST /auth/logout?everywhere=true` ends all of them.
  - **Delete Account** removes the user and everything they own, as the App Store requires.
  - `/auth/*` is rate-limited per IP. `scripts/clean_up.py`, run daily, deletes guests unseen for 180 days.
- **Shelf photos** are served from signed links that expire after an hour, because an `<Image>` can't send the session.
- **The database** is Postgres. The schema is in `taste/storage/db.py`, and migrations live in `backend/migrations` (`alembic upgrade head`).
  - **Locally:** a portable Postgres works, nothing installed system-wide. Download the PostgreSQL Windows binaries zip and unzip it (e.g. to `D:/Tools/pgsql`). Then run, once: `initdb -D data/pg -U taste --auth=trust`, start it, and `psql -U taste -h localhost -d postgres -c "create database taste" -c "create database taste_test"`. Set `TASTE_PG_BIN` so `dev.py` starts it.
  - **With Docker:** `docker compose up` runs Postgres and the API.
- **Tests** use a throwaway SQLite file. Set `TASTE_TEST_DATABASE_URL` (e.g. `postgresql+psycopg://taste@localhost/taste_test`) to run them all against Postgres instead.

| Setting | |
|---|---|
| `TASTE_DATABASE_URL` | e.g. `postgresql+psycopg://taste@localhost:5432/taste` (required) |
| `TASTE_SECRET` | signs photo links; set a long random value in production (unset: random per start) |
| `TASTE_APPLE_CLIENT_IDS` | JSON list: the iOS bundle id (`TASTE_APP_ID` in the app's build) |
| `TASTE_GOOGLE_CLIENT_IDS` | JSON list: the Google web, iOS and Android client ids |
| `TASTE_DEV_LOGIN` | `true` locally: sign in as any email (no proof). Never in production |
| `TASTE_COOKIE_SECURE` | default `true` (browsers accept Secure cookies on `http://localhost`) |
| `TASTE_PG_BIN` | for `dev.py`: the folder with `pg_ctl` |

### Sign-in setup

- **Apple:** in the Apple Developer portal, create an App ID with the bundle id you'll ship (`TASTE_APP_ID`) and enable Sign in with Apple. Put the same id in `TASTE_APPLE_CLIENT_IDS`. Apple sign-in runs on iOS only for now. Web and Android need a Services ID and an https domain: a follow-up.
- **Google:** in Google Cloud, configure the OAuth consent screen and create three OAuth client ids: Web (with the web app's origin), iOS (with the bundle id) and Android. The app needs these in `frontend/.env.local`:
  - `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`
  - `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`
  - `EXPO_PUBLIC_GOOGLE_IOS_URL_SCHEME`, the iOS client's reversed client id.

  The API needs all three ids in `TASTE_GOOGLE_CLIENT_IDS`.
- **Native builds:** Google's native sign-in and Apple's need a development build (`npx expo run:ios`, or EAS), not Expo Go.
- **Until these exist,** guests and the dev email sign-in (`TASTE_DEV_LOGIN` plus the app's `EXPO_PUBLIC_DEV_LOGIN`) work end to end.

## Using the app

Three tabs: **Discover**, **Shelf scan** and **Profile**.

- **Discover:** unrated books ranked by how well they match you. The score chip opens a breakdown: which tags push the book up or down. Tap a title for the book's page: cover, first-publication year, description, subjects, why it scores what it does, and similar books. Search covers the whole catalogue, and **Filter by tags** puts books that have the chosen tags *and* rank high for you first. The thumbs-up, minus and thumbs-down buttons rate a book (like, meh, dislike); tapping the current one again clears it.
- **Shelf scan.** Photograph a bookshelf, at home or in a shop ("Take Photo" opens the camera on phones, including phone browsers; desktop browsers show only "Choose Photo"). Claude (Sonnet 5.5, `ANTHROPIC_API_KEY`) reads every spine in one request, at up to 2576 px on the long edge, noting each book's shelf and position (`taste/model/claude_vision.py`; `TASTE_SHELF_MODEL` and `TASTE_SHELF_EFFORT`, default `medium`, tune it). Without a key, a local Ollama vision model does it instead, finding each shelf row and reading it in pieces: `ollama pull qwen3-vl:8b-instruct`, or set `OLLAMA_VISION_MODEL`. The titles are matched to the catalogue, and the ones we know come back sorted for you. Spines it read but couldn't find are listed too, and each match says roughly where it is on the shelf. Your last scan is saved (in the database, with a small copy of the photo) and shown again until you scan another. The catalogue covers about 9,400 popular books, so newer or niche titles won't be found.
- **Profile.** Two tabs. **Taste**: your taste in books as an infographic: how you've rated (liked, meh, disliked), your 3 books (the best matches among books you liked or haven't read; a summary of your taste, not just recommendations), a one-line summary, and a butterfly chart of the ten tags you're most into against the ten you're least into, by how much each moves your scores (hover or tap a bar for its weight and the books you rated its way that have most of it). **Ratings**: the books you've rated.

Scores in the app are pure taste match: it sends `quality=0`, so other readers' ratings don't count (the truegenome release won't carry them for every book). The API still takes `quality` (default 0.1).

## API

`backend/taste/api/`, FastAPI. Everything about the signed-in user is under `/me` (the session says who):

| | |
|---|---|
| `POST /auth/guest`, `/auth/apple`, `/auth/google`, `/auth/dev`; `POST /auth/logout` | start a session (returns `{token, user}` and sets the cookie); end it |
| `GET /me`, `DELETE /me` | who's signed in; delete the account and everything in it |
| `GET /domains`, `GET /me/summary` | catalogues; per-domain confidence |
| `GET /domains/{domain}/tags` | the active genome's tags, to filter by |
| `GET …/{domain}/items?mode=for_you\|rate&q=&page=&quality=&tags=` | a page of item cards; with `tags` (repeatable), sorted by `tag_match` × the item's percentile in the mode's own order (has the tags *and* is high on your list) |
| `GET …/{domain}/items/{key}` | an item's page: card, distinctive tags, score breakdown, most similar items, and for books what Open Library knows (`book`) |
| `GET …/{domain}/items/{key}/explanation`, `GET …/{domain}/rated` | why an item scores what it does; your rated items |
| `PUT` / `DELETE …/ratings/{key}` | rate (`{"value": 1\|0\|-1}`) or clear |
| `GET …/profile` | shared traits and each domain's own taste, with evidence |
| `POST …/shelf-scans` + `GET …/shelf-scan` | start a scan (multipart `photo`), then poll for progress and ranked results, with a signed `image_url` for the photo |

`backend/scripts/export_openapi.py` writes the spec for the frontend's generated types. `backend/Dockerfile` builds the API image, with `data/` mounted at `/data`; it runs migrations on start.

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
taste/storage/    the database: db.py (schema), sql_store.py (accounts, sessions, ratings, shelf scans)
taste/api/        FastAPI: engine (catalogues, cached models, scan jobs), auth (sign-in, sessions), routes, schemas
taste/settings.py settings from the environment / .env
scripts/
  prepare_data.py     prepare_data.py <domain>
  openlibrary.py      refresh the books' Open Library metadata from the newest monthly dump
  clean_up.py         daily: delete long-idle guests and expired sessions
  export_openapi.py   the API spec, for the frontend
  scan_photo.py       run Shelf scan on photos from the command line
  sources/            one adapter per source dataset, all writing the common format
tests/            pytest: model, storage, accounts and API (no network)
migrations/       Alembic database migrations
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
- **Shelf-scan jobs and the sign-in rate limit live in the API process's memory.** A restart loses a running scan, and running several API instances needs a shared queue (e.g. SQS) and limiter first.
- **Apple sign-in is iOS-only,** and deleting an account doesn't yet revoke its Apple token (that needs an Apple signing key).
