# Taste

A prototype of a person-centred recommender across films and books, built on per-item tag relevance scores. Rate items 👍 / 😐 / 👎, then see recommendations, how strongly any item is recommended and why, and the profile the system has inferred about you. Taste learnt in one domain carries over to the other through shared traits.

New to the maths? Start with [docs/how-it-works.md](docs/how-it-works.md), a plain-language walkthrough.

## Run

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
cp .env.example .env                               # then fill in the source URLs (and Ollama settings, if not the defaults)
.venv/Scripts/python scripts/prepare_data.py film  # one-off, writes data/film/
.venv/Scripts/python scripts/prepare_data.py book  # one-off, writes data/book/ and data/traits.json
.venv/Scripts/streamlit run taste/view/app.py
.venv/Scripts/python -m pytest                     # tests
```

`data/` is generated locally and not committed. It holds the prepared catalogues, the shared-trait list, and `data/user.json`: your ratings and your latest Describe Me.

## Using the app

- **Sidebar.** Pick Films or Books. **Weight on general quality** sets how much widely-liked items get a boost.
- **For you.** Unrated items ranked by how well they match you. The percentile button opens a breakdown: which tags push the item up or down, how much comes from general quality, and how much carried over from your other domain. Book series show as one entry: the next volume you haven't rated.
- **Rate films / Rate books.** Every unrated item. The 600 best-known come first, ordered by how unsure your profile is about them, i.e. the ratings that would teach it most. The rest follow, best-known first.
- **Profile.** Three views:
  - **Shared traits:** taste that carries across domains.
  - **Films only** and **Books only:** taste each domain adds on top.

  Every claim lists the rated items behind it. **Describe Me** asks a local [Ollama](https://ollama.com) model for a fun four-line "taste horoscope" built from your profile. By default it uses `qwen3:8b` at `http://localhost:11434`; set `OLLAMA_MODEL` / `OLLAMA_URL` in `.env` to change that.

## Layout

```
taste/model/      calculations, no UI
  catalog.py      one domain's items + centred item × tag matrix (common on-disk format)
  ratings.py      data/user.json: ratings across domains, and the saved Describe Me
  user_model.py   per-domain profile fit (Bayesian ridge with an optional prior), scoring,
                  ranking, series collapsing, teaching order, explanations
  traits.py       shared traits across domains: calibration, shared-taste posterior, priors
  describe.py     Describe Me: profile -> text brief -> a four-line taste horoscope from a local LLM
taste/env.py      reads .env (source URLs, Ollama settings)
taste/view/       Streamlit UI, imports taste.model
  app.py          entry point: sidebar, tabs, wiring
  components.py   item rows, rating buttons, score breakdown, profile lists
scripts/
  prepare_data.py     prepare_data.py <domain>
  sources/            one adapter per source dataset, all writing the common format
tests/            pytest: films, books, ratings, cross-domain transfer, Describe Me (no network)
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
- **A single user and a local JSON file.** Two browser tabs can overwrite each other's ratings.
