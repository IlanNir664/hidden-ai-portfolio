# The Portfolio X-Ray

A single-page Streamlit app on top of this project's own research machinery
(`analysis/factor_lib.py`). Build a portfolio from a ~100-ticker demo universe
-- the AI basket and original research tickers, six low/near-zero-AI reference
ETFs (XLU, XLP, XLV, VNQ, SCHD, IJR), and a wide set of popular broad-market,
sector, international, bond, and commodity ETFs plus single stocks (see
`data/pull_prices.py`'s `XRAY_UNIVERSE`) -- via a categorized, searchable
picker (with a manual-entry fallback), and get back its hidden AI exposure,
where it sits among the project's reference portfolios, and its projected
outcome under four conditional scenarios (no-bubble, 2022-style, 2008-style,
dot-com-style). See `outputs/m4_methodology.md` for what it computes and
`LIMITATIONS.md` (Module 4 section) for what it doesn't.

Dark-fintech visual design, interactive Plotly charts throughout.

## Run locally

From the project root, with the venv activated and `data/prices.db` already
populated (run `python data/pull_prices.py` once first if it isn't):

```
pip install streamlit
streamlit run app/xray_app.py
```

Opens at `http://localhost:8501` by default. The app is fully offline after
that first pull -- everything reads from `data/prices.db`, nothing fetches
tickers at runtime.

## Run the tests

```
pip install pytest
pytest tests/ -v
```

## Deploying to Streamlit Community Cloud

1. Push this repo (including `data/prices.db`) to a public or private GitHub repo.
   `prices.db` is a small SQLite file (~10-15 MB) -- fine to commit directly for
   a demo app; for a larger universe you'd want a build step that runs
   `pull_prices.py` instead of committing the DB.
2. At https://share.streamlit.io, create a new app pointing at this repo,
   branch, and set the main file path to `app/xray_app.py`.
3. A `requirements.txt` is already committed at the repo root
   (`streamlit`, `pandas`, `numpy`, `statsmodels`, `matplotlib`, `plotly`,
   `yfinance`, `pytest`).
4. Deploy. The gate check runs on every app startup/reboot -- if it ever fails
   (e.g. the committed `prices.db` is stale or corrupted), the app will show an
   error screen instead of any numbers, by design.

## Extending the ticker universe

Today the supported universe is exactly what's cached in `data/prices.db`.
`factor_lib.available_tickers()` has an `# EXTENSION POINT` comment marking the
one function to change if you want the app to fetch new tickers live via
yfinance instead of only reading the cache -- everything else (validation,
regression, charts) is written generically against "whatever's in the
universe" and shouldn't need to change.
