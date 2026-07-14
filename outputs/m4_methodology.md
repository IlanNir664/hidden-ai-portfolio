# Module 4 Methodology -- The Portfolio X-Ray App (T2.4 pulled forward)

What the app (`app/xray_app.py`) computes, the refactor that backs it, and how
edge cases are handled. Same format as `m1_methodology.md` and
`m3_methodology.md`.

## The refactor

Modules 1 and 3 each independently implemented the same beta/regression/
scenario machinery. That duplication is now gone: `analysis/factor_lib.py`
holds the single shared implementation --

- `load_prices`, `to_log_returns`, `ai_basket_simple_returns`
- `build_portfolio_simple_returns` (new: weighted-sum portfolio construction
  from an arbitrary ticker/weight dict -- needed by the app and tests, not used
  by `m1`/`m3` since they only ever build one fixed synthetic 60/40)
- `gate_check`, `single_factor_regress` (Module 1 convention)
- `build_rest_factor`, `two_factor_regress`, `annualized_return`,
  `load_m2_shocks`, `project_scenario` (Module 3 convention)
- `rolling_beta` (new: vectorized rolling single-factor beta, for the app's
  bonus panel)
- `overlapping_obs_count`, `MIN_REGRESSION_OBS` (new: a pre-flight check so a
  too-short user portfolio fails cleanly instead of crashing inside
  statsmodels -- see Edge cases below)
- `DIRECT_WEIGHT_PCT`, `AI_BASKET`, `WINDOW`, `LONG_WINDOW`, and the shared
  color palette constants

`m1_concentration.py` and `m3_scenarios.py` were both rewritten to import from
`factor_lib` instead of duplicating this logic. **After the refactor, both
scripts were re-run end to end and their CSV outputs (`m1_beta_table.csv`,
`m3_scenario_table.csv`) diffed byte-for-byte against the pre-refactor
versions -- identical.** The app imports the exact same `factor_lib` module, so
the research and the app share one implementation, not two that happen to
agree today.

## What the app computes

For a user-entered portfolio (ticker + weight rows, weights summing to 100%,
tickers restricted to the 20 cached in `data/prices.db`):

1. **Portfolio construction:** `build_portfolio_simple_returns` -- the
   weight-sum of constituent simple daily returns, restricted to dates where
   every constituent has data (a fixed-weight, daily-rebalanced portfolio; see
   Limitations for what that assumption skips).
2. **Single-factor regression** (`single_factor_regress`, Module 1 convention):
   the user portfolio's log returns regressed on the AI basket's log returns
   over the trailing 252 trading days -> `beta` (headline "effective exposure"
   %) and R².
3. **Two-factor regression** (`two_factor_regress`, Module 3 convention): the
   same portfolio regressed on `[AI basket, RSP-residualized rest-of-market
   factor]` -> `beta_ai` and `beta_rest`.
4. **Four scenario projections** (`project_scenario`): no-bubble (AI and rest
   factors' own trailing 3-year annualized returns), 2022-style, 2008-style, and
   dot-com-style, with shocks read live from `outputs/m2_drawdown_table.csv` --
   never hand-typed, exactly like Module 3. Bar order is ascending severity
   left to right (no-bubble -> 2022-style -> 2008-style -> dot-com-style).
5. **Direct (naive) weight**, computed only when every ticker in the user's
   portfolio resolves to a known contribution: AI-basket members contribute
   their full weight (holding NVDA directly is 100% "AI" by definition), and
   the five reference-portfolio tickers use `DIRECT_WEIGHT_PCT`. Any other
   ticker (VTV, EFA, TLT alone, GLD, the index tickers, IWD) makes the direct
   figure "not computable," and the app says so and explains why rather than
   guessing.

## Gate check

The app recomputes SPY's 2022 max drawdown from `data/prices.db` on every
startup and refuses to render anything if it's off by more than 1 percentage
point from -24.5% -- an `st.error` and `st.stop()`, not a silent fallback.

## The four panels + bonus panel

1. **Headline:** effective exposure % (beta), R², direct weight if computable,
   with an explicit `st.warning` when effective exposure exceeds 100% (see
   Edge cases).
2. **Comparison chart** (Chart 2 style): the five reference portfolios' direct
   and effective bars (read from `outputs/m1_beta_table.csv` and
   `factor_lib.DIRECT_WEIGHT_PCT`) plus the user's portfolio as a highlighted
   green "YOU" bar pair.
3. **Scenario bars** (Chart 5 style): the user's own three projected outcomes,
   same conditional titling and footnote as the PNG.
4. **The menu** (Chart 6 style): the five reference portfolios' dot-com-loss
   vs. no-bubble-gain points (read from `outputs/m3_scenario_table.csv`) in
   muted gray, the user's portfolio as a highlighted green diamond labeled
   "YOU." Repeats the project's stance: no recommended weight.
5. **Bonus, collapsed by default:** 252-day rolling beta_AI of the user's
   portfolio through time (via `factor_lib.rolling_beta`, a vectorized
   Cov(x,y)/Var(x) computation -- algebraically identical to the OLS slope
   `single_factor_regress` returns, just fast enough to compute at every date),
   with SPY's own rolling beta as a cached reference line.

## Visual identity

Every chart (`render_comparison_chart`, `render_scenario_chart`,
`render_tradeoff_chart`, `render_rolling_beta_chart`) reuses the exact hex
values from `factor_lib`'s palette constants -- the same light chart surface,
blue/yellow/red/muted-gray categorical colors, ink tones, and footnote
conventions as the PNG-producing scripts. Only the Streamlit page chrome
around the charts (background, headers, buttons, captions) uses the black
background / green terminal theme, injected via a scoped CSS block. This is
deliberate: golden rule 5 says match the existing chart visual identity, and
that identity is the light-surface research palette, not the app shell.

## Edge cases and how they're handled

- **Single-ticker portfolio:** works with no special-casing --
  `build_portfolio_simple_returns` with a one-entry weight dict just reproduces
  that ticker's own returns.
- **Portfolio holding basket members directly (e.g. 100% NVDA):** beta > 1 is
  possible and expected (verified: 100% NVDA shows ~122% effective exposure).
  The app shows an explicit `st.warning` explaining that the "direct weight %"
  reading assumes the non-basket remainder is uncorrelated with AI, which
  breaks down when the portfolio IS basket members -- see LIMITATIONS.md.
  Chart axes scale automatically to accommodate values over 100%.
- **Unsupported ticker:** validation lists exactly which ticker(s) aren't in
  the 26-ticker demo universe and shows the full supported list, rather than
  silently dropping or guessing.
- **Weights not summing to 100%:** a clear error plus a "Normalize to 100%"
  button that rescales proportionally -- the app never silently rescales
  without the user clicking it.
- **Duplicate tickers:** weights are summed automatically with an `st.info`
  notice, rather than erroring.
- **Very short overlapping history (< 252 obs):** `n_obs` is shown prominently
  and a warning fires when it's below the standard 252-day window.
- **Degenerate case (< 2 overlapping observations):** this used to crash
  inside statsmodels with an opaque `KeyError('const')` (`add_constant` treats
  a single-row input as already having a constant column and skips adding
  one). Fixed at the library level: `factor_lib.overlapping_obs_count` is
  checked *before* calling the regression, and `single_factor_regress` now
  raises a clean `ValueError` if called with fewer than
  `MIN_REGRESSION_OBS` rows regardless. Covered by
  `tests/test_factor_lib.py::test_single_factor_regress_raises_cleanly_on_degenerate_input`.
  This isn't reachable through the app's current 20-ticker universe (every
  cached ticker has ample recent overlapping history) but is defended anyway,
  since a future universe expansion could hit it.

## Testing

`tests/test_factor_lib.py` (11 tests, run via `pytest tests/ -v`): the gate
check (and that it raises on a wrong expectation), QQQ has the highest
beta_AI, TLT's beta_AI < 0.1, a 100% SPY user portfolio reproduces
`m1_beta_table.csv`'s SPY beta to 4 decimals, a 60% SPY / 40% TLT user
portfolio reproduces the synthetic 60/40 row, the two-factor beta_AI matches
the single-factor beta, the scenario formula is exactly
`beta_AI x AI_shock + beta_rest x rest_shock`, `load_m2_shocks` reads real
data, the degenerate-input guard, and the ticker universe includes the full
20-ticker set.

App-level behavior (no exceptions, correct values, edge cases) was verified
using Streamlit's `AppTest` harness rather than a manual browser click-through,
covering: the default 60/40 example, a single-ticker portfolio, 100% NVDA
(beta > 1), an unsupported ticker, weights not summing to 100%, and duplicate
tickers.

## Universe expansion: low/near-zero-AI reference ETFs

The original 20-ticker universe (the 8-name AI basket plus the research
modules' reference portfolios and crash-window proxies) meant every buildable
user portfolio had at least some measurable AI tilt -- there was no clean way
to test "what does a genuinely low-AI portfolio look like in this tool."
`data/pull_prices.py` now also pulls six sector/style ETFs chosen specifically
for minimal overlap with the AI basket's names: **XLU** (utilities), **XLP**
(consumer staples), **XLV** (health care), **VNQ** (real estate), **SCHD**
(dividend/value), and **IJR** (small-cap, which dilutes mega-cap concentration
the same way RSP does). Measured against the AI basket over the same 252-day
window used everywhere else in this project:

| Ticker | beta_AI | R² |
|---|---|---|
| XLP | -0.14 | 0.05 |
| SCHD | ~0.00 | ~0.00 |
| XLU | ~0.00 | ~0.00 |
| XLV | ~0.01 | ~0.00 |
| VNQ | 0.04 | 0.00 |
| IJR | 0.39 | 0.23 |

Five of the six read as genuinely uncorrelated with the AI basket (XLP and
SCHD even come out slightly negative -- noise around zero, not a real hedge,
per the app's own in-app caption for that case). IJR lands closer to RSP's
0.25, consistent with the same "diluted, not eliminated" concentration story
Module 1 tells for equal-weighting. Adding these did **not** change any
existing module's output: `m1_beta_table.csv` and `m3_scenario_table.csv` were
re-diffed byte-identical after the pull, since neither script references the
new tickers.

## Visual redesign

The app's chrome (not its charts -- see "Visual identity" above, unchanged) was
reworked into a black-background, green-terminal aesthetic: a box-drawn ASCII
banner, section headers styled like a diagnostic readout (`[1] YOUR HEADLINE
NUMBER`), each panel wrapped in a bordered `st.container`, a sidebar showing
live gate-check status and the categorized ticker universe, and a quick-preset
selector (60/40, 100% QQQ, 100% NVDA, a low-AI mix, 100% RSP, an all-weather-
ish mix) so a first-time user can explore without typing. All styling is a
scoped CSS block using only system-local monospace fonts -- no external font
or asset requests, preserving the "runs fully offline" requirement.

## App v2: universe expansion + dark fintech redesign

Two additive changes, neither touching `factor_lib`'s math (AI basket
definition and every regression/scenario formula are unchanged):

**Universe expansion.** `data/pull_prices.py` gained an `XRAY_UNIVERSE` dict
(~70 more tickers: broad-market and sector ETFs, international, bonds,
commodities, and popular single stocks) so users can build a portfolio out of
names they actually recognize, not just the original research tickers. The
pull is strictly additive at the data layer: `main()` now skips any ticker
already cached rather than re-fetching it, specifically so a universe
expansion can never shift the trailing 252/756-day windows `m1`/`m3` use and
silently break their byte-identical output. Verified: `m1_beta_table.csv`,
`m2_drawdown_table.csv`, and `m3_scenario_table.csv` were re-diffed
byte-identical after the pull. The DB now holds 100 tickers total. The app's
ticker input changed from free-text to a categorized, searchable multiselect
(`pull_prices.categories_for_app()` groups tickers for display) with a
manual-entry fallback for anything the picker's search doesn't surface.

Two new consequences of the wider universe, both handled explicitly:
direct (naive) weight remains computable for the original 5 reference
portfolios, AI-basket members, and now also bond/Treasury/physical-commodity
funds (`factor_lib.ZERO_DIRECT_WEIGHT_TICKERS`), which resolve to a known 0%
rather than "unknown" -- they hold no equities, so their AI-basket overlap is
zero by construction, exactly the reasoning already used for TLT inside the
synthetic 60/40 row (60% of SPY's weight + 0% from TLT = 20.26%, see
`outputs/m1_beta_table.csv`). This was a real gap in the initial v2 cut: the
default 60/40 preset was showing "naive weight: N/A" for a portfolio whose
direct weight the project's own research had already computed as 20.26% --
fixed so the app can't contradict `m1_beta_table.csv` for a portfolio that
matches a reference row. Everything else added in the expansion (equity ETFs,
single stocks) still has no sourced top-10-holdings weight and correctly
shows N/A. And single-stock/narrow
portfolios can post a low R² next to a large beta (e.g. 100% TSLA: beta > 1,
R² well under 0.3) -- the app now surfaces R² with a plain-language caption
explaining that beta is the slope of the relationship while R² is how much of
the portfolio's actual movement that relationship explains, with an extra
callout whenever R² drops below 0.3.

**Visual redesign.** The v1 black-background/green-terminal chrome (see
"Visual redesign" above) is replaced with a dark-fintech look: charcoal
background (`#0E0F0C`), card surfaces (`#1A1B17`) with large corner radii, a
lime-green primary accent (`#C8F135`) for the user's own series and the
headline numeral, indigo (`#5B4CF5`) used sparingly for the dot-com-style
scenario series, and a muted-amber tone for the 2022-style series. The
headline panel became a hero card: a large numeral for effective exposure
with naive weight, R², and trading-days-used as small labeled sub-stats
beside it. All four in-app charts moved from Matplotlib to Plotly (rounded
bars, direct end-of-line labels, a gradient glow-fill under the rolling-beta
line, interactive hover tooltips) -- **this is a deliberate departure from
v1's rule of matching the research PNGs' light-surface palette inside the
app.** The published research charts (`outputs/chart1-6*.png`) are completely
untouched; only the interactive, in-app versions now use their own dark
palette. Typography uses a system-local geometric-sans stack only (`Inter`,
`Space Grotesk`, `Segoe UI`, `system-ui`) -- no Google Fonts `@import`, to
preserve the "runs fully offline from a clean clone" requirement. Streamlit's
own theme is set via `.streamlit/config.toml` (dark base, matching colors) to
avoid a flash of default styling before the CSS block applies.

Two bugs surfaced by edge-case testing during this pass (both fixed in
`app/xray_app.py`, not `factor_lib.py`):
- Naive equal-weight redistribution (`round(100/n, 2)` per ticker) drifts off
  100.00 for any `n` that doesn't divide evenly (3 tickers -> 33.33 x 3 =
  99.99), which used to auto-trigger the "weights don't sum to 100%" error the
  moment a third ticker was added. Fixed by assigning the rounding remainder
  to the last ticker so the split always sums to exactly 100.00.
- The manual ticker-entry fallback used to write to
  `st.session_state["selected_tickers"]` *after* the multiselect widget bound
  to that same key had already been instantiated in the same script run --
  Streamlit forbids that and raised `StreamlitAPIException`. Fixed by moving
  the manual-entry expander above the multiselect call in the script, so its
  session-state write always happens before that widget is created.

A visual-review pass caught four more, all in `app/xray_app.py`'s CSS/chart
code, none touching `factor_lib`:
- A blanket `* { font-family: ... !important }` rule (added to keep the app's
  own text on a system-local geometric-sans stack) also overrode Streamlit's
  own bundled icon font (`data-testid="stIconMaterial"`, a local ligature font
  where the on-screen glyph literally IS the element's text content, e.g.
  `keyboard_double_arrow_right`). With the wrong font applied, those icons
  rendered as their raw text name instead of a glyph, visible in the sidebar
  collapse control, expanders, and select dropdowns. Fixed with a targeted
  `[data-testid="stIconMaterial"] { font-family: "Material Symbols Rounded" }`
  override, which wins on specificity regardless of source order.
- The same blanket-selector pattern broke two hand-written color rules: a
  generic `span { color: <muted> !important }` rule (added so plain markdown
  text stays muted) has `!important`, and CSS resolves importance before
  specificity -- so it beat two more-specific but non-`!important` custom
  rules (`.hero-number .unit` and `.diag-ok`), turning the hero card's "% AI"
  suffix and the sidebar's "PASS" badge gray instead of lime. Fixed by adding
  `!important` (and, for `.diag-ok`, extra scope) to the custom rules so they
  win outright.
- Each chart had both an in-figure Plotly title and the Streamlit step header
  directly above it stating the same thing -- redundant, and in the
  comparison chart the in-figure title visually overlapped the legend. Fixed
  by dropping every in-figure title; the step header is now the only title.
- The tradeoff chart's "YOU" label can land exactly on top of a reference
  portfolio's label when the user's portfolio matches that reference
  (unavoidable on the very first load: the default preset **is** the 60/40
  reference portfolio). Fixed by comparing the user's point to each reference
  point within a small tolerance and suppressing that reference's text label
  (the dot stays visible) whenever they coincide, so "YOU" is never fighting
  another label for the same pixels.

## Known limitations

See `LIMITATIONS.md`, Module 4 section, for the full list: the ~100-ticker
demo universe and why it can't grow without a code change; direct weight
being computable for only a small minority of that universe; the low-R²
single-stock case; the fixed-weight daily-rebalanced assumption and what it
ignores (drift, trading costs); that every Module 1 and Module 3 limitation
applies verbatim to any user portfolio built through this app; and the
beta > 1 case's specific breakdown of the direct-weight-% reading.
