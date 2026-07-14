# Module 1 Methodology -- RQ1: Hidden Concentration

What was done to produce `chart1_sp500_concentration.png`, `chart2_effective_exposure.png`,
`m1_beta_table.csv`, and `m1_findings.md`. Code lives in `analysis/m1_concentration.py`.

## Data

Daily adjusted close prices for 19 tickers were pulled from yfinance (max available
history) into a local SQLite database (`data/prices.db`), per the project-wide pipeline
in `data/pull_prices.py`. Module 1 uses:

- **AI basket:** NVDA, MSFT, GOOGL, META, AMZN, AAPL, AVGO, TSM -- equal-weighted.
- **Portfolios tested:** SPY, VT, QQQ, RSP, plus a synthetic 60/40 (60% SPY + 40% TLT).
- **Sanity-check ticker:** TLT (long-term Treasuries), expected to show ~zero AI exposure.

A gate check (SPY's 2022 peak-to-trough drawdown, reproduced at -24.5% against a known
~-25%) was run before any Module 1 analysis, per the project's rigor rule: if the
pipeline can't reproduce a known fact, nothing downstream is trusted.

## Part A -- Effective exposure (the regression)

For each portfolio, daily log returns were regressed (OLS) on the AI basket's daily log
returns over the trailing 252 trading days (~1 calendar year, 2025-07-10 to 2026-07-10).
The basket itself is the equal-weighted mean of the 8 tickers' simple daily returns,
converted to log returns, restricted to days where all 8 have data.

The regression coefficient (beta) is treated as "effective exposure": the fraction of a
portfolio's day-to-day return variation that moves in step with the AI basket, regardless
of what the portfolio's fact sheet says it holds. R^2 indicates how much of the
portfolio's variance the basket explains on its own.

Two built-in sanity checks: QQQ should show the highest beta among the portfolios (it
did, 0.75), and TLT should be near zero (it was, 0.05).

## Part B -- Direct (naive) weight

For comparison, each portfolio's "naive" AI-basket weight was computed as the sum of
AI-basket tickers appearing in its published top-10 holdings list:

- **SPY** (SSGA fact sheet, as of 2026-07-09): sum of NVDA/AAPL/MSFT/AMZN/GOOGL/AVGO/META
  in its top 10 = 33.77%. TSM does not appear because it is a foreign-domiciled ADR and
  is not S&P 500-eligible -- a real exclusion, not a data gap.
- **QQQ** (via stockanalysis.com, Invesco data, as of 2026-07-10): sum of the AI-basket
  names in its top 10 = 33.31%. This is a **lower bound** -- AVGO and TSM are Nasdaq-100
  constituents but fell outside QQQ's published top 10, so their real (nonzero) weight
  isn't captured.
- **VT** (via stockanalysis.com, Vanguard data, as of 2026-05-31): all 8 AI-basket
  tickers appear in its top 10 (a global fund, so TSM is a normal constituent) = 20.92%,
  a complete figure.
- **RSP:** not fetched -- computed analytically. RSP tracks the S&P 500 Equal Weight
  Index (~503 constituents, each ~1/503 of the fund), so 8 basket tickers contribute
  8 x (1/503) = 1.59%.
- **60/40:** derived, not fetched. 60% x SPY's 33.77% + 40% x 0% (TLT) = 20.26%.

Effective exposure and direct weight are on the same 0-100% scale by construction: if a
basket makes up X% of a portfolio and the remaining (100-X)% were completely uncorrelated
with the basket, the portfolio's regression beta on the basket would be approximately X.
Where effective exposure exceeds direct weight, the excess reflects portfolio holdings
*outside* the named AI basket that still move with it (other tech/semis/correlated
names) -- this is the "hidden" part of the exposure.

## Part C -- S&P 500 concentration history (Chart 1)

Per the Tier 1 shortcut in the project methodology, this is a set of documented anchor
points from press/research sources, not a reconstructed daily series:

| Year | Top-10 % of S&P 500 market cap | Source |
|---|---|---|
| 1990 | 19% | RBC Wealth Management, "The Great Narrowing" |
| 2000 | 23% (intra-year peak ~27%) | RBC Wealth Management |
| 2005 | 19% | General press consensus (same trough period) |
| 2010 | 19% | General press consensus (same trough period) |
| 2015 | 19% | RBC Wealth Management |
| 2020 | 27% | Press coverage of the zero-rate-era mega-cap rally surpassing the dot-com peak |
| 2025 | 40.7% | RBC Wealth Management, stated record for the year |
| 2026 (current) | 43% | CryptoBriefing, 2026-07-09, stated record high |

Anchor years are plotted at evenly-spaced positions (not a true year-linear axis),
since the gaps between anchors are uneven by design and a linear axis would crowd the
final two points (2025, 2026) together illegibly.

## Known limitations

- The AI basket is a single, hindsight-selected definition (8 large, currently-obvious
  AI/mega-cap names). No sensitivity check against an alternative basket was run in
  Tier 1 (planned for Tier 2).
- Linear beta from OLS is a rough, symmetric measure -- it does not distinguish
  upside vs. downside co-movement, which tends to understate correlation specifically
  during crashes.
- QQQ's direct weight is a known lower bound (see above); the true naive weight is
  higher, meaning QQQ's effective-vs-direct gap in Chart 2 is somewhat overstated
  relative to what a full-holdings pull would show.
- The concentration-history series (Chart 1) blends multiple secondary sources rather
  than one consistent primary methodology; exact "top-10 weight" definitions can vary
  slightly by source (float-adjusted vs. full market cap, timing within the year).
- All direct-weight and concentration figures are point-in-time snapshots (pulled
  2026-05 to 2026-07) and will drift as prices and index composition change.
