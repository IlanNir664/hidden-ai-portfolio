# Limitations

Honest accounting of what this project's numbers can and can't support. Written
alongside the analysis, not after -- per the project's rigor rule (see
`hidden_ai_portfolio_methodology.md`, T1.5).

## Project-wide

- **Hindsight-selected basket.** The AI basket (NVDA, MSFT, GOOGL, META, AMZN, AAPL,
  AVGO, TSM) is a single, currently-obvious set of large AI/mega-cap names chosen with
  the benefit of hindsight. No alternative basket definition (e.g. a basket as it would
  have looked in 2015) has been tested against it in Tier 1 -- headline findings have
  not yet been checked for survival under a different basket. Planned for Tier 2
  (basket sensitivity, T2.2). Partial exception: the X-ray app's "Why these 8 tickers?"
  expander (Module 4) does compute a live cap-weighted alternative, using a rough
  market-cap snapshot (`factor_lib.AI_BASKET_CAP_WEIGHT_PCT`), but only as a
  self-contained sensitivity check on the user's own portfolio, not as a re-run of
  Module 1/3's published findings -- those remain equal-weighted-only.
- **Linear beta understates crash correlations.** Effective exposure is measured via
  OLS beta, a linear, symmetric measure. It does not distinguish upside from downside
  co-movement, and cross-asset correlations are well documented to rise specifically
  during drawdowns -- so beta estimated over a normal period likely understates how
  correlated a portfolio would actually be with the AI basket in a crash.
- **Index proxies pre-2003.** Several ETFs used as "diversified portfolio" proxies
  (VT, RSP, EFA, TLT, GLD) don't have price history reaching back to the dot-com era;
  where a crash-era comparison is needed before an ETF's inception, the underlying
  index (^GSPC, ^IXIC, ^NDX) is substituted. This is a proxy, not the same instrument
  investors could have actually held at the time.
- **Scenario ≠ forecast.** Nothing in this project claims AI is a bubble or that a
  crash will happen. Every crash-adjacent conclusion is conditional ("if a 2000-style
  repricing occurred...") -- past patterns are described, not projected, in Tier 1.

## Module 1 -- Hidden Concentration (RQ1)

- **QQQ's direct weight is a lower bound.** The naive/direct AI-basket weight for each
  portfolio was computed from published top-10 holdings lists. AVGO and TSM are
  Nasdaq-100 constituents but fell outside QQQ's published top 10, so their real
  (nonzero) weight isn't captured -- QQQ's true direct weight is higher than the 33.31%
  used, meaning the effective-vs-direct gap shown for QQQ in Chart 2 is somewhat
  overstated relative to what a full-holdings pull would show.
- **SPY excludes TSM by construction, not by gap.** TSM does not appear in SPY's direct
  weight because it's a foreign-domiciled ADR and isn't S&P 500-eligible -- a real
  exclusion, not missing data.
- **RSP and the synthetic 60/40's direct weights are computed, not fetched.** RSP's
  1.59% assumes ~503 equal-weighted constituents; 60/40's 20.26% is 60% of SPY's figure
  plus 0% from TLT. Both are simplifying assumptions rather than pulled fund data.
- **Concentration-history anchor points blend sources.** Chart 1's 1990-2026 series
  combines RBC Wealth Management (1990/2000/2015/2025), general press consensus
  (2005/2010), and CryptoBriefing (2026) rather than one consistent primary
  methodology. Exact "top-10 weight" definitions can vary slightly by source
  (float-adjusted vs. full market cap, timing within the year) -- treat the series as
  directionally reliable, not decimal-precise.
- **Point-in-time snapshots.** All direct-weight and concentration figures were pulled
  2026-05 to 2026-07 and will drift as prices and index composition change; they are
  not re-derived from the priced time series in `data/prices.db` the way the beta
  regression is.

## Module 2 -- The Crash Replay (RQ2)

- **IWD and EFA are truncated in the dot-com window.** VTV (value) and the 2003+
  diversified ETFs don't reach back to March 2000, so IWD (Russell 1000 Value,
  inception 2000-05-26) and EFA (inception 2001-08-27) stand in -- but both start
  partway through the Mar 2000-Oct 2002 window. Their reported max drawdown is a
  floor, not the true peak-to-trough figure: if either asset class fell further
  before its data starts, this analysis understates that decline. Marked with `*`
  on Chart 3 and flagged `truncated_start` in `m2_drawdown_table.csv`.
- **No bonds or gold in the dot-com replay.** TLT (inception 2002-07-30) and GLD
  (inception 2004-11-18) have no price history before the window and are omitted
  from Chart 3 entirely, rather than shown with a multi-year gap. The dot-com
  "concentration crash" story therefore rests on four series, not the six used for
  the 2022 window.
- **Index vs. ETF instruments aren't identical even within the same role.** ^GSPC and
  ^IXIC (used for the dot-com window) are price-return indices, not investable
  total-return instruments -- they exclude the dividend reinvestment that SPY and
  QQQ (used for the 2022 window) include. This slightly understates the dot-com
  window's actual investor returns relative to the 2022 figures.
- **Max drawdown is a single worst-case number**, not a distribution. It says
  nothing about how long a drawdown lasted or how an investor's actual entry/exit
  timing would have changed the loss they experienced.
- **Historical replay only, not a projection.** This module does not apply the
  dot-com or 2022 shock to today's portfolios -- that link is deliberately left
  qualitative in Tier 1 (see `outputs/m2_findings.md`) and is planned as Tier 2's
  scenario projection (T2.1).

## Module 3 -- Scenario Projection (T2.1)

- **Linearity breaks in real crashes.** The core formula
  (`beta_AI x AI_shock + beta_rest x rest_shock`) assumes a fixed linear
  relationship holds across the entire size of a shock. Real relationships between
  asset classes are not linear at crash scale, and betas estimated over calm
  periods are a poor guide to how instruments actually move together once a real
  drawdown starts.
- **Correlations rise in drawdowns, so this likely understates losses, not
  overstates them.** Betas here are estimated over a trailing 252-day window with
  no major stress event in it. Cross-asset correlations are well documented to
  rise specifically during crashes -- meaning the true co-movement between a
  portfolio and the AI basket in an actual repricing would likely be higher than
  the calm-period beta used here, making the projected losses in Chart 5 and
  Chart 6 probably optimistic, not pessimistic.
- **The shock mapping is an analogy, not an identity.** Nasdaq Composite's 2000
  drawdown is used as the "AI basket" shock, and Value/IWD's 2000 drawdown as the
  "rest of market" shock, because both played structurally similar roles
  (concentrated leader vs. non-epicenter) in that crash. They are not the same
  instruments, sectors, or market structure as today's AI basket and today's
  rest-of-market factor -- the mapping is a reasoned analogy, not a mathematical
  equivalence.
- **The residualized rest-of-market factor is a construction, not an investable
  asset.** It's built as RSP's return with its AI-basket-explained component
  removed (an OLS residual) -- nobody can buy this series. It's a modeling device
  for decomposing returns, not a real fund, and its scale (calm-period residual
  noise) is much smaller than the real crash-era shock magnitudes it gets
  multiplied by in the scenario formula. This is most visible in RSP's own row:
  because RSP is the series used to build the factor, its two-factor regression
  on itself is close to a mathematical tautology (`beta_rest = 1.0`,
  `R^2 = 1.0`), and combined with a large real-world shock this produces a
  projected dot-com loss for RSP (-54%) that runs deeper than the actual
  value-stock drawdown (-34%) the shock itself is based on. Read RSP's scenario
  numbers as a mechanical reference point, not an independent finding.
- **Alpha is ignored in every projection.** Each portfolio's estimated alpha
  (average daily return unexplained by either factor) is computed and reported
  but deliberately excluded from the scenario formula -- projections are
  purely factor-driven, with no baseline drift term added on top.
- **The 2008 mapping is the weakest structural analogy of the three.** The
  dot-com and 2022 shock mappings both map a concentrated/hyped leader onto
  today's AI basket -- a genuine, if imperfect, concentration-crash analogy. The
  2008 mapping does not: tech was NOT the epicenter of the Global Financial
  Crisis, so "Nasdaq's (QQQ's) 2008 drawdown maps to today's AI basket" really
  means "what happened to growth assets in a systemic crisis that was not about
  them at all." Read the 2008-style scenario as the systemic-crash counterpoint
  to the other two, not as another data point in the concentration story --
  it exists to show what happens when diversification away from the "hot" trade
  does *not* help, which is a different and arguably more important question
  than "did the AI basket specifically get overpriced."
- **Flight-to-quality asymmetry: the 2008-style projection cannot credit bonds
  for what bonds actually did.** TLT *gained* about 26% over the 2007-2009
  window (Module 2) -- a real flight-to-quality effect specific to systemic
  crises, absent from the dot-com and 2022 windows. But the two-factor model's
  `rest_shock` is built from an equity-only proxy (RSP residualized against the
  AI basket), so a bond-holding portfolio's 2008-style projection only reflects
  bonds through `beta_rest x rest_shock` -- an equity-market shock -- never
  through bonds' own actual (positive) behavior. A real 60/40 investor's
  2008-style outcome would likely be meaningfully better than this module's own
  projected number for 60/40 shows, precisely because of a mechanism this
  factor model has no way to represent. See `m3_findings.md` for the specific
  number.
- **Scenario, not forecast.** As with Module 2, nothing here claims a bubble
  exists or that any repricing will occur. The four scenarios describe what
  today's measured exposures would imply under three specific historical shock
  sizes and one trend-continuation baseline -- full stop.

## Module 4 -- The Portfolio X-Ray App

- **The ~140-ticker demo universe is fixed, not a general portfolio tool.**
  The app can only price a portfolio built from tickers already cached in
  `data/prices.db` -- it does not fetch new tickers at runtime. Beyond the
  original research tickers and the six low/near-zero-AI reference ETFs
  (XLU, XLP, XLV, VNQ, SCHD, IJR), app v2 added roughly 70 more popular ETFs
  and single stocks (`data/pull_prices.py`'s `XRAY_UNIVERSE`) purely so users
  can build a portfolio out of names they actually recognize or hold. Pick a
  ticker outside the full set (via the manual-entry fallback -- the main
  picker only ever offers tickers already in the universe) and the app tells
  you so rather than guessing or silently dropping it. See
  `factor_lib.available_tickers` for the one function that would need to
  change to support a live ticker lookup.
- **Direct (naive) weight is still only computable for a minority of the
  universe.** `factor_lib.DIRECT_WEIGHT_PCT` covers exactly the five original
  reference portfolios (SPY, QQQ, VT, RSP, 60/40); AI-basket members are also
  resolvable (holding NVDA directly is 100% "AI" by definition). Bond,
  Treasury, and physical-commodity funds (`factor_lib.ZERO_DIRECT_WEIGHT_TICKERS`:
  TLT, IEF, SHY, BND, AGG, LQD, HYG, GLD, IAU, SLV, DBC) resolve to a known
  **0%** rather than "unknown" -- they hold no equities at all, so their
  overlap with an equity basket is zero by construction, the same logic
  Module 1 already used for TLT inside the synthetic 60/40 (60% of SPY's
  weight + 0% from TLT = 20.26%). Everything else added in the v2 universe
  expansion (VOO, TSLA, JPM, and most other single stocks/equity ETFs) still
  has no sourced top-10-holdings weight, so a portfolio containing one of
  those shows "naive weight: N/A" -- effective exposure (the beta) is still
  computed and shown regardless.
- **Single-stock and narrow portfolios can show a low R² alongside a large
  beta, and that's expected, not a defect.** Beta describes the slope of the
  relationship between a portfolio and the AI basket; R² describes how much
  of the portfolio's actual movement that relationship explains. A 100% TSLA
  portfolio, for example, can show effective exposure over 100% with R² well
  under 0.3 -- most of TSLA's day-to-day movement is idiosyncratic, not
  AI-basket-driven, even though the measured beta is real. The app surfaces
  R² with a plain-language caption for exactly this reason, and calls it out
  explicitly whenever R² is below 0.3.
- **Regression p-values are not shown anywhere in the app, and would be
  misleadingly small if they were.** Checked ad hoc (not surfaced in the UI):
  both the single-factor and two-factor regressions come back significant at
  roughly p=1e-20 to p=1e-114, for an ordinary default portfolio and a
  themed sector preset alike. That's not a meaningful signal -- daily
  financial returns violate OLS's iid-error assumption (they're
  autocorrelated and heteroskedastic; volatility clusters in time), which
  biases standard errors, and therefore p-values, down. This is not a
  clustering problem -- there's no grouping structure here, just one
  portfolio's return series against one basket's return series, not panel
  data -- so clustered standard errors wouldn't be the right fix even if
  p-values were added. HAC/Newey-West standard errors would be, since they
  correct a single time series for exactly this autocorrelation/
  heteroskedasticity. Either way, beta and R² -- the two numbers the app
  actually shows -- are point estimates, unaffected by which standard-error
  method would be used to test their significance.
- **The rolling 252-day beta chart can show step-like artifacts, not just smooth
  drift.** A single extreme-return day (e.g. the AI basket's -13.9% on
  2020-03-16, during the COVID crash) entering the trailing window as the
  newest observation shifts the beta abruptly; the same day produces a mirror-
  image shift exactly 252 trading days later when it drops off the window's
  trailing edge -- producing a sharp jump, a ~252-day flat shelf, and a sharp
  drop that is a real artifact of the trailing-window mechanism, not a data or
  computation error.
- **The short-overlapping-history warning path is defended but not reachable
  by any currently-cached ticker.** The app warns when a portfolio's common
  history with the AI basket is under the standard 252-day window. Every
  ticker added in the v2 universe expansion -- including the shortest-history
  ones (COIN, PLTR, JEPI, QQQM) -- already has several years of daily history,
  so none of them trip this warning as of this writing; it remains in place
  for whatever gets added next, or simply as the DB ages and any newly-listed
  ticker is added later with a shorter track record.
- **User portfolios are treated as fixed-weight and daily-rebalanced.**
  `build_portfolio_simple_returns` computes a portfolio's daily return as a
  constant weighted sum of its constituents' daily returns, every day. A real
  portfolio's weights drift as constituent prices move and only get rebalanced
  back to target periodically (if ever), and any actual rebalancing incurs
  trading costs and, for taxable accounts, tax events -- none of that is
  modeled here.
- **Every Module 1 and Module 3 limitation applies verbatim to any user
  portfolio run through this app**, since the app is built on exactly the same
  `factor_lib` machinery those modules use: hindsight-selected basket, linear
  beta understating crash correlations, the linear scenario-projection
  assumption, correlations rising in drawdowns, the shock-mapping analogy, the
  residualized rest-of-market factor being a construction rather than an
  investable asset (with the same RSP-tautology caveat, since the app reuses
  the identical 252-day rest factor Module 3 built), alpha being ignored in
  every projection, and scenario-not-forecast. See the Module 1 and Module 3
  sections above rather than duplicating them here.
- **Beta > 1 breaks the "exposure %" reading.** The headline "your portfolio is
  effectively X% AI" reading, and the direct-weight comparison next to it,
  implicitly assume the portfolio's non-basket remainder is uncorrelated with
  the AI basket -- i.e., that X% is a plausible *share* of the portfolio. That
  assumption fails once effective exposure exceeds 100%, which happens when a
  user's portfolio directly holds AI-basket members themselves (more
  concentrated than the equal-weighted basket) or otherwise amplifies its
  moves -- e.g. a 100% NVDA portfolio measures at roughly 122% effective
  exposure. A beta over 100% is a real, correctly-computed regression result,
  but "your portfolio is 122% AI" should be read as "moves more than the AI
  basket itself," not as a weight that could describe a real allocation. The
  app shows an explicit warning whenever this happens rather than presenting
  the number as an ordinary percentage.
- **Step 0's proof point went through two DIY price-ratio constructions before
  settling on Module 1's own sourced concentration history.** Both were
  investigated and dropped: (1) AI-basket fixed-share value vs. QQQ's own
  price double-counts the basket (QQQ's return already embeds the basket's
  contribution); (2) AI-basket vs. a "rest of QQQ" proxy basket, built as
  "1-share-of-each" dollar value, let a handful of high-priced members (e.g.
  MU rising from ~$465 to ~$1213 over ~10 weeks in 2026) swing the whole
  proxy regardless of genuine concentration dynamics -- confirmed as a
  construction artifact by rebuilding the same comparison equal-weighted
  (average of each ticker's own return, matching `ai_basket_simple_returns`'s
  existing convention), which erased the effect and showed flat-to-negative
  results at every window tested (12/24/36 months). Step 0 now reuses
  `m1_concentration.CONCENTRATION_HISTORY` (externally sourced: RBC Wealth
  Management, press consensus, CryptoBriefing) instead of computing anything
  from `data/prices.db` for this panel.
