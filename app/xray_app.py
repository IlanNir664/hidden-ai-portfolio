"""The Portfolio X-Ray -- how much AI is secretly in YOUR portfolio?

A single-page Streamlit app on top of the Hidden AI Portfolio project's own
research machinery (analysis/factor_lib.py). Users build a portfolio from a
~100-ticker demo universe (whatever is cached in data/prices.db -- the original
research tickers plus a wide set of popular ETFs and single stocks, see
data/pull_prices.py) and get back:
  1. Their portfolio's effective AI exposure (beta) vs. its naive direct weight.
  2. Where they sit among the project's five reference portfolios (Chart 2 style).
  3. Their projected outcome under four conditional scenarios (Chart 5 style).
  4. The upside-kept-vs-downside-risked tradeoff (Chart 6 style).
  5. (bonus, collapsed) When their portfolio's rolling AI beta crossed today's level.

NEVER claim a bubble exists or a crash will happen. Every projected number carries
conditional language on screen -- "if a 2000-style repricing occurred..." -- not
buried in a tooltip. All analysis reads from data/prices.db only; nothing here
fetches new tickers at runtime (see factor_lib.available_tickers -- EXTENSION
POINT). Simple returns for performance/drawdowns, log returns for regressions,
same as every other module in this project.

Visual identity (v2): a dark-fintech app shell and in-app Plotly charts, both
using this file's own palette -- a deliberate departure from v1's convention of
matching the research PNGs' light-surface palette inside the app too. The
published research charts (outputs/chart1-6*.png) are untouched by this file and
keep their original look; only the interactive, in-app versions are restyled.

Run: streamlit run app/xray_app.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "analysis"))
sys.path.insert(0, str(PROJECT_ROOT / "data"))
import factor_lib as fl  # noqa: E402
import pull_prices as pp  # noqa: E402

M1_TABLE_PATH = PROJECT_ROOT / "outputs" / "m1_beta_table.csv"
M3_TABLE_PATH = PROJECT_ROOT / "outputs" / "m3_scenario_table.csv"

REFERENCE_PORTFOLIOS = ["QQQ", "SPY", "VT", "60/40", "RSP"]

# --- Dark fintech palette (app chrome + in-app charts only -- see module docstring) ---
BG_APP = "#0E0F0C"
BG_CARD = "#1A1B17"
LIME = "#C8F135"          # primary accent: positive numbers, user's own series, main action
LIME_DIM = "rgba(200,241,53,0.45)"  # dimmer tint for the user's "direct weight" half-bar
INDIGO = "#5B4CF5"        # secondary accent, used sparingly (dot-com-style scenario series)
AMBER = "#E3A83B"         # 2022-style scenario series
NEG_RED = "#F4534A"
TEXT_PRIMARY = "#F4F5F0"
TEXT_MUTED = "#9A9C93"
MUTED_GRAY_1 = "#5C5E56"  # reference-portfolio "direct weight" bars
MUTED_GRAY_2 = "#8B8D82"  # reference-portfolio dots/lines (tradeoff chart, rolling beta)
SAGE = "#6FA287"          # reference-portfolio "effective exposure" bars -- distinct hue from
                          # the muted-gray "direct weight" bars, so the direct-vs-effective gap
                          # (this chart's entire point) stays visually legible
GRIDLINE = "rgba(154,156,147,0.15)"
FONT_STACK = "'Inter','Space Grotesk','Segoe UI',system-ui,-apple-system,sans-serif"

# Page-background "atmosphere" (CSS only -- see the html/body/.stApp rule and the
# .stApp::before diagonal-line rule below). v2: sharper and more designed than the
# original soft-glow version -- a real blueprint/terminal grid with two tiers,
# one focused lime glow (harder falloff than before), a vignette, and a single
# diagonal lime "laser edge" behind the hero. All values chosen to stay well
# clear of the readability floor (muted-gray captions on the flat charcoal) --
# see the contrast check run during this task for the numbers. The indigo glow
# from v1 is dropped entirely -- with the grid and diagonal line added, a second
# glow made the page feel busy rather than sharp.
BG_GRID_FINE_SPACING_PX = 56     # fine grid, within the requested 48-64px range
BG_GRID_FINE_OPACITY = 0.045     # within the requested 4-5%
BG_GRID_MAJOR_SPACING_PX = BG_GRID_FINE_SPACING_PX * 4   # every 4th line, for hierarchy
BG_GRID_MAJOR_OPACITY = 0.075    # within the requested 7-8%
BG_GLOW_LIME_OPACITY = 0.08      # tighter/harder-falloff top-right glow (was 0.055 wash)
BG_GLOW_LIME_RADIUS_PCT = 32     # fades out within this % of viewport -- a focused spot
BG_VIGNETTE_OPACITY = 0.20       # radial darkening toward the corners
BG_DIAGONAL_LINE_OPACITY = 0.40  # the sharp lime edge itself, within the requested 35-45%
BG_DIAGONAL_GLOW_OPACITY = 0.10  # the soft halo running parallel to it

# Portfolio-donut palette: three groups (AI basket / no-equity-exposure bond &
# commodity funds / other equity), each with a few shades of its own family so
# two adjacent same-group segments still visually separate (e.g. NVDA next to
# MSFT, or TLT next to GLD). Cycled per group in the order encountered, not
# hashed, so shade assignment is stable and predictable within one render.
DONUT_LIME_SHADES = ["#C8F135", "#96C42A", "#E6FF8C", "#7A9E20"]
DONUT_GRAY_SHADES = ["#9A9C93", "#6E706A", "#B8BAB0", "#54564F"]
DONUT_SAGE_SHADES = ["#6FA287", "#4C7862", "#8FC2A8", "#3D5F4E"]
DONUT_GROUP_LABELS = {
    "ai": "AI basket member",
    "zero": "No equity exposure (bond/Treasury/commodity)",
    "other": "Other equity",
}
DONUT_LABEL_MIN_PCT = 5.0  # segments below this weight get no outside label, hover only

# Default portfolio shown on first visit -- a diversified DIY-style mix (broad
# market core + a couple of single-stock/sector tilts), not the research
# project's 60/40 reference portfolio. Defined ONCE here; the multiselect
# default, the weight-editor's starting values, and the "Modern DIY mix" preset
# below all read from this single dict so they can never drift out of sync.
# Dict order matters -- it's the order tickers appear as multiselect tags and
# weight-editor rows on first load. Values are percent (0-100), summing to 100.
DEFAULT_PORTFOLIO = {
    "NVDA": 5.0,
    "QQQM": 14.0,
    "VOO": 55.0,
    "AAPL": 3.0,
    "MU": 3.0,
    "SCHD": 5.0,
    "VXUS": 15.0,
}

PRESETS = {
    "Modern DIY mix (default)": dict(DEFAULT_PORTFOLIO),
    "60/40 (SPY/TLT)": {"SPY": 60.0, "TLT": 40.0},
    "100% QQQ -- max AI exposure": {"QQQ": 100.0},
    "100% NVDA -- direct AI holding": {"NVDA": 100.0},
    "Low-AI mix (utilities/staples/REITs/dividend)": {"XLU": 25.0, "XLP": 25.0, "VNQ": 25.0, "SCHD": 25.0},
    "100% RSP -- equal-weight S&P": {"RSP": 100.0},
    "All-weather-ish (SPY/TLT/GLD/VNQ)": {"SPY": 40.0, "TLT": 30.0, "GLD": 15.0, "VNQ": 15.0},
    "100% TSLA -- single growth stock": {"TSLA": 100.0},
    "Crypto-adjacent (COIN/SPY) -- shorter-history demo": {"COIN": 60.0, "SPY": 40.0},
}


# ============================================================================
# Cached data layer -- everything here is independent of the user's portfolio,
# so it's computed once per session and reused across every rerun.
# ============================================================================

@st.cache_data
def load_prices_cached() -> pd.DataFrame:
    return fl.load_prices()


@st.cache_data
def get_simple_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change()


@st.cache_data
def get_ai_log(prices: pd.DataFrame) -> pd.Series:
    simple_returns = get_simple_returns(prices)
    return fl.to_log_returns(fl.ai_basket_simple_returns(simple_returns))


@st.cache_data
def get_rest_factors(prices: pd.DataFrame):
    simple_returns = get_simple_returns(prices)
    ai_log = get_ai_log(prices)
    rsp_log = fl.to_log_returns(simple_returns["RSP"])
    _, _, rest_252 = fl.build_rest_factor(rsp_log, ai_log, fl.WINDOW)
    _, ai_756, rest_756 = fl.build_rest_factor(rsp_log, ai_log, fl.LONG_WINDOW)
    return rest_252, ai_756, rest_756


@st.cache_data
def get_no_bubble_shocks(prices: pd.DataFrame):
    _, ai_756, rest_756 = get_rest_factors(prices)
    return fl.annualized_return(ai_756), fl.annualized_return(rest_756)


@st.cache_data
def get_m2_shocks() -> dict:
    return fl.load_m2_shocks()


@st.cache_data
def get_m1_table() -> pd.DataFrame:
    return pd.read_csv(M1_TABLE_PATH).set_index("portfolio")


@st.cache_data
def get_m3_table() -> pd.DataFrame:
    return pd.read_csv(M3_TABLE_PATH).set_index("portfolio")


@st.cache_data
def get_spy_rolling_beta(prices: pd.DataFrame) -> pd.Series:
    simple_returns = get_simple_returns(prices)
    ai_log = get_ai_log(prices)
    spy_log = fl.to_log_returns(simple_returns["SPY"])
    return fl.rolling_beta(spy_log, ai_log, fl.WINDOW)


# ============================================================================
# Portfolio validation
# ============================================================================

def validate_weights(weight_map: dict):
    """Returns (weights_dict, errors, warnings). weights_dict is None if invalid.

    Duplicate/unsupported tickers can't reach this function: the multiselect only
    offers tickers already in the DB universe, and the manual-entry fallback
    validates membership before adding to the selection. The only thing left to
    check here is whether weights sum to 100%.
    """
    errors, warnings = [], []
    if not weight_map:
        errors.append("Select at least one ticker above.")
        return None, errors, warnings

    total = sum(weight_map.values())
    if abs(total - 100.0) > 0.01:
        errors.append(f"Weights sum to {total:.2f}%, not 100%.")
        return None, errors, warnings

    return {t: w / 100.0 for t, w in weight_map.items()}, errors, warnings


# ============================================================================
# Chart builders (Plotly) -- dark-fintech styling, shared base layout
# ============================================================================

PLOTLY_CONFIG = {"displayModeBar": False}  # hide the camera/zoom toolbar -- chart junk in this look


def _apply_base_layout(fig: go.Figure, y_title: str = None, x_title: str = None, height: int = 460,
                        top_margin: int = 36, bottom_margin: int = 48):
    """Shared dark-fintech layout. No in-chart title -- the Streamlit step header
    above each chart already states it; a second title inside the figure duplicated
    it and, worse, could overlap the legend/data. Title lives in exactly one place.
    """
    fig.update_layout(
        paper_bgcolor=BG_CARD,
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT_MUTED, family=FONT_STACK, size=12),
        margin=dict(t=top_margin, l=56, r=24, b=bottom_margin),
        height=height,
        showlegend=False,
        hoverlabel=dict(bgcolor="#23251E", font_color=TEXT_PRIMARY, font_family=FONT_STACK, bordercolor=LIME),
        xaxis=dict(showgrid=False, zeroline=False, showline=True, linecolor="rgba(154,156,147,0.3)",
                    tickfont=dict(color=TEXT_MUTED)),
        yaxis=dict(showgrid=True, gridcolor=GRIDLINE, zeroline=False, showline=False,
                    tickfont=dict(color=TEXT_MUTED)),
    )
    if y_title:
        fig.update_yaxes(title=dict(text=y_title, font=dict(color=TEXT_MUTED, size=11)))
    if x_title:
        fig.update_xaxes(title=dict(text=x_title, font=dict(color=TEXT_MUTED, size=11)))
    return fig


def render_comparison_chart(m1_table: pd.DataFrame, user_beta_pct: float, user_direct_pct):
    names = REFERENCE_PORTFOLIOS
    direct = [fl.DIRECT_WEIGHT_PCT[p] for p in names]
    effective = [m1_table.loc[p, "beta"] * 100 for p in names]

    all_names = names + ["YOU"]
    all_direct_raw = direct + [user_direct_pct]
    all_effective = effective + [user_beta_pct]

    direct_y = [v if v is not None else 0 for v in all_direct_raw]
    direct_text = [f"{v:.0f}%" if v is not None else "N/A" for v in all_direct_raw]
    direct_colors = [MUTED_GRAY_1] * len(names) + [LIME_DIM]
    effective_colors = [SAGE] * len(names) + [LIME]

    fig = go.Figure()
    fig.add_bar(
        name="Direct weight (top-10 holdings)", x=all_names, y=direct_y, marker_color=direct_colors,
        marker_cornerradius=8, text=direct_text, textposition="outside", textfont=dict(color=TEXT_PRIMARY, size=11),
        hovertemplate="%{x}<br>Direct weight: %{text}<extra></extra>",
    )
    fig.add_bar(
        name="Effective exposure (252-day beta)", x=all_names, y=all_effective, marker_color=effective_colors,
        marker_cornerradius=8, text=[f"{v:.0f}%" for v in all_effective], textposition="outside",
        textfont=dict(color=TEXT_PRIMARY, size=11),
        hovertemplate="%{x}<br>Effective exposure: %{y:.1f}%<extra></extra>",
    )

    _apply_base_layout(fig, y_title="Share of portfolio driven by the AI basket (%)", top_margin=44)
    fig.update_layout(
        barmode="group",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)", font=dict(color=TEXT_MUTED, size=11)),
    )
    return fig


def render_scenario_chart(no_bubble_pct: float, style_2022_pct: float, style_2008_pct: float,
                           style_dotcom_pct: float, spy_crash_refs: dict = None):
    """Bar order is no-bubble -> 2022-style -> 2008-style -> dot-com-style: ascending
    severity left to right (no-bubble is a gain; each crash scenario's shock is a
    larger-magnitude loss than the last), same convention as m3_scenarios.py's
    chart5. spy_crash_refs, if given, is {"2022": pct, "2008": pct, "dotcom": pct} --
    SPY's own projection under each of the three crash scenarios (not no-bubble),
    read from the same source Step 5 already uses.
    """
    labels = ["No bubble<br>(trend continuation)", "If a 2022-style<br>repricing occurred",
              "If a 2008-style<br>repricing occurred", "If a dot-com-style<br>repricing occurred"]
    values = [no_bubble_pct, style_2022_pct, style_2008_pct, style_dotcom_pct]
    colors = [LIME, AMBER, NEG_RED, INDIGO]
    # Emphasis (not recolor) on the dot-com bar, still the deepest single shock of
    # the three crash scenarios -- a brighter outline on just that bar, none on
    # the others.
    line_colors = ["rgba(0,0,0,0)", "rgba(0,0,0,0)", "rgba(0,0,0,0)", "#8B7FFF"]
    line_widths = [0, 0, 0, 2.5]

    fig = go.Figure(go.Bar(
        x=labels, y=values, marker=dict(color=colors, cornerradius=10, line=dict(color=line_colors, width=line_widths)),
        text=[f"{v:+.0f}%" for v in values], textposition="outside",
        textfont=dict(color=TEXT_PRIMARY, size=13),
        hovertemplate="%{x}<br>Projected outcome: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="rgba(154,156,147,0.35)", line_width=1)

    if spy_crash_refs:
        # "Is my number bad?" reference: where SPY lands in the SAME scenario, read
        # from the same m3_scenario_table.csv Step 5 already uses -- never
        # hardcoded. A single page-wide line no longer makes sense with 4 bars on
        # different scales (no-bubble is a gain), so this is a short horizontal
        # tick centered on each crash-scenario bar specifically, at SPY's value for
        # that scenario -- not drawn under no-bubble. Skipped entirely by the
        # caller when the user's own portfolio IS SPY.
        ref_labels = [lbl for lbl, key in zip(labels[1:], ["2022", "2008", "dotcom"]) if key in spy_crash_refs]
        ref_values = [spy_crash_refs[key] for key in ["2022", "2008", "dotcom"] if key in spy_crash_refs]
        fig.add_scatter(
            x=ref_labels, y=ref_values, mode="markers", showlegend=False,
            marker=dict(symbol="line-ew", size=46, line=dict(color=MUTED_GRAY_2, width=2.5)),
            hovertemplate="SPY, same scenario: %{y:.1f}%<extra></extra>",
        )
        fig.add_annotation(
            x=ref_labels[-1], y=ref_values[-1], text="SPY, same scenario", showarrow=False,
            yshift=16, font=dict(color=MUTED_GRAY_2, size=10),
        )

    _apply_base_layout(fig, y_title="Projected outcome (%)", bottom_margin=80)
    return fig


def render_tradeoff_chart(m3_reference: dict, user_loss_pct: float, user_gain_pct: float):
    # If the user's portfolio coincides (or nearly so) with a reference point -- e.g.
    # the default preset IS the 60/40 reference portfolio -- both text labels would
    # sit on the same spot and turn to mush. Hide that reference's label (its dot
    # stays visible) and let "YOU" own the position instead.
    coincide_tol = 0.5  # percentage points, on the projected-loss/gain scale
    ref_names, ref_x, ref_y, ref_text = [], [], [], []
    for name, (loss, gain) in m3_reference.items():
        ref_names.append(name)
        ref_x.append(loss)
        ref_y.append(gain)
        coincides = abs(loss - user_loss_pct) < coincide_tol and abs(gain - user_gain_pct) < coincide_tol
        ref_text.append("" if coincides else name)

    fig = go.Figure()
    fig.add_scatter(
        x=ref_x, y=ref_y, mode="markers+text", text=ref_text, textposition="top center",
        textfont=dict(color=TEXT_MUTED, size=11),
        marker=dict(size=11, color=MUTED_GRAY_2, line=dict(color=BG_CARD, width=1)),
        customdata=ref_names,
        hovertemplate="%{customdata}<br>Dot-com loss: %{x:.1f}%<br>No-bubble gain: %{y:.1f}%<extra></extra>",
    )
    # soft glow halo behind the user's marker -- tightened vs. v1 (was reading as a
    # separate blob): smaller, lower-opacity ring plus a light border on the main
    # marker instead of relying on the halo alone for pop.
    fig.add_scatter(x=[user_loss_pct], y=[user_gain_pct], mode="markers",
                     marker=dict(size=24, color=LIME, opacity=0.30), hoverinfo="skip")
    fig.add_scatter(
        x=[user_loss_pct], y=[user_gain_pct], mode="markers+text", text=["YOU"], textposition="top center",
        textfont=dict(color=LIME, size=13, family=FONT_STACK),
        marker=dict(size=15, color=LIME, symbol="diamond", line=dict(color=TEXT_PRIMARY, width=1.5)),
        hovertemplate="YOU<br>Dot-com loss: %{x:.1f}%<br>No-bubble gain: %{y:.1f}%<extra></extra>",
    )
    fig.add_hline(y=0, line_color="rgba(154,156,147,0.35)", line_width=1)
    fig.add_vline(x=0, line_color="rgba(154,156,147,0.35)", line_width=1)

    _apply_base_layout(
        fig,
        x_title="Projected loss if a dot-com-style repricing occurred (%)",
        y_title="Projected gain if no repricing occurs (%)", height=520,
    )
    return fig


def render_rolling_beta_chart(user_rolling: pd.Series, spy_rolling: pd.Series, user_label: str):
    fig = go.Figure()
    fig.add_scatter(
        x=spy_rolling.index, y=spy_rolling.values * 100, mode="lines",
        line=dict(color=MUTED_GRAY_2, width=1.5),
        hovertemplate="%{x|%Y-%m-%d}<br>SPY beta: %{y:.0f}%<extra></extra>",
    )
    fig.add_scatter(
        x=user_rolling.index, y=user_rolling.values * 100, mode="lines",
        line=dict(color=LIME, width=2.5), fill="tozeroy",
        fillgradient=dict(type="vertical", colorscale=[[0, "rgba(200,241,53,0.32)"], [1, "rgba(200,241,53,0)"]]),
        hovertemplate="%{x|%Y-%m-%d}<br>" + user_label + " beta: %{y:.0f}%<extra></extra>",
    )
    fig.add_annotation(x=user_rolling.index[-1], y=user_rolling.values[-1] * 100, text=user_label,
                        showarrow=False, xanchor="left", xshift=10, font=dict(color=LIME, size=12))
    fig.add_annotation(x=spy_rolling.index[-1], y=spy_rolling.values[-1] * 100, text="SPY",
                        showarrow=False, xanchor="left", xshift=10, font=dict(color=MUTED_GRAY_2, size=12))
    _apply_base_layout(fig, y_title="252-day rolling AI beta (%)")
    fig.update_layout(margin=dict(t=36, l=56, r=70, b=48))
    return fig


def render_hero_sparkline(user_rolling_recent: pd.Series, current_beta_pct: float):
    """Tiny lime-glow sparkline for the top-of-page hero -- last ~2 years of the
    user's rolling AI beta, no axes/gridlines, just the shape and where it ends up.
    Shares the same rolling-beta series the Step 5 (bonus) chart uses; this function
    only handles a truncated slice and stripped-down layout, no new computation.
    """
    fig = go.Figure()
    fig.add_scatter(
        x=user_rolling_recent.index, y=user_rolling_recent.values * 100, mode="lines",
        line=dict(color=LIME, width=2.5), fill="tozeroy",
        fillgradient=dict(type="vertical", colorscale=[[0, "rgba(200,241,53,0.32)"], [1, "rgba(200,241,53,0)"]]),
        hoverinfo="skip",
    )
    fig.add_annotation(
        x=user_rolling_recent.index[-1], y=user_rolling_recent.values[-1] * 100,
        text=f"{current_beta_pct:.0f}%", showarrow=False, xanchor="left", xshift=8,
        font=dict(color=LIME, size=16, family=FONT_STACK),
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=160, margin=dict(t=10, l=4, r=48, b=10),
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def _donut_group_for(ticker: str) -> str:
    if ticker in fl.AI_BASKET:
        return "ai"
    if ticker in fl.ZERO_DIRECT_WEIGHT_TICKERS:
        return "zero"
    return "other"


def render_portfolio_donut(weights: dict, beta_pct: float):
    """Donut (go.Pie, hole=0.55) -- one segment per holding, sized by weight.
    Color signals the GROUP a holding belongs to (AI basket / no equity exposure /
    other equity), with a few shades per group so two same-group segments sitting
    next to each other (e.g. NVDA next to MSFT) still visually separate. The
    donut hole carries the portfolio's already-computed effective AI exposure --
    this chart is placed after the Computation block specifically so that number
    is available here, not recomputed.
    """
    tickers = list(weights.keys())
    weight_pcts = [weights[t] * 100 for t in tickers]

    shade_pools = {"ai": DONUT_LIME_SHADES, "zero": DONUT_GRAY_SHADES, "other": DONUT_SAGE_SHADES}
    group_counters = {"ai": 0, "zero": 0, "other": 0}
    colors, hover_group_labels = [], []
    for ticker in tickers:
        group = _donut_group_for(ticker)
        shades = shade_pools[group]
        colors.append(shades[group_counters[group] % len(shades)])
        group_counters[group] += 1
        hover_group_labels.append(DONUT_GROUP_LABELS[group])

    outside_text = [f"{t} {w:.0f}%" if w >= DONUT_LABEL_MIN_PCT else "" for t, w in zip(tickers, weight_pcts)]
    text_positions = ["outside" if w >= DONUT_LABEL_MIN_PCT else "none" for w in weight_pcts]

    fig = go.Figure(go.Pie(
        labels=tickers, values=weight_pcts, hole=0.55, sort=False, direction="clockwise",
        marker=dict(colors=colors, line=dict(color=BG_CARD, width=2)),
        text=outside_text, textinfo="text", textposition=text_positions,
        textfont=dict(color=TEXT_PRIMARY, size=11, family=FONT_STACK),
        customdata=list(zip(tickers, hover_group_labels)),
        hovertemplate="%{customdata[0]}<br>Weight: %{value:.1f}%<br>%{customdata[1]}<extra></extra>",
        showlegend=False,
    ))

    fig.add_annotation(
        text=f"{beta_pct:.0f}% AI", x=0.5, y=0.56, xref="paper", yref="paper",
        showarrow=False, font=dict(color=LIME, size=26, family=FONT_STACK),
    )
    fig.add_annotation(
        text="effectively AI", x=0.5, y=0.44, xref="paper", yref="paper",
        showarrow=False, font=dict(color=TEXT_MUTED, size=11, family=FONT_STACK),
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin=dict(t=30, l=30, r=30, b=30),
        height=340,
        font=dict(family=FONT_STACK, color=TEXT_MUTED),
    )
    return fig


# ============================================================================
# Copy-generation helpers -- plain-language sentences built ONLY from values
# already computed elsewhere (m1_table betas, the user's own beta/scenario
# numbers). No new math, just phrasing.
# ============================================================================

def format_ticker_list(tickers: list, max_named: int = 3) -> str:
    """'A, B, C' for a short list; 'A, B, C and N others' once naming every ticker
    would read as a wall of text (e.g. this app's own default portfolio, where 5
    of 7 holdings have no known top-10 weight)."""
    if len(tickers) <= max_named:
        return ", ".join(tickers)
    remaining = len(tickers) - max_named
    return f"{', '.join(tickers[:max_named])} and {remaining} other{'s' if remaining != 1 else ''}"


def nearest_reference_portfolio(user_beta_pct: float, ref_betas_pct: dict) -> str:
    """Name of the reference portfolio with the smallest |beta_AI| difference."""
    return min(ref_betas_pct, key=lambda p: abs(ref_betas_pct[p] - user_beta_pct))


def comparative_anchor_line(user_beta_pct: float, ref_betas_pct: dict, tie_tol: float = 0.05) -> str:
    """'more AI than X (n%), less than Y (m%)' -- or the below-all/above-all edge
    phrasing when the user's beta doesn't sit between any two reference points.

    tie_tol (percentage points) treats a reference within this margin of the user's
    own beta as a tie rather than strictly above/below -- otherwise a user portfolio
    that reproduces a reference portfolio exactly (e.g. 100% QQQ) would flip-flop
    between "just above" and "just below" QQQ based on float noise between the live
    regression and the CSV-rounded m1_beta_table.csv value, instead of reading as
    the "at the top" edge case it actually is. 0.05pp is comfortably below the
    smallest real gap between two distinct reference portfolios (SPY/VT, ~0.26pp).
    """
    below = {p: b for p, b in ref_betas_pct.items() if b < user_beta_pct - tie_tol}
    above = {p: b for p, b in ref_betas_pct.items() if b > user_beta_pct + tie_tol}
    if below and above:
        below_name = max(below, key=below.get)
        above_name = min(above, key=above.get)
        return f"more AI than a {below_name} ({below[below_name]:.0f}%), less than {above_name} ({above[above_name]:.0f}%)"
    if not below:
        lowest_name = min(ref_betas_pct, key=ref_betas_pct.get)
        return f"less AI than every standard portfolio tested (lowest: {lowest_name}, {ref_betas_pct[lowest_name]:.0f}%)"
    highest_name = max(ref_betas_pct, key=ref_betas_pct.get)
    return f"more AI than even {highest_name}, {ref_betas_pct[highest_name]:.0f}%"


# ============================================================================
# Page shell -- dark fintech theme. See module docstring: v2 restyles the
# in-app charts too (Plotly, dark), a deliberate departure from v1's "app
# chrome only" convention. Published research PNGs are untouched.
# ============================================================================

st.set_page_config(page_title="The Portfolio X-Ray", page_icon="\U0001fa7b", layout="wide")

st.markdown(f"""
<style>
    /* Offline-only: no external font/asset requests (golden rule 2 -- app must run
       fully offline from a clean clone). System-local geometric-sans stack only. */
    /* Background "atmosphere" v2 -- sharp blueprint grid (two tiers), one focused
       lime glow, and a vignette, all CSS-only and fixed so none of it scrolls
       with content. Cards/charts paint a fully opaque BG_CARD on top, so none of
       this shows through a card -- it only lives in the page gaps. The diagonal
       "laser edge" is a separate .stApp::before rule below (needs its own box to
       stay bounded to the upper-right quadrant and its own layer to add a glow
       band alongside the sharp line -- awkward to fold into this list). */
    html, body, .stApp {{
        background-color: {BG_APP}; color: {TEXT_PRIMARY};
        background-image:
            radial-gradient(ellipse 70% 65% at 50% 50%, transparent 55%, rgba(0,0,0,{BG_VIGNETTE_OPACITY}) 100%),
            radial-gradient(circle at 100% 0%, rgba(200,241,53,{BG_GLOW_LIME_OPACITY}) 0%, rgba(200,241,53,0) {BG_GLOW_LIME_RADIUS_PCT}%),
            repeating-linear-gradient(to right, rgba(255,255,255,{BG_GRID_MAJOR_OPACITY}) 0 1px, transparent 1px {BG_GRID_MAJOR_SPACING_PX}px),
            repeating-linear-gradient(to bottom, rgba(255,255,255,{BG_GRID_MAJOR_OPACITY}) 0 1px, transparent 1px {BG_GRID_MAJOR_SPACING_PX}px),
            repeating-linear-gradient(to right, rgba(255,255,255,{BG_GRID_FINE_OPACITY}) 0 1px, transparent 1px {BG_GRID_FINE_SPACING_PX}px),
            repeating-linear-gradient(to bottom, rgba(255,255,255,{BG_GRID_FINE_OPACITY}) 0 1px, transparent 1px {BG_GRID_FINE_SPACING_PX}px);
        background-size: 100% 100%, 100% 100%, auto, auto, auto, auto;
        background-position: 0 0, 0 0, 0 0, 0 0, 0 0, 0 0;
        background-repeat: no-repeat, no-repeat, repeat, repeat, repeat, repeat;
        background-attachment: fixed, fixed, fixed, fixed, fixed, fixed;
    }}
    /* The single diagonal lime "laser edge" -- a fixed pseudo-element bounded to
       roughly the upper-right quadrant (own box, not a full-page gradient layer)
       so it stays a single accent line, not a wash. Two stacked gradients inside
       it: a wide, low-opacity band for the soft glow and a 2px high-opacity band
       for the sharp edge -- a "blurred parallel line" rather than filter: blur(),
       which keeps this cheap (no blur compositing cost) despite being fixed.
       z-index: -1 keeps it behind every real element in .stApp regardless of
       whether .stApp forms its own stacking context, since the pseudo-element and
       the rest of the app's content share that same context either way -- it can
       never end up in front of text or cards. Bounded to 70vw/58vh and anchored at
       top:0/right:0 (never past the viewport edge), so it cannot introduce a
       horizontal scrollbar the way an oversized or mis-anchored box could. */
    .stApp::before {{
        content: "";
        position: fixed;
        top: 0; right: 0;
        width: 70vw; height: 58vh;
        background-image:
            linear-gradient(-30deg, transparent calc(50% - 16px), rgba(200,241,53,{BG_DIAGONAL_GLOW_OPACITY}) 50%, transparent calc(50% + 16px)),
            linear-gradient(-30deg, transparent calc(50% - 1px), rgba(200,241,53,{BG_DIAGONAL_LINE_OPACITY}) 50%, transparent calc(50% + 1px));
        pointer-events: none;
        z-index: -1;
    }}
    * {{ font-family: {FONT_STACK} !important; }}
    /* Streamlit renders its chevrons/arrows as ligature text in a bundled local icon
       font (data-testid="stIconMaterial") -- the blanket rule above stomps it, which
       makes the icon literally show up as its text name (e.g. "keyboard_double_arrow_right")
       instead of a glyph. Restore it specifically; this attribute selector is more
       specific than the bare "*" above so it wins regardless of source order. */
    [data-testid="stIconMaterial"] {{ font-family: "Material Symbols Rounded" !important; }}

    h1, h2, h3, h4, h5, h6 {{ color: {TEXT_PRIMARY} !important; font-weight: 700; letter-spacing: -0.02em; }}
    p, li, label, span, .stMarkdown {{ color: #D6D8CF !important; }}
    a {{ color: {LIME} !important; }}
    .stCaption, [data-testid="stCaptionContainer"] {{ color: {TEXT_MUTED} !important; }}

    div[data-testid="stMetricValue"] {{ color: {LIME} !important; font-weight: 800; }}
    div[data-testid="stMetricLabel"] {{ color: {TEXT_MUTED} !important; text-transform: uppercase; font-size: 0.72rem !important; letter-spacing: 1px; }}
    div[data-testid="stMetric"] {{ background: {BG_CARD}; border: none; border-radius: 16px; padding: 14px 18px; }}

    .stButton button {{
        background-color: {BG_CARD}; color: {LIME}; border: 1px solid #2A2C24; border-radius: 999px;
        padding: 6px 20px; font-weight: 600; transition: all 0.15s ease;
    }}
    .stButton button:hover {{ background-color: #23251E; border-color: {LIME}; box-shadow: 0 0 16px rgba(200,241,53,0.25); }}

    [data-testid="stExpander"] {{ border: none; background-color: {BG_CARD}; border-radius: 16px; }}
    .stAlert {{ background-color: {BG_CARD} !important; border: 1px solid #2A2C24; border-radius: 14px; }}
    [data-testid="stDataFrame"], [data-testid="stTable"], [data-testid="stDataEditor"] {{ border: none; border-radius: 14px; overflow: hidden; }}
    hr {{ border-color: #23251E; }}
    code {{ color: {LIME} !important; background-color: {BG_CARD} !important; border-radius: 6px; }}
    [data-testid="stSidebar"] {{ background-color: #0B0C09; border-right: 1px solid {BG_CARD}; }}
    [data-testid="stSidebar"] * {{ color: #D6D8CF !important; }}

    div[data-testid="stVerticalBlockBorderWrapper"] {{
        border: none !important; border-left: 4px solid {LIME} !important;
        border-radius: 20px !important; background: {BG_CARD}; padding: 6px 8px;
    }}
    /* Tighten the dead space between steps (~30% less than the prior default gap)
       so the sequence reads as connected sections rather than isolated islands. */
    div[data-testid="stVerticalBlock"] {{ gap: 0.7rem !important; }}

    .stMultiSelect [data-baseweb="tag"] {{ background-color: #23251E !important; border: 1px solid #3A3D33 !important; border-radius: 999px !important; }}
    .stMultiSelect [data-baseweb="tag"] span {{ color: {LIME} !important; }}
    .stSelectbox div[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {{
        background-color: {BG_CARD} !important; border-radius: 12px !important; border: 1px solid #2A2C24 !important; color: {TEXT_PRIMARY} !important;
    }}

    /* Masthead (v2): overline badge -> big two-tone title -> subtitle -> compact
       disclaimer note. Vertically centered against the sparkline column via the
       stHorizontalBlock rule below -- this is the app's only st.columns() call,
       so it's safe to target broadly without affecting anything else. */
    div[data-testid="stHorizontalBlock"] {{ align-items: center; }}

    .masthead-badge {{
        display: inline-flex; align-items: center; gap: 7px;
        border: 1px solid rgba(255,255,255,0.10); border-radius: 999px;
        padding: 4px 12px; margin-bottom: 12px;
        font-size: 0.68rem; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;
        color: {TEXT_MUTED};
    }}
    .masthead-badge-dot {{ width: 6px; height: 6px; border-radius: 50%; background: {LIME}; box-shadow: 0 0 6px rgba(200,241,53,0.7); }}

    .app-title {{
        font-size: clamp(2.2rem, 2.2rem + 2.2vw, 3.8rem); font-weight: 800;
        letter-spacing: -0.02em; line-height: 1.05; margin-bottom: 10px;
    }}
    /* !important on both spans: the blanket "span {{ color: ... !important }}" rule
       above otherwise wins over these despite being more specific -- same fix as
       .hero-number .unit-pct/.unit-suffix and .diag-ok earlier in this file. */
    .app-title .title-plain {{ color: {TEXT_PRIMARY} !important; }}
    .app-title .title-accent {{ color: {LIME} !important; text-shadow: 0 0 18px rgba(200,241,53,0.35); }}

    .app-subtitle {{ color: {TEXT_MUTED}; font-size: 1.15rem; margin-bottom: 10px; }}

    .disclaimer-note {{
        border-left: 3px solid {LIME}; padding: 4px 0 4px 12px;
        font-size: 0.82rem; color: {TEXT_MUTED}; line-height: 1.4; max-width: 46rem;
    }}

    .hero-label {{ color: {TEXT_MUTED}; text-transform: uppercase; letter-spacing: 2px; font-size: 0.78rem; font-weight: 600; }}
    .hero-number {{ color: {LIME}; font-size: 4.4rem; font-weight: 800; line-height: 1.0; margin: 6px 0 20px 0; }}
    /* explicit !important on both spans below: the blanket "span {{ color: ... !important }}"
       rule earlier in this block otherwise wins over an un-marked rule despite these being
       more specific -- !important is compared before specificity, not after. "%" stays the
       same lime as the big numeral (same unit, just a smaller mark); "AI" is the muted
       suffix labeling what the number measures -- two sizes/colors, not three. */
    .hero-number .unit-pct {{ color: {LIME} !important; font-size: 2.6rem; font-weight: 800; }}
    .hero-number .unit-suffix {{ color: {TEXT_MUTED} !important; font-size: 1.9rem; font-weight: 600; margin-left: 6px; }}
    .hero-substats {{ display: flex; gap: 36px; flex-wrap: wrap; }}
    .hero-substat .sub-label {{ color: {TEXT_MUTED}; text-transform: uppercase; letter-spacing: 1px; font-size: 0.68rem; font-weight: 600; }}
    .hero-substat .sub-value {{ color: {TEXT_PRIMARY}; font-size: 1.5rem; font-weight: 700; margin-top: 2px; }}

    .section-label {{ color: {TEXT_MUTED}; text-transform: uppercase; letter-spacing: 2px; font-size: 0.75rem; font-weight: 700; margin: 4px 0 1px 0; }}
    .section-title {{ color: {TEXT_PRIMARY}; font-size: 1.35rem; font-weight: 700; margin-bottom: 7px; }}

    .verdict-text {{ color: {TEXT_PRIMARY}; font-size: 1.08rem; line-height: 1.55; margin: 2px 0 12px 0; }}
    .comparative-line {{ color: {TEXT_MUTED}; font-size: 0.88rem; margin: 0 0 4px 0; }}

    .hero-right-fallback {{ color: {LIME}; font-size: 3rem; font-weight: 800; text-align: center; line-height: 1.0; }}
    .hero-right-fallback-label {{ color: {TEXT_MUTED}; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 1.5px; text-align: center; margin-top: 6px; }}
    .diag-line {{ color: {TEXT_MUTED}; font-size: 0.85rem; }}
    /* same !important-vs-specificity issue as .unit above, plus it's nested inside the
       sidebar's own "[data-testid="stSidebar"] * {{ color: ... !important }}" rule --
       scope + !important so this one reliably wins. */
    [data-testid="stSidebar"] .diag-ok {{ color: {LIME} !important; font-weight: 700; }}
</style>
""", unsafe_allow_html=True)

# Two-column hero: title/subtitle/disclaimer (left) + a live preview of the CURRENT
# result (right), so the very first thing on screen is an insight, not just a form.
# The right column's content depends on the portfolio computation that happens much
# further down the script (after Step 1's form resolves the user's weights) -- an
# st.empty() placeholder reserves this visual position now; it gets filled in later,
# once computed, via the "with hero_right:" block near the Computation section.
# Streamlit renders a placeholder's content at the position it was created, not where
# it was last written to, so this achieves the visual order without recomputing or
# duplicating any of the underlying math.
hero_left, hero_right = st.columns([3, 2])
with hero_left:
    st.markdown(
        '<div class="masthead-badge"><span class="masthead-badge-dot"></span>100-TICKER UNIVERSE</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="app-title"><span class="title-plain">The Portfolio</span> '
        '<span class="title-accent">X-Ray</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="app-subtitle">How much AI is secretly in your portfolio?</div>', unsafe_allow_html=True)
    # Wording unchanged from v1 -- only the container/styling changed (a compact
    # bordered note instead of a full-width st.caption paragraph).
    st.markdown(
        '<div class="disclaimer-note">Every projected number on this page is conditional -- '
        '"if a 2000-style repricing occurred..." -- not a prediction. This app does not claim '
        'a bubble exists or that a crash will happen.</div>',
        unsafe_allow_html=True,
    )
hero_right_placeholder = hero_right.empty()

# --- Gate check: must pass before anything renders ---
prices = load_prices_cached()
try:
    gate_drawdown = fl.gate_check(prices)
except AssertionError as e:
    st.error(f"GATE CHECK FAILED -- refusing to render results.\n\n{e}")
    st.stop()

universe = fl.available_tickers(prices)

# ticker -> category, for the grouped multiselect and the sidebar universe browser
categories = pp.categories_for_app()
category_of = {}
for cat, tickers in categories.items():
    for t in tickers:
        if t in universe:
            category_of.setdefault(t, cat)
for t in universe:
    category_of.setdefault(t, "Other")
sorted_universe = sorted(universe, key=lambda t: (category_of[t], t))


def section_header(number: str, title: str) -> None:
    st.markdown(f'<div class="section-label">STEP {number}</div><div class="section-title">{title}</div>',
                unsafe_allow_html=True)


# ============================================================================
# Sidebar -- diagnostics, quick presets, ticker universe browser
# ============================================================================

with st.sidebar:
    st.markdown("**Diagnostics**")
    st.markdown(
        f'<div class="diag-line">Gate check: <span class="diag-ok">PASS</span></div>'
        f'<div class="diag-line">SPY 2022 drawdown: {gate_drawdown * 100:.2f}%</div>'
        f'<div class="diag-line">Universe: {len(universe)} tickers</div>'
        f'<div class="diag-line">Source: data/prices.db</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    st.markdown("**Quick presets**")
    preset_choice = st.selectbox("Load a preset portfolio", list(PRESETS.keys()), key="preset_select",
                                  label_visibility="collapsed")
    if st.button("Load preset", width="stretch"):
        preset = PRESETS[preset_choice]
        st.session_state["selected_tickers"] = list(preset.keys())
        st.session_state["weight_map"] = dict(preset)
        st.session_state["weight_editor_base_tickers"] = None  # force the weight editor to resync
        st.rerun()

    st.markdown("---")
    st.markdown("**Supported universe**")
    st.caption(f"{len(universe)} tickers cached in data/prices.db -- no live ticker lookup at runtime.")
    with st.expander("Browse by category"):
        for cat, tickers in categories.items():
            present = [t for t in tickers if t in universe]
            if present:
                st.caption(f"**{cat}** ({len(present)}): {', '.join(present)}")

# ============================================================================
# Input
# ============================================================================

section_header("1", "Build your portfolio")

if "selected_tickers" not in st.session_state:
    st.session_state["selected_tickers"] = list(DEFAULT_PORTFOLIO.keys())
if "weight_map" not in st.session_state:
    st.session_state["weight_map"] = dict(DEFAULT_PORTFOLIO)
# The weight editor's OWN stable snapshot of {ticker: weight_pct} -- see the
# st.data_editor call below for why this must be a separate thing from
# weight_map (which tracks live edits for everything else in the app).
if "weight_editor_base_tickers" not in st.session_state:
    st.session_state["weight_editor_base_tickers"] = tuple(st.session_state["selected_tickers"])
    st.session_state["weight_editor_base_weights"] = dict(st.session_state["weight_map"])

with st.container(border=True):
    # Manual-entry fallback runs BEFORE the multiselect widget below is instantiated,
    # so it can still write to st.session_state["selected_tickers"] this same rerun --
    # Streamlit forbids mutating a widget's session_state key after that widget has
    # already been created in the same script run.
    with st.expander("Manual entry (comma-separated tickers) -- fallback"):
        manual_text = st.text_input("e.g. SPY, TLT, NVDA", key="manual_ticker_input", label_visibility="collapsed",
                                     placeholder="e.g. SPY, TLT, NVDA")
        if st.button("Add to portfolio", key="manual_add_btn"):
            candidates = [t.strip().upper() for t in manual_text.split(",") if t.strip()]
            unsupported = [t for t in candidates if t not in universe]
            new_tickers = [t for t in candidates if t in universe and t not in st.session_state["selected_tickers"]]
            if unsupported:
                st.error(f"Not in the supported universe: {', '.join(unsupported)}.")
            if new_tickers:
                st.session_state["selected_tickers"] = st.session_state["selected_tickers"] + new_tickers
                st.rerun()

    selected = st.multiselect(
        "Search & select tickers (grouped by category)",
        options=sorted_universe,
        format_func=lambda t: f"{t} — {category_of[t]}",
        key="selected_tickers",
    )

    # Resync the weight editor's stable snapshot ONLY when the ticker selection
    # actually changed (add/remove/preset/normalize -- the last two force this via
    # the None sentinel below) -- not on every rerun. See the st.data_editor call
    # below for why this matters: rebuilding its `data` from live edits every
    # keystroke was the revert bug.
    current_tickers = tuple(selected)
    if st.session_state["weight_editor_base_tickers"] != current_tickers:
        merged = fl.merge_selected_weights(list(selected), st.session_state["weight_map"])
        st.session_state["weight_map"] = merged
        st.session_state["weight_editor_base_tickers"] = current_tickers
        st.session_state["weight_editor_base_weights"] = dict(merged)

    weights_pct_map = {}
    if selected:
        # ROOT CAUSE of the weight-editor revert bug (diagnosed against Streamlit
        # 1.59's st.elements.widgets.data_editor source): st.data_editor computes
        # its *internal* widget identity via compute_and_register_element_id(...,
        # key_as_main_identity=False, data=arrow_bytes, ...) -- so even with an
        # explicit `key=`, that identity is a hash that includes the CONTENT of
        # `data`. The previous code rebuilt `weight_df` from
        # st.session_state["weight_map"] -- which the same rerun's write-back had
        # just updated -- so every edit changed `data`'s content and therefore the
        # widget's internal id on the NEXT rerun. The frontend's pending edit
        # (tagged with the id from the render it was typed against) then arrived
        # one render behind the server's freshly-recomputed id, so
        # register_widget() found no stored state for the new id and returned an
        # empty diff -- silently dropping that edit and re-displaying the old
        # value. This only bit on the 2nd+ edit in a session (the 1st edit's
        # `data` still matched the initial render's id), matching the reported
        # "sometimes" symptom.
        #
        # Fix: keep `data` byte-identical across reruns unless the ticker
        # selection itself changed (weight_editor_base_weights above, updated
        # only on add/remove/preset/normalize) -- so the widget's id, and thus
        # Streamlit's accumulated edited_rows diff, stays stable across any
        # number of consecutive cell edits. Live edits are read from st.data_editor's
        # *return value* (always correct -- Streamlit reapplies the full diff to
        # `data` before returning it) and written into weight_map for everything
        # else in the app to use; they deliberately do NOT feed back into
        # weight_editor_base_weights, which is what breaks the feedback loop.
        weight_df = pd.DataFrame({
            "ticker": list(selected),
            "weight_pct": [st.session_state["weight_editor_base_weights"].get(t, 0.0) for t in selected],
        })
        edited = st.data_editor(
            weight_df,
            key="weight_editor_widget",
            column_config={
                "ticker": st.column_config.TextColumn("Ticker", disabled=True),
                "weight_pct": st.column_config.NumberColumn("Weight %", format="%.2f"),
            },
            num_rows="fixed",
            hide_index=True,
            width="stretch",
        )
        weights_pct_map = {row["ticker"]: float(row["weight_pct"]) for _, row in edited.iterrows()}
        st.session_state["weight_map"] = dict(weights_pct_map)
        st.caption(
            "Edit a weight and press Enter (or click away) to apply it. Adding a ticker starts it "
            "at 0% -- edit its weight, or use Normalize below once your mix sums to 100%."
        )

    weights, errors, warnings_ = validate_weights(weights_pct_map)

    for w in warnings_:
        st.info(w)

    if errors:
        for e in errors:
            st.error(e)
        total = sum(weights_pct_map.values())
        if total > 0:
            if st.button("Normalize weights to 100%"):
                st.session_state["weight_map"] = {t: w / total * 100.0 for t, w in weights_pct_map.items()}
                st.session_state["weight_editor_base_tickers"] = None  # force the weight editor to resync
                st.rerun()
        st.stop()

# ============================================================================
# Computation -- spinner covers exactly this block. The get_*/load_* calls are
# @st.cache_data, so this is only slow on a cold cache (first load, or a DB
# change); on every later rerun of an already-computed portfolio they return
# instantly and the spinner flashes too briefly to notice, by design -- no
# special "is this cached?" branching needed, that's what st.cache_data gives us.
# ============================================================================

with st.spinner("X-raying your portfolio…"):
    simple_returns = get_simple_returns(prices)
    ai_log = get_ai_log(prices)
    rest_factor_252, ai_756, rest_factor_756 = get_rest_factors(prices)
    ai_shock_no_bubble, rest_shock_no_bubble = get_no_bubble_shocks(prices)
    m2_shocks = get_m2_shocks()
    m1_table = get_m1_table()
    spy_rolling = get_spy_rolling_beta(prices)

    user_simple = fl.build_portfolio_simple_returns(simple_returns, weights)
    user_log = fl.to_log_returns(user_simple)

    overlap = fl.overlapping_obs_count(user_log, ai_log)
    if overlap < fl.MIN_REGRESSION_OBS:
        st.error(
            f"Only {overlap} overlapping trading day(s) between these tickers and the AI basket -- "
            f"not enough to compute a beta. Try a different mix."
        )
        st.stop()

    single = fl.single_factor_regress(user_log, ai_log)
    two_factor = fl.two_factor_regress(user_log, ai_log, rest_factor_252)

    n_obs = single["n_obs"]

    beta_pct = single["beta"] * 100
    r_squared = single["r_squared"]

    # direct weight: see factor_lib.compute_direct_weight_pct for the resolution rules
    # (AI-basket member / named reference portfolio / known-zero bond-commodity fund /
    # genuinely unresolvable). Pulled out of this file so it's unit-testable without
    # Streamlit -- see tests/test_factor_lib.py.
    user_direct_pct, unresolvable = fl.compute_direct_weight_pct(weights)

    proj_no_bubble = fl.project_scenario(two_factor["beta_ai"], two_factor["beta_rest"], ai_shock_no_bubble, rest_shock_no_bubble) * 100
    proj_2022 = fl.project_scenario(two_factor["beta_ai"], two_factor["beta_rest"], m2_shocks["2022_ai_shock"], m2_shocks["2022_rest_shock"]) * 100
    proj_2008 = fl.project_scenario(two_factor["beta_ai"], two_factor["beta_rest"], m2_shocks["gfc_ai_shock"], m2_shocks["gfc_rest_shock"]) * 100
    proj_dotcom = fl.project_scenario(two_factor["beta_ai"], two_factor["beta_rest"], m2_shocks["dotcom_ai_shock"], m2_shocks["dotcom_rest_shock"]) * 100

    # Rolling beta -- computed exactly once here, shared by the hero sparkline (a
    # recent-2-years slice) below and the Step 5 bonus expander (the full series)
    # further down. Not wrapped in @st.cache_data since it depends on the user's
    # arbitrary weights dict; it's a cheap vectorized computation either way.
    user_rolling_full = fl.rolling_beta(user_log, ai_log, fl.WINDOW)

# --- Fill the hero-right placeholder reserved at the top of the page ---
with hero_right_placeholder:
    HERO_SPARKLINE_DAYS = 504  # ~2 trading years
    if user_rolling_full.empty:
        st.markdown(
            f'<div class="hero-right-fallback">{beta_pct:.0f}%</div>'
            f'<div class="hero-right-fallback-label">Effective AI exposure</div>',
            unsafe_allow_html=True,
        )
    else:
        recent = user_rolling_full.tail(HERO_SPARKLINE_DAYS)
        hero_fig = render_hero_sparkline(recent, beta_pct)
        st.plotly_chart(hero_fig, theme=None, width="stretch", config=PLOTLY_CONFIG)

# ============================================================================
# Your allocation -- a donut view of what was just built, sized by weight and
# colored by group (AI basket / no equity exposure / other equity), with the
# already-computed effective AI exposure in the hole. Placed after the
# Computation block (not right after Step 1) specifically so beta_pct is
# available here instead of being recomputed.
# ============================================================================

st.markdown(
    '<div class="section-label">YOUR ALLOCATION</div>'
    '<div class="section-title">Portfolio at a glance</div>',
    unsafe_allow_html=True,
)
with st.container(border=True):
    donut_fig = render_portfolio_donut(weights, beta_pct)
    st.plotly_chart(donut_fig, theme=None, width="stretch", config=PLOTLY_CONFIG)
    st.caption(
        "Segment size = weight in your portfolio. Lime = AI basket member, gray = "
        "bond/Treasury/commodity fund (no equity exposure), sage = other equity -- "
        "shades vary within each group so neighboring segments stay distinct."
    )

# ============================================================================
# Panel 1: Headline (hero card)
# ============================================================================

section_header("2", "Your headline number")

with st.container(border=True):
    # Naive weight shown to 1 decimal (not the headline's rounded whole number) so it
    # can be checked against Module 1's published figures (e.g. 60/40 -> 20.26%) at a
    # glance, without the rounding making an exact match look approximate.
    direct_value_html = f"{user_direct_pct:.1f}%" if user_direct_pct is not None else "N/A"
    st.markdown(
        f'''
        <div class="hero-label">Your portfolio is effectively</div>
        <div class="hero-number">{beta_pct:.0f}<span class="unit-pct">%</span> <span class="unit-suffix">AI</span></div>
        <div class="hero-substats">
          <div class="hero-substat"><div class="sub-label">Naive weight</div><div class="sub-value">{direct_value_html}</div></div>
          <div class="hero-substat"><div class="sub-label">R²</div><div class="sub-value">{r_squared:.2f}</div></div>
          <div class="hero-substat"><div class="sub-label">Trading days used</div><div class="sub-value">{n_obs}</div></div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    ref_betas_pct = {p: m1_table.loc[p, "beta"] * 100 for p in REFERENCE_PORTFOLIOS}
    nearest_name = nearest_reference_portfolio(beta_pct, ref_betas_pct)
    verdict_html = (
        f"Your portfolio behaves like it's {beta_pct:.0f}% AI — closest to <strong>{nearest_name}</strong>. "
        f"If a dot-com-style repricing occurred, that would imply <strong>{proj_dotcom:+.0f}%</strong>; "
        f"if the trend simply continued, <strong>{proj_no_bubble:+.0f}%</strong>."
    )
    st.markdown(f'<div class="verdict-text">{verdict_html}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="comparative-line">{comparative_anchor_line(beta_pct, ref_betas_pct)}</div>',
                unsafe_allow_html=True)

    if user_direct_pct is None:
        st.caption(
            f"Naive direct weight isn't computable for this mix -- {format_ticker_list(unresolvable)} "
            f"{'has' if len(unresolvable) == 1 else 'have'} no known top-10 holdings weight."
        )

    st.caption(
        f"R² of {r_squared:.2f} means the AI basket explains **{r_squared * 100:.0f}%** of your portfolio's "
        f"daily movement -- the remaining **{(1 - r_squared) * 100:.0f}%** is specific to your own holdings, "
        "not captured by this basket."
    )
    if r_squared < 0.3:
        st.caption(
            "Because R² is low here, the exposure % above describes a real but partial relationship -- "
            "most of this portfolio's day-to-day movement isn't AI-basket-driven at all. This is common for "
            "single-stock or narrow portfolios: beta measures the relationship's *slope*, R² measures how much "
            "of the movement that relationship actually accounts for."
        )

    if beta_pct > 100:
        st.warning(
            "Your effective exposure is over 100% -- your portfolio moves even more than the AI basket "
            "itself. This happens when your holdings ARE basket members (more concentrated than the "
            "equal-weighted basket) or otherwise amplify its moves. The 'direct weight %' reading assumes "
            "the non-basket remainder is uncorrelated with AI, which breaks down here -- see LIMITATIONS.md, Module 4."
        )
    elif beta_pct <= 3:
        st.info(
            "A reading at or near zero (including slightly negative) just means near-zero correlation "
            "with the AI basket over the trailing year -- not a deliberate hedge against it."
        )

    if n_obs < fl.WINDOW:
        st.warning(
            f"Only {n_obs} overlapping trading days available for this portfolio (fewer than the "
            f"standard {fl.WINDOW}-day window) -- estimates above are less reliable than for a "
            f"portfolio with full history."
        )

# ============================================================================
# Panel 2: Comparison chart
# ============================================================================

section_header("3", "Where you sit among the standard portfolios")
with st.container(border=True):
    fig2 = render_comparison_chart(m1_table, beta_pct, user_direct_pct)
    st.plotly_chart(fig2, theme=None, width="stretch", config=PLOTLY_CONFIG)
    st.caption("AI basket: NVDA, MSFT, GOOGL, META, AMZN, AAPL, AVGO, TSM (equal-weighted). Your bar in lime.")

# ============================================================================
# Panel 3: Scenario bars
# ============================================================================

section_header("4", "If a repricing happened")
with st.container(border=True):
    m3_table = get_m3_table()
    is_pure_spy = set(weights.keys()) == {"SPY"}
    spy_crash_refs = None if is_pure_spy else {
        "2022": m3_table.loc["SPY", "proj_2022_style_pct"],
        "2008": m3_table.loc["SPY", "proj_2008_style_pct"],
        "dotcom": m3_table.loc["SPY", "proj_dotcom_style_pct"],
    }

    fig3 = render_scenario_chart(proj_no_bubble, proj_2022, proj_2008, proj_dotcom, spy_crash_refs)
    st.plotly_chart(fig3, theme=None, width="stretch", config=PLOTLY_CONFIG)
    st.caption(
        "Linear projection: beta_AI x AI_shock + beta_rest x rest_shock. No alpha/drift term. "
        "Projection, not a forecast. See LIMITATIONS.md."
    )

# ============================================================================
# Panel 4: The menu (tradeoff scatter)
# ============================================================================

section_header("5", "The menu: upside kept vs. downside risked")
with st.container(border=True):
    m3_reference = {
        p: (m3_table.loc[p, "proj_dotcom_style_pct"], m3_table.loc[p, "proj_no_bubble_pct"])
        for p in REFERENCE_PORTFOLIOS
    }

    fig4 = render_tradeoff_chart(m3_reference, proj_dotcom, proj_no_bubble)
    st.plotly_chart(fig4, theme=None, width="stretch", config=PLOTLY_CONFIG)

    st.markdown(
        "*This app does not recommend a weight -- it shows the tradeoff your portfolio implies, "
        "same stance as the rest of this project.*"
    )

# ============================================================================
# Bonus panel: rolling beta through time
# ============================================================================

with st.expander("Bonus: When did your portfolio become an AI fund? (rolling beta through time)"):
    # Reuses user_rolling_full/spy_rolling computed once in the Computation block
    # above (also shared with the hero sparkline) -- not recomputed here.
    if user_rolling_full.empty:
        st.warning("Not enough history for this portfolio to compute a rolling beta series.")
    else:
        fig5 = render_rolling_beta_chart(user_rolling_full, spy_rolling, "Your portfolio")
        st.plotly_chart(fig5, theme=None, width="stretch", config=PLOTLY_CONFIG)
        st.caption("Series starts once all constituents (yours and the AI basket's) have 252 trading days of overlap.")

st.markdown("---")
st.caption(
    f"Demo universe: {len(universe)} tickers cached in data/prices.db. Fixed-weight, daily-rebalanced "
    "portfolio assumption -- ignores real-world drift and trading costs. See LIMITATIONS.md (Module 4) "
    "and outputs/m4_methodology.md for full detail. Every Module 1 and Module 3 limitation applies here too."
)
