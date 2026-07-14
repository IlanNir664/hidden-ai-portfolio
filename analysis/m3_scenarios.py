"""Module 3 (T2.1) -- Scenario Projection: "what if a repricing happened".

NEVER claim a bubble exists or a crash will happen. Every projected number below is
strictly conditional: "if a 2000-style repricing occurred..." / "if a 2022-style
repricing occurred...". This module projects historical shock patterns onto today's
measured betas -- it does not forecast anything.

Method: a two-factor decomposition of each portfolio's daily log returns --
  Factor 1 (AI):   the equal-weighted AI basket (same construction as m1_concentration.py)
  Factor 2 (rest): RSP residualized against the AI basket (RSP's return left over after
                    removing its AI-basket-explained component) -- an orthogonal proxy
                    for "the rest of the market"
Projected drawdown ~= beta_AI * AI_shock + beta_rest * rest_shock (LINEAR; see
outputs/m3_methodology.md and LIMITATIONS.md for why this likely understates real
crash losses -- correlations rise and the relationship is not actually linear).

Run: python analysis/m3_scenarios.py
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
    COLOR_RED,
    COLOR_SURFACE,
    COLOR_VIOLET,
    COLOR_YELLOW,
    COLOR_ZERO_LINE,
    LONG_WINDOW,
    WINDOW,
    ai_basket_simple_returns,
    annualized_return,
    build_rest_factor,
    gate_check as lib_gate_check,
    load_m2_shocks,
    load_prices,
    project_scenario,
    to_log_returns,
    two_factor_regress,
)

M1_TABLE_PATH = Path(__file__).parent.parent / "outputs" / "m1_beta_table.csv"
TABLE_PATH = Path(__file__).parent.parent / "outputs" / "m3_scenario_table.csv"
CHART5_PATH = Path(__file__).parent.parent / "outputs" / "chart5_scenario_outcomes.png"
CHART6_PATH = Path(__file__).parent.parent / "outputs" / "chart6_tradeoff.png"
FINDINGS_PATH = Path(__file__).parent.parent / "outputs" / "m3_findings.md"

PORTFOLIOS = ["SPY", "VT", "QQQ", "RSP"]  # 60/40 built synthetically below
SANITY_CHECK_TICKER = "TLT"
CHART_ORDER = ["QQQ", "SPY", "VT", "60/40", "RSP", "TLT"]


def gate_check(prices: pd.DataFrame) -> None:
    drawdown = lib_gate_check(prices)  # raises AssertionError on failure
    print(f"Gate check -- SPY 2022 max drawdown: {drawdown*100:.2f}% (expected ~-24.5%)")
    print("Gate check PASSED.\n")


def run_sanity_checks(table: pd.DataFrame) -> None:
    print("--- Sanity checks ---")

    qqq_ai = table.loc["QQQ", "beta_ai"]
    others_max = table.drop(SANITY_CHECK_TICKER)["beta_ai"].max()
    qqq_highest = qqq_ai == others_max
    print(f"QQQ has highest beta_AI among portfolios: {qqq_highest} (QQQ={qqq_ai:.4f}, max={others_max:.4f})")
    assert qqq_highest, "SANITY CHECK FAILED: QQQ does not have the highest beta_AI."

    tlt_ai = table.loc[SANITY_CHECK_TICKER, "beta_ai"]
    tlt_low = tlt_ai < 0.1
    print(f"TLT beta_AI < 0.1: {tlt_low} (beta_AI={tlt_ai:.4f})")
    assert tlt_low, f"SANITY CHECK FAILED: TLT beta_AI={tlt_ai:.4f} is not < 0.1."

    m1 = pd.read_csv(M1_TABLE_PATH).set_index("portfolio")
    print("Two-factor beta_AI vs. Module 1 single-factor beta (tolerance 0.05):")
    for portfolio in table.index:
        if portfolio not in m1.index:
            continue
        diff = abs(table.loc[portfolio, "beta_ai"] - m1.loc[portfolio, "beta"])
        ok = diff <= 0.05
        print(f"  {portfolio}: two-factor={table.loc[portfolio, 'beta_ai']:.4f}, "
              f"m1={m1.loc[portfolio, 'beta']:.4f}, diff={diff:.4f}, {'OK' if ok else 'MISMATCH'}")
        assert ok, f"SANITY CHECK FAILED: {portfolio} beta_AI diverges from m1_beta_table.csv by {diff:.4f} (>0.05)."

    print("All sanity checks PASSED.\n")


def build_table(prices: pd.DataFrame) -> pd.DataFrame:
    simple_returns = prices.pct_change()
    basket_simple = ai_basket_simple_returns(simple_returns)
    ai_log = to_log_returns(basket_simple)
    rsp_log = to_log_returns(simple_returns["RSP"])

    # 252-day rest factor -- used as the second regressor for portfolio betas
    _, ai_252_aligned, rest_factor_252 = build_rest_factor(rsp_log, ai_log, WINDOW)

    # 756-day (~3yr) rest factor -- used only for the "no bubble" trend-continuation baseline
    _, ai_756_aligned, rest_factor_756 = build_rest_factor(rsp_log, ai_log, LONG_WINDOW)

    ai_shock_no_bubble = annualized_return(ai_756_aligned)
    rest_shock_no_bubble = annualized_return(rest_factor_756)
    print(f"No-bubble baseline: AI basket trailing 3yr annualized return = {ai_shock_no_bubble*100:.1f}%, "
          f"rest-of-market factor trailing 3yr annualized return = {rest_shock_no_bubble*100:.1f}%\n")

    shocks = load_m2_shocks()
    print(f"Dot-com-style shocks: AI={shocks['dotcom_ai_shock']*100:.1f}%, rest={shocks['dotcom_rest_shock']*100:.1f}%")
    print(f"2022-style shocks:    AI={shocks['2022_ai_shock']*100:.1f}%, rest={shocks['2022_rest_shock']*100:.1f}%")
    # Unlike dot-com, the GFC's rest_shock is expected to be roughly EQUAL to or
    # LARGER in magnitude than its AI_shock -- 2008 was a systemic crash, not a
    # concentration crash, so "the rest of the market" (value/IWD) fell about as
    # hard as the epicenter (Nasdaq/QQQ), sometimes harder. See m3_methodology.md.
    print(f"2008-style shocks:    AI={shocks['gfc_ai_shock']*100:.1f}%, rest={shocks['gfc_rest_shock']*100:.1f}%\n")

    sixty_forty_simple = 0.6 * simple_returns["SPY"] + 0.4 * simple_returns["TLT"]
    targets = {p: to_log_returns(simple_returns[p]) for p in PORTFOLIOS}
    targets["60/40"] = to_log_returns(sixty_forty_simple)
    targets[SANITY_CHECK_TICKER] = to_log_returns(simple_returns[SANITY_CHECK_TICKER])

    rows = []
    for name, y_log in targets.items():
        result = two_factor_regress(y_log, ai_log, rest_factor_252)
        result["portfolio"] = name
        result["proj_no_bubble_pct"] = round(
            project_scenario(result["beta_ai"], result["beta_rest"], ai_shock_no_bubble, rest_shock_no_bubble) * 100, 1)
        result["proj_2022_style_pct"] = round(
            project_scenario(result["beta_ai"], result["beta_rest"], shocks["2022_ai_shock"], shocks["2022_rest_shock"]) * 100, 1)
        result["proj_2008_style_pct"] = round(
            project_scenario(result["beta_ai"], result["beta_rest"], shocks["gfc_ai_shock"], shocks["gfc_rest_shock"]) * 100, 1)
        result["proj_dotcom_style_pct"] = round(
            project_scenario(result["beta_ai"], result["beta_rest"], shocks["dotcom_ai_shock"], shocks["dotcom_rest_shock"]) * 100, 1)
        rows.append(result)

    table = pd.DataFrame(rows).set_index("portfolio")[
        ["beta_ai", "beta_rest", "alpha", "r_squared", "n_obs",
         "proj_no_bubble_pct", "proj_2022_style_pct", "proj_2008_style_pct", "proj_dotcom_style_pct"]
    ]
    table[["beta_ai", "beta_rest", "r_squared"]] = table[["beta_ai", "beta_rest", "r_squared"]].round(4)
    return table


def plot_chart5(table: pd.DataFrame) -> None:
    """Chart 5: projected outcome per portfolio under each of the 4 scenarios,
    ordered no-bubble -> 2022-style -> 2008-style -> dot-com-style -- ascending
    severity left to right within each portfolio's group (no-bubble is a gain, then
    each successive scenario's shock is a larger-magnitude loss than the last: 2022
    QQQ shock -34.8%, GFC QQQ shock -53.4%, dot-com Nasdaq shock -77.9%)."""
    names = CHART_ORDER
    no_bubble = [table.loc[p, "proj_no_bubble_pct"] for p in names]
    style_2022 = [table.loc[p, "proj_2022_style_pct"] for p in names]
    style_2008 = [table.loc[p, "proj_2008_style_pct"] for p in names]
    style_dotcom = [table.loc[p, "proj_dotcom_style_pct"] for p in names]

    x = np.arange(len(names))
    width = 0.19

    fig, ax = plt.subplots(figsize=(11, 6), dpi=150)
    fig.patch.set_facecolor(COLOR_SURFACE)
    ax.set_facecolor(COLOR_SURFACE)

    ax.axhline(0, color=COLOR_ZERO_LINE, linewidth=1, zorder=1)

    bars_a = ax.bar(x - 1.5 * width, no_bubble, width, color=COLOR_BLUE, label="No bubble (trend continuation)", zorder=3)
    bars_b = ax.bar(x - 0.5 * width, style_2022, width, color=COLOR_YELLOW, label="If a 2022-style repricing occurred", zorder=3)
    bars_c = ax.bar(x + 0.5 * width, style_2008, width, color=COLOR_VIOLET, label="If a 2008-style repricing occurred", zorder=3)
    bars_d = ax.bar(x + 1.5 * width, style_dotcom, width, color=COLOR_RED, label="If a dot-com-style repricing occurred", zorder=3)

    for bars in (bars_a, bars_b, bars_c, bars_d):
        for bar in bars:
            h = bar.get_height()
            va = "bottom" if h >= 0 else "top"
            offset = 1.5 if h >= 0 else -1.5
            ax.text(bar.get_x() + bar.get_width() / 2, h + offset, f"{h:.0f}%",
                    ha="center", va=va, fontsize=7, color=COLOR_INK_PRIMARY)

    ax.set_ylabel("Projected outcome (%)", fontsize=10, color=COLOR_INK_SECONDARY)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{n}\n(control)" if n == SANITY_CHECK_TICKER else n for n in names])

    fig.text(0.01, 0.965, "If a repricing happened: projected ETF outcomes by scenario", fontsize=14.5,
              color=COLOR_INK_PRIMARY, weight="bold")
    fig.text(0.01, 0.93, "Projection, not a forecast -- today's measured AI/rest-of-market betas applied to historical shock sizes",
              fontsize=9, color=COLOR_INK_SECONDARY)

    ax.spines[["top", "right"]].set_visible(False)
    ax.spines["left"].set_color(COLOR_INK_MUTED)
    ax.spines["bottom"].set_color(COLOR_INK_MUTED)
    ax.tick_params(axis="x", colors=COLOR_INK_SECONDARY, labelsize=9.5)
    ax.tick_params(axis="y", colors=COLOR_INK_MUTED, labelsize=9)
    ax.yaxis.grid(True, color=COLOR_GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    ax.legend(loc="upper right", frameon=False, fontsize=8.5, labelcolor=COLOR_INK_SECONDARY)

    fig.text(0.01, 0.04,
              "Linear projection: beta_AI x AI_shock + beta_rest x rest_shock. No alpha/drift term. See",
              fontsize=7.5, color=COLOR_INK_MUTED)
    fig.text(0.01, 0.015,
              "LIMITATIONS.md -- this is a scenario, not a prediction that any repricing will occur.",
              fontsize=7.5, color=COLOR_INK_MUTED)

    fig.tight_layout(rect=(0, 0.09, 1, 0.9))
    fig.savefig(CHART5_PATH, facecolor=COLOR_SURFACE)
    plt.close(fig)
    print(f"Chart saved to {CHART5_PATH}")


def plot_chart6(table: pd.DataFrame) -> None:
    """Chart 6: the tradeoff -- projected dot-com-scenario loss vs. no-bubble gain."""
    names = [p for p in CHART_ORDER if p != SANITY_CHECK_TICKER]

    fig, ax = plt.subplots(figsize=(8, 6.5), dpi=150)
    fig.patch.set_facecolor(COLOR_SURFACE)
    ax.set_facecolor(COLOR_SURFACE)

    ax.axhline(0, color=COLOR_ZERO_LINE, linewidth=1, zorder=1)
    ax.axvline(0, color=COLOR_ZERO_LINE, linewidth=1, zorder=1)

    for name in names:
        x_loss = table.loc[name, "proj_dotcom_style_pct"]
        y_gain = table.loc[name, "proj_no_bubble_pct"]
        ax.scatter(x_loss, y_gain, s=90, color=COLOR_BLUE, zorder=3, edgecolor=COLOR_SURFACE, linewidth=1.2)
        ax.annotate(name, (x_loss, y_gain), xytext=(7, 5), textcoords="offset points",
                    fontsize=10, color=COLOR_INK_PRIMARY, weight="bold")

    ax.set_xlabel("Projected loss if a dot-com-style repricing occurred (%)", fontsize=10, color=COLOR_INK_SECONDARY)
    ax.set_ylabel("Projected gain if no repricing occurs (%)", fontsize=10, color=COLOR_INK_SECONDARY)

    fig.text(0.01, 0.965, "The menu: upside kept vs. downside risked", fontsize=14.5,
              color=COLOR_INK_PRIMARY, weight="bold")
    fig.text(0.01, 0.925, "Each point is one portfolio's projected outcome under two conditional scenarios",
              fontsize=9, color=COLOR_INK_SECONDARY)

    ax.spines[["top", "right"]].set_visible(False)
    ax.spines["left"].set_color(COLOR_INK_MUTED)
    ax.spines["bottom"].set_color(COLOR_INK_MUTED)
    ax.tick_params(axis="both", colors=COLOR_INK_MUTED, labelsize=9)
    ax.grid(True, color=COLOR_GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    fig.text(0.01, 0.04,
              "This chart does not recommend a weight -- it shows the tradeoff each portfolio implies.",
              fontsize=7.5, color=COLOR_INK_MUTED)
    fig.text(0.01, 0.015,
              "Projection, not a forecast. See LIMITATIONS.md.",
              fontsize=7.5, color=COLOR_INK_MUTED)

    fig.tight_layout(rect=(0, 0.09, 1, 0.9))
    fig.savefig(CHART6_PATH, facecolor=COLOR_SURFACE)
    plt.close(fig)
    print(f"Chart saved to {CHART6_PATH}")


def write_findings(table: pd.DataFrame) -> None:
    qqq = table.loc["QQQ"]
    rsp = table.loc["RSP"]
    spy = table.loc["SPY"]
    sixty_forty = table.loc["60/40"]

    text = f"""# Module 3 Findings -- Scenario Projection

If a dot-com-style repricing occurred, QQQ's projected loss ({qqq['proj_dotcom_style_pct']:.0f}%)
is the largest of the portfolios tested, versus RSP's ({rsp['proj_dotcom_style_pct']:.0f}%) --
but QQQ's projected no-bubble gain ({qqq['proj_no_bubble_pct']:.0f}%) is also the largest,
against RSP's ({rsp['proj_no_bubble_pct']:.0f}%). SPY and the synthetic 60/40 sit between
the two: {spy['proj_dotcom_style_pct']:.0f}%/{spy['proj_no_bubble_pct']:.0f}% and
{sixty_forty['proj_dotcom_style_pct']:.0f}%/{sixty_forty['proj_no_bubble_pct']:.0f}%
respectively (Chart 6). Every portfolio in this study sits somewhere on the same
upside-kept-versus-downside-risked line -- none dominates the others on both axes at
once, and this project does not recommend a weight. These are conditional projections
built from today's measured betas and historical shock sizes, not forecasts that any
scenario will happen -- see `m3_methodology.md` and `LIMITATIONS.md` for why real
crash losses likely run worse than the linear numbers shown here.

**A third scenario, 2008-style, tells a different kind of story -- and it is not the
milder one.** The synthetic 60/40's projected outcome if a 2008-style repricing
occurred is {sixty_forty['proj_2008_style_pct']:.0f}%, *worse* than its {sixty_forty['proj_dotcom_style_pct']:.0f}% dot-com-style
projection, even though the 2008 AI_shock itself (-53.4%, QQQ) is smaller in
magnitude than the dot-com AI_shock (-77.9%, Nasdaq Composite). The reason is the
rest_shock: 2008's (-59.8%, value/IWD) is far deeper than dot-com's (-34.1%, also
value/IWD, different era) -- because 2008 was systemic, "the rest of the market"
fell almost as hard as the epicenter, whereas in the dot-com crash it barely fell at
all. A portfolio like 60/40, with meaningful exposure to both factors (`beta_ai`
0.32, `beta_rest` 0.41), takes the hit on both sides at once in the 2008 scenario in
a way it doesn't in the dot-com one. This projection likely still *understates* the
real difference: the two-factor model only "sees" bonds through `beta_rest` applied
to an equity rest-of-market shock -- it has no way to represent TLT's actual 2008
behavior, a +26% *gain* (Module 2's flight-to-quality finding), so a real 60/40
investor's 2008-style outcome would likely have been meaningfully better than even
this worse-than-dot-com number shows. See `LIMITATIONS.md`, Module 3 section.
"""
    FINDINGS_PATH.write_text(text)
    print(f"Findings written to {FINDINGS_PATH}")


def main() -> None:
    prices = load_prices()
    gate_check(prices)

    table = build_table(prices)
    run_sanity_checks(table)

    print(table.to_string())

    TABLE_PATH.parent.mkdir(exist_ok=True)
    table.to_csv(TABLE_PATH)
    print(f"\nSaved to {TABLE_PATH}")

    plot_chart5(table)
    plot_chart6(table)
    write_findings(table)


if __name__ == "__main__":
    main()
