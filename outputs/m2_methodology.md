# Module 2 Methodology -- RQ2: What Crashes Actually Looked Like

What was done to produce `chart3_dotcom_replay.png`, `chart4_2022_replay.png`,
`chart_gfc_replay.png`, `m2_drawdown_table.csv`, and `m2_findings.md`. Code lives in
`analysis/m2_replay.py`. No projection or scenario math -- this module only replays
what actually happened in three historical windows.

## Windows

- **Dot-com:** 2000-03-01 to 2002-10-31.
- **2022:** 2022-01-01 to 2022-10-31 (matches the window already validated in the
  pipeline gate check: SPY's 2022 peak-to-trough drawdown of -24.5%, reproduced here
  as -24.5% for SPY -- the same gate-check number, computed independently by this
  module's own drawdown function).
- **GFC:** 2007-10-01 to 2009-03-31 (peak-to-trough of the 2008 Global Financial
  Crisis bear market).

## Series per window

Per METHODOLOGY.md T1.3, each window compares a cap-weighted index, a Nasdaq/growth
proxy, a value proxy, an international proxy, bonds, and gold -- but pre-2003 ETF
coverage is incomplete, so the three windows don't use identical instruments:

| Role | Dot-com window | 2022 window | GFC window |
|---|---|---|---|
| Cap-weighted | ^GSPC (S&P 500 index) | SPY | ^GSPC (S&P 500 index) |
| Nasdaq / growth | ^IXIC (Nasdaq Composite) | QQQ (Nasdaq-100) | QQQ (Nasdaq-100) |
| Value | IWD (Russell 1000 Value) | VTV | IWD (Russell 1000 Value) |
| International | EFA | EFA | EFA |
| Bonds | *omitted* -- no coverage | TLT | TLT |
| Gold | *omitted* -- no coverage | GLD | GLD |

**Why the substitutions:** SPY, QQQ, VTV, TLT, and GLD either don't exist yet or start
too late to cover the dot-com window (VTV starts 2004-01-30, TLT starts 2002-07-30,
GLD starts 2004-11-18). ^GSPC and ^IXIC have full coverage back to well before 2000.
IWD was added specifically for this module (inception 2000-05-26) as the best available
value proxy reaching close to the dot-com window's start. EFA (inception 2001-08-27)
is the only international proxy available and only covers the back half of the window.
Bonds and gold have no usable proxy before the dot-com window and are left out of that
chart entirely rather than shown with a multi-year gap.

**Why the GFC window uses QQQ, not ^IXIC, for Nasdaq/growth:** every candidate series
was checked against the DB before writing this module, and all six (^GSPC, QQQ, IWD,
EFA, TLT, GLD) have full coverage over the whole window -- each one's first row lands
exactly on 2007-10-01, zero truncation, zero proxy substitutions needed. Since QQQ
(inception March 1999) is fully covered, it's used instead of the index, matching the
same "use the ETF when it's available" convention the 2022 window already follows.
Cap-weighted still uses the index (^GSPC) rather than SPY for this window, per this
module's own convention of anchoring truncation checks to the same reference series
used elsewhere -- a deliberate minor inconsistency in which instrument anchors the
role, not a gap in coverage.

## Calculation

For each series, within its window:

1. Slice to the window's date range and drop any leading dates before the ticker has
   data (this is where the truncation for IWD/EFA in the dot-com window comes from).
2. Index the series to 100 at its own first available date in the window (not
   necessarily the window's nominal start date) -- this is cumulative return, not
   absolute price.
3. Max drawdown = the minimum value of (price / running historical max - 1) across
   the indexed series, i.e. the worst peak-to-trough decline observed within the
   window.

A series is flagged **truncated** in the output table and marked with `*` on the
chart if its first available date is more than 7 calendar days after the window's
reference series' first available date (^GSPC for dot-com, SPY for 2022, ^GSPC for
GFC) -- the 7-day tolerance absorbs ordinary weekend/holiday differences between
exchanges without flagging them as real data gaps. No series is truncated in the GFC
window -- all six start exactly on 2007-10-01.

## Charts

All three charts are line plots of indexed cumulative return over the window, one
line per series, direct-labeled with the final value at the line's end plus a
standard legend (the dataviz-skill "relief" requirement for two of the six
categorical hues, which sit under the 3:1 contrast floor against the light chart
surface). Colors are assigned by **role**, not by ticker, so "cap-weighted" is
always the same blue and "value" is always the same yellow whether the underlying
instrument is an index or an ETF -- this keeps all three charts visually comparable
side by side.

## Results summary

| Window | Series | Max drawdown | Window return |
|---|---|---|---|
| Dot-com | S&P 500 (^GSPC) | -49.1% | -35.8% |
| Dot-com | Nasdaq Composite (^IXIC) | -77.9% | -72.2% |
| Dot-com | Value (IWD)* | -34.1% | -14.8% |
| Dot-com | International (EFA)* | -29.8% | -22.9% |
| 2022 | SPY | -24.5% | -18.2% |
| 2022 | QQQ | -34.8% | -30.5% |
| 2022 | Value (VTV) | -17.0% | -4.9% |
| 2022 | International (EFA) | -28.7% | -23.4% |
| 2022 | Bonds (TLT) | -34.9% | -32.3% |
| 2022 | Gold (GLD) | -21.0% | -9.8% |
| GFC | S&P 500 (^GSPC) | -56.8% | -48.4% |
| GFC | QQQ (Nasdaq-100) | -53.4% | -41.3% |
| GFC | Value (IWD) | -59.8% | -51.1% |
| GFC | International (EFA) | -61.0% | -52.4% |
| GFC | Bonds (TLT) | -17.0% | **+26.4%** |
| GFC | Gold (GLD) | -29.4% | +22.2% |

\* truncated start -- see Limitations below and `LIMITATIONS.md`. No GFC-window
series is truncated.

Note the GFC's "max drawdown" vs. "window return" gap for bonds and gold: both fell
sharply intra-window (TLT -17.0%, GLD -29.4%, during the acute liquidity crunch in
late 2008) but *recovered to a net gain* by the window's end -- the flight-to-quality
flows that a systemic crisis produces and a sector-specific one (dot-com, 2022) does
not.

## Known limitations

- **IWD and EFA truncation in the dot-com window** means their reported max drawdown
  is a floor, not the true peak-to-trough figure -- IWD's series starts 2000-05-26
  (missing the market's initial March 2000 top) and EFA's starts 2001-08-27 (missing
  the first ~17 months of the window entirely). If either asset class fell further
  before its data starts, this analysis would understate that decline.
- **No bonds or gold comparison for the dot-com window** -- TLT and GLD have no price
  history before the window, so the "concentration crash" story for 2000-2002 rests on
  four series (cap-weighted, Nasdaq, value, international) rather than the full six
  used for 2022 and the GFC.
- **Index vs. ETF instruments aren't identical** even within the same role: ^GSPC and
  ^IXIC are price-return indices, not investable total-return instruments, and don't
  include the dividend reinvestment that SPY/QQQ do. This slightly understates the
  dot-com and GFC windows' actual investor returns relative to the 2022 window's
  fully-ETF-based figures.
- **The GFC window is a systemic-crash counter-example, not another concentration
  story.** Unlike dot-com and 2022, growth (QQQ) did not fall meaningfully more than
  value (IWD) in this window -- if anything, value fell slightly more. Anyone reusing
  this window's Nasdaq/growth drawdown as an analogy for "the AI basket" should read
  it as "what happened to growth assets in a systemic crisis that was not about them,"
  not as evidence of a concentration effect. See `LIMITATIONS.md`, Module 3 section.
- **Max drawdown is a single worst-case number**, not a distribution -- it says nothing
  about how long the drawdown lasted or how a real investor's entry/exit timing would
  have changed the experienced loss. The GFC's bond/gold rows are the clearest example
  in this project of why that matters: the window RETURN (positive) tells a very
  different story than the max DRAWDOWN (negative) for the same series.
- This module is a **historical replay only**. It does not project what a similar
  event would do to today's portfolios -- that link is deliberately left qualitative
  in Tier 1 (see `m2_findings.md`) and is planned as Tier 2's scenario projection
  (T2.1).
