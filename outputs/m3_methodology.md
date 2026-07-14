# Module 3 Methodology -- Scenario Projection (T2.1)

What was done to produce `chart5_scenario_outcomes.png`, `chart6_tradeoff.png`,
`m3_scenario_table.csv`, and `m3_findings.md`. Code lives in `analysis/m3_scenarios.py`.

**Golden rule, restated:** nothing here claims a bubble exists or that a crash will
happen. Every number is conditional -- "if a 2000-style repricing occurred..." /
"if a 2022-style repricing occurred..." / "if a 2008-style repricing occurred...".
This module projects historical shock patterns onto today's measured betas; it does
not forecast anything.

## Gate check

Before any analysis, the script recomputes SPY's 2022 calendar-year max drawdown
directly from `data/prices.db` and asserts it's within 1 percentage point of -24.5%
(the same known number established in the M0 pipeline gate check). It reproduced
-24.50% and passed. The script aborts if this check fails.

## The two-factor model

Each portfolio's daily log returns are regressed on two factors over the trailing
252 trading days (same window convention as Module 1):

- **Factor 1 (AI):** the equal-weighted AI basket (NVDA, MSFT, GOOGL, META, AMZN,
  AAPL, AVGO, TSM) -- identical construction to `m1_concentration.py`.
- **Factor 2 (rest):** RSP (equal-weight S&P 500) residualized against the AI
  basket. RSP's own log returns are regressed on the AI basket's log returns over
  the same window; the OLS residual -- what's left of RSP's return after removing
  its AI-basket-explained component -- is used as an orthogonal "rest of market"
  factor. Because it's constructed as an OLS residual, it is exactly uncorrelated
  with the AI basket over its fitting window by definition, and its mean return
  over that same window is ~0 (OLS residuals with an intercept always sum to zero).

Each portfolio (SPY, VT, QQQ, RSP, synthetic 60/40, TLT) is then regressed on
`[AI factor, rest factor]` together to get `beta_ai` and `beta_rest`.

### Sanity checks (all passed)

- QQQ has the highest `beta_ai` of the six portfolios (0.7461).
- TLT's `beta_ai` is under 0.1 (0.0487).
- Because the rest factor is exactly orthogonal to the AI factor over the fitting
  window, each portfolio's two-factor `beta_ai` should equal its Module 1
  single-factor beta almost exactly. It does -- every portfolio matched to within
  0.0001, well inside the 0.05 tolerance.

### A known tautology: RSP's own row

RSP is used to *build* the rest factor, so when RSP itself is regressed on
`[AI factor, rest factor]`, the fit is close to a mathematical identity: RSP's
return by construction equals `alpha + beta_ai_single x AI + 1 x residual`. The
table shows exactly this: RSP's `beta_rest = 1.0000` and `r_squared = 1.0000`.
**Read RSP's row as a mechanical reference point, not an independently estimated
finding** -- every other portfolio's beta_rest is a genuine regression result;
RSP's is not.

## The four scenarios

`Projected outcome ~= beta_ai x AI_shock + beta_rest x rest_shock` (linear, no
alpha/drift term -- see Limitations).

1. **"No bubble" (trend continuation).** `AI_shock` = the AI basket's own trailing
   3-year (756 trading day) annualized return (43.6%). `rest_shock` = the rest
   factor's trailing 3-year annualized return, computed the same
   residualization way as the 252-day factor but over the 3-year window. Because
   OLS residuals have ~zero mean over their own fitting window by construction,
   this comes out to ~0.0% -- meaning the "no bubble" baseline's upside is being
   driven almost entirely by each portfolio's `beta_ai`, not by any assumed
   rest-of-market drift. This is a direct, expected consequence of the
   residualization method, not a separate modeling choice; see Limitations.
2. **"Dot-com-style repricing."** `AI_shock = -77.9%` (Nasdaq Composite's Module 2
   dot-com max drawdown -- the era's most concentrated, most tech-heavy index maps
   to today's AI basket). `rest_shock = -34.1%` (Module 2's dot-com Value/IWD max
   drawdown -- the era's non-epicenter maps to today's rest-of-market factor).
3. **"2022-style repricing."** `AI_shock = -34.8%` (QQQ's Module 2 2022 max
   drawdown). `rest_shock = -17.0%` (VTV's Module 2 2022 max drawdown).
4. **"2008-style repricing" (the GFC).** `AI_shock = -53.4%` (QQQ's Module 2 GFC
   max drawdown). `rest_shock = -59.8%` (Module 2's GFC Value/IWD max drawdown).
   Unlike the dot-com mapping, this `rest_shock` is *not* small relative to its
   `AI_shock` -- it's actually larger in magnitude. That's expected, not a data
   error: 2008 was a systemic crash, not a concentration crash (see Module 2's GFC
   findings), so "the rest of the market" fell about as hard as the epicenter,
   sometimes harder. This is the weakest of the three historical analogies used in
   this module -- tech was not the epicenter of the GFC, so "Nasdaq's 2008 drawdown
   maps to today's AI basket" really means "what happened to growth assets in a
   crisis that was not about them." See `LIMITATIONS.md`, Module 3 section.

All four shock values are read programmatically from `outputs/m2_drawdown_table.csv`,
not re-typed by hand, so they can't drift out of sync with Module 2's own numbers.

## Results summary

| Portfolio | beta_AI | beta_rest | No bubble | 2022-style | 2008-style | Dot-com-style |
|---|---|---|---|---|---|---|
| QQQ | 0.75 | 0.41 | +33% | -33% | -64% | -72% |
| SPY | 0.50 | 0.52 | +22% | -26% | -58% | -57% |
| VT | 0.50 | 0.65 | +22% | -28% | -66% | -61% |
| 60/40 | 0.32 | 0.41 | +14% | -18% | -41% | -39% |
| RSP | 0.25 | 1.00* | +11% | -26% | -73% | -54% |
| TLT (control) | 0.05 | 0.23 | +2% | -6% | -16% | -12% |

\* tautological, see above.

**Notice the 60/40 (and RSP) row: the 2008-style projection is *worse* than the
dot-com-style one**, even though the dot-com `AI_shock` (-77.9%) is larger in
magnitude than the 2008 `AI_shock` (-53.4%). The reason is `beta_rest`: 60/40 has
meaningful exposure to the rest-of-market factor (0.41), and 2008's `rest_shock`
(-59.8%) is much deeper than dot-com's (-34.1%) -- so a portfolio with balanced
factor exposure takes a bigger hit from the "systemic" scenario than from the
"concentration" one, even though the latter's headline AI-basket shock number looks
scarier in isolation. See `m3_findings.md` for the full comparative read.

## Known limitations (see also `LIMITATIONS.md` Module 3 section)

- **Linear projection, real crashes are not linear.** The formula assumes a fixed
  beta holds all the way through a shock of that size. In practice, correlations
  between asset classes rise specifically during drawdowns (already flagged as a
  project-wide limitation) -- so a beta measured over a calm 252-day window likely
  understates how correlated a portfolio would actually be with the AI basket in a
  real crash, meaning the loss-scenario numbers here are more likely too small than
  too large.
- **Scale mismatch in beta_rest x rest_shock.** `beta_rest` is estimated against a
  residual factor whose day-to-day swings, over a calm year, are small relative to
  a real crash-era ETF return. The scenario shocks plugged in (-34%, -17%) are real
  crash-era magnitudes. Multiplying a beta calibrated on small idiosyncratic noise
  by a large real-world shock is a simplification, not a rigorous factor-model
  projection -- it's most visible in RSP's row, where the tautological
  `beta_rest = 1.0` combined with a large `rest_shock` produces a projected dot-com
  loss (-54%) that runs deeper than Module 2's actual measured value-stock drawdown
  (-34%) it's partly built from.
- **The shock mapping is an analogy, not an identity.** "Nasdaq Composite in 2000 is
  like the AI basket today" and "Value/IWD in 2000 is like the rest-of-market factor
  today" are structural analogies (concentrated leader vs. non-epicenter), not the
  same instruments or even the same market structure 20+ years apart. The 2008
  mapping is weaker still -- see `LIMITATIONS.md`, Module 3 section, for why.
- **Alpha is ignored in every projection.** Each portfolio's estimated `alpha`
  (average daily return unexplained by either factor) is reported in the table but
  deliberately excluded from the scenario formula -- the projection is purely
  factor-driven.
- **RSP's rest-of-market factor is a constructed series, not an investable asset.**
  Nobody can buy "the residual of RSP after removing its AI-basket-explained
  return" -- it's a modeling device, useful for decomposition, not a real fund.
- **Scenario, not forecast.** Nothing here claims either repricing will happen. The
  three scenarios describe what today's measured exposures would imply under two
  specific historical shock sizes, full stop.
