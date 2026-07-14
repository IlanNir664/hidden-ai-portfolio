"""Module 2 (RQ2) -- The Crash Replay: what actually happened, no projection.

For two crash windows (dot-com, 2022), compute each series' cumulative return path
(indexed to 100 at its first available date within the window) and max drawdown
(running-max peak-to-trough). No projection math -- this module only replays history.

Per METHODOLOGY.md T1.3: pre-2003, ETF proxies don't reach back far enough, so the
dot-com window uses index series (^GSPC, ^IXIC) plus the best available ETF proxies
for value (IWD) and international (EFA) -- both of which start partway through the
window. Bonds and gold have no price history before the dot-com window at all
(TLT starts 2002-07-30, GLD starts 2004-11-18) and are omitted from that replay.

Run: python analysis/m2_replay.py
"""

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "prices.db"
TABLE_PATH = Path(__file__).parent.parent / "outputs" / "m2_drawdown_table.csv"
CHART3_PATH = Path(__file__).parent.parent / "outputs" / "chart3_dotcom_replay.png"
CHART4_PATH = Path(__file__).parent.parent / "outputs" / "chart4_2022_replay.png"
CHART_GFC_PATH = Path(__file__).parent.parent / "outputs" / "chart_gfc_replay.png"
FINDINGS_PATH = Path(__file__).parent.parent / "outputs" / "m2_findings.md"

# dataviz skill palette (light mode), fixed role -> hue mapping used across both charts
ROLE_COLOR = {
    "cap_weighted": "#2a78d6",   # blue
    "nasdaq": "#1baf7a",         # aqua
    "value": "#eda100",          # yellow
    "international": "#008300",  # green
    "bonds": "#4a3aa7",          # violet
    "gold": "#e34948",           # red
}
COLOR_INK_PRIMARY = "#0b0b0b"
COLOR_INK_SECONDARY = "#52514e"
COLOR_INK_MUTED = "#898781"
COLOR_GRIDLINE = "#e1e0d9"
COLOR_SURFACE = "#fcfcfb"
COLOR_ZERO_LINE = "#c3c2b7"

WINDOWS = {
    "dotcom": {
        "start": "2000-03-01",
        "end": "2002-10-31",
        "label": "Dot-com (Mar 2000 - Oct 2002)",
        "reference": "^GSPC",  # full-coverage series; others compared against its first trading day
        "series": [
            ("^GSPC", "cap_weighted", "S&P 500 (cap-weighted)"),
            ("^IXIC", "nasdaq", "Nasdaq Composite"),
            ("IWD", "value", "Value (Russell 1000 Value)"),
            ("EFA", "international", "International (EFA)"),
        ],
    },
    "2022": {
        "start": "2022-01-01",
        "end": "2022-10-31",
        "label": "2022 (Jan - Oct 2022)",
        "reference": "SPY",  # full-coverage series; others compared against its first trading day
        "series": [
            ("SPY", "cap_weighted", "SPY (cap-weighted)"),
            ("QQQ", "nasdaq", "QQQ (Nasdaq-100)"),
            ("VTV", "value", "Value (VTV)"),
            ("EFA", "international", "International (EFA)"),
            ("TLT", "bonds", "Bonds (TLT)"),
            ("GLD", "gold", "Gold (GLD)"),
        ],
    },
    # GFC peak-to-trough. Unlike the dot-com window, every candidate series here has
    # full coverage over the whole window (verified against the DB before writing this:
    # ^GSPC, QQQ, IWD, EFA, TLT, and GLD all have their first row exactly on 2007-10-01,
    # zero truncation) -- so no proxy substitutions are needed and no series is omitted.
    # Nasdaq/growth uses QQQ, not ^IXIC: QQQ existed since 1999 and is fully covered
    # over this window, so (per the same "ETF when available" convention the 2022
    # window already uses) there's no reason to fall back to the index here. Cap-
    # weighted stays on the index (^GSPC) rather than SPY per this task's spec, so the
    # window's own internal "reference" series (used for the truncation check) is an
    # index like the dot-com window's, not an ETF like the 2022 window's -- a minor,
    # deliberate inconsistency in which instrument anchors the truncation check, not a
    # gap in coverage.
    "gfc": {
        "start": "2007-10-01",
        "end": "2009-03-31",
        "label": "Global Financial Crisis (Oct 2007 - Mar 2009)",
        "reference": "^GSPC",
        "series": [
            ("^GSPC", "cap_weighted", "S&P 500 (^GSPC)"),
            ("QQQ", "nasdaq", "QQQ (Nasdaq-100)"),
            ("IWD", "value", "Value (IWD)"),
            ("EFA", "international", "International (EFA)"),
            ("TLT", "bonds", "Bonds (TLT)"),
            ("GLD", "gold", "Gold (GLD)"),
        ],
    },
}

TRUNCATION_TOLERANCE_DAYS = 7  # calendar days; absorbs weekends/holidays, not real gaps


def load_prices() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT date, ticker, adj_close FROM prices", conn, parse_dates=["date"])
    conn.close()
    return df.pivot(index="date", columns="ticker", values="adj_close").sort_index()


def window_series(prices: pd.DataFrame, ticker: str, start: str, end: str) -> pd.Series:
    """Slice to [start, end], drop leading NaNs (ticker not yet listed), index to 100."""
    s = prices.loc[start:end, ticker].dropna()
    if s.empty:
        return s
    indexed = s / s.iloc[0] * 100
    return indexed


def max_drawdown(indexed: pd.Series) -> float:
    running_max = indexed.cummax()
    drawdown = indexed / running_max - 1
    return drawdown.min()


def build_table(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for window_key, window in WINDOWS.items():
        reference = window_series(prices, window["reference"], window["start"], window["end"])
        reference_start = reference.index.min()
        for ticker, role, label in window["series"]:
            indexed = window_series(prices, ticker, window["start"], window["end"])
            if indexed.empty:
                continue
            gap_days = (indexed.index.min() - reference_start).days
            rows.append({
                "window": window_key,
                "ticker": ticker,
                "role": role,
                "label": label,
                "first_available": indexed.index.min().strftime("%Y-%m-%d"),
                "last_available": indexed.index.max().strftime("%Y-%m-%d"),
                "window_return_pct": round((indexed.iloc[-1] / 100 - 1) * 100, 1),
                "max_drawdown_pct": round(max_drawdown(indexed) * 100, 1),
                "truncated_start": gap_days > TRUNCATION_TOLERANCE_DAYS,
            })
    return pd.DataFrame(rows)


def is_truncated(prices: pd.DataFrame, window: dict, ticker: str) -> bool:
    reference = window_series(prices, window["reference"], window["start"], window["end"])
    indexed = window_series(prices, ticker, window["start"], window["end"])
    if indexed.empty or reference.empty:
        return False
    return (indexed.index.min() - reference.index.min()).days > TRUNCATION_TOLERANCE_DAYS


def plot_replay(prices: pd.DataFrame, window_key: str, output_path: Path, title: str, subtitle: str) -> None:
    window = WINDOWS[window_key]

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    fig.patch.set_facecolor(COLOR_SURFACE)
    ax.set_facecolor(COLOR_SURFACE)

    ax.axhline(100, color=COLOR_ZERO_LINE, linewidth=1, zorder=1)

    for ticker, role, label in window["series"]:
        indexed = window_series(prices, ticker, window["start"], window["end"])
        if indexed.empty:
            continue
        truncated = is_truncated(prices, window, ticker)
        line_label = f"{label}*" if truncated else label
        ax.plot(indexed.index, indexed.values, color=ROLE_COLOR[role], linewidth=2, label=line_label, zorder=3)
        ax.annotate(f"{indexed.iloc[-1]:.0f}", xy=(indexed.index[-1], indexed.iloc[-1]),
                    xytext=(6, 0), textcoords="offset points", va="center", fontsize=8.5,
                    color=ROLE_COLOR[role], weight="bold")

    ax.set_ylabel("Cumulative return (indexed to 100)", fontsize=10, color=COLOR_INK_SECONDARY)

    fig.text(0.01, 0.96, title, fontsize=15, color=COLOR_INK_PRIMARY, weight="bold")
    fig.text(0.01, 0.925, subtitle, fontsize=9.5, color=COLOR_INK_SECONDARY)

    ax.spines[["top", "right"]].set_visible(False)
    ax.spines["left"].set_color(COLOR_INK_MUTED)
    ax.spines["bottom"].set_color(COLOR_INK_MUTED)
    ax.tick_params(axis="x", colors=COLOR_INK_SECONDARY, labelsize=9)
    ax.tick_params(axis="y", colors=COLOR_INK_MUTED, labelsize=9)
    ax.yaxis.grid(True, color=COLOR_GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    legend = ax.legend(loc="lower left", frameon=False, fontsize=8.5, labelcolor=COLOR_INK_SECONDARY)

    has_truncated = any(is_truncated(prices, window, t) for t, _, _ in window["series"])
    footnote = "Source: yfinance daily adjusted close / index close. Indexed to 100 at each series' first available date in the window."
    if has_truncated:
        footnote += "\n* starts partway through the window (no earlier price data) -- see LIMITATIONS.md."

    fig.text(0.01, 0.02 if has_truncated else 0.03, footnote, fontsize=7.5, color=COLOR_INK_MUTED)

    fig.tight_layout(rect=(0, 0.1, 1, 0.885))
    fig.savefig(output_path, facecolor=COLOR_SURFACE)
    plt.close(fig)
    print(f"Chart saved to {output_path}")


def write_findings(table: pd.DataFrame) -> None:
    dc = table[table["window"] == "dotcom"].set_index("role")
    tw = table[table["window"] == "2022"].set_index("role")
    gfc = table[table["window"] == "gfc"].set_index("role")

    text = f"""# Module 2 Findings -- RQ2: What Crashes Actually Looked Like

**Dot-com (Mar 2000 - Oct 2002).** The S&P 500 (cap-weighted) fell {abs(dc.loc['cap_weighted', 'max_drawdown_pct']):.0f}%
peak-to-trough, but the Nasdaq Composite -- the most concentrated, most tech-heavy
index of the period -- fell {abs(dc.loc['nasdaq', 'max_drawdown_pct']):.0f}%. Value stocks (Russell 1000
Value, available from {dc.loc['value', 'first_available']} onward) drew down only
{abs(dc.loc['value', 'max_drawdown_pct']):.0f}% over the same stretch. The dot-com crash was not a uniform
market crash -- it was concentrated almost entirely in the names and indices most
exposed to the late-90s tech run-up; a value-tilted or non-tech investor barely felt it
by comparison.

**2022 (Jan - Oct 2022).** The same shape repeats at smaller scale: SPY drew down
{abs(tw.loc['cap_weighted', 'max_drawdown_pct']):.0f}%, QQQ (Nasdaq-100) {abs(tw.loc['nasdaq', 'max_drawdown_pct']):.0f}%, while value (VTV)
held up better at {abs(tw.loc['value', 'max_drawdown_pct']):.0f}% and bonds (TLT), unusually, also fell
{abs(tw.loc['bonds', 'max_drawdown_pct']):.0f}% (a 2022-specific case where rate hikes hurt both stocks and
bonds at once -- not a repeat of the dot-com pattern). Gold (GLD) drew down only
{abs(tw.loc['gold', 'max_drawdown_pct']):.0f}%, the mildest of the six.

**The Global Financial Crisis (Oct 2007 - Mar 2009) breaks the pattern the other two
windows share.** The S&P 500 fell {abs(gfc.loc['cap_weighted', 'max_drawdown_pct']):.0f}% peak-to-trough --
deeper than either the dot-com or 2022 cap-weighted drawdown -- but this time growth
(QQQ, {abs(gfc.loc['nasdaq', 'max_drawdown_pct']):.0f}%) did not fall further than value (IWD, {abs(gfc.loc['value', 'max_drawdown_pct']):.0f}%); if
anything, value fell slightly more. International (EFA) fell {abs(gfc.loc['international', 'max_drawdown_pct']):.0f}%, similarly
deep. This was not a concentration crash in the dot-com/2022 sense -- it was a systemic
one, where being outside the "hyped" trade did not protect a portfolio. The one
instrument that did its job was bonds: TLT *gained* {gfc.loc['bonds', 'window_return_pct']:.0f}% over the window even
though it drew down {abs(gfc.loc['bonds', 'max_drawdown_pct']):.0f}% intra-window -- the flight-to-quality flows that show up
in a systemic crisis but not in a sector-specific one. Gold (GLD) also ended the window
up {gfc.loc['gold', 'window_return_pct']:.0f}%, despite a sharp {abs(gfc.loc['gold', 'max_drawdown_pct']):.0f}% intra-window drawdown of its own during
the acute liquidity crunch in late 2008.

**Qualitative read (Tier 1, no projection):** in the dot-com and 2022 windows, the
portfolios that look most like the era's most-concentrated, most-hyped index took the
deepest drawdowns, and the portfolios furthest from that concentration were hit
lightest. Module 1 showed today's cap-weighted and Nasdaq-tracking portfolios (SPY,
QQQ) carry AI-basket exposure in the same range, or higher, than the 2000 leaders'
share of the index at the time. The GFC window is included specifically as the
counter-example: a crisis where diversification away from the "hot" trade did not
help, and only an entirely different asset class (bonds) did. Whether either pattern
predicts a similar outcome for today's AI-heavy portfolios is exactly what Tier 1 does
not claim -- this module replays what happened, not what will happen.
"""
    FINDINGS_PATH.write_text(text)
    print(f"Findings written to {FINDINGS_PATH}")


def run_gfc_sanity_checks(table: pd.DataFrame) -> None:
    """Loose (+-5pp) sanity check on the GFC window before anything downstream (M3,
    the app) reads it. TLT's window RETURN must be positive -- that's the
    flight-to-quality fact this window exists to demonstrate; if it isn't, stop and
    investigate rather than silently propagate a bad number.
    """
    gfc = table[table["window"] == "gfc"].set_index("role")

    gspc_dd = gfc.loc["cap_weighted", "max_drawdown_pct"]
    expected, tolerance = -55.0, 5.0
    print(f"GFC sanity check -- ^GSPC max drawdown: {gspc_dd:.1f}% (expected {expected}% +-{tolerance}pp)")
    assert abs(gspc_dd - expected) <= tolerance, (
        f"SANITY CHECK FAILED: ^GSPC GFC max drawdown {gspc_dd:.1f}% is more than "
        f"{tolerance}pp from the expected ~{expected}%."
    )

    tlt_return = gfc.loc["bonds", "window_return_pct"]
    print(f"GFC sanity check -- TLT window return: {tlt_return:.1f}% (must be positive -- flight to quality)")
    assert tlt_return > 0, (
        f"SANITY CHECK FAILED: TLT's GFC window return is {tlt_return:.1f}%, not positive. "
        "This window exists specifically to show flight-to-quality -- stop and investigate "
        "before trusting any downstream GFC shock derived from this table."
    )
    print("GFC sanity checks PASSED.\n")


def main() -> None:
    prices = load_prices()

    table = build_table(prices)
    print(table.to_string(index=False))
    run_gfc_sanity_checks(table)

    TABLE_PATH.parent.mkdir(exist_ok=True)
    table.to_csv(TABLE_PATH, index=False)
    print(f"\nSaved to {TABLE_PATH}")

    plot_replay(prices, "dotcom", CHART3_PATH,
                "The dot-com crash was a concentration crash",
                "Cumulative return by style, Mar 2000 - Oct 2002")
    plot_replay(prices, "2022", CHART4_PATH,
                "2022: the same shape, smaller scale",
                "Cumulative return by style, Jan - Oct 2022")
    plot_replay(prices, "gfc", CHART_GFC_PATH,
                "2008: the systemic crash, not a concentration crash",
                "Cumulative return by style, Oct 2007 - Mar 2009")

    write_findings(table)


if __name__ == "__main__":
    main()
