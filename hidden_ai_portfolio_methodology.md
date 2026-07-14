# "The Hidden AI Portfolio" — Tiered Methodology

**Working title:** *You Think You're Diversified. You're Holding an AI Fund.*
**One-line thesis:** Quantify how much hidden AI/mega-cap exposure sits inside portfolios people believe are diversified, show what happened to concentrated vs. diversified styles in past crashes, and map the tradeoff between too much and too little AI exposure.

**What this project never claims:** that AI *is* a bubble or that a crash *will* happen. Every conclusion is conditional ("if a 2000-style repricing occurred..."). This discipline is a feature, not a limitation.

**How to use this document:** Tier 1 is the actual project — start-to-finish doable with BA-level econometrics and intermediate pandas, and it is fully shippable on its own. Tiers 2 and 3 are the published roadmap: they stay in `METHODOLOGY.md` marked "planned," which signals research maturity even before you build them. Do not touch Tier 2 until Tier 1 is posted.

---

# TIER 1 — The Core Project (BA level, ship this)

## T1.0 Research Questions

- **RQ1 — Hidden concentration:** How much AI/mega-cap exposure do "standard advice" portfolios actually carry (SPY, VT, QQQ, 60/40)? How does today's S&P concentration compare to 2000?
- **RQ2 — What crashes actually looked like:** In the dot-com crash (and 2022), what happened to cap-weighted vs. equal-weight vs. value vs. international vs. bonds? Was 2000 a market crash or a concentration crash?
- **RQ3 — The cost of both sides:** What did *avoiding* tech cost since 2015, and what did *concentrating* in it cost in 2000–2002?

Success criterion: each RQ ends in one shareable chart + a 3–5 sentence written finding.

## T1.1 Data

**Tickers (all yfinance, daily adjusted close, max history):**

| Group | Tickers | Role |
|---|---|---|
| AI basket (one definition only for now) | NVDA, MSFT, GOOGL, META, AMZN, AAPL, AVGO, TSM — equal-weighted | The exposure factor |
| "Diversified" portfolios | SPY, VT, QQQ, RSP | What people actually hold |
| Alternatives | VTV (value), EFA (intl), TLT (bonds), GLD | The comparison set |
| Dot-com era (ETFs don't reach back) | ^GSPC, ^IXIC, ^NDX | Crash replay |

**Rules (simple but non-negotiable):**
1. Pull once, store in SQLite (`prices`: date, ticker, adj_close). All analysis reads from the DB — this is your SQL layer.
2. Common trading calendar via inner join on dates; note each series' start date in the README.
3. Simple returns for performance and drawdowns; log returns for regressions. Say which you used under every chart.
4. **Gate before any analysis:** reproduce one known number (e.g., SPY's 2022 peak-to-trough drawdown, ≈ −25%). If your pipeline can't reproduce a known fact, nothing downstream can be trusted.

## T1.2 Module 1 — Hidden Concentration (RQ1)

*Techniques needed: portfolio weights, OLS regression (one X variable), a rolling window loop. That's it.*

1. **Direct weight:** current weight of the AI basket inside SPY and QQQ (from published top-holdings lists — no scraping needed, fund pages publish top 10).
2. **Concentration history:** S&P top-10 weight over time. Practical shortcut for Tier 1: use documented historical values from S&P/press sources for a handful of anchor years (1990, 1995, 2000, 2005, ..., today) rather than reconstructing daily series. A dotted line through 8 anchor points tells the story.
   → **Chart 1:** S&P top-10 concentration, 2000 peak vs. today annotated.
3. **Effective exposure:** rolling 252-day regression of each portfolio's returns on the AI-basket returns. Report beta and R². Sanity check: QQQ highest, TLT ≈ 0.
   → **Chart 2 (launch post):** "How much AI is secretly in your portfolio" — current effective exposure per portfolio (SPY, VT, QQQ, RSP, 60/40) vs. its naive direct weight.

## T1.3 Module 2 — The Crash Replay (RQ2)

*Techniques needed: cumulative returns, drawdown calculation (running max), window slicing. No projection math in Tier 1 — just show what actually happened.*

1. Define windows precisely: dot-com (Mar 2000–Oct 2002), 2022 (Jan–Oct 2022). GFC and COVID optional additions.
2. For each window: cumulative return path + max drawdown for cap-weighted index, Nasdaq, value, international, bonds, gold. (Pre-2003 use index series; note the proxy.)
   → **Chart 3:** the dot-com replay — the punchline the data should reveal: equal-weight/value investors barely felt it; it was a concentration crash.
   → **Chart 4:** same layout for 2022 — the recent, milder, actually-lived version.
3. The Tier 1 "stress" statement stays qualitative and honest: "Portfolios whose measured AI exposure (Module 1) resembles the 2000 leaders' share are the ones that pattern-matched to the worst outcomes." No projected-loss numbers yet — that's Tier 2.

## T1.4 Module 3 — The Cost of Both Sides (RQ3)

*Techniques needed: cumulative return comparison. The easiest module technically, the strongest rhetorically.*

1. **Cost of caution:** cumulative performance of RSP / VTV / EFA vs. SPY, 2015→today.
   → **Chart 5:** "What diversifying away from tech cost you" — this keeps the project symmetric and non-doomer.
2. **Cost of concentration:** cumulative performance of ^NDX vs. ^GSPC vs. value through 2000–2002.
   → **Chart 6:** the mirror image.
3. Written finding: present both prices side by side; explicitly refuse to recommend a weight. "Here is the menu" is the analyst's stance.

## T1.5 Rigor Layer (do all of it — it's free)

- Assumptions stated under every chart (data source, range, return type, basket definition).
- A `LIMITATIONS.md` written by you first: hindsight-selected basket, linear beta understates crash correlations, index proxies pre-2003, scenario ≠ forecast.
- Public `METHODOLOGY.md` = this document.
- Neutral tone everywhere: numbers, not adjectives.

## T1.6 Deliverables, Repo, Milestones

```
hidden-ai-portfolio/
├── README.md            # findings-first: 3 charts, 5-sentence summary
├── METHODOLOGY.md       # this doc, tiers marked
├── LIMITATIONS.md
├── data/pull_prices.py  # yfinance → SQLite
├── data/schema.sql
├── analysis/m1_concentration.py
├── analysis/m2_replay.py
├── analysis/m3_costs.py
└── outputs/             # final charts + findings.md per module
```

- **M0 (one weekend):** pipeline + DB + reproduce the known number. Done = runs from a clean clone.
- **M1:** Module 1 → Charts 1–2 → first LinkedIn post (Hebrew + English).
- **M2:** Module 2 → Charts 3–4 → second post.
- **M3:** Module 3 → Charts 5–6 → flagship post + findings-first README rewrite.

Rule: a milestone isn't done until documented and posted. No starting the next with the previous unshipped.

---

# TIER 2 — Planned Extensions (after Tier 1 is public)

*Each of these is 1–2 weeks on top of existing infrastructure. Mark "planned" in the public methodology.*

- **T2.1 Scenario projection:** turn Module 2 from replay into projection — apply the 2000 factor shocks to today's measured betas: `projected drawdown ≈ β_AI × AI_shock + β_rest × rest_shock`. State the linearity assumption. Produces the "if 2000 happened to today's SPY" chart with a number on it.
- **T2.2 Basket sensitivity:** add basket v2 (cap-weighted) and v3 (±TSLA, AMD, PLTR). Rule: headline findings must survive all versions; any that flips is demoted from the README.
- **T2.3 The Goldilocks frontier:** portfolios of w% AI basket + (100−w)% RSP for w = 0…100; plot historical CAGR vs. 2022-realized drawdown (realized, not projected — keeps it Tier-2 honest). The flagship interactive chart.
- **T2.4 Streamlit dashboard:** basket toggle + frontier explorer, deployed free. Link goes on the CV.

# TIER 3 — The Research-Grade Layer (only with momentum)

- **T3.1 Bootstrap stress distributions:** resample crisis-period daily returns; report drawdown *distributions* with confidence bands instead of point estimates. (You said you partly get bootstrapping — building this is exactly how it clicks. One paragraph intuition: instead of asking "what happened in the one 2000 that occurred," you shuffle-and-redraw those crisis days thousands of times to ask "what range of 2000s could have happened," and report the spread.)
- **T3.2 Hindsight-free basket:** rebuild the AI basket as "largest tech names as of 2015" and re-run everything — the strongest possible answer to survivorship criticism.
- **T3.3 Regime correlations:** show formally that cross-market correlations rise in drawdowns (the original "Diversification Lie" module), closing the loop between the two project ideas.

---

# Interview Narrative (why the tiers themselves are an asset)

The story this structure lets you tell: "I shipped a complete analysis with methods I fully understood, published the limitations myself, then leveled up the methodology in public — replay → projection → bootstrap." That progression demonstrates learning velocity, which for a junior hire is worth more than arriving with Tier 3 skills.
