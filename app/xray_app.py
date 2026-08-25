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
import time
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
import m1_concentration as m1  # noqa: E402 -- Step 0 reuses CONCENTRATION_HISTORY, not a re-pull

M1_TABLE_PATH = PROJECT_ROOT / "outputs" / "m1_beta_table.csv"
M3_TABLE_PATH = PROJECT_ROOT / "outputs" / "m3_scenario_table.csv"

REFERENCE_PORTFOLIOS = ["QQQ", "SPY", "VT", "60/40", "RSP"]

# --- Tactical-telemetry / x-ray-scan palette (app chrome + in-app charts only --
# see module docstring). v3: replaces v2's dark-fintech lime palette with a
# green-phosphor HUD look -- near-black CRT background, terminal-green primary
# accent, a cyan "scan" secondary for the one series that needs to read as
# distinct from green (the dot-com-style scenario line), amber/red kept as the
# universal caution/danger colors. Zero border-radius anywhere in the CSS below
# is deliberate (see the style block) -- this palette is built for that flat,
# 90-degree-corners HUD-panel look, not the old pill/rounded-corner shapes.
BG_APP = "#0A0D0A"
BG_CARD = "#111712"
GREEN = "#39FF6E"          # primary accent: positive numbers, user's own series, main action
GREEN_DIM = "rgba(57,255,110,0.45)"  # dimmer tint for the user's "direct weight" half-bar
GREEN_BRIGHT = "#8FFFB8"   # hover/pressed state for the primary green CTA
CYAN = "#3EE8FF"           # secondary accent, used sparingly (dot-com-style scenario series)
AMBER = "#E8A93C"          # 2022-style scenario series / caution
NEG_RED = "#FF4433"        # danger / 2008-style scenario series
TEXT_PRIMARY = "#EAF5EC"
TEXT_MUTED = "#6F8C7A"
MUTED_GRAY_1 = "#454B4D"   # reference-portfolio "direct weight" bars -- neutral cool gray
MUTED_GRAY_2 = "#8A9296"   # reference-portfolio dots/lines (tradeoff chart, rolling beta) --
                          # deliberately neutral, not green-tinted, so it doesn't blend into
                          # GREEN/TEAL on the donut and every wheel doesn't read as "all green"
TEAL = "#2FB8D9"           # "other equity" donut group + reference-portfolio "effective exposure"
                          # bars -- a distinct blue-family hue from the primary GREEN (AI basket)
                          # and neutral-gray (bonds/zero-exposure), so the three donut groups read
                          # as three different colors instead of two shades of green plus gray
GRIDLINE = "rgba(111,140,122,0.15)"
FONT_STACK = "'Inter','Space Grotesk','Segoe UI',system-ui,-apple-system,sans-serif"
# Technical/telemetry type -- labels, badges, step numbers, data tables. System-
# local monospace stack only (offline rule, same as FONT_STACK above).
MONO_STACK = "'Cascadia Mono','Consolas','SFMono-Regular','Menlo','Courier New',monospace"
# Panel/chrome tones -- named (not just inlined as hex) so the CSS block below
# reads as "what role does this color play" rather than a wall of hex literals.
TEXT_PRIMARY_DIM = "#D8E6DA"  # body prose color (p/li/label/span) -- a notch dimmer than TEXT_PRIMARY
PANEL_BORDER = "#1C2B20"      # thin border on every flat HUD panel (cards, inputs, alerts)
PANEL_BG_HOVER = "#101A13"    # hover/active fill for panels and secondary buttons
SIDEBAR_BG = "#060A07"

# Backward-compatible aliases -- kept so the rest of this file (chart builders,
# CSS block) can be updated incrementally without one giant simultaneous rename.
LIME = GREEN
LIME_DIM = GREEN_DIM
INDIGO = CYAN

# Page-background "atmosphere" (CSS only -- see the html/body/.stApp rule and the
# .stApp::before diagonal-line rule below). v2: sharper and more designed than the
# original soft-glow version -- a real blueprint/terminal grid with two tiers,
# one focused green glow (harder falloff than before), a vignette, and a single
# diagonal green "laser edge" behind the hero. All values chosen to stay well
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

# Portfolio-donut palette: three GROUPS carry meaning (AI basket / no-equity-
# exposure bond & commodity funds / other equity -- see DONUT_GROUP_LABELS),
# but only "ai" and "zero" need a single consistent hue, since those two are
# flags the reader should recognize at a glance across every wheel in the app.
# "other equity" carries no such flag -- it's just "everything else" -- so it
# cycles through a full categorical rainbow (red/orange/teal/violet/pink/blue)
# instead of shades of one hue, both for real per-ticker legibility on a
# multi-holding wheel and so a page full of wheels doesn't read as monochrome
# green. Cycled per group in the order encountered, not hashed, so shade
# assignment is stable and predictable within one render.
DONUT_LIME_SHADES = ["#39FF6E", "#28C455", "#8CFFB2", "#1C8F3D"]
DONUT_GRAY_SHADES = ["#7C9585", "#526354", "#A6C2AE", "#3A4A3D"]
DONUT_OTHER_SHADES = ["#E8574A", "#FF8A3D", "#2FB8D9", "#8B6FF5", "#F2569E", "#4A90E8"]
DONUT_GROUP_LABELS = {
    "ai": "AI basket member",
    "zero": "No equity exposure (bond/Treasury/commodity)",
    "other": "Other equity",
}
DONUT_LABEL_MIN_PCT = 5.0  # segments below this weight get no outside label, hover only

# Default portfolio shown on first visit -- NOT the research project's textbook
# 60/40 reference portfolio, and not "what everyone holds" either. It's a
# broad-market core (VOO) with a Nasdaq-growth tilt (QQQM) and a couple of
# single-stock adds (NVDA, AAPL, MU) layered on top -- the kind of mix a
# reasonable, still-mostly-passive self-directed investor can end up with one
# ticker at a time, each addition individually defensible, without necessarily
# noticing how far the composition has drifted from the two/three-fund
# textbook version. See the caption at the top of Step 1 for the copy that
# says this explicitly to the user. Defined ONCE here; the multiselect
# default, the weight-editor's starting values, and the matching preset below
# all read from this single dict so they can never drift out of sync. Dict
# order matters -- it's the order tickers appear as multiselect tags and
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
    "A common self-directed mix (default)": dict(DEFAULT_PORTFOLIO),
    "60/40 (SPY/TLT)": {"SPY": 60.0, "TLT": 40.0},
    "100% QQQ (max AI exposure)": {"QQQ": 100.0},
    "100% NVDA (direct AI holding)": {"NVDA": 100.0},
    "Low-AI mix (utilities/staples/REITs/dividend)": {"XLU": 25.0, "XLP": 25.0, "VNQ": 25.0, "SCHD": 25.0},
    "100% RSP (equal-weight S&P)": {"RSP": 100.0},
    "All-weather-ish (SPY/TLT/GLD/VNQ)": {"SPY": 40.0, "TLT": 30.0, "GLD": 15.0, "VNQ": 15.0},
    "100% TSLA (single growth stock)": {"TSLA": 100.0},
    "Crypto-adjacent (COIN/SPY, shorter-history demo)": {"COIN": 60.0, "SPY": 40.0},
}

# Sector preset gallery (v4) -- one-click themed portfolios shown as cards right
# after Step 1's manual builder, before the "Calculate my AI %" button (see the
# render block right after the Computation section below). Every ticker here is
# drawn from the same
# XRAY_UNIVERSE / TICKER_GROUPS mapping that already backs the sidebar's "Browse
# by category" and the Step 1 multiselect (see pull_prices.categories_for_app) --
# no new tickers, no new data pull. Weights are an equal split across each
# sector's tickers (fl.equal_split_weights, the same helper the app already uses
# for "pick a fresh set of tickers from empty" in merge_selected_weights) --
# illustrative, not a real sector-fund methodology; see the caption rendered
# alongside the gallery. "AI Basket" reuses fl.AI_BASKET directly rather than
# repeating the 8 tickers here, so it can never drift from the basket the rest of
# the app measures against. Presets are filtered against the live `universe` at
# render time (a ticker present here could still be missing from a given
# data/prices.db pull), not assumed to always be fully available.
SECTOR_PRESETS = {
    "Healthcare Core": {"tag": "Healthcare", "tickers": ["JNJ", "UNH", "LLY", "PFE"]},
    "Big Bank Financials": {"tag": "Financials", "tickers": ["JPM", "BAC", "V", "MA"]},
    "Consumer Staples": {"tag": "Staples", "tickers": ["WMT", "PG", "KO", "PEP"]},
    "Energy Majors": {"tag": "Energy", "tickers": ["XOM", "CVX", "XLE"]},
    "Industrial Heavyweights": {"tag": "Industrials", "tickers": ["BA", "CAT", "GE"]},
    "Semiconductors": {"tag": "Semis", "tickers": ["MU", "AMD", "QCOM", "INTC"]},
    "Broad Market Baseline": {"tag": "Index", "tickers": ["VOO"]},
    # Not an equal split like the others -- half broad-market core, half a
    # handful of stable/defensive blue chips, the same "core + a few familiar
    # names" shape as this app's own DEFAULT_PORTFOLIO above, just built from
    # defensive names instead of a growth tilt. Weights hardcoded directly
    # (see the setdefault() loop below) rather than via equal_split_weights,
    # since 50% VOO isn't an equal share of 4 tickers.
    "Classic Investor": {
        "tag": "Balanced", "tickers": ["VOO", "JNJ", "PG", "KO"],
        "weights": {"VOO": 50.0, "JNJ": 17.0, "PG": 17.0, "KO": 16.0},
    },
    "AI Basket": {"tag": "AI", "tickers": list(fl.AI_BASKET)},
}
for _preset in SECTOR_PRESETS.values():
    _preset.setdefault("weights", fl.equal_split_weights(_preset["tickers"]))
del _preset


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
def get_ai_log_capweighted(prices: pd.DataFrame) -> pd.Series:
    """Cap-weighted alternative to get_ai_log, for the "Why these 8 tickers?"
    sensitivity check only -- see fl.AI_BASKET_CAP_WEIGHT_PCT. Not used anywhere
    else in the app; the headline number, comparison chart, and scenario
    projections all stay on the equal-weighted basket so they remain comparable
    to the reference portfolios' precomputed (equal-weighted) figures.
    """
    simple_returns = get_simple_returns(prices)
    return fl.to_log_returns(fl.ai_basket_capweighted_simple_returns(simple_returns))


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


# Step 0's proof point (v3): reuses Module 1's own S&P 500 top-10 concentration
# anchor-year history (m1_concentration.CONCENTRATION_HISTORY) instead of a
# DIY price-ratio proxy. Two prior constructions (QQQ beta; AI-basket vs.
# rest-of-QQQ price ratio, in both its 1-share-each and equal-weighted forms)
# were investigated and dropped -- see LIMITATIONS.md -- because a from-price
# proxy kept surfacing either window-choice sensitivity or construction
# artifacts. CONCENTRATION_HISTORY is a real, externally-sourced statistic
# (RBC Wealth Management / press consensus / CryptoBriefing -- see
# m1_concentration.py's own sourcing comment), not something computed here.
@st.cache_data
def get_concentration_history_df() -> pd.DataFrame:
    """Module 1's S&P 500 top-10 concentration anchor years as a DataFrame --
    no new data pull, just reshaping m1.CONCENTRATION_HISTORY for Plotly.
    """
    return pd.DataFrame(m1.CONCENTRATION_HISTORY, columns=["year", "pct", "source"])


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
        errors.append(f"Your weights add up to {total:.2f}%, not 100%.")
        return None, errors, warnings

    return {t: w / 100.0 for t, w in weight_map.items()}, errors, warnings


# ============================================================================
# Shareable-link encoding (polish pass, item 4) -- serializes {ticker: weight_pct}
# into a single URL query param value so a portfolio can be attached to an email/
# LinkedIn message and land the recipient back in this exact state, not just a
# blank app. Deliberately simple (TICKER:WEIGHT pairs, comma-joined) rather than
# base64/JSON -- stays human-readable in the address bar, and Streamlit's own
# st.query_params already handles URL-escaping the joined string on write/read.
# ============================================================================

def encode_portfolio_query(weights_pct_map: dict) -> str:
    return ",".join(f"{ticker}:{weight:.2f}" for ticker, weight in weights_pct_map.items())


def decode_portfolio_query(raw: str) -> dict:
    """Best-effort parse -- a hand-edited or truncated URL degrades to dropping
    the unparseable pair(s) rather than failing the whole link."""
    decoded = {}
    for pair in raw.split(","):
        ticker, _, weight_str = pair.partition(":")
        ticker = ticker.strip().upper()
        if not ticker or not weight_str:
            continue
        try:
            decoded[ticker] = float(weight_str)
        except ValueError:
            continue
    return decoded


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
        font=dict(color=TEXT_MUTED, family=MONO_STACK, size=12),
        margin=dict(t=top_margin, l=56, r=24, b=bottom_margin),
        height=height,
        showlegend=False,
        hoverlabel=dict(bgcolor="#101A13", font_color=TEXT_PRIMARY, font_family=MONO_STACK, bordercolor=LIME),
        xaxis=dict(showgrid=False, zeroline=False, showline=True, linecolor="rgba(154,156,147,0.3)",
                    tickfont=dict(color=TEXT_MUTED), automargin=True),
        yaxis=dict(showgrid=True, gridcolor=GRIDLINE, zeroline=False, showline=False,
                    tickfont=dict(color=TEXT_MUTED)),
    )
    if y_title:
        fig.update_yaxes(title=dict(text=y_title, font=dict(color=TEXT_MUTED, size=11)))
    if x_title:
        fig.update_xaxes(title=dict(text=x_title, font=dict(color=TEXT_MUTED, size=11)))
    return fig


def render_concentration_history_chart(history_df: pd.DataFrame):
    """S&P 500 top-10 concentration, anchor years -- Module 1's Chart 1 data,
    reused directly (get_concentration_history_df), not recomputed. Same
    evenly-spaced categorical x-axis convention as m1_concentration.py's own
    plot_chart1: the gaps between anchor years are uneven (5,5,5,5,5,1), and a
    true year-linear scale would crowd the final two labels illegibly close
    together. Redrawn in this app's dark lime house style instead of the
    published PNG's light-surface palette (see this file's module docstring on
    why the two never need to match), with the same EXPLICIT y-axis range fix
    used by the other Step 0 / Step 3 charts.
    """
    years = history_df["year"].tolist()
    pcts = history_df["pct"].tolist()
    positions = list(range(len(years)))

    y_min, y_max = min(pcts), max(pcts)
    y_pad = (y_max - y_min) * 0.35 or 1.0

    fig = go.Figure()
    fig.add_scatter(
        x=positions, y=pcts, mode="lines+markers+text", text=[f"{p:.0f}%" for p in pcts],
        textposition="top center", textfont=dict(color=TEXT_PRIMARY, size=12),
        line=dict(color=LIME, width=2.5), marker=dict(color=LIME, size=8, line=dict(color=BG_CARD, width=1.5)),
        fill="tozeroy",
        fillgradient=dict(type="vertical", colorscale=[[0, "rgba(57,255,110,0.32)"], [1, "rgba(57,255,110,0)"]]),
        customdata=years, hovertemplate="%{customdata}<br>Top-10 share: %{y:.1f}%<extra></extra>",
    )
    dotcom_idx = years.index(2000)
    fig.add_annotation(x=positions[dotcom_idx], y=pcts[dotcom_idx], text="dot-com peak", showarrow=False,
                        yanchor="top", yshift=-20, font=dict(color=MUTED_GRAY_2, size=11))
    fig.add_annotation(x=positions[-1], y=pcts[-1], text="today", showarrow=False,
                        yanchor="top", yshift=-20, font=dict(color=LIME, size=11))
    _apply_base_layout(fig, y_title="Top-10 share of S&P 500 market cap (%)", height=280)
    fig.update_xaxes(tickmode="array", tickvals=positions, ticktext=[str(y) for y in years])
    fig.update_layout(margin=dict(t=40, l=56, r=24, b=40))
    fig.update_yaxes(range=[y_min - y_pad, y_max + y_pad])
    return fig


def render_realized_return_chart(user_indexed: pd.Series, spy_indexed: pd.Series,
                                  user_return_pct: float, spy_return_pct: float):
    """Cumulative return path over the trailing window, indexed to 100 at the
    window's start -- same convention as m2_replay.py's crash-replay charts,
    built here from compounded SIMPLE returns via factor_lib.indexed_cumulative_returns
    (a synthetic weighted portfolio has no price level of its own to index directly).
    User's line in lime with the house gradient glow-fill; SPY as a muted-gray
    dashed reference line. Both get a direct end-of-line label stating the
    realized % return, not just the indexed value, so the number in the sentence
    above the chart is also readable straight off the line.

    v2: the original fill="tozeroy" forced the y-axis to include 0, which
    squeezed the real ~99-135 index band into a thin strip at the top of the
    chart (the "can barely see the upside" bug) -- a plotly gotcha where a
    tozeroy fill's implicit lower bound of 0 counts toward autorange even though
    no actual data point is anywhere near it. Fixed two ways: the fill now runs
    "tonexty" against an invisible baseline trace pinned at 100 (the window's
    start value) instead of down to zero, so it shades gain/loss *from the
    starting point* rather than from an arbitrary zero; and the y-axis range is
    set explicitly from the real data's own min/max (with a little padding)
    instead of autoranging around whatever the fill happens to touch.
    """
    all_values = list(user_indexed.values) + list(spy_indexed.values) + [100.0]
    y_min, y_max = min(all_values), max(all_values)
    y_pad = (y_max - y_min) * 0.12 or 1.0

    fig = go.Figure()
    fig.add_scatter(
        x=spy_indexed.index, y=spy_indexed.values, mode="lines",
        line=dict(color=MUTED_GRAY_2, width=1.5, dash="dash"),
        hovertemplate="%{x|%Y-%m-%d}<br>SPY: %{y:.1f}<extra></extra>",
    )
    # Invisible baseline at 100 -- exists only so the user's line below can fill
    # "tonexty" against its own starting point instead of tozeroy's implicit 0.
    fig.add_scatter(
        x=user_indexed.index, y=[100.0] * len(user_indexed), mode="lines",
        line=dict(width=0), hoverinfo="skip", showlegend=False,
    )
    fig.add_scatter(
        x=user_indexed.index, y=user_indexed.values, mode="lines",
        line=dict(color=LIME, width=2.5), fill="tonexty",
        fillgradient=dict(type="vertical", colorscale=[[0, "rgba(57,255,110,0.32)"], [1, "rgba(57,255,110,0)"]]),
        hovertemplate="%{x|%Y-%m-%d}<br>Your portfolio: %{y:.1f}<extra></extra>",
    )
    fig.add_annotation(x=user_indexed.index[-1], y=user_indexed.values[-1], text=f"{user_return_pct:+.1f}%",
                        showarrow=False, xanchor="left", xshift=10, font=dict(color=LIME, size=13))
    fig.add_annotation(x=spy_indexed.index[-1], y=spy_indexed.values[-1], text=f"SPY {spy_return_pct:+.1f}%",
                        showarrow=False, xanchor="left", xshift=10, font=dict(color=MUTED_GRAY_2, size=12))
    fig.add_hline(y=100, line_color="rgba(154,156,147,0.35)", line_width=1)
    _apply_base_layout(fig, y_title="Cumulative return (indexed to 100)")
    fig.update_layout(margin=dict(t=36, l=56, r=90, b=48))
    fig.update_yaxes(range=[y_min - y_pad, y_max + y_pad])
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
    effective_colors = [TEAL] * len(names) + [LIME]

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
    read from the same source Step 6 already uses.
    """
    labels = ["No bubble<br>(trend continuation)", "If a 2022-style<br>repricing occurred",
              "If a 2008-style<br>repricing occurred", "If a dot-com-style<br>repricing occurred"]
    values = [no_bubble_pct, style_2022_pct, style_2008_pct, style_dotcom_pct]
    colors = [LIME, AMBER, NEG_RED, INDIGO]
    # Emphasis (not recolor) on the dot-com bar, still the deepest single shock of
    # the three crash scenarios -- a brighter outline on just that bar, none on
    # the others.
    line_colors = ["rgba(0,0,0,0)", "rgba(0,0,0,0)", "rgba(0,0,0,0)", "#3EE8FF"]
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
        # from the same m3_scenario_table.csv Step 6 already uses -- never
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
        textfont=dict(color=LIME, size=13, family=MONO_STACK),
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
        fillgradient=dict(type="vertical", colorscale=[[0, "rgba(57,255,110,0.32)"], [1, "rgba(57,255,110,0)"]]),
        hovertemplate="%{x|%Y-%m-%d}<br>" + user_label + " beta: %{y:.0f}%<extra></extra>",
    )
    fig.add_annotation(x=user_rolling.index[-1], y=user_rolling.values[-1] * 100, text=user_label,
                        showarrow=False, xanchor="left", xshift=10, font=dict(color=LIME, size=12))
    fig.add_annotation(x=spy_rolling.index[-1], y=spy_rolling.values[-1] * 100, text="SPY",
                        showarrow=False, xanchor="left", xshift=10, font=dict(color=MUTED_GRAY_2, size=12))
    _apply_base_layout(fig, y_title="252-day rolling AI beta (%)")
    fig.update_layout(margin=dict(t=36, l=56, r=70, b=48))
    return fig


def _donut_group_for(ticker: str) -> str:
    if ticker in fl.AI_BASKET:
        return "ai"
    if ticker in fl.ZERO_DIRECT_WEIGHT_TICKERS:
        return "zero"
    return "other"


def render_portfolio_donut(weights: dict, beta_pct: float, height: int = 340,
                            number_font_size: int = 26, label_font_size: int = 11, margin: int = 48,
                            reveal: bool = True):
    """Donut (go.Pie, hole=0.55) -- one segment per holding, sized by weight.
    Color signals the GROUP a holding belongs to (AI basket / no equity exposure /
    other equity), with a few shades per group so two same-group segments sitting
    next to each other (e.g. NVDA next to MSFT) still visually separate. The
    donut hole carries the portfolio's already-computed effective AI exposure --
    this chart is placed after the Computation block specifically so that number
    is available here, not recomputed.

    height/number_font_size/label_font_size/margin default to the full-size "Portfolio
    at a glance" rendering; the sector preset gallery cards pass smaller values to reuse
    this exact same component (same color logic, same hover behavior) at card scale
    instead of a second bespoke donut builder.

    reveal=False swaps the hole's "X% AI" annotation for a neutral placeholder --
    used by the sector gallery when it's shown before the user has pressed
    "Calculate my AI %", so picking a card to peek at its composition doesn't
    leak that portfolio's number ahead of the button that promises to reveal it.
    """
    tickers = list(weights.keys())
    weight_pcts = [weights[t] * 100 for t in tickers]

    shade_pools = {"ai": DONUT_LIME_SHADES, "zero": DONUT_GRAY_SHADES, "other": DONUT_OTHER_SHADES}
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
        textfont=dict(color=TEXT_PRIMARY, size=11, family=MONO_STACK),
        customdata=list(zip(tickers, hover_group_labels)),
        hovertemplate="%{customdata[0]}<br>Weight: %{value:.1f}%<br>%{customdata[1]}<extra></extra>",
        showlegend=False,
    ))

    if reveal:
        fig.add_annotation(
            text=f"{beta_pct:.0f}% AI", x=0.5, y=0.56, xref="paper", yref="paper",
            showarrow=False, font=dict(color=LIME, size=number_font_size, family=MONO_STACK),
        )
        fig.add_annotation(
            text="effectively AI", x=0.5, y=0.44, xref="paper", yref="paper",
            showarrow=False, font=dict(color=TEXT_MUTED, size=label_font_size, family=MONO_STACK),
        )
    else:
        fig.add_annotation(
            text="?", x=0.5, y=0.56, xref="paper", yref="paper",
            showarrow=False, font=dict(color=TEXT_MUTED, size=number_font_size, family=MONO_STACK),
        )
        fig.add_annotation(
            text="tap Calculate to reveal", x=0.5, y=0.44, xref="paper", yref="paper",
            showarrow=False, font=dict(color=TEXT_MUTED, size=label_font_size, family=MONO_STACK),
        )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin=dict(t=margin, l=margin, r=margin, b=margin),
        height=height,
        font=dict(family=MONO_STACK, color=TEXT_MUTED),
    )
    return fig


# ============================================================================
# Copy-generation helpers -- plain-language sentences built ONLY from values
# already computed elsewhere (m1_table betas, the user's own beta/scenario
# numbers). No new math, just phrasing.
# ============================================================================

# Risk-flag band for the headline number's badge -- thresholds are a disclosed,
# arbitrary convention (~25% / ~50%), not a claim backed by an external benchmark
# figure (no defensible, sourced comparison number -- e.g. a real Nasdaq 100 AI
# weighting -- was available to cite here; see the polish-pass notes on why this
# app doesn't fabricate one). Banded on the raw signed value, not its magnitude:
# a negative or near-zero beta genuinely means low/no measured AI co-movement,
# so it belongs in the same "LOW" band as a small positive one, not its own case.
AI_RISK_BAND_MODERATE_FLOOR = 25.0
AI_RISK_BAND_HIGH_FLOOR = 50.0


def ai_risk_band(beta_pct: float) -> tuple:
    """(band_label, css_class, color, one_line_caption) for the badge next to the
    headline AI% number. Pure function of beta_pct -- no new computation."""
    if beta_pct < AI_RISK_BAND_MODERATE_FLOOR:
        return ("LOW", "low", LIME,
                f"Below {AI_RISK_BAND_MODERATE_FLOOR:.0f}%: this portfolio's daily moves are only "
                "lightly tied to the AI basket.")
    if beta_pct < AI_RISK_BAND_HIGH_FLOOR:
        return ("MODERATE", "moderate", AMBER,
                f"{AI_RISK_BAND_MODERATE_FLOOR:.0f}-{AI_RISK_BAND_HIGH_FLOOR:.0f}%: a meaningful share "
                "of this portfolio's moves now track the AI basket.")
    return ("HIGH", "high", NEG_RED,
            f"Above {AI_RISK_BAND_HIGH_FLOOR:.0f}%: this portfolio behaves more like a concentrated "
            "AI bet than a diversified fund.")


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
        return f"more AI than a {below_name} ({below[below_name]:.0f}%) but less than {above_name} ({above[above_name]:.0f}%)"
    if not below:
        lowest_name = min(ref_betas_pct, key=ref_betas_pct.get)
        return f"less AI than every standard portfolio tested here (the lowest, {lowest_name}, sits at {ref_betas_pct[lowest_name]:.0f}%)"
    highest_name = max(ref_betas_pct, key=ref_betas_pct.get)
    return f"more AI than even {highest_name}, which sits at {ref_betas_pct[highest_name]:.0f}%"


# ============================================================================
# Page shell -- dark fintech theme. See module docstring: v2 restyles the
# in-app charts too (Plotly, dark), a deliberate departure from v1's "app
# chrome only" convention. Published research PNGs are untouched.
# ============================================================================

st.set_page_config(page_title="The Portfolio X-Ray", page_icon="\U0001fa7b", layout="wide")

st.markdown(f"""
<style>
    /* Offline-only: no external font/asset requests (golden rule 2 -- app must run
       fully offline from a clean clone). System-local fonts only: FONT_STACK for
       macro typography (titles, section headers, body prose) and MONO_STACK for
       micro/telemetry typography (labels, badges, data readouts) -- see the
       "Tactical Telemetry" design system this v3 pass switched to (module-level
       palette comment above). Heavy-sans-vs-monospace IS the intended contrast;
       monospace is deliberately NOT applied to prose/captions, only to short
       labels and numbers, so long explanatory text stays readable.
       Zero border-radius everywhere below is deliberate too, not an oversight --
       this is a flat, 90-degree-corner HUD-panel look, not the old pill shapes. */
    html, body, .stApp {{
        background-color: {BG_APP}; color: {TEXT_PRIMARY};
        background-image:
            radial-gradient(ellipse 70% 65% at 50% 50%, transparent 55%, rgba(0,0,0,{BG_VIGNETTE_OPACITY}) 100%),
            radial-gradient(circle at 100% 0%, rgba(57,255,110,{BG_GLOW_LIME_OPACITY}) 0%, rgba(57,255,110,0) {BG_GLOW_LIME_RADIUS_PCT}%),
            radial-gradient(circle at 0% 100%, rgba(62,232,255,0.06) 0%, rgba(62,232,255,0) 34%),
            repeating-linear-gradient(to right, rgba(255,255,255,{BG_GRID_MAJOR_OPACITY}) 0 1px, transparent 1px {BG_GRID_MAJOR_SPACING_PX}px),
            repeating-linear-gradient(to bottom, rgba(255,255,255,{BG_GRID_MAJOR_OPACITY}) 0 1px, transparent 1px {BG_GRID_MAJOR_SPACING_PX}px),
            repeating-linear-gradient(to right, rgba(255,255,255,{BG_GRID_FINE_OPACITY}) 0 1px, transparent 1px {BG_GRID_FINE_SPACING_PX}px),
            repeating-linear-gradient(to bottom, rgba(255,255,255,{BG_GRID_FINE_OPACITY}) 0 1px, transparent 1px {BG_GRID_FINE_SPACING_PX}px),
            url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch' result='t'/%3E%3CfeColorMatrix in='t' type='matrix' values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.05 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
        background-size: 100% 100%, 100% 100%, 100% 100%, auto, auto, auto, auto, 120px 120px;
        background-position: 0 0, 0 0, 0 0, 0 0, 0 0, 0 0, 0 0, 0 0;
        background-repeat: no-repeat, no-repeat, no-repeat, repeat, repeat, repeat, repeat, repeat;
        background-attachment: fixed, fixed, fixed, fixed, fixed, fixed, fixed, fixed;
    }}
    /* The diagonal green "laser edge" -- unchanged mechanism from v2 (fixed
       pseudo-element bounded to the upper-right quadrant), just recolored. See
       the historical comment this replaced for why it's built this way (bounded
       box + two stacked gradients instead of filter: blur(), z-index: -1). */
    .stApp::before {{
        content: "";
        position: fixed;
        top: 0; right: 0;
        width: 70vw; height: 58vh;
        background-image:
            linear-gradient(-30deg, transparent calc(50% - 16px), rgba(57,255,110,{BG_DIAGONAL_GLOW_OPACITY}) 50%, transparent calc(50% + 16px)),
            linear-gradient(-30deg, transparent calc(50% - 1px), rgba(57,255,110,{BG_DIAGONAL_LINE_OPACITY}) 50%, transparent calc(50% + 1px));
        pointer-events: none;
        z-index: -1;
    }}
    /* CRT/x-ray scanline texture (v3, new) -- a full-viewport, fixed, very-low-
       opacity repeating horizontal-line layer, the classic "phosphor scan" cue.
       Cheap: no blur, no per-frame JS, just a slow background-position drift via
       the scanlineDrift keyframe below so it reads as faintly alive rather than
       static wallpaper. z-index: -1, same stacking-context reasoning as
       .stApp::before -- always behind real content, never in front of a card. */
    .stApp::after {{
        content: "";
        position: fixed;
        inset: 0;
        background-image: repeating-linear-gradient(
            0deg,
            rgba(57,255,110,0.05) 0px,
            rgba(57,255,110,0.05) 1px,
            transparent 1px,
            transparent 3px
        );
        pointer-events: none;
        z-index: -1;
        animation: scanlineDrift 9s ease-in-out infinite alternate;
    }}
    @keyframes scanlineDrift {{
        from {{ background-position-y: 0px; }}
        to {{ background-position-y: 6px; }}
    }}

    /* Fixed viewport-corner HUD tags (v3.3, new) -- small persistent chrome
       around the page edges, the last bit of "more cyberpunk background"
       texture beyond the grid/glow/scanline/noise layers above. position:
       fixed so they hold their corner regardless of scroll, like a HUD
       frame; pointer-events: none so they're purely decorative and never
       intercept a click meant for the real content scrolling underneath
       them. Deliberately avoids the top-right corner -- that's Streamlit's
       own Deploy/menu chrome, not ours to cover. z-index set very high
       (Streamlit's own sidebar/header chrome otherwise paints over a fixed
       element at a "normal" z-index, since those establish their own
       stacking context) -- pointer-events: none means going this high can
       never accidentally block a real click, so there's no real downside
       to clearing every other layer this way. */
    .hud-corner-tag {{
        position: fixed; z-index: 999999; pointer-events: none;
        display: inline-flex; align-items: center; gap: 6px;
        border: 1px solid {PANEL_BORDER}; background: rgba(10,13,10,0.55);
        padding: 4px 10px; font-family: {MONO_STACK} !important; font-size: 0.68rem;
        letter-spacing: 1px; text-transform: uppercase; color: {TEXT_MUTED};
    }}
    .hud-corner-tl {{ top: 58px; left: 12px; }}
    .hud-corner-bl {{ bottom: 12px; left: 12px; }}
    .hud-corner-br {{ bottom: 12px; right: 12px; }}
    .hud-corner-tag .pulse-dot {{
        width: 6px; height: 6px; background: {LIME};
        box-shadow: 0 0 6px rgba(57,255,110,0.8);
        animation: hudPulse 1.8s ease-in-out infinite;
    }}
    @keyframes hudPulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.25; }}
    }}
    * {{ font-family: {FONT_STACK} !important; }}
    /* Streamlit renders its chevrons/arrows as ligature text in a bundled local icon
       font (data-testid="stIconMaterial") -- the blanket rule above stomps it, which
       makes the icon literally show up as its text name (e.g. "keyboard_double_arrow_right")
       instead of a glyph. Restore it specifically; this attribute selector is more
       specific than the bare "*" above so it wins regardless of source order. */
    [data-testid="stIconMaterial"] {{ font-family: "Material Symbols Rounded" !important; }}

    h1, h2, h3, h4, h5, h6 {{ color: {TEXT_PRIMARY} !important; font-weight: 700; letter-spacing: -0.02em; }}
    p, li, label, span, .stMarkdown {{ color: {TEXT_PRIMARY_DIM} !important; }}
    a {{ color: {LIME} !important; }}
    .stCaption, [data-testid="stCaptionContainer"] {{ color: {TEXT_MUTED} !important; }}

    div[data-testid="stMetricValue"] {{ color: {LIME} !important; font-weight: 800; font-family: {MONO_STACK} !important; font-variant-numeric: tabular-nums; }}
    div[data-testid="stMetricLabel"] {{ color: {TEXT_MUTED} !important; text-transform: uppercase; font-size: 0.72rem !important; letter-spacing: 1px; font-family: {MONO_STACK} !important; }}
    div[data-testid="stMetric"] {{ background: {BG_CARD}; border: 1px solid {PANEL_BORDER}; border-radius: 0; padding: 14px 18px; }}

    /* Secondary/utility buttons -- flat panel look (zero radius, thin border),
       monospace + uppercase label, bracketed like a terminal menu option
       ("[ + ADD ]") via ::before/::after content on the <button> itself, so no
       Python call site needs to change its label text. */
    .stButton button {{
        background-color: {BG_CARD}; color: {LIME}; border: 1px solid {PANEL_BORDER}; border-radius: 0;
        padding: 6px 20px; font-weight: 600; font-family: {MONO_STACK} !important;
        text-transform: uppercase; letter-spacing: 0.6px; transition: all 0.15s ease;
    }}
    .stButton button::before {{ content: "[ "; opacity: 0.65; }}
    .stButton button::after {{ content: " ]"; opacity: 0.65; }}
    .stButton button:hover {{ background-color: {PANEL_BG_HOVER}; border-color: {LIME}; box-shadow: 0 0 16px rgba(57,255,110,0.25); }}

    /* Shared "primary CTA" button style -- one rule block, applied to every
       key that needs the loud treatment (solid green fill, near-black text,
       large, centered) instead of the muted outline every other .stButton uses.
       Currently: Step 0's continue button, the "Calculate my AI %" button
       (gates Step 2/4), and the "Run repricing simulation" button (gates
       Step 5/6) -- same class, same rules, just a different label text and
       session_state key at each call site. Add a new key to this selector
       list rather than writing a new rule block if a fourth CTA button is
       ever needed. Prefixed ">>> " instead of the secondary buttons' "[ ]"
       brackets -- a forward/action marker for "the next step", vs. the
       brackets' "pick one of these" framing on ordinary controls. */
    /* width:fit-content + margin:auto (not display:flex + width:100%) --
       forcing the element-container to width:100% made the button itself
       stretch to fill it (Streamlit sizes a plain st.button to 100% of its
       own wrapper), which is why the button rendered edge-to-edge instead of
       "slightly bigger, centered". Staying shrink-to-content and centering
       the whole box with margin:auto keeps the button its own natural size. */
    .st-key-step0_continue, .st-key-calc_ai_pct, .st-key-run_repricing_sim {{
        width: fit-content; margin: 6px auto 0 auto;
    }}
    .st-key-step0_continue button, .st-key-calc_ai_pct button, .st-key-run_repricing_sim button {{
        background-color: {LIME} !important; color: {BG_APP} !important;
        border: none !important; border-radius: 0;
        padding: 16px 44px !important; font-size: 1.25rem; font-weight: 700;
        font-family: {MONO_STACK} !important; text-transform: uppercase; letter-spacing: 1px;
        box-shadow: 0 0 22px rgba(57,255,110,0.4);
    }}
    .st-key-step0_continue button::before, .st-key-calc_ai_pct button::before, .st-key-run_repricing_sim button::before {{ content: ">>> "; opacity: 1; }}
    .st-key-step0_continue button::after, .st-key-calc_ai_pct button::after, .st-key-run_repricing_sim button::after {{ content: ""; }}
    .st-key-step0_continue button:hover, .st-key-calc_ai_pct button:hover, .st-key-run_repricing_sim button:hover {{
        background-color: {GREEN_BRIGHT} !important; box-shadow: 0 0 30px rgba(57,255,110,0.6);
    }}
    .st-key-step0_continue button p, .st-key-calc_ai_pct button p, .st-key-run_repricing_sim button p {{
        color: {BG_APP} !important; font-size: 1.25rem; font-weight: 700; font-family: {MONO_STACK} !important;
    }}

    [data-testid="stExpander"] {{ border: 1px solid {PANEL_BORDER}; background-color: {BG_CARD}; border-radius: 0; }}

    /* Sector-gallery expander -- same green CTA family as the Calculate/Run
       buttons above (scoped to this one expander via its key), just a
       smaller tag since it's a secondary, optional path rather than the
       main flow. The clickable region is the <summary>, not the whole
       expander shell, so the CTA look only applies there. */
    .st-key-sector_gallery_expander [data-testid="stExpander"] {{
        background-color: transparent; border: none;
    }}
    .st-key-sector_gallery_expander summary,
    .st-key-repricing_gallery_expander summary {{
        background-color: {LIME} !important; border-radius: 0 !important;
        padding: 8px 18px !important; box-shadow: 0 0 14px rgba(57,255,110,0.35);
        display: inline-flex !important; width: fit-content !important; margin: 0 auto !important;
        font-family: {MONO_STACK} !important;
    }}
    .st-key-sector_gallery_expander summary::before, .st-key-repricing_gallery_expander summary::before {{ content: ">>> "; }}
    .st-key-sector_gallery_expander summary:hover,
    .st-key-repricing_gallery_expander summary:hover {{
        background-color: {GREEN_BRIGHT} !important; box-shadow: 0 0 20px rgba(57,255,110,0.5);
    }}
    .st-key-sector_gallery_expander summary p,
    .st-key-repricing_gallery_expander summary p {{
        color: {BG_APP} !important; font-weight: 700; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.6px;
    }}
    .st-key-sector_gallery_expander summary [data-testid="stIconMaterial"],
    .st-key-repricing_gallery_expander summary [data-testid="stIconMaterial"] {{
        color: {BG_APP} !important;
    }}
    .st-key-repricing_gallery_expander [data-testid="stExpander"] {{
        background-color: transparent; border: none;
    }}

    /* Sector-preset dropdowns -- a green outline so they visually read as an
       interactive control instead of a flat label (otherwise looks like
       plain text with no obvious affordance to open more options). */
    .st-key-sector_preset_pick [data-testid="stSelectbox"] [role="group"],
    .st-key-repricing_preset_pick [data-testid="stSelectbox"] [role="group"] {{
        border: 2px solid {LIME} !important; border-radius: 0 !important;
        box-shadow: 0 0 10px rgba(57,255,110,0.25);
    }}
    .stAlert {{ background-color: {BG_CARD} !important; border: 1px solid {PANEL_BORDER}; border-radius: 0; }}
    [data-testid="stDataFrame"], [data-testid="stTable"], [data-testid="stDataEditor"] {{ border: 1px solid {PANEL_BORDER}; border-radius: 0; overflow: hidden; }}
    hr {{ border-color: {PANEL_BG_HOVER}; }}
    code {{ color: {LIME} !important; background-color: {BG_CARD} !important; border-radius: 0; font-family: {MONO_STACK} !important; }}
    [data-testid="stSidebar"] {{ background-color: {SIDEBAR_BG}; border-right: 1px solid {PANEL_BORDER}; }}
    [data-testid="stSidebar"] * {{ color: {TEXT_PRIMARY_DIM} !important; }}

    /* HUD panel frame -- every st.container(border=True) in the app (step
       boxes, the donut card, sector/side-by-side cards, the hero card) goes
       through this one selector, so one change here restyles all of them.
       Flat panel (zero radius, thin all-round border, no more left-accent-bar
       convention) with a two-corner bracket frame layered on via ::before/
       ::after -- the same "targeting reticle corner" language as the
       reference screenshots this redesign is modeled on. position: relative
       is required so the absolutely-positioned corner brackets anchor to
       this box instead of the page. */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        position: relative;
        border: 1px solid {PANEL_BORDER} !important;
        border-radius: 0 !important; background: {BG_CARD}; padding: 10px 14px;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]::before,
    div[data-testid="stVerticalBlockBorderWrapper"]::after {{
        content: ""; position: absolute; width: 16px; height: 16px; pointer-events: none;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]::before {{
        top: -1px; left: -1px; border-top: 2px solid {LIME}; border-left: 2px solid {LIME};
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]::after {{
        bottom: -1px; right: -1px; border-bottom: 2px solid {LIME}; border-right: 2px solid {LIME};
    }}
    /* Tighten the dead space between steps (~30% less than the prior default gap)
       so the sequence reads as connected sections rather than isolated islands. */
    div[data-testid="stVerticalBlock"] {{ gap: 0.7rem !important; }}

    .stMultiSelect [data-baseweb="tag"] {{ background-color: {PANEL_BG_HOVER} !important; border: 1px solid {PANEL_BORDER} !important; border-radius: 0 !important; }}
    .stMultiSelect [data-baseweb="tag"] span {{ color: {LIME} !important; }}
    .stSelectbox div[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {{
        background-color: {BG_CARD} !important; border-radius: 0 !important; border: 1px solid {PANEL_BORDER} !important; color: {TEXT_PRIMARY} !important;
        font-family: {MONO_STACK} !important;
    }}

    /* Masthead (v3 lime -> v3.1 green/HUD): overline badge -> big two-tone
       title -> subtitle -> compact disclaimer note, centered as a single
       block in the middle of the page. */
    .masthead-center {{ text-align: center; }}

    .masthead-badge {{
        display: inline-flex; align-items: center; gap: 7px;
        border: 1px solid {PANEL_BORDER}; border-radius: 0;
        padding: 4px 12px; margin-bottom: 12px;
        font-size: 0.68rem; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;
        color: {TEXT_MUTED}; font-family: {MONO_STACK} !important;
    }}
    .masthead-badge::before {{ content: "[ "; }}
    .masthead-badge::after {{ content: " ]"; }}
    .masthead-badge-dot {{
        width: 6px; height: 6px; border-radius: 0; background: {LIME};
        box-shadow: 0 0 6px rgba(57,255,110,0.7); transform: rotate(45deg);
    }}

    .app-title {{
        font-size: clamp(2.2rem, 2.2rem + 2.2vw, 3.8rem); font-weight: 800;
        letter-spacing: -0.03em; line-height: 1.05; margin-bottom: 10px;
        text-align: center; text-transform: uppercase;
    }}
    /* !important on both spans: the blanket "span {{ color: ... !important }}" rule
       above otherwise wins over these despite being more specific -- same fix as
       .hero-number .unit-pct/.unit-suffix and .diag-ok earlier in this file. */
    .app-title .title-plain {{ color: {TEXT_PRIMARY} !important; }}
    .app-title .title-accent {{ color: {LIME} !important; text-shadow: 0 0 18px rgba(57,255,110,0.35); }}

    .app-subtitle {{ color: {TEXT_MUTED}; font-size: 1.15rem; margin-bottom: 10px; text-align: center; }}

    /* Byline (polish pass, item 6) -- the same "Built by..." credit as the
       persistent footer (see .app-footer below), just also surfaced here so a
       visitor who never scrolls to the bottom still sees it. Small and muted on
       purpose -- a name/link line, not a second subtitle competing with the
       actual hero copy above it. Footer stays as-is; this is additive. */
    .hero-byline {{ text-align: center; color: {TEXT_MUTED}; font-size: 0.82rem; margin: -6px 0 14px 0; }}
    .hero-byline a {{ font-weight: 600; }}
    .hero-byline .byline-sep {{ margin: 0 6px; opacity: 0.5; }}

    /* Block itself centered (margin: auto within its max-width); the note's
       own text stays left-aligned inside that centered box -- a left-border
       "callout" reads oddly with centered paragraph text, and the title/
       subtitle above it are already what carries the centering. */
    .disclaimer-note {{
        border-left: 3px solid {LIME}; padding: 4px 0 4px 12px;
        font-size: 0.82rem; color: {TEXT_MUTED}; line-height: 1.4;
        max-width: 46rem; margin: 0 auto;
    }}

    .hero-label {{ color: {TEXT_MUTED}; text-transform: uppercase; letter-spacing: 2px; font-size: 0.78rem; font-weight: 600; font-family: {MONO_STACK} !important; }}
    .hero-label::before {{ content: "// "; }}
    .hero-number {{ color: {LIME}; font-size: 4.4rem; font-weight: 800; line-height: 1.0; margin: 6px 0 10px 0; font-family: {MONO_STACK} !important; font-variant-numeric: tabular-nums; }}
    /* explicit !important on both spans below: the blanket "span {{ color: ... !important }}"
       rule earlier in this block otherwise wins over an un-marked rule despite these being
       more specific -- !important is compared before specificity, not after. "%" stays the
       same green as the big numeral (same unit, just a smaller mark); "AI" is the muted
       suffix labeling what the number measures -- two sizes/colors, not three. */
    .hero-number .unit-pct {{ color: {LIME} !important; font-size: 2.6rem; font-weight: 800; }}
    .hero-number .unit-suffix {{ color: {TEXT_MUTED} !important; font-size: 1.9rem; font-weight: 600; margin-left: 6px; }}
    /* Risk-flag badge (polish pass, item 1) -- sits beside the headline number,
       one glance "so what" before the reader has to parse the verdict paragraph
       below. vertical-align + explicit smaller font-size pull it out of the
       4.4rem/line-height:1.0 numeral it's nested inside; !important on color for
       the same span-selector-precedence reason as unit-pct/unit-suffix above.
       Background is the same color at low opacity, not a solid fill -- a solid
       red/amber fill this large would read as an alarm/error state, which this
       app deliberately avoids (see the module docstring: never claim a crash). */
    .risk-badge {{
        display: inline-flex; align-items: center; vertical-align: middle;
        border-radius: 0; padding: 5px 14px; margin-left: 16px;
        font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px;
        font-family: {MONO_STACK} !important;
    }}
    .risk-badge::before {{ content: "[ "; }}
    .risk-badge::after {{ content: " ]"; }}
    .risk-badge-low {{ background: rgba(57,255,110,0.14); color: {LIME} !important; border: 1px solid rgba(57,255,110,0.4); }}
    .risk-badge-moderate {{ background: rgba(232,169,60,0.14); color: {AMBER} !important; border: 1px solid rgba(232,169,60,0.4); }}
    .risk-badge-high {{ background: rgba(255,68,51,0.14); color: {NEG_RED} !important; border: 1px solid rgba(255,68,51,0.4); }}
    .risk-caption {{ color: {TEXT_MUTED}; font-size: 0.85rem; margin: 0 0 18px 0; }}
    .hero-substats {{ display: flex; gap: 36px; flex-wrap: wrap; }}
    .hero-substat .sub-label {{ color: {TEXT_MUTED}; text-transform: uppercase; letter-spacing: 1px; font-size: 0.68rem; font-weight: 600; font-family: {MONO_STACK} !important; }}
    .hero-substat .sub-value {{ color: {TEXT_PRIMARY}; font-size: 1.5rem; font-weight: 700; margin-top: 2px; font-family: {MONO_STACK} !important; font-variant-numeric: tabular-nums; }}

    .section-label {{ color: {TEXT_MUTED}; text-transform: uppercase; letter-spacing: 2px; font-size: 0.75rem; font-weight: 700; margin: 4px 0 1px 0; font-family: {MONO_STACK} !important; }}
    .section-label::before {{ content: "// "; }}
    .section-title {{ color: {TEXT_PRIMARY}; font-size: 1.35rem; font-weight: 700; margin-bottom: 7px; }}

    .verdict-text {{ color: {TEXT_PRIMARY}; font-size: 1.08rem; line-height: 1.55; margin: 2px 0 12px 0; }}
    .comparative-line {{ color: {TEXT_MUTED}; font-size: 0.88rem; margin: 0 0 4px 0; }}

    .diag-line {{ color: {TEXT_MUTED}; font-size: 0.85rem; font-family: {MONO_STACK} !important; }}
    /* One-line plain-language gloss under "Gate check: PASS" (polish pass, item
       3) -- so it reads as a verified data-quality check instead of leftover
       debug output. Smaller and dimmer than the diag-line it sits under; kept
       as its own class rather than reusing .diag-line so it stays visually
       secondary to the PASS/FAIL line itself. */
    .diag-subcaption {{ color: {TEXT_MUTED}; font-size: 0.75rem; opacity: 0.8; margin: -1px 0 6px 0; }}
    /* same !important-vs-specificity issue as .unit above, plus it's nested inside the
       sidebar's own "[data-testid="stSidebar"] * {{ color: ... !important }}" rule --
       scope + !important so this one reliably wins. */
    [data-testid="stSidebar"] .diag-ok {{ color: {LIME} !important; font-weight: 700; }}

    /* Progressive step-reveal (v3) -- fade + slight upward slide, ~380ms ease-out.
       Scoped per-render to a single step's st.container(key=...) via its
       auto-generated .st-key-<key> class -- see animate_container() below --
       so a step only plays this once, on the run it actually unlocks, never on
       a later rerun (e.g. re-editing Step 1's weights after Step 2+ are already
       visible). Kept subtle on purpose: this is a finance tool, not a game. */
    @keyframes stepFadeIn {{
        from {{ opacity: 0; transform: translateY(16px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    /* Slim, non-clickable "how far did I get" indicator -- see render_progress_dots().
       Squares, not circles (zero-radius rule), each rotated 45deg into a small
       diamond "reticle" mark, same shape language as .masthead-badge-dot. */
    .progress-dots {{ display: flex; gap: 8px; align-items: center; margin: 2px 0 22px 0; }}
    .progress-dot {{
        width: 6px; height: 6px; background: rgba(255,255,255,0.14); transform: rotate(45deg);
        transition: background 0.35s ease, box-shadow 0.35s ease;
    }}
    .progress-dot.is-unlocked {{ background: {LIME}; box-shadow: 0 0 6px rgba(57,255,110,0.55); }}

    /* Persistent footer watermark -- deliberately quiet: small, muted, centered,
       plenty of top margin so it reads as a signature line, not another panel.
       Plain text (no <a>) so it doesn't pick up the site-wide green link color
       and start competing visually with the real content above it. */
    .app-footer {{
        text-align: center; color: {TEXT_MUTED}; font-size: 0.72rem;
        opacity: 0.75; margin: 56px 0 8px 0; font-family: {MONO_STACK} !important;
    }}

    /* Skeletal x-ray glyph (v3.1, new) -- a small hand-drawn-in-SVG figure
       above the masthead badge, the one purely decorative nod to "x-ray" as
       imagery rather than just a color scheme. Kept abstract/schematic (a
       fishbone ribcage, not anatomically literal) so it reads clearly at
       small size instead of turning to mush. The ::after sweep is a thin
       glowing bar translating top-to-bottom on a loop -- "actively scanning"
       -- confined to this one small element so it stays a flourish, not a
       page-wide distraction in a finance tool. */
    .xray-glyph-wrap {{
        position: relative; width: 108px; margin: 0 auto 10px auto;
        filter: drop-shadow(0 0 10px rgba(57,255,110,0.35));
    }}
    .xray-glyph-wrap svg {{ display: block; width: 100%; height: auto; }}
    .xray-glyph-wrap::after {{
        content: ""; position: absolute; left: 4%; right: 4%; height: 2px; top: 6%;
        background: linear-gradient(90deg, transparent, {LIME}, transparent);
        box-shadow: 0 0 8px rgba(57,255,110,0.8); pointer-events: none;
        animation: xraySweep 3.4s ease-in-out infinite;
    }}
    @keyframes xraySweep {{
        0% {{ top: 4%; opacity: 0; }}
        12% {{ opacity: 1; }}
        88% {{ opacity: 1; }}
        100% {{ top: 92%; opacity: 0; }}
    }}
</style>
""", unsafe_allow_html=True)

# Fixed corner HUD tags -- see the .hud-corner-tag CSS comment above for why
# these are position: fixed + pointer-events: none. Top-left and bottom-left
# need no runtime data so they render here, right after the stylesheet;
# bottom-right (ticker universe count) renders later, right after `universe`
# is computed, so it can show a real number instead of a placeholder.
st.markdown(
    '<div class="hud-corner-tag hud-corner-tl">X-RAY.SYS</div>'
    '<div class="hud-corner-tag hud-corner-bl"><span class="pulse-dot"></span>LIVE</div>',
    unsafe_allow_html=True,
)

# Centered hero: badge -> two-tone title -> subtitle -> disclaimer, full width
# and center-aligned (see the .masthead-center/.app-title/.app-subtitle CSS
# above). v3 dropped the live sparkline preview that used to sit beside/below
# this text -- at full page width it rendered oversized (830x160, vs. the
# ~330px-wide column it was designed for) and visually dominated the hero
# instead of reading as a small supporting preview. The same rolling-beta
# series is still shown full-size in the "Bonus" expander near the end of the
# page (see the Computation block's user_rolling_full, reused there).
# Portfolio-glyph x-ray -- pure decoration, see the .xray-glyph-wrap CSS
# comment above for the scan-sweep mechanism. A quartered "portfolio dial"
# (mini bar chart / trend arrow / percent / dollar coin, one per quadrant)
# rather than a body -- keeps the scan motif but makes the thing being
# scanned legibly "a portfolio", matching this app's own subject. Inline SVG,
# no external asset request (offline rule, same as every font choice here).
XRAY_GLYPH_SVG = """
<div class="xray-glyph-wrap">
<svg viewBox="0 0 140 160" xmlns="http://www.w3.org/2000/svg" stroke="#39FF6E" fill="none"
     stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="70" cy="78" r="50" opacity="0.85" />
  <line x1="70" y1="28" x2="70" y2="128" opacity="0.55" />
  <line x1="20" y1="78" x2="120" y2="78" opacity="0.55" />

  <g fill="#39FF6E" stroke="none" opacity="0.85">
    <rect x="28" y="62" width="6" height="8" rx="1" />
    <rect x="38" y="54" width="6" height="16" rx="1" />
    <rect x="48" y="46" width="6" height="24" rx="1" />
    <rect x="58" y="38" width="6" height="32" rx="1" />
  </g>

  <path d="M78,70 L90,56 L100,60 L114,34" opacity="0.85" />
  <path d="M104,34 L114,34 L114,44" opacity="0.85" />

  <circle cx="34" cy="94" r="4.5" fill="#39FF6E" stroke="none" opacity="0.85" />
  <circle cx="58" cy="118" r="4.5" fill="#39FF6E" stroke="none" opacity="0.85" />
  <line x1="60" y1="90" x2="32" y2="122" opacity="0.85" />

  <circle cx="96" cy="103" r="17" opacity="0.85" />
  <line x1="96" y1="88" x2="96" y2="118" opacity="0.65" />
  <path d="M103,94 C96,90 89,94 89,99 C89,104 103,102 103,107 C103,112 96,116 89,112"
        opacity="0.85" stroke-width="2" />

  <g stroke="#3EE8FF" stroke-width="1.2" stroke-dasharray="3 6" opacity="0.3">
    <line x1="6" y1="50" x2="134" y2="50" />
    <line x1="6" y1="106" x2="134" y2="106" />
  </g>
</svg>
</div>
"""
st.markdown(XRAY_GLYPH_SVG, unsafe_allow_html=True)
st.markdown(
    '<div class="masthead-center"><div class="masthead-badge">'
    '<span class="masthead-badge-dot"></span>100-TICKER UNIVERSE</div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="app-title"><span class="title-plain">The Portfolio</span> '
    '<span class="title-accent">X-Ray</span></div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="app-subtitle">How much AI is secretly in your portfolio?</div>', unsafe_allow_html=True)
# Byline (polish pass, item 6) -- surfaces the same credit as the persistent
# footer near the top too, since most visitors arriving from a cold email/link
# never scroll to the bottom far enough to see it (see .app-footer below,
# which stays in place -- this is additive, not a replacement).
st.markdown(
    '<div class="hero-byline">Built by '
    '<a href="https://github.com/IlanNir664/hidden-ai-portfolio" target="_blank">Ilan Niraev</a>'
    '<span class="byline-sep">&middot;</span>'
    '<a href="https://www.linkedin.com/in/ilan-niraev-054a233b4" target="_blank">LinkedIn</a></div>',
    unsafe_allow_html=True,
)
# v3: added a short "why 2000" clause -- the disclaimer's headline reference scenario
# used to go unexplained here (see Step 5's own caption for the fuller version: 2000
# is the closest concentration-crash analogy on record; 2008 and 2022 are shown too,
# as weaker structural matches, not omitted).
st.markdown(
    '<div class="disclaimer-note">Every projected number here is conditional: if a '
    '2000-style repricing occurred (the closest concentration-crash analogy on record, '
    'see Step 5 for 2008 and 2022 too), this is what it would imply, not what will happen. '
    'This app isn\'t claiming a bubble exists or that a crash is coming.</div>',
    unsafe_allow_html=True,
)

# --- Gate check: must pass before anything renders ---
prices = load_prices_cached()
try:
    gate_drawdown = fl.gate_check(prices)
except AssertionError as e:
    st.error(f"Gate check failed, so nothing below will render.\n\n{e}")
    st.stop()

universe = fl.available_tickers(prices)
st.markdown(
    f'<div class="hud-corner-tag hud-corner-br">UNIVERSE:{len(universe)}</div>',
    unsafe_allow_html=True,
)

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
# Progressive step-reveal state -- each step stays visible once unlocked (this
# is not a wizard that hides earlier steps), so "unlocked_steps" only ever
# grows within a session. Numbering matches the section_header() step numbers
# below (0-6), plus 7 for the bonus expander.
#
# Two different unlock triggers are in play, depending on the step:
#   - Bonus (7) has no readiness signal of its own beyond Step 1's portfolio
#     validating, and no dependency on a number some OTHER button is meant to
#     reveal first -- it auto-unlocks the instant a valid portfolio first
#     exists (see the "Cascade unlock" comment near the end of Step 1),
#     rather than gating on a click that wouldn't correspond to anything the
#     user actually did.
#   - Steps 2, 3, and 4 (the donut/headline AI%, the realized-return panel,
#     and the cross-portfolio comparison bar, which plots that same
#     beta_pct) are gated together behind one explicit "Calculate my AI %"
#     button + progress animation. Steps 3 and 4 both used to auto-unlock
#     with the cascade -- moved out once it turned out Step 4's chart
#     directly plots beta_pct (spoiling the exact number the button promises
#     to reveal), and Step 3 rendered "your portfolio" results before the
#     button was ever clicked. See the gate right after the Computation
#     block, before the donut section.
#   - Steps 5 and 6 (repricing scenario bars + tradeoff scatter) are gated
#     together behind their own explicit "Run repricing simulation" button --
#     see the gate right before Step 5's header. That whole gate (including
#     the button itself) is nested inside "4 in unlocked_steps" -- the same
#     AI%-calculation flag -- so it doesn't appear at all until Step 2/3/4
#     have already been revealed; these two gates are sequential, not
#     independent.
# Every gate is enforced via st.rerun() before the guarded content is ever
# reached in the script, and unlock_step() is a persisting, add-only
# session_state write -- so re-editing Step 1's portfolio afterward never
# re-locks anything, on any of the three triggers above.
# ============================================================================

STEP_NAMES = {0: "Why", 1: "Build", 2: "Headline", 3: "Last year", 4: "Compare",
              5: "Repricing", 6: "Menu", 7: "Bonus"}

if "unlocked_steps" not in st.session_state:
    st.session_state["unlocked_steps"] = {0}

# Button-gated reveal animation -- shared by every "click to reveal already-
# computed results" gate in this app (currently: the AI%-calculation gate
# before Step 2/4, and the repricing-simulation gate before Step 5/6). A
# deliberate pacing/reveal device, not real computation: in every case, the
# numbers it reveals are already computed almost instantly elsewhere in this
# same script run (the Computation block below, unchanged either way). This
# just delays the reveal behind a click and a short animated progress bar so
# it reads as "something is happening" instead of an instant table lookup.
# One function, called with a different `stages` list per gate -- not a
# separate copy of the animation logic for each button.
GATE_ANIMATION_TOTAL_SECONDS = 2.0
GATE_ANIMATION_STEPS = 32

AI_PCT_GATE_STAGES = [
    (0.0, "Reading your holdings..."),
    (0.4, "Running the regression..."),
    (0.75, "Calculating exposure..."),
]
REPRICING_SIM_STAGES = [
    (0.0, "Loading historical shock data..."),
    (0.4, "Applying your portfolio's betas..."),
    (0.75, "Modeling scenarios..."),
]


def run_gate_animation(stages: list) -> None:
    """Blocking ~GATE_ANIMATION_TOTAL_SECONDS animated progress bar with a few
    status messages (from `stages`, a list of (threshold_fraction, text)
    tuples) that change as it fills, then clears itself. Called once,
    synchronously, inside a gate button's click handler."""
    progress_bar = st.progress(0)
    status = st.empty()
    for i in range(GATE_ANIMATION_STEPS + 1):
        frac = i / GATE_ANIMATION_STEPS
        stage_msg = stages[0][1]
        for threshold, msg in stages:
            if frac >= threshold:
                stage_msg = msg
        progress_bar.progress(frac)
        status.caption(stage_msg)
        time.sleep(GATE_ANIMATION_TOTAL_SECONDS / GATE_ANIMATION_STEPS)
    progress_bar.empty()
    status.empty()


def unlock_step(n: int) -> bool:
    """Adds step n to the unlocked set. Returns True only the first time --
    the transition this app animates -- so a rerun where it was already
    unlocked (e.g. re-editing Step 1's weights) is a silent no-op."""
    if n in st.session_state["unlocked_steps"]:
        return False
    st.session_state["unlocked_steps"].add(n)
    return True


def render_progress_dots() -> None:
    """Slim, non-clickable progress indicator for returning users -- a visual
    sense of how far they already got, not jump-ahead nav (jumping still
    requires going through Step 1's portfolio construction)."""
    unlocked = st.session_state["unlocked_steps"]
    dots = "".join(
        f'<span class="progress-dot{" is-unlocked" if n in unlocked else ""}" title="{STEP_NAMES[n]}"></span>'
        for n in STEP_NAMES
    )
    st.markdown(f'<div class="progress-dots">{dots}</div>', unsafe_allow_html=True)


def step_anchor(n: int) -> None:
    """Zero-height marker div for each step -- kept as a stable DOM id per
    step in case a future feature needs to target it; no longer used for
    auto-scrolling (removed: it fired on every gate button, not just the
    first time, and users found it disorienting)."""
    st.markdown(f'<div id="step-anchor-{n}"></div>', unsafe_allow_html=True)


def animate_container(key: str, step_n: int, animate_now: set) -> None:
    """Scopes the stepFadeIn keyframe (defined in the page's <style> block) to
    one st.container/expander(key=...)'s auto-generated `.st-key-<key>` class,
    and only on the run where step_n is newly unlocked."""
    if step_n in animate_now:
        st.html(f"<style>.st-key-{key} {{ animation: stepFadeIn 380ms ease-out both; }}</style>")


# Consumed exactly once per run -- set by a trigger (Step 0's continue button,
# the sidebar preset loader, or the Step 1 -> Step 2+ cascade) immediately
# before its own st.rerun(), so this always reflects "what just unlocked".
animate_now = st.session_state.pop("_flash_animate", set())

# Sector preset gallery cards (below, in script order after this point)
# stash their chosen preset here and rerun rather than writing
# selected_tickers/weight_map directly from the card's own click handler --
# keeps every "load a whole portfolio at once" entry point (sidebar preset,
# sector card, shared link) funneling through the same one place, right
# before Step 1 reads this state, instead of three separately-timed writes.
pending_sector_preset = st.session_state.pop("_pending_sector_preset", None)
if pending_sector_preset is not None:
    st.session_state["selected_tickers"] = list(pending_sector_preset.keys())
    st.session_state["weight_map"] = dict(pending_sector_preset)
    st.session_state["weight_map_version"] = st.session_state.get("weight_map_version", 0) + 1

# Shareable link (polish pass, item 4) -- restores a portfolio encoded in the
# "p" query param (see encode_portfolio_query/decode_portfolio_query and the
# "Copy shareable link" button in the donut section below) exactly once per
# browser session, on whatever the first run happens to be. Checked here
# (before Step 1's multiselect is ever instantiated this run, same
# requirement as pending_sector_preset above) so a shared link works whether
# this is a brand-new session or a resumed one, but never re-applies itself
# afterward and fights the user's own edits or their own later use of the
# same "Copy shareable link" button (which also writes "p", but only this
# once-per-session flag decides whether it gets read back as an incoming
# portfolio to load).
if "_shared_link_checked" not in st.session_state:
    st.session_state["_shared_link_checked"] = True
    shared_raw = st.query_params.get("p")
    if shared_raw:
        shared_weights = {
            t: w for t, w in decode_portfolio_query(shared_raw).items() if t in universe
        }
        if shared_weights:
            st.session_state["selected_tickers"] = list(shared_weights.keys())
            st.session_state["weight_map"] = dict(shared_weights)
            st.session_state["weight_map_version"] = st.session_state.get("weight_map_version", 0) + 1
            unlock_step(1)

# Consumed once, right after the "Copy shareable link" button's own st.rerun()
# (see the donut section below) -- st.query_params was already set to the new
# "p" value in the run that clicked the button, so by this run the browser's
# address bar already reflects it; this just best-effort copies that URL to
# the clipboard (wrapped in .catch since clipboard permission can be denied
# silently in some embeds) and confirms via st.toast either way, since the
# toast doesn't depend on the clipboard write actually succeeding.
if st.session_state.pop("_flash_copy_link", False):
    st.html(
        "<script>setTimeout(function() { "
        "navigator.clipboard.writeText(window.location.href).catch(function() {}); "
        "}, 150);</script>",
        unsafe_allow_javascript=True,
    )
    st.toast("Shareable link copied — this portfolio is now saved in the URL.")

render_progress_dots()

# ============================================================================
# Step 0 -- why this exists, plus a real-world proof point (QQQM) that a
# fund's measured AI exposure can drift while its stated strategy, name, and
# the investor's own holdings never change. Static, independent of anything
# built in Step 1 below -- this is the project's thesis statement, not a
# reaction to the user's own portfolio.
# ============================================================================

section_header("0", "Why this exists")
with st.container(border=True):
    st.markdown(
        "Passive investors buy \"diversified\" funds expecting broad, stable exposure. "
        "But an index's composition drifts as its constituent weights shift over time, and "
        "most holders never notice. The fund's name and stated strategy stay exactly the "
        "same, even while what it actually holds, and what actually drives its returns, "
        "quietly changes underneath it."
    )

    # Reuses Module 1's own sourced concentration history (RBC Wealth
    # Management / press consensus / CryptoBriefing -- see
    # m1_concentration.py's CONCENTRATION_HISTORY comment) instead of a DIY
    # price-ratio proxy. Two prior from-price constructions were investigated
    # and dropped for this panel; see LIMITATIONS.md, Module 4.
    history_df = get_concentration_history_df()
    hist_fig = render_concentration_history_chart(history_df)
    st.plotly_chart(hist_fig, theme=None, width="stretch", config=PLOTLY_CONFIG)

    hist_start_year = int(history_df["year"].iloc[0])
    hist_early_pct = history_df.loc[history_df["year"] == 1990, "pct"].iloc[0]
    hist_early_end_year = int(history_df.loc[history_df["year"] <= 2015, "year"].max())
    hist_current_pct = history_df["pct"].iloc[-1]
    st.caption(
        f"The S&P 500 has been marketed as \"a broad, diversified market index\" since "
        f"{hist_start_year}, and its name and stated strategy haven't changed since. What has "
        f"changed is how much of the index sits in its top 10 holdings: {hist_early_pct:.0f}% "
        f"for a quarter-century ({hist_start_year}-{hist_early_end_year}), {hist_current_pct:.0f}% "
        f"today, nearly double the level right before the 2000 dot-com crash. That's composition "
        f"drift happening in plain sight, inside the most widely held index in the world."
    )

    st.markdown("**This app measures the same drift for any portfolio you build below.**")

    if 1 not in st.session_state["unlocked_steps"]:
        st.markdown('<div style="margin-top:14px;"></div>', unsafe_allow_html=True)
        if st.button("Show me how →", key="step0_continue", type="primary"):
            if unlock_step(1):
                st.session_state["_flash_animate"] = {1}
            st.rerun()

# ============================================================================
# Sidebar -- diagnostics, quick presets, ticker universe browser
# ============================================================================

with st.sidebar:
    st.markdown("**Diagnostics**")
    st.markdown(
        f'<div class="diag-line">Gate check: <span class="diag-ok">PASS</span></div>'
        f'<div class="diag-subcaption">Confirms the {len(universe)}-ticker price data is complete '
        f'and internally consistent.</div>'
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
        st.session_state["weight_map_version"] = st.session_state.get("weight_map_version", 0) + 1
        # A preset is a complete, always-valid portfolio -- treat loading one as
        # equivalent to clicking Step 0's continue button, so a returning user
        # who jumps straight to a preset still gets Step 1 revealed (and, once
        # this rerun re-validates below, the same Step 2+ cascade unlock manual
        # ticker entry would trigger).
        if unlock_step(1):
            st.session_state["_flash_animate"] = {1}
        st.rerun()

    st.markdown("---")
    st.markdown("**Supported universe**")
    st.caption(f"{len(universe)} tickers, all cached locally. See Step 1 for what that covers.")
    with st.expander("Browse by category"):
        for cat, tickers in categories.items():
            present = [t for t in tickers if t in universe]
            if present:
                st.caption(f"**{cat}** ({len(present)}): {', '.join(present)}")

# ============================================================================
# Input
# ============================================================================

if 1 not in st.session_state["unlocked_steps"]:
    st.stop()

step_anchor(1)
section_header("1", "Build your portfolio")

st.caption(
    f"Covers {len(universe)} tickers across major US index funds, sector ETFs, and mega-cap "
    "stocks, all cached locally ahead of time. Nothing is fetched live, so search below to "
    "see if yours is included; if it isn't, this tool can't measure it yet."
)
st.caption(
    "Pre-loaded below is a broad-market core plus a Nasdaq-growth fund and a couple of "
    "single-stock adds. It's a common self-directed mix, not the textbook two/three-fund "
    "passive portfolio, shown here as an example of how a reasonable, still-mostly-passive "
    "portfolio can drift toward AI exposure a ticker at a time. Change it to anything below."
)

if "selected_tickers" not in st.session_state:
    st.session_state["selected_tickers"] = list(DEFAULT_PORTFOLIO.keys())
if "weight_map" not in st.session_state:
    st.session_state["weight_map"] = dict(DEFAULT_PORTFOLIO)
# Bumped every time weight_map is replaced wholesale from OUTSIDE the weight
# inputs below (preset load, sector-card pick, shared link, Normalize) --
# each ticker's st.number_input is keyed on this version, so a bulk replace
# gives every box a fresh key and therefore picks up its new `value=`
# instead of a stale one, without needing to touch each key individually.
# A single per-ticker edit (typing into that ticker's own box) does NOT bump
# this -- Streamlit already reflects that edit via the widget's own state.
if "weight_map_version" not in st.session_state:
    st.session_state["weight_map_version"] = 0

animate_container("step1_box", 1, animate_now)
with st.container(border=True, key="step1_box"):
    # Ticker add/remove now lives entirely in this container instead of split
    # across a multiselect widget + a collapsed "manual entry" expander --
    # "selected_tickers" is plain app state here (a list we read/write
    # directly), not a widget's own session_state key, so none of these
    # buttons need the deferred "pending write + rerun" dance that widget
    # keys (like the multiselect this replaced) would require.
    # Weight-on-add (v3.2) -- a number_input next to the search box so a
    # ticker can be given a starting weight in the same click as adding it,
    # instead of always landing at 0% and requiring a second trip down to its
    # table row. Left at its last-entered value across adds on purpose (not
    # reset to 0 after each click) -- adding several tickers at the same
    # weight in a row is a real workflow, and resetting it would fight that.
    add_col, weight_col, btn_col = st.columns([3.4, 1.3, 1])
    with add_col:
        addable = [t for t in sorted_universe if t not in st.session_state["selected_tickers"]]
        ticker_to_add = st.selectbox(
            "Add a ticker",
            options=addable,
            format_func=lambda t: f"{t} ({category_of[t]})",
            key="ticker_add_select",
            index=None,
            placeholder="Search by ticker or category to add…",
            label_visibility="collapsed",
        )
    with weight_col:
        ticker_add_weight = st.number_input(
            "Weight % to add at", min_value=0.0, max_value=100.0, step=1.0, value=0.0,
            key="ticker_add_weight", label_visibility="collapsed",
        )
    with btn_col:
        if st.button("+ Add", key="ticker_add_btn", width="stretch", disabled=ticker_to_add is None):
            st.session_state["selected_tickers"] = st.session_state["selected_tickers"] + [ticker_to_add]
            if ticker_add_weight > 0:
                st.session_state["weight_map"] = {
                    **st.session_state["weight_map"], ticker_to_add: ticker_add_weight,
                }
                st.session_state["weight_map_version"] = st.session_state.get("weight_map_version", 0) + 1
            st.rerun()

    selected = st.session_state["selected_tickers"]
    if selected:
        chip_row_cols = st.columns([5, 1.3])
        with chip_row_cols[0]:
            st.caption("In your portfolio -- click to remove:")
        with chip_row_cols[1]:
            if st.button("Remove all", key="remove_all_tickers", width="stretch"):
                st.session_state["selected_tickers"] = []
                st.session_state["weight_map"] = {}
                st.rerun()
        remove_cols = st.columns(min(len(selected), 7))
        for i, t in enumerate(selected):
            with remove_cols[i % len(remove_cols)]:
                if st.button(f"{t} ✕", key=f"remove_chip_{t}", width="stretch"):
                    st.session_state["selected_tickers"] = [x for x in selected if x != t]
                    st.rerun()

    weights_pct_map = {}
    if selected:
        version = st.session_state["weight_map_version"]
        header_cols = st.columns([2, 3, 0.6])
        with header_cols[0]:
            st.markdown(f'<div style="color:{TEXT_MUTED}; font-size:0.78rem;">TICKER</div>',
                        unsafe_allow_html=True)
        with header_cols[1]:
            st.markdown(f'<div style="color:{TEXT_MUTED}; font-size:0.78rem;">WEIGHT %</div>',
                        unsafe_allow_html=True)
        row_removed = False
        for t in selected:
            row_cols = st.columns([2, 3, 0.6])
            with row_cols[0]:
                st.markdown(f'<div style="padding-top:10px; font-weight:600;">{t}</div>',
                            unsafe_allow_html=True)
            with row_cols[1]:
                # Keyed on weight_map_version, not just the ticker, so a bulk
                # replace of weight_map (preset/sector pick/shared
                # link/Normalize -- see the version-bump comment above) gives
                # this box a fresh widget identity and re-reads `value=`
                # instead of Streamlit preserving whatever was last typed here.
                weights_pct_map[t] = st.number_input(
                    f"{t} weight", min_value=0.0, max_value=100.0, step=5.0,
                    value=float(st.session_state["weight_map"].get(t, 0.0)),
                    key=f"weight_input_{t}_v{version}", label_visibility="collapsed",
                )
            with row_cols[2]:
                # Same remove action as the chip strip above, surfaced again
                # right on the row being edited -- so removing a stock doesn't
                # require scrolling back up to its chip once you're down here
                # adjusting weights.
                if st.button("✕", key=f"remove_row_{t}", width="stretch"):
                    st.session_state["selected_tickers"] = [x for x in selected if x != t]
                    st.session_state["weight_map"].pop(t, None)
                    row_removed = True
        if row_removed:
            st.rerun()
        st.session_state["weight_map"] = dict(weights_pct_map)
        st.caption(
            "Type a weight or use the −/+ steppers, then press Enter (or click away) to apply it. "
            "New tickers start at 0%, so update the weight yourself, or hit Normalize below once "
            "your mix adds up to 100%."
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
                st.session_state["weight_map_version"] = st.session_state.get("weight_map_version", 0) + 1
                st.rerun()
        st.stop()

# ============================================================================
# Cascade unlock -- reaching here means the weights above validated (the
# errors branch just above already st.stop()'d otherwise), so every
# downstream step in this list has what it needs and they unlock together.
# See the "Progressive step-reveal state" comment near the top of the script
# for why this cascades instead of gating on N separate clicks. This is a
# no-op after the first time a valid portfolio exists in this session
# (unlock_step() returns False for anything already unlocked), so re-editing
# Step 1's weights later doesn't re-trigger it or re-lock anything.
#
# Steps 2, 3, and 4 (donut/headline AI%, the realized-return panel, and the
# comparison bar that plots the same beta_pct) and steps 5 and 6 (repricing
# scenario bars + tradeoff scatter) are deliberately NOT in this list -- each
# group is gated behind its own explicit button + progress animation instead
# (see the "Calculate my AI %" gate right after the Computation block, and
# the "Run repricing simulation" gate right before Step 5's header). Step 3
# used to be here (auto-unlocked) -- moved out because that let "Your
# portfolio, the last year" render before the AI%-calculation button was
# ever clicked; see that section's own comment. Bonus (7) is unrelated to
# either gate and stays automatic.
# ============================================================================
CASCADE_STEPS = (7,)
newly_cascade = {n for n in CASCADE_STEPS if unlock_step(n)}
if newly_cascade:
    st.session_state["_flash_animate"] = newly_cascade
    st.rerun()

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
            f"Only {overlap} overlapping trading day(s) between these tickers and the AI basket. "
            f"That's not enough to compute a beta, so try a different mix."
        )
        st.stop()

    single = fl.single_factor_regress(user_log, ai_log)
    two_factor = fl.two_factor_regress(user_log, ai_log, rest_factor_252)

    # Cap-weighted sensitivity check for the "Why these 8 tickers?" expander only
    # -- see get_ai_log_capweighted's own comment for why this doesn't touch the
    # headline number or anything downstream of it.
    ai_log_capweighted = get_ai_log_capweighted(prices)
    beta_pct_capweighted = fl.single_factor_regress(user_log, ai_log_capweighted)["beta"] * 100

    n_obs = single["n_obs"]

    # Realized last-year return (Step 3 panel) -- SIMPLE-return compounding, indexed
    # to 100 at the window's start, same convention as m2_replay.py's crash-replay
    # charts. Aligned against SPY over the SAME trailing dates the user's own
    # portfolio has data for, so a short-history holding doesn't get compared
    # against a SPY window it didn't actually overlap with.
    user_indexed, spy_indexed, realized_n_days = fl.indexed_cumulative_returns(
        user_simple, simple_returns["SPY"], fl.WINDOW
    )
    user_return_pct = user_indexed.iloc[-1] - 100
    spy_return_pct = spy_indexed.iloc[-1] - 100

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

    # Rolling beta -- computed exactly once here, reused by the Step 6 bonus
    # expander further down (see its own comment). Not wrapped in
    # @st.cache_data since it depends on the user's arbitrary weights dict;
    # it's a cheap vectorized computation either way.
    user_rolling_full = fl.rolling_beta(user_log, ai_log, fl.WINDOW)

# ============================================================================
# Sector preset gallery -- one-click themed portfolios, shown right after
# Step 1's manual builder and BEFORE the "Calculate my AI %" button, as a
# faster alternative way to load a portfolio (not a replacement for the
# manual ticker/weight table above, which is untouched). Deliberately NOT
# gated behind "2 in unlocked_steps": a user should be able to browse and
# pick a themed mix before ever calculating, the same way they can already
# pick from the sidebar's "Quick presets" dropdown before calculating.
#
# What IS gated is the AI% number inside each card's donut hole (see
# `reveal` on render_portfolio_donut): pre-calculate, every card shows only
# its composition, not its number, so browsing sector cards can't spoil the
# "Calculate my AI %" button's own reveal. Once that button is pressed,
# revisiting this section (it stays in place, doesn't move or disappear)
# shows every card's real AI%, so the user can compare their chosen
# portfolio's headline number above against every sector at a glance --
# not just the one they picked.
# ============================================================================

reveal_sector_ai = 2 in st.session_state["unlocked_steps"]

# Always shown pre-Calculate (not just once the portfolio differs from the
# default) -- a big "?"-holed wheel that mirrors Step 1's table live, so
# there's always something visual to X-ray before the button is pressed, not
# just a table of numbers. Hidden once Step 2 unlocks: the "Portfolio at a
# glance" donut_box below (see the "Your allocation (donut) + Panel 1" section
# further down) takes over from that point, showing the SAME weights with the
# real number revealed -- keeping both on screen at once would just duplicate
# the same wheel twice.
if 2 not in st.session_state["unlocked_steps"]:
    # ----------------------------------------------------------------------------
    # Live preview of the user's own (not-yet-calculated) portfolio -- same "?"
    # placeholder donut style as the sector cards just below, so both speak one
    # visual language: composition now, number after Calculate. Reads
    # weights_pct_map directly, so it updates on every edit to Step 1's table
    # above.
    #
    # The "Normalize to 100%" button reuses the exact same proportional-scaling
    # math as Step 1's own "Normalize weights to 100%" button (which only ever
    # appears in the weights-don't-sum-to-100 error state, which st.stop()s
    # before reaching this point) -- same behavior, just also reachable here
    # without having to first break your weights to see it.
    # ----------------------------------------------------------------------------
    st.markdown(
        '<div class="section-label">YOUR ALLOCATION SO FAR</div>'
        '<div class="section-title">Your current mix</div>',
        unsafe_allow_html=True,
    )
    with st.container(border=True, key="your_mix_preview"):
        preview_weights_frac = {t: w / 100.0 for t, w in weights_pct_map.items()}
        preview_donut = render_portfolio_donut(
            preview_weights_frac, 0.0,
            reveal=False,
        )
        st.plotly_chart(preview_donut, theme=None, width="stretch", config=PLOTLY_CONFIG,
                         key="your_mix_chart")
        st.caption(" · ".join(f"{t} {w:.0f}%" for t, w in weights_pct_map.items()))

    st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">MORE OPTIONS</div>', unsafe_allow_html=True)
# Collapsed by default -- this is a secondary path (the manual table above is
# the primary one), so it stays out of the way until the user actually wants
# to browse sector mixes, instead of permanently occupying page space.
with st.expander("Or start from a popular portfolio", expanded=False, key="sector_gallery_expander"):
    if reveal_sector_ai:
        st.caption(
            "Pick a sector mix to swap it into the builder above and re-run the numbers. Now that "
            "you've calculated your own AI %, its number is shown below too, so you can compare your "
            "portfolio against it at a glance."
        )
        st.caption(
            "AI% here is a sensitivity measure (regression beta against the AI basket), not a share "
            "of holdings -- it can go over 100% if a mix is more volatile than the basket itself."
        )
    else:
        st.caption(
            "Not sure what to build? Pick a themed sector mix below to load it into the builder above, "
            "then press “Calculate my AI %” to reveal how exposed it is -- yours and this "
            "mix's number stay hidden until then."
        )
    available_sector_presets = {
        name: preset for name, preset in SECTOR_PRESETS.items()
        if all(t in universe for t in preset["tickers"])
    }
    preset_names = list(available_sector_presets.keys())

    # Every option's AI% up front (not just the one currently picked) so the
    # dropdown list itself shows each entry's number once revealed -- same
    # reveal_sector_ai gate as the donut below, so nothing here shows before
    # Calculate is pressed.
    preset_beta_by_name = {}
    if reveal_sector_ai:
        for _name, _preset in available_sector_presets.items():
            _preset_frac = {t: w / 100.0 for t, w in _preset["weights"].items()}
            _preset_log = fl.to_log_returns(fl.build_portfolio_simple_returns(simple_returns, _preset_frac))
            preset_beta_by_name[_name] = fl.single_factor_regress(_preset_log, ai_log)["beta"] * 100
        del _name, _preset, _preset_frac, _preset_log

    def _format_sector_option(name: str) -> str:
        tag = available_sector_presets[name]["tag"]
        if name in preset_beta_by_name:
            return f"{name} ({tag}) -- {preset_beta_by_name[name]:.0f}% AI"
        return f"{name} ({tag})"

    sector_pick = st.selectbox(
        "Pick a themed sector mix",
        options=preset_names,
        format_func=_format_sector_option,
        index=preset_names.index("Classic Investor") if "Classic Investor" in preset_names else 0,
        key="sector_preset_pick",
        label_visibility="collapsed",
    )
    preset = available_sector_presets[sector_pick]
    preset_weights_pct = preset["weights"]
    is_active = (
        set(preset_weights_pct.keys()) == set(weights_pct_map.keys())
        and all(abs(preset_weights_pct[t] - weights_pct_map.get(t, -1.0)) < 0.01
                for t in preset_weights_pct)
    )
    preset_weights_frac = {t: w / 100.0 for t, w in preset_weights_pct.items()}
    preset_beta_pct = preset_beta_by_name.get(sector_pick, 0.0)
    donut_col, info_col = st.columns([1, 1])
    with donut_col:
        mini_donut = render_portfolio_donut(
            preset_weights_frac, preset_beta_pct,
            height=170, number_font_size=16, label_font_size=8, margin=22,
            reveal=reveal_sector_ai,
        )
        st.plotly_chart(mini_donut, theme=None, width="stretch", config=PLOTLY_CONFIG,
                         key="sector_pick_chart")
    with info_col:
        st.caption(" · ".join(f"{t} {w:.0f}%" for t, w in preset_weights_pct.items()))
        if st.button(
            "Currently active" if is_active else "Try this mix →",
            key="sector_pick_btn", disabled=is_active, width="stretch",
        ):
            # See the "pending_sector_preset" comment near the top of the
            # script for why this can't write selected_tickers/weight_map
            # directly from here.
            st.session_state["_pending_sector_preset"] = dict(preset_weights_pct)
            st.rerun()
    st.caption(
        "Each sector mix is an equal-weighted, illustrative sample from this app's supported "
        "universe, not investment advice or a real sector fund's methodology. Same fixed-weight, "
        "daily-rebalanced assumption as the rest of this tool."
    )

# ============================================================================
# Your allocation (donut) + Panel 1: Headline (hero card) -- both gated behind
# one explicit "Calculate my AI %" button + the shared run_gate_animation()
# progress animation, directly after the portfolio-building table (Step 1)
# and before the donut. Placed here (after the Computation block, not right
# after Step 1) specifically so beta_pct is available -- unchanged from
# before, just now the reveal of that already-computed number is gated
# rather than automatic. Steps 3 and 4 are ALSO gated by this same flag,
# further down -- see each section's own comment for why.
# ============================================================================

step_anchor(2)  # shared by the donut and Step 2 -- both unlock on the same click
if 2 not in st.session_state["unlocked_steps"]:
    if st.button("Calculate my AI % →", key="calc_ai_pct", type="primary"):
        run_gate_animation(AI_PCT_GATE_STAGES)
        newly_ai = {n for n in (2, 3, 4) if unlock_step(n)}
        if newly_ai:
            st.session_state["_flash_animate"] = newly_ai
        st.rerun()
else:
    st.markdown(
        '<div class="section-label">YOUR ALLOCATION</div>'
        '<div class="section-title">Portfolio at a glance</div>',
        unsafe_allow_html=True,
    )
    animate_container("donut_box", 2, animate_now)
    with st.container(border=True, key="donut_box"):
        donut_fig = render_portfolio_donut(weights, beta_pct)
        st.plotly_chart(donut_fig, theme=None, width="stretch", config=PLOTLY_CONFIG)
        st.caption(
            "Segment size is your portfolio weight. Green marks an AI basket member and gray is a "
            "bond/Treasury/commodity fund with no equity exposure; other equity cycles through a "
            "mixed color set so individual holdings stay visually distinct."
        )
        # Shareable link (polish pass, item 4) -- see encode_portfolio_query and
        # the "_shared_link_checked" consumption block near the top of the
        # script for the other half of this. Sets the "p" query param (so the
        # portfolio survives a copy/paste of the address bar even without the
        # clipboard write below succeeding) and best-effort copies the full URL
        # via the same unsafe_allow_javascript pattern the "_flash_copy_link"
        # consumption block near the top of this file already uses.
        if st.button("🔗 Copy shareable link", key="copy_share_link"):
            st.query_params["p"] = encode_portfolio_query(weights_pct_map)
            st.session_state["_flash_copy_link"] = True
            st.rerun()

    section_header("2", "Your headline number")

    animate_container("step2_box", 2, animate_now)
    with st.container(border=True, key="step2_box"):
        # Naive weight shown to 1 decimal (not the headline's rounded whole number) so it
        # can be checked against Module 1's published figures (e.g. 60/40 -> 20.26%) at a
        # glance, without the rounding making an exact match look approximate.
        direct_value_html = f"{user_direct_pct:.1f}%" if user_direct_pct is not None else "N/A"
        risk_label, risk_css_class, _risk_color, risk_caption = ai_risk_band(beta_pct)
        st.markdown(
            f'''
            <div class="hero-label">Your portfolio is effectively</div>
            <div class="hero-number">{beta_pct:.0f}<span class="unit-pct">%</span> <span class="unit-suffix">AI</span>
              <span class="risk-badge risk-badge-{risk_css_class}">{risk_label}</span>
            </div>
            <div class="risk-caption">{risk_caption}</div>
            <div class="hero-substats">
              <div class="hero-substat"><div class="sub-label">Naive weight</div><div class="sub-value">{direct_value_html}</div></div>
              <div class="hero-substat"><div class="sub-label">R²</div><div class="sub-value">{r_squared:.2f}</div></div>
              <div class="hero-substat"><div class="sub-label">Trading days used</div><div class="sub-value">{n_obs}</div></div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

        # Methodology caveat, surfaced near the headline (polish pass, item 2) --
        # same exact wording as Step 5's own caption (see the "Linear projection"
        # st.caption() call further down), just also reachable from here via a
        # click instead of only after scrolling all the way to the repricing
        # chart. The verdict paragraph right below this already quotes the
        # dot-com/no-bubble projected numbers this methodology produces, so this
        # is the natural place for a reader to want the caveat. Step 5's own
        # caption is untouched -- this is an additional pointer, not a move.
        with st.popover("ⓘ How the projected numbers below are calculated", key="methodology_popover"):
            st.caption(
                "Linear projection: beta_AI x AI_shock + beta_rest x rest_shock, with no alpha or "
                "drift term. A projection, not a forecast. See LIMITATIONS.md."
            )

        ref_betas_pct = {p: m1_table.loc[p, "beta"] * 100 for p in REFERENCE_PORTFOLIOS}
        nearest_name = nearest_reference_portfolio(beta_pct, ref_betas_pct)
        verdict_html = (
            f"Your portfolio behaves like it's {beta_pct:.0f}% AI, closest to {nearest_name}. "
            f"If a dot-com-style repricing occurred, that would put you around "
            f"<strong>{proj_dotcom:+.0f}%</strong>. If the current trend just kept going, "
            f"more like <strong>{proj_no_bubble:+.0f}%</strong>."
        )
        st.markdown(f'<div class="verdict-text">{verdict_html}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="comparative-line">{comparative_anchor_line(beta_pct, ref_betas_pct)}</div>',
                    unsafe_allow_html=True)

        if user_direct_pct is None:
            st.caption(
                f"Naive direct weight isn't computable for this mix: {format_ticker_list(unresolvable)} "
                f"{'has' if len(unresolvable) == 1 else 'have'} no known top-10 holdings weight."
            )

        st.caption(
            f"An R² of {r_squared:.2f} means the AI basket explains **{r_squared * 100:.0f}%** of your "
            f"portfolio's daily movement. The other **{(1 - r_squared) * 100:.0f}%** comes from your own "
            "holdings and isn't captured by this basket."
        )
        if r_squared < 0.3:
            st.caption(
                "R² is low here, which means the exposure % above is a real but partial relationship: "
                "most of this portfolio's day-to-day movement isn't AI-basket-driven at all. That's common "
                "for single-stock or narrow portfolios. Beta measures the *slope* of the relationship; "
                "R² measures how much of the movement it actually accounts for."
            )

        if beta_pct > 100:
            st.warning(
                "Your effective exposure is over 100%, meaning your portfolio moves even more than the AI "
                "basket itself. That happens when your holdings are basket members at a higher concentration "
                "than the equal-weighted basket, or otherwise amplify its moves. The 'direct weight %' reading "
                "assumes the non-basket remainder is uncorrelated with AI, and that assumption breaks down "
                "here. See LIMITATIONS.md, Module 4."
            )
        elif beta_pct <= 3:
            st.info(
                "A reading at or near zero (including slightly negative) just means near-zero correlation "
                "with the AI basket over the trailing year. It's not a deliberate hedge against it."
            )

        if n_obs < fl.WINDOW:
            st.warning(
                f"Only {n_obs} overlapping trading days available for this portfolio, fewer than the "
                f"standard {fl.WINDOW}-day window, so the estimates above are less reliable than for a "
                f"portfolio with full history."
            )

        with st.expander("Why these 8 tickers?"):
            st.markdown(
                "NVDA, MSFT, GOOGL, META, AMZN, AAPL, AVGO, and TSM: the largest, most "
                "obviously AI-exposed mega-cap names, picked with the benefit of hindsight. "
                "There's no revenue-exposure threshold or index-membership rule behind the "
                "list; it's the project's own judgment call about which companies today's "
                "\"AI trade\" actually runs through. A different, equally defensible basket "
                "(narrower, broader, picked as of 2015 instead of today) would likely produce "
                "a different number. See LIMITATIONS.md for the full caveat."
            )
            st.markdown(
                "The basket is also **equal-weighted**: each of the 8 counts the same "
                "regardless of size, so NVDA and META pull equally even though NVDA's market "
                "cap is roughly triple META's. A cap-weighted basket would let the biggest "
                "names dominate instead, closer to how a real index behaves."
            )
            beta_pct_delta = beta_pct_capweighted - beta_pct
            st.markdown(
                f"That choice matters for your own number too. Equal-weighted, your "
                f"portfolio reads as **{beta_pct:.0f}% AI**. Cap-weighted, using a rough "
                f"market-cap snapshot for the 8 tickers, it reads as "
                f"**{beta_pct_capweighted:.0f}% AI** ({beta_pct_delta:+.0f} points). Same "
                f"holdings, same math, a different weighting assumption inside the reference "
                f"basket, and the answer moves."
            )
            st.caption(
                "The headline number above, the comparison chart, and the repricing "
                "simulation all use the equal-weighted basket throughout, so they stay "
                "consistent with each other and with this project's published research. "
                "This cap-weighted figure is a live sensitivity check only, computed the same "
                "way as the headline number against a differently-weighted basket."
            )


# ============================================================================
# Panel 2: Realized last-year return -- the upside your measured AI exposure
# has already produced, shown before Panel 3's cross-portfolio comparison and
# Panel 4's conditional downside scenarios.
#
# Gated by the SAME "Calculate my AI %" flag as the donut/Step 2 and Step 4
# below (fixed: this block used to render unconditionally regardless of that
# flag, which meant "Your portfolio, the last year" was visible before the
# user had clicked "Calculate my AI %" -- a real gating gap, not a
# computational one. Step 3's own numbers (realized returns, via
# fl.indexed_cumulative_returns) don't actually depend on beta_pct, but
# showing "your portfolio" results before the user has explicitly triggered
# the calculation undercuts the whole click-to-reveal pacing, so it waits
# for the same flag anyway -- checked here via `4 in unlocked_steps`,
# literally the same condition Step 4 already uses, not a new flag.
# ============================================================================

if 4 in st.session_state["unlocked_steps"]:
    step_anchor(3)
    section_header("3", "Your portfolio, the last year")
    animate_container("step3_box", 3, animate_now)
    with st.container(border=True, key="step3_box"):
        if realized_n_days < fl.WINDOW:
            st.markdown(
                f"Over the last {realized_n_days} trading days, which is all the history this "
                f"portfolio has, it would have returned **{user_return_pct:+.1f}%**, versus "
                f"**{spy_return_pct:+.1f}%** for SPY over the same stretch."
            )
        else:
            st.markdown(
                f"Over the last year, your portfolio would have returned "
                f"**{user_return_pct:+.1f}%**, versus **{spy_return_pct:+.1f}%** for SPY."
            )
        fig_realized = render_realized_return_chart(user_indexed, spy_indexed, user_return_pct, spy_return_pct)
        st.plotly_chart(fig_realized, theme=None, width="stretch", config=PLOTLY_CONFIG)
        st.caption(
            "This is realized performance under a fixed-weight, daily-rebalanced assumption, not "
            "what you'd actually have earned with your own trade timing. It's the upside your "
            "measured AI exposure has already produced. Step 5 covers the conditional downside."
        )

# ============================================================================
# Panel 3: Comparison chart -- gated by the SAME "Calculate my AI %" flag as
# the donut/Step 2/Step 3 above (not its own button): render_comparison_chart()
# plots beta_pct directly as the "YOU" bar, so auto-revealing this chart
# would show that number in bar-chart form before the user ever clicks the
# button that promises to reveal it. Silently withheld (no second button --
# the one before the donut already covers it) until that same flag flips.
# ============================================================================

if 4 in st.session_state["unlocked_steps"]:
    step_anchor(4)
    section_header("4", "Where you sit among the standard portfolios")
    animate_container("step4_box", 4, animate_now)
    with st.container(border=True, key="step4_box"):
        fig2 = render_comparison_chart(m1_table, beta_pct, user_direct_pct)
        st.plotly_chart(fig2, theme=None, width="stretch", config=PLOTLY_CONFIG)
        st.caption("AI basket: NVDA, MSFT, GOOGL, META, AMZN, AAPL, AVGO, TSM, equal-weighted. Your bar is the green one.")

    # The same themed sector mixes offered in Step 1's "Or start from a
    # popular portfolio" picker, redrawn as wheels here so you can see every
    # one of them next to your own number at once, instead of flipping
    # through them one at a time in that dropdown. Betas are computed the
    # same way as everywhere else in this app (single_factor_regress against
    # ai_log), not looked up from a different table, so this can't drift
    # from that dropdown's own numbers.
    st.markdown(
        '<div class="section-label">SIDE BY SIDE</div>'
        '<div class="section-title">Other portfolios\' X-ray results</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "The same wheel as your own, run on the themed sector mixes from Step 1's picker, "
        "so you can see how your number above compares against every one of them at once."
    )
    st.caption(
        "AI% here is a sensitivity measure (regression beta against the AI basket), not a share "
        "of holdings -- it can go over 100% if a mix is more volatile than the basket itself."
    )
    side_by_side_presets = {
        name: preset for name, preset in SECTOR_PRESETS.items()
        if all(t in universe for t in preset["tickers"])
    }
    side_by_side_cols = st.columns(4)
    for i, (sbs_name, sbs_preset) in enumerate(side_by_side_presets.items()):
        with side_by_side_cols[i % 4]:
            with st.container(border=True, key=f"side_by_side_card_{i}"):
                sbs_weights_frac = {t: w / 100.0 for t, w in sbs_preset["weights"].items()}
                sbs_log = fl.to_log_returns(fl.build_portfolio_simple_returns(simple_returns, sbs_weights_frac))
                sbs_beta_pct = fl.single_factor_regress(sbs_log, ai_log)["beta"] * 100
                sbs_donut = render_portfolio_donut(
                    sbs_weights_frac, sbs_beta_pct,
                    height=140, number_font_size=13, label_font_size=7, margin=18,
                )
                st.plotly_chart(sbs_donut, theme=None, width="stretch", config=PLOTLY_CONFIG,
                                 key=f"side_by_side_chart_{i}")
                st.markdown(
                    f'<div style="text-align:center; font-weight:700; color:{TEXT_PRIMARY};">{sbs_name}</div>',
                    unsafe_allow_html=True,
                )

# ============================================================================
# Panel 4: Scenario bars, and Panel 5: the tradeoff scatter -- both gated
# behind one explicit "Run repricing simulation" button + the shared
# run_gate_animation() progress animation (defined near the top of the
# script), rather than the automatic cascade every other step uses. Once run,
# this is a one-time gate: unlock_step() persists in session_state, so it
# stays revealed and re-editing Step 1's portfolio afterward just recomputes
# these two panels in place, same as every other already-unlocked step.
#
# The whole block (including the button itself, not just Step 5/6's charts)
# is further wrapped in `4 in unlocked_steps` -- the "Calculate my AI %" flag
# -- so "Run repricing simulation" doesn't even render until that first gate
# has been opened. Fixed: this button used to have no outer gate at all, so
# it rendered immediately alongside "Calculate my AI %" on a fresh session,
# before Step 2/3/4 had ever been revealed.
# ============================================================================

if 4 in st.session_state["unlocked_steps"]:
    step_anchor(5)
    if 5 not in st.session_state["unlocked_steps"]:
        if st.button("Run repricing simulation on your selected portfolio →", key="run_repricing_sim", type="primary"):
            run_gate_animation(REPRICING_SIM_STAGES)
            newly_sim = {n for n in (5, 6) if unlock_step(n)}
            if newly_sim:
                st.session_state["_flash_animate"] = newly_sim
            st.rerun()
    else:
        section_header("5", "If a repricing happened")
        animate_container("step5_box", 5, animate_now)
        with st.container(border=True, key="step5_box"):
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
                "Linear projection: beta_AI x AI_shock + beta_rest x rest_shock, with no alpha or "
                "drift term. A projection, not a forecast. See LIMITATIONS.md."
            )
            st.caption(
                "This app uses three historical analogies: 2022 (a smaller, rate-driven "
                "growth-stock repricing), 2008 (a systemic crash where the \"rest of market\" "
                "fell about as hard as the epicenter, the weakest analogy of the three since "
                "tech wasn't what 2008 was about), and dot-com 2000. Dot-com gets the emphasis "
                "elsewhere in this app (the disclaimer above, Step 6's chart) because it's the "
                "one true **concentration** crash on record, with the market's top holdings "
                "cracking under their own weight the same way Step 0's chart shows happening "
                "again today. 2022 and 2008 are real data points here too, just weaker "
                "structural matches to what this app measures."
            )

        step_anchor(6)
        section_header("6", "The menu: upside kept vs. downside risked")
        animate_container("step6_box", 6, animate_now)
        with st.container(border=True, key="step6_box"):
            m3_reference = {
                p: (m3_table.loc[p, "proj_dotcom_style_pct"], m3_table.loc[p, "proj_no_bubble_pct"])
                for p in REFERENCE_PORTFOLIOS
            }

            fig4 = render_tradeoff_chart(m3_reference, proj_dotcom, proj_no_bubble)
            st.plotly_chart(fig4, theme=None, width="stretch", config=PLOTLY_CONFIG)

            st.caption(
                "This chart plots the dot-com scenario rather than 2022 or 2008, because it's "
                "the closest structural match to a concentration crash (see Step 5's caption). "
                "The other two scenarios' numbers are still in the table above, just not drawn "
                "as a second axis here."
            )
            st.markdown(
                "*This app doesn't recommend a weight. It just shows the tradeoff your portfolio "
                "implies, same stance as the rest of this project.*"
            )

        # --------------------------------------------------------------------
        # Other portfolios' repricing -- same dropdown pattern as Step 1's
        # "Or start from a popular portfolio" (mirrored key names below get
        # matching CSS), but run through the SAME projection math as Step 5
        # above (fl.two_factor_regress + fl.project_scenario) for a small
        # fixed set of other portfolios instead of the user's own. Reuses
        # simple_returns/ai_log/rest_factor_252/the shock values already
        # computed in the Computation block earlier in the script -- nothing
        # new pulled or recomputed globally, just re-run per preset. Only
        # available inside this same `else` (i.e. only once the repricing
        # sim has actually been run), consistent with everything else here.
        # --------------------------------------------------------------------
        st.markdown('<div class="section-label">MORE OPTIONS</div>', unsafe_allow_html=True)
        with st.expander("Other portfolios' repricing", expanded=False, key="repricing_gallery_expander"):
            st.caption(
                "Same projection math as Step 5 above, run on a few other portfolios from this "
                "app's sector picker, so you can see how their repricing exposure compares to yours."
            )
            repricing_preset_names = [
                name for name in ("Semiconductors", "Healthcare Core", "Classic Investor", "AI Basket")
                if name in SECTOR_PRESETS and all(t in universe for t in SECTOR_PRESETS[name]["tickers"])
            ]
            if repricing_preset_names:
                repricing_pick = st.selectbox(
                    "Pick a portfolio",
                    options=repricing_preset_names,
                    format_func=lambda name: f"{name} ({SECTOR_PRESETS[name]['tag']})",
                    key="repricing_preset_pick",
                    label_visibility="collapsed",
                )
                repricing_preset = SECTOR_PRESETS[repricing_pick]
                repricing_frac = {t: w / 100.0 for t, w in repricing_preset["weights"].items()}
                repricing_log = fl.to_log_returns(
                    fl.build_portfolio_simple_returns(simple_returns, repricing_frac)
                )
                repricing_two_factor = fl.two_factor_regress(repricing_log, ai_log, rest_factor_252)
                repricing_proj_no_bubble = fl.project_scenario(
                    repricing_two_factor["beta_ai"], repricing_two_factor["beta_rest"],
                    ai_shock_no_bubble, rest_shock_no_bubble,
                ) * 100
                repricing_proj_2022 = fl.project_scenario(
                    repricing_two_factor["beta_ai"], repricing_two_factor["beta_rest"],
                    m2_shocks["2022_ai_shock"], m2_shocks["2022_rest_shock"],
                ) * 100
                repricing_proj_2008 = fl.project_scenario(
                    repricing_two_factor["beta_ai"], repricing_two_factor["beta_rest"],
                    m2_shocks["gfc_ai_shock"], m2_shocks["gfc_rest_shock"],
                ) * 100
                repricing_proj_dotcom = fl.project_scenario(
                    repricing_two_factor["beta_ai"], repricing_two_factor["beta_rest"],
                    m2_shocks["dotcom_ai_shock"], m2_shocks["dotcom_rest_shock"],
                ) * 100
                fig_repricing = render_scenario_chart(
                    repricing_proj_no_bubble, repricing_proj_2022, repricing_proj_2008,
                    repricing_proj_dotcom, spy_crash_refs=None,
                )
                st.plotly_chart(fig_repricing, theme=None, width="stretch", config=PLOTLY_CONFIG,
                                 key="repricing_preset_chart")

# ============================================================================
# Bonus panel: rolling beta through time
# ============================================================================

step_anchor(7)
animate_container("bonus_box", 7, animate_now)
with st.expander("Bonus: When did your portfolio become an AI fund? (rolling beta through time)", key="bonus_box"):
    # Reuses user_rolling_full/spy_rolling computed once in the Computation
    # block above -- not recomputed here. This is the only place that series
    # is rendered now that the masthead's sparkline preview is gone (see the
    # comment above the masthead's st.markdown calls).
    if user_rolling_full.empty:
        st.warning("Not enough history for this portfolio to compute a rolling beta series.")
    else:
        fig5 = render_rolling_beta_chart(user_rolling_full, spy_rolling, "Your portfolio")
        st.plotly_chart(fig5, theme=None, width="stretch", config=PLOTLY_CONFIG)
        st.caption("Series starts once all constituents (yours and the AI basket's) have 252 trading days of overlap.")

st.markdown("---")
st.caption(
    f"Demo universe: {len(universe)} tickers cached in data/prices.db. This assumes a fixed-weight, "
    "daily-rebalanced portfolio, so it ignores real-world drift and trading costs. See LIMITATIONS.md "
    "(Module 4) and outputs/m4_methodology.md for the full detail. Every Module 1 and Module 3 "
    "limitation applies here too."
)

# Persistent footer watermark -- see the .app-footer rule in the page's <style>
# block for why it's plain text (no link) and deliberately quiet.
st.markdown(
    '<div class="app-footer">Built by Ilan Niraev, 2026 '
    '(https://github.com/IlanNir664/hidden-ai-portfolio)</div>',
    unsafe_allow_html=True,
)

