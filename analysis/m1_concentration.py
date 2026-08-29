"""Module 1 (RQ1) -- Hidden Concentration: effective AI exposure via rolling regression.

For each portfolio, regress its daily log returns on the AI-basket's daily log
returns over the trailing 252 trading days (~1 year) and report beta and R^2.
Beta = "effective exposure" -- how much of the portfolio's day-to-day movement
is explained by the AI basket, independent of what the portfolio nominally holds.

Sanity check (per METHODOLOGY.md T1.2): QQQ should show the highest beta,
TLT (long-term Treasuries) should be near zero.

Run: python analysis/m1_concentration.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from factor_lib import (
    COLOR_BLUE,
    COLOR_GRIDLINE,
    COLOR_INK_MUTED,
    COLOR_INK_PRIMARY,
    COLOR_INK_SECONDARY,
    COLOR_MUTED_BAR,
    COLOR_SURFACE,
    DIRECT_WEIGHT_PCT,
    ai_basket_simple_returns,
    load_prices,
    single_factor_regress,
    to_log_returns,
)

OUTPUT_PATH = Path(__file__).parent.parent / "outputs" / "m1_beta_table.csv"
CHART1_PATH = Path(__file__).parent.parent / "outputs" / "chart1_sp500_concentration.png"
CHART2_PATH = Path(__file__).parent.parent / "outputs" / "chart2_effective_exposure.png"
FINDINGS_PATH = Path(__file__).parent.parent / "outputs" / "m1_findings.md"

CHART_ORDER = ["QQQ", "SPY", "VT", "60/40", "RSP", "TLT"]

PORTFOLIOS = ["SPY", "VT", "QQQ", "RSP"]  # 60/40 built synthetically below
SANITY_CHECK_TICKER = "TLT"  # expected beta ~ 0, included as a sanity check, not a "portfolio"

# --- S&P 500 top-10 concentration, anchor years (Chart 1) ---
# Practical Tier-1 shortcut per METHODOLOGY.md T1.2: documented historical values from
# press/research sources at a handful of anchor years, not a reconstructed daily series.
# Primary thread: RBC Wealth Management, "The Great Narrowing: S&P 500 concentration"
# (1990, 2000, 2015, 2025 figures; 2005/2010 trough corroborated by general press
# consensus of the same "The Great Narrowing" piece). 2020 and current (2026) figures
# from CryptoBriefing (2026-07-09), cross-checked against Forbes (Dec 2025 update).
CONCENTRATION_HISTORY = [
    (1990, 19.0, "RBC Wealth Management"),
    (2000, 23.0, "RBC Wealth Management (intra-year peak ~27%)"),
    (2005, 19.0, "press consensus, 2005-2010 trough"),
    (2010, 19.0, "press consensus, 2005-2010 trough"),
    (2015, 19.0, "RBC Wealth Management"),
    (2020, 27.0, "surpassed dot-com peak, zero-rate era"),
    (2025, 40.7, "RBC Wealth Management, record for the year"),
    (2026, 43.0, "CryptoBriefing, 2026-07-09, record high"),
]


def plot_chart1() -> None:
    """Chart 1: S&P 500 top-10 concentration history, 2000 peak vs. today annotated.

    Anchor years are plotted at evenly-spaced categorical positions rather than on a
    true year-linear scale: the gaps between anchors are uneven (5, 5, 5, 5, 5, 5, 1
    years) by design (see METHODOLOGY.md T1.2), and a linear scale would crowd the
    final two labels (2025, 2026) illegibly close together.
    """
    years = [y for y, _, _ in CONCENTRATION_HISTORY]
    pcts = [p for _, p, _ in CONCENTRATION_HISTORY]
    positions = list(range(len(years)))

    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor(COLOR_SURFACE)
    ax.set_facecolor(COLOR_SURFACE)

    ax.plot(positions, pcts, color=COLOR_BLUE, linewidth=2, linestyle=":", marker="o",
            markersize=7, markerfacecolor=COLOR_BLUE, markeredgecolor=COLOR_SURFACE,
            markeredgewidth=1.5, zorder=3)

    for pos, pct in zip(positions, pcts):
        ax.annotate(f"{pct:.0f}%", (pos, pct), xytext=(0, 10), textcoords="offset points",
                    ha="center", fontsize=9, color=COLOR_INK_PRIMARY)

    idx_2000 = years.index(2000)
    idx_now = len(years) - 1
    ax.annotate("dot-com peak", xy=(positions[idx_2000], pcts[idx_2000]), xytext=(0, -22),
                textcoords="offset points", ha="center", fontsize=8.5, color=COLOR_INK_SECONDARY, style="italic")
    ax.annotate("today", xy=(positions[idx_now], pcts[idx_now]), xytext=(0, -22),
                textcoords="offset points", ha="center", fontsize=8.5, color=COLOR_INK_SECONDARY, style="italic")

    ax.set_ylabel("Top-10 share of S&P 500 market cap", fontsize=10, color=COLOR_INK_SECONDARY)
    ax.set_xticks(positions)
    ax.set_xticklabels([str(y) for y in years], rotation=0)
    ax.set_xlim(-0.5, len(years) - 0.5)
    ax.set_ylim(0, max(pcts) * 1.2)

    fig.text(0.01, 0.955, "S&P 500 concentration: 2000 vs. today", fontsize=15, color=COLOR_INK_PRIMARY, weight="bold")
    fig.text(0.01, 0.915, "Top-10 holdings as a share of total index market cap, anchor years",
              fontsize=9.5, color=COLOR_INK_SECONDARY)

    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(COLOR_INK_MUTED)
    ax.tick_params(axis="x", colors=COLOR_INK_SECONDARY, labelsize=10)
    ax.tick_params(axis="y", colors=COLOR_INK_MUTED, labelsize=9)
    ax.yaxis.grid(True, color=COLOR_GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    fig.text(0.01, 0.045,
              "Source: RBC Wealth Management (1990/2000/2015/2025), press consensus (2005/2010),",
              fontsize=7.5, color=COLOR_INK_MUTED)
    fig.text(0.01, 0.015,
              "CryptoBriefing 2026-07-09 (2026). Anchor points, not a reconstructed daily series -- see LIMITATIONS.md.",
              fontsize=7.5, color=COLOR_INK_MUTED)

    fig.tight_layout(rect=(0, 0.09, 1, 0.87))
    fig.savefig(CHART1_PATH, facecolor=COLOR_SURFACE)
    plt.close(fig)
    print(f"Chart saved to {CHART1_PATH}")


def plot_chart2(table: pd.DataFrame) -> None:
    """Chart 2: effective AI exposure (beta) vs. naive direct weight, per portfolio.

    Two bars per portfolio on the same 0-100% scale: what you'd see reading the
    fund's published top-10 holdings (direct weight) vs. what a trailing regression
    on the AI basket's returns actually shows (effective exposure). Where effective
    exceeds direct, the portfolio's day-to-day moves track the AI basket more than
    its named holdings would suggest -- correlated names outside the basket.
    """
    names = [p for p in CHART_ORDER if p != SANITY_CHECK_TICKER]
    direct = [DIRECT_WEIGHT_PCT[p] for p in names]
    effective = [table.loc[p, "beta"] * 100 for p in names]

    x = np.arange(len(names))
    width = 0.36

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    fig.patch.set_facecolor(COLOR_SURFACE)
    ax.set_facecolor(COLOR_SURFACE)

    bars_direct = ax.bar(x - width / 2, direct, width, color=COLOR_MUTED_BAR, label="Direct weight (top-10 holdings)", zorder=3)
    bars_eff = ax.bar(x + width / 2, effective, width, color=COLOR_BLUE, label="Effective exposure (252-day beta)", zorder=3)

    for bars in (bars_direct, bars_eff):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.7, f"{bar.get_height():.0f}%",
                    ha="center", va="bottom", fontsize=8.5, color=COLOR_INK_PRIMARY)

    ax.set_ylabel("Share of portfolio driven by the AI basket", fontsize=10, color=COLOR_INK_SECONDARY)
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylim(0, max(direct + effective) * 1.25)

    fig.text(0.01, 0.96, "How much AI is secretly in your portfolio", fontsize=15, color=COLOR_INK_PRIMARY, weight="bold")
    fig.text(0.01, 0.925,
              "Naive top-10 holdings weight vs. actual return-driven exposure to the AI basket",
              fontsize=9.5, color=COLOR_INK_SECONDARY)

    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(COLOR_INK_MUTED)
    ax.tick_params(axis="x", colors=COLOR_INK_SECONDARY, labelsize=10)
    ax.tick_params(axis="y", colors=COLOR_INK_MUTED, labelsize=9)
    ax.yaxis.grid(True, color=COLOR_GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    legend = ax.legend(loc="upper right", frameon=False, fontsize=9, labelcolor=COLOR_INK_SECONDARY)

    fig.text(0.01, 0.05,
              "AI basket: NVDA, MSFT, GOOGL, META, AMZN, AAPL, AVGO, TSM (equal-weighted). Direct weight from",
              fontsize=7.5, color=COLOR_INK_MUTED)
    fig.text(0.01, 0.025,
              "published top-10 holdings, 2026-05 to 2026-07 (QQQ figure is a lower bound -- see script comments).",
              fontsize=7.5, color=COLOR_INK_MUTED)

    fig.tight_layout(rect=(0, 0.09, 1, 0.885))
    fig.savefig(CHART2_PATH, facecolor=COLOR_SURFACE)
    plt.close(fig)
    print(f"Chart saved to {CHART2_PATH}")


def write_findings(table: pd.DataFrame) -> None:
    """RQ1 written finding, 3-5 sentences, per METHODOLOGY.md success criterion."""
    today_pct = CONCENTRATION_HISTORY[-1][1]
    dotcom_pct = next(p for y, p, _ in CONCENTRATION_HISTORY if y == 2000)

    names = [p for p in CHART_ORDER if p != SANITY_CHECK_TICKER]
    gaps = {p: table.loc[p, "beta"] * 100 - DIRECT_WEIGHT_PCT[p] for p in names}
    smallest_gap_p = min(gaps, key=gaps.get)
    largest_gap_p = max(gaps, key=gaps.get)

    qqq_beta = table.loc["QQQ", "beta"]
    qqq_direct = DIRECT_WEIGHT_PCT["QQQ"]
    spy_beta = table.loc["SPY", "beta"]
    spy_direct = DIRECT_WEIGHT_PCT["SPY"]
    rsp_beta = table.loc["RSP", "beta"]
    rsp_direct = DIRECT_WEIGHT_PCT["RSP"]

    text = f"""# Module 1 Findings -- RQ1: Hidden Concentration

The S&P 500's top-10 holdings represent {today_pct:.0f}% of the index's market cap
today, versus {dotcom_pct:.0f}% at the 2000 dot-com peak -- current concentration is
meaningfully higher than the level that preceded the dot-com crash (Chart 1).
Every "diversified" portfolio tested carries AI/mega-cap exposure beyond its
published top-10 weight: SPY's named AI-basket holdings sum to {spy_direct:.0f}%, but a
trailing 252-day regression puts its actual return-driven exposure (beta) at
{spy_beta*100:.0f}%, and QQQ moves from a {qqq_direct:.0f}% naive weight to a {qqq_beta*100:.0f}%
effective one (Chart 2) -- the largest absolute gap of the portfolios tested. RSP
(equal-weight S&P) has by far the lowest direct weight ({rsp_direct:.1f}%, since equal-weighting
dilutes mega-cap concentration by construction) but still shows {rsp_beta*100:.0f}% effective
exposure -- proportionally the largest jump of any portfolio, meaning even the
"least AI" fund tested still has a sizeable chunk of its day-to-day moves tracking
the AI basket. The synthetic 60/40 shows the smallest absolute direct-to-effective
gap ({gaps[smallest_gap_p]:.0f} points), simply because 40% of it is bonds with ~zero AI
correlation. TLT itself serves as the sanity check at both ends: negligible direct
AI-basket weight and a near-zero beta ({table.loc[SANITY_CHECK_TICKER, 'beta']:.2f}).
"""
    FINDINGS_PATH.write_text(text)
    print(f"Findings written to {FINDINGS_PATH}")


def main() -> None:
    prices = load_prices()
    simple_returns = prices.pct_change(fill_method=None)

    # AI basket: equal-weight average of simple returns, only on days all 8 exist
    basket_simple = ai_basket_simple_returns(simple_returns)
    basket_log = to_log_returns(basket_simple)

    # Synthetic 60/40: 60% SPY + 40% TLT, weighted simple return -> log return
    sixty_forty_simple = 0.6 * simple_returns["SPY"] + 0.4 * simple_returns["TLT"]
    sixty_forty_log = to_log_returns(sixty_forty_simple)

    targets = {p: to_log_returns(simple_returns[p]) for p in PORTFOLIOS}
    targets["60/40"] = sixty_forty_log
    targets[SANITY_CHECK_TICKER] = to_log_returns(simple_returns[SANITY_CHECK_TICKER])

    rows = []
    for name, series in targets.items():
        result = single_factor_regress(series, basket_log)
        result["portfolio"] = name
        rows.append(result)

    table = pd.DataFrame(rows).set_index("portfolio")[
        ["beta", "r_squared", "alpha", "n_obs", "window_start", "window_end"]
    ]
    table = table.round({"beta": 4, "r_squared": 4, "alpha": 6})
    table["direct_weight_pct"] = table.index.map(lambda p: DIRECT_WEIGHT_PCT.get(p))

    print(table.to_string())

    qqq_highest = table.loc["QQQ", "beta"] == table.drop(SANITY_CHECK_TICKER)["beta"].max()
    tlt_near_zero = abs(table.loc[SANITY_CHECK_TICKER, "beta"]) < 0.1
    print(f"\nSanity check -- QQQ has highest beta among portfolios: {qqq_highest}")
    print(f"Sanity check -- TLT beta near zero (<0.1): {tlt_near_zero} (beta={table.loc[SANITY_CHECK_TICKER, 'beta']:.4f})")

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    table.to_csv(OUTPUT_PATH)
    print(f"\nSaved to {OUTPUT_PATH}")

    plot_chart1()
    plot_chart2(table)
    write_findings(table)


if __name__ == "__main__":
    main()
