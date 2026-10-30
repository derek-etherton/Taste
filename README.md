# Taste

A proof of concept for a person-centred film recommender built on per-film tag relevance scores. Rate films 👍 / 😐 / 👎, then see recommendations, how strongly any film is recommended and why, and the profile the system has inferred about you.

## Run

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
cp .env.example .env                           # then fill in TASTE_DATA_URL
.venv/Scripts/python scripts/prepare_data.py   # one-off (~250 MB), writes data/
.venv/Scripts/streamlit run taste/view/app.py
.venv/Scripts/python -m pytest                 # tests
```

## Layout

```
taste/model/      calculations, no UI
  catalog.py      films + centred film × tag matrix
  ratings.py      load / save / toggle the user's ratings (data/user.json)
  user_model.py   profile fit, scoring, ranking, teaching order, explanations
taste/view/       Streamlit UI, imports taste.model
  app.py          entry point: sidebar, tabs, wiring
  components.py   film rows, rating buttons, score breakdown, profile panel
scripts/          prepare_data.py
tests/            pytest
```

## How it works

- Each film is a vector of 1,128 tag relevances, centred on the average watched film.
- Your profile is one signed weight per tag, fit by ridge regression on likes (+1), mehs (0) and dislikes (−1).
- A film's score is `profile · film + quality_weight · quality`, so every score splits into per-tag contributions. The app shows these as "because" tags and in each row's percentile popover.
- **For you** ranks unrated films by score. **Rate films** ranks well-known films by how uncertain the profile still is about them, which is how much rating them would teach it.

`data/` is generated locally and not committed.
