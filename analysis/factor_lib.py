"""Shared factor-model machinery for the Hidden AI Portfolio project.

Extracted from m1_concentration.py and m3_scenarios.py (Module 4 refactor) so the
research scripts and the Streamlit X-ray app share exactly one implementation. If
you find yourself duplicating a beta/regression/scenario calculation instead of
importing it from here, that's the refactor failing -- put it here instead.

NEVER claim a bubble exists or a crash will happen. Every projected number this
module helps produce is conditional: "if a 2000-style repricing occurred...".
"""

import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "prices.db"
M2_TABLE_PATH = PROJECT_ROOT / "outputs" / "m2_drawdown_table.csv"

AI_BASKET = ["NVDA", "MSFT", "GOOGL", "META", "AMZN", "AAPL", "AVGO", "TSM"]
WINDOW = 252        # trading days, ~1 year -- the standard beta-estimation window
LONG_WINDOW = 756   # trading days, ~3 years -- the "no bubble" trend-continuation window

GATE_CHECK_TICKER = "SPY"
GATE_CHECK_START, GATE_CHECK_END = "2022-01-01", "2022-12-31"
GATE_CHECK_EXPECTED = -0.245
GATE_CHECK_TOLERANCE = 0.01  # 1 percentage point

# --- Direct (naive) weight of the AI basket inside each of the project's reference
# portfolios, in percent. See outputs/m1_methodology.md for full sourcing detail:
# published top-10 holdings pages (SSGA/SPY, Invesco/QQQ via stockanalysis.com,
# Vanguard/VT via stockanalysis.com), pulled 2026-05 to 2026-07. RSP and 60/40 are
# computed analytically (equal-weight arithmetic; 60% of SPY's figure), not fetched.
DIRECT_WEIGHT_PCT = {
    "SPY": 33.77,
    "QQQ": 33.31,
    "VT": 20.92,
    "RSP": round(8 * (1 / 503) * 100, 2),
    "60/40": round(0.6 * 33.77, 2),
}

# Bond/treasury/physical-commodity funds: their direct AI-basket weight is a KNOWN
# zero, not an unknown -- they hold no equities at all (debt instruments or physical
# commodities/futures), so their overlap with an equity basket is 0% by construction,
# the same logic already used for TLT inside the synthetic 60/40 above (60% of SPY's
# weight + 0% from TLT = 20.26%, see DIRECT_WEIGHT_PCT["60/40"]). This lets the app
# apply that same zero to a user's TLT/GLD/etc. holding directly, instead of lumping
# it in with genuinely-unknown tickers (single stocks, unmapped sector ETFs).
ZERO_DIRECT_WEIGHT_TICKERS = {
    "TLT", "IEF", "SHY",       # US Treasuries
    "BND", "AGG", "LQD", "HYG",  # broad/corporate/high-yield bond funds
    "GLD", "IAU", "SLV", "DBC",  # physical commodities / futures
}

# Cap-weighted alternative to the basket's default equal-weighting -- a rough,
# point-in-time market-cap snapshot (aggregated market data, ~2026-08-22),
# same "hardcoded and sourced" convention as DIRECT_WEIGHT_PCT above. Used only
# for the app's "Why these 8 tickers?" sensitivity check (does the headline
# number move much under a different weighting), not by any research module --
# m1/m3's published figures are equal-weighted only, per AI_BASKET's docstring
# elsewhere. This is a snapshot, not a live market-cap feed; it will drift out
# of date the same way DIRECT_WEIGHT_PCT does.
AI_BASKET_CAP_WEIGHT_PCT = {
    "NVDA": 20.68,
    "AAPL": 16.79,
    "GOOGL": 15.99,
    "MSFT": 13.94,
    "AMZN": 10.97,
    "TSM": 8.49,
    "AVGO": 7.54,
    "META": 5.60,
}


def compute_direct_weight_pct(weights: dict):
    """Naive/direct AI-basket weight for an arbitrary user portfolio, in percent.

    A ticker resolves to a KNOWN contribution three ways: it's an AI-basket member
    itself (100% direct by definition -- holding NVDA directly is 100% "AI"), it's
    one of the five reference portfolios in DIRECT_WEIGHT_PCT, or it's a bond/
    Treasury/commodity fund in ZERO_DIRECT_WEIGHT_TICKERS (a known 0%, NOT an
    unknown -- those funds hold no equities at all, so their overlap with an
    equity basket is zero by construction, not "we don't know"). Any other ticker
    (a single stock outside the basket, an unmapped sector ETF, etc.) is genuinely
    unresolvable -- the whole portfolio's direct weight becomes "not computable"
    rather than a guess, and the caller gets back exactly which ticker(s) are why.

    weights: {ticker: fractional_weight} (fractions summing to ~1.0, not percent).
    Returns (direct_weight_pct_or_None, list_of_unresolvable_tickers). The list is
    empty when the return value is a number, and non-empty (naming the culprits)
    whenever the number is None.
    """
    contributions, unresolvable = [], []
    for ticker, w in weights.items():
        if ticker in AI_BASKET:
            contributions.append(w * 100.0)
        elif ticker in DIRECT_WEIGHT_PCT:
            contributions.append(w * DIRECT_WEIGHT_PCT[ticker])
        elif ticker in ZERO_DIRECT_WEIGHT_TICKERS:
            contributions.append(0.0)
        else:
            unresolvable.append(ticker)
    if unresolvable:
        return None, unresolvable
    return sum(contributions), []


def equal_split_weights(tickers: list) -> dict:
    """Equal-weight split across tickers, summing to exactly 100.00.

    A naive round(100/n, 2) per ticker drifts off 100 for any n that doesn't
    divide evenly (e.g. 3 tickers -> 33.33 x 3 = 99.99), which would otherwise
    spuriously trigger a "weights don't sum to 100%" error. The leftover
    remainder goes to the last ticker.
    """
    n = len(tickers)
    if n == 0:
        return {}
    eq_weight = round(100.0 / n, 2)
    weights = {t: eq_weight for t in tickers}
    drift = round(100.0 - eq_weight * n, 2)
    weights[tickers[-1]] = round(weights[tickers[-1]] + drift, 2)
    return weights


def merge_selected_weights(selected: list, existing_weights: dict) -> dict:
    """Ticker -> weight_pct for the currently selected tickers, preserving edits.

    Pure merge logic behind the X-ray app's weight editor, pulled out of the
    widget layer so it's unit-testable without Streamlit. A ticker already
    present in existing_weights (including one the user hand-edited) keeps its
    value -- this is what lets adding or removing a ticker leave the remaining
    rows untouched. A ticker with no prior weight starts at 0.0 -- except when
    NONE of the selected tickers have a prior weight (nothing to preserve),
    in which case the whole selection gets an equal-weight split instead of an
    unhelpful wall of zeros (e.g. picking a fresh set of tickers from empty).

    selected: ordered list of currently-selected tickers.
    existing_weights: {ticker: weight_pct} from before this selection change.
    """
    if not any(t in existing_weights for t in selected):
        return equal_split_weights(selected)
    return {t: existing_weights.get(t, 0.0) for t in selected}


def validate_weights(weight_map: dict):
    """Returns (weights_dict, errors, warnings). weights_dict is None if invalid.

    Duplicate/unsupported tickers can't reach this function: the app's multiselect
    only offers tickers already in the DB universe, and the manual-entry fallback
    validates membership before adding to the selection. Individual weight VALUES
    are a different story -- the shareable-link path (decode_portfolio_query)
    writes straight into weight_map and bypasses the number_input widgets' min/max
    bounds entirely, so a non-finite or negative weight CAN reach this function via
    a hand-edited or corrupted "?p=" link. This checks for that itself rather than
    trusting the caller.
    """
    errors, warnings = [], []
    if not weight_map:
        errors.append("Select at least one ticker above.")
        return None, errors, warnings

    bad = sorted(t for t, w in weight_map.items() if not math.isfinite(w) or w < 0)
    if bad:
        errors.append(f"Invalid weight(s) for: {', '.join(bad)}.")
        return None, errors, warnings

    total = sum(weight_map.values())
    if abs(total - 100.0) > 0.01:
        errors.append(f"Your weights add up to {total:.2f}%, not 100%.")
        return None, errors, warnings

    return {t: w / 100.0 for t, w in weight_map.items()}, errors, warnings


# ============================================================================
# Shareable-link encoding (X-ray app polish pass) -- serializes {ticker: weight_pct}
# into a single URL query param value so a portfolio can be attached to an email/
# LinkedIn message and land the recipient back in this exact state, not just a
# blank app. Deliberately simple (TICKER:WEIGHT pairs, comma-joined) rather than
# base64/JSON -- stays human-readable in the address bar, and Streamlit's own
# st.query_params already handles URL-escaping the joined string on write/read.
# ============================================================================

def encode_portfolio_query(weights_pct_map: dict) -> str:
    return ",".join(f"{ticker}:{weight:.2f}" for ticker, weight in weights_pct_map.items())


def decode_portfolio_query(raw: str) -> dict | None:
    """Parse a shareable-link "p" query param into {ticker: weight_pct}.

    Returns None -- meaning "reject the whole link" -- the moment ANY pair's
    weight is unparseable, not finite, negative, or over 100. This used to be
    a best-effort parse that dropped only the bad pair, but that's what let a
    single corrupted pair through silently: `?p=AAPL:nan` parses as a float,
    passes both `nan > 100` and `nan < 0` (both False for NaN), and would have
    reached build_portfolio_simple_returns' `.sum(axis=1)`, which skips NaN
    silently -- producing a confident beta, risk badge and scenario for a
    portfolio quietly missing a holding. `?p=AAPL:150` / `?p=AAPL:-50` would
    instead have reached st.number_input(min_value=0, max_value=100, value=...)
    and raised StreamlitValueAboveMaxError/BelowMinError, killing the whole page
    for whoever opened the link. Neither failure mode requires hostile intent,
    just a truncated paste -- so any single bad pair now invalidates the link
    entirely; the caller falls back to the default portfolio and warns, rather
    than either crashing or building a silently-wrong one.

    Ticker membership in the app's universe is deliberately NOT checked here
    (the caller filters against `universe`) -- an unrecognized ticker (renamed,
    delisted, or just a typo) is a milder problem than a malformed weight and
    is still handled per-ticker, not as a whole-link failure.
    """
    decoded = {}
    for pair in raw.split(","):
        ticker, sep, weight_str = pair.partition(":")
        ticker = ticker.strip().upper()
        if not sep or not ticker or not weight_str:
            return None
        try:
            weight = float(weight_str)
        except ValueError:
            return None
        if not math.isfinite(weight) or weight < 0 or weight > 100:
            return None
        decoded[ticker] = weight
    return decoded if decoded else None


# dataviz skill palette (light mode) -- shared across every chart in the project,
# PNG or in-app, so research output and the X-ray app stay visually one system.
COLOR_BLUE = "#2a78d6"
COLOR_YELLOW = "#eda100"
COLOR_RED = "#e34948"
COLOR_VIOLET = "#4a3aa7"    # 2008-style scenario bar in chart5 -- blue/yellow/red are
                            # already taken by no-bubble/2022-style/dot-com-style
COLOR_MUTED_BAR = "#898781"
COLOR_INK_PRIMARY = "#0b0b0b"
COLOR_INK_SECONDARY = "#52514e"
COLOR_INK_MUTED = "#898781"
COLOR_GRIDLINE = "#e1e0d9"
COLOR_ZERO_LINE = "#c3c2b7"
COLOR_SURFACE = "#fcfcfb"


def load_prices(db_path: Path = DB_PATH) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT date, ticker, adj_close FROM prices", conn, parse_dates=["date"])
    conn.close()
    return df.pivot(index="date", columns="ticker", values="adj_close").sort_index()


def available_tickers(prices: pd.DataFrame) -> list:
    # EXTENSION POINT: today the "supported universe" is exactly what's cached in
    # prices.db by data/pull_prices.py. To support arbitrary user tickers, this is
    # the one function to change -- have it fall back to a live yfinance pull (and
    # persist the result back into the DB) for tickers not already present, instead
    # of only reading what's cached.
    return sorted(prices.columns.tolist())


def to_log_returns(simple_returns: pd.Series) -> pd.Series:
    return np.log1p(simple_returns)


def ai_basket_simple_returns(simple_returns: pd.DataFrame, basket: list = AI_BASKET) -> pd.Series:
    """Equal-weight mean of the basket's simple returns, only on days all members exist."""
    return simple_returns[basket].dropna().mean(axis=1)


def ai_basket_capweighted_simple_returns(simple_returns: pd.DataFrame) -> pd.Series:
    """Cap-weighted version of the same basket, using AI_BASKET_CAP_WEIGHT_PCT.

    Only for the app's basket-weighting sensitivity check -- see that dict's own
    comment. Same restricted-to-overlapping-days rule as ai_basket_simple_returns.
    """
    weights = {t: w / 100.0 for t, w in AI_BASKET_CAP_WEIGHT_PCT.items()}
    return build_portfolio_simple_returns(simple_returns, weights)


def build_portfolio_simple_returns(simple_returns: pd.DataFrame, weights: dict) -> pd.Series:
    """Weighted sum of constituent simple daily returns -- a fixed-weight, daily-
    rebalanced portfolio (see LIMITATIONS.md Module 4 for what that assumption
    ignores: real-world drift and trading costs). Restricted to dates where every
    weighted constituent has data, matching the project's data rule elsewhere (the
    AI basket, the synthetic 60/40).
    """
    tickers = list(weights.keys())
    aligned = simple_returns[tickers].dropna()
    weight_vector = pd.Series(weights)
    return aligned.mul(weight_vector, axis=1).sum(axis=1)


def gate_check(prices: pd.DataFrame, ticker: str = GATE_CHECK_TICKER, start: str = GATE_CHECK_START,
               end: str = GATE_CHECK_END, expected: float = GATE_CHECK_EXPECTED,
               tolerance: float = GATE_CHECK_TOLERANCE) -> float:
    """Recompute a known drawdown from the DB; raise if the pipeline can't reproduce it.

    If this fails, nothing downstream can be trusted -- callers (scripts, the app,
    tests) must not show any results when this raises.
    """
    series = prices.loc[start:end, ticker].dropna()
    running_max = series.cummax()
    drawdown = float((series / running_max - 1).min())
    if abs(drawdown - expected) > tolerance:
        raise AssertionError(
            f"GATE CHECK FAILED: {ticker} {start[:4]} drawdown {drawdown:.4f} is more than "
            f"{tolerance} away from expected {expected}. If the pipeline can't reproduce a "
            f"known number, nothing downstream can be trusted."
        )
    return drawdown


MIN_REGRESSION_OBS = 2  # below this, statsmodels' add_constant degenerates (no 'const' column)


def overlapping_obs_count(y_log: pd.Series, x_log: pd.Series) -> int:
    """How many dates y and x both have data for -- check before regressing.

    A single-observation (or empty) alignment makes statsmodels' `add_constant`
    silently skip adding the constant column (it looks "constant" with one row),
    which crashes the regression with a KeyError on 'const' rather than a clean
    error. Callers (the app, in particular) must check this first and stop with a
    clear message instead of letting that crash surface.
    """
    return len(pd.concat([y_log, x_log], axis=1, keys=["y", "x"]).dropna())


def single_factor_regress(y_log: pd.Series, x_log: pd.Series, window: int = WINDOW) -> dict:
    """OLS of y (portfolio log returns) on x (AI basket log returns), trailing window.

    Module 1 convention: one factor, "beta" = effective AI exposure. Raises
    ValueError (not the raw statsmodels crash) if there are fewer than
    MIN_REGRESSION_OBS overlapping observations -- check overlapping_obs_count
    first if you need to show a friendlier message before this raises.
    """
    aligned = pd.concat([y_log, x_log], axis=1, keys=["y", "x"]).dropna().tail(window)
    if len(aligned) < MIN_REGRESSION_OBS:
        raise ValueError(f"Only {len(aligned)} overlapping observation(s); need at least {MIN_REGRESSION_OBS}.")
    X = sm.add_constant(aligned["x"])
    model = sm.OLS(aligned["y"], X).fit()
    return {
        "beta": model.params["x"],
        "alpha": model.params["const"],
        "r_squared": model.rsquared,
        "n_obs": int(model.nobs),
        "window_start": aligned.index.min().strftime("%Y-%m-%d"),
        "window_end": aligned.index.max().strftime("%Y-%m-%d"),
    }


def build_rest_factor(rsp_log: pd.Series, ai_log: pd.Series, window: int):
    """Rest-of-market factor: RSP residualized against the AI basket.

    Regress RSP's log returns on the AI basket's log returns over the trailing
    `window` days; the OLS residual (mean ~0 over the fit window, by construction)
    is the orthogonal "rest of market" factor -- RSP's return with its AI-basket-
    explained component removed. See outputs/m3_methodology.md for why this makes
    RSP's own two-factor decomposition a near-tautology.
    """
    aligned = pd.concat([rsp_log, ai_log], axis=1, keys=["y", "x"]).dropna().tail(window)
    X = sm.add_constant(aligned["x"])
    model = sm.OLS(aligned["y"], X).fit()
    return model, aligned["x"], model.resid


def two_factor_regress(y_log: pd.Series, ai_log: pd.Series, rest_factor: pd.Series) -> dict:
    """Module 3 convention: two factors, beta_ai + beta_rest."""
    aligned = pd.concat([y_log, ai_log, rest_factor], axis=1, keys=["y", "ai", "rest"]).dropna()
    X = sm.add_constant(aligned[["ai", "rest"]])
    model = sm.OLS(aligned["y"], X).fit()
    return {
        "beta_ai": model.params["ai"],
        "beta_rest": model.params["rest"],
        "alpha": model.params["const"],
        "r_squared": model.rsquared,
        "n_obs": int(model.nobs),
    }


def annualized_return(log_returns: pd.Series, periods_per_year: int = 252) -> float:
    """Geometric annualized simple return from a series of log returns."""
    years = len(log_returns) / periods_per_year
    return float(np.expm1(log_returns.sum() / years))


def load_m2_shocks(m2_table_path: Path = M2_TABLE_PATH) -> dict:
    """Scenario shocks, read from Module 2's own results -- never hand-typed.

    dotcom_ai_shock:   Nasdaq Composite's dot-com max drawdown -- the era's
                       concentrated leader maps to today's AI basket.
    dotcom_rest_shock: Value/IWD's dot-com max drawdown -- the era's non-epicenter
                       maps to today's rest-of-market factor.
    2022_ai_shock:     QQQ's 2022 max drawdown.
    2022_rest_shock:   VTV's 2022 max drawdown.
    gfc_ai_shock:      QQQ's GFC (2007-2009) max drawdown.
    gfc_rest_shock:    Value/IWD's GFC max drawdown -- unlike the dot-com mapping,
                       this is expected to be roughly EQUAL to or LARGER in
                       magnitude than the AI-shock side (see m3_methodology.md):
                       2008 was a systemic crash, not a concentration crash, so
                       the "rest of market" fell about as hard as the epicenter.
    """
    m2 = pd.read_csv(m2_table_path)

    def dd(window: str, ticker: str) -> float:
        row = m2[(m2["window"] == window) & (m2["ticker"] == ticker)]
        return row["max_drawdown_pct"].iloc[0] / 100

    return {
        "dotcom_ai_shock": dd("dotcom", "^IXIC"),
        "dotcom_rest_shock": dd("dotcom", "IWD"),
        "2022_ai_shock": dd("2022", "QQQ"),
        "2022_rest_shock": dd("2022", "VTV"),
        "gfc_ai_shock": dd("gfc", "QQQ"),
        "gfc_rest_shock": dd("gfc", "IWD"),
    }


def rolling_beta(y_log: pd.Series, x_log: pd.Series, window: int = WINDOW) -> pd.Series:
    """Rolling single-factor beta through time: Cov(x,y)/Var(x) over a trailing window.

    Vectorized (pandas rolling cov/var), not a per-window OLS loop -- algebraically
    identical to the OLS slope coefficient `single_factor_regress` returns (the OLS
    slope IS Cov(x,y)/Var(x) regardless of the intercept), just fast enough to compute
    at every date in a series instead of once at the end.
    """
    aligned = pd.concat([y_log, x_log], axis=1, keys=["y", "x"]).dropna()
    cov = aligned["y"].rolling(window).cov(aligned["x"])
    var = aligned["x"].rolling(window).var()
    return (cov / var).dropna()


def indexed_cumulative_returns(user_simple: pd.Series, reference_simple: pd.Series, window: int = WINDOW):
    """Cumulative return paths for a portfolio and a reference series, indexed to
    100 at the trailing window's start -- the same "index to 100" convention
    m2_replay.py's window_series() applies to raw prices, adapted here since a
    synthetic weighted portfolio has no price level of its own, only a daily
    return series (see build_portfolio_simple_returns). Built from compounded
    SIMPLE returns (not log), matching the M2 crash-replay charts' convention.

    Aligns both series first (pd.concat + dropna, same idiom single_factor_regress
    and rolling_beta already use above) so a short-history portfolio's window can't
    silently pull in reference dates it has no data for, then takes the trailing
    `window` overlapping days. Returns (user_indexed, reference_indexed, n_days):
    n_days is how many trailing overlapping trading days were actually available,
    so callers can tell a short-history portfolio apart from a full
    trailing-window one without re-deriving it.
    """
    aligned = pd.concat([user_simple, reference_simple], axis=1, keys=["user", "ref"]).dropna().tail(window)
    n_days = len(aligned)
    user_indexed = (1 + aligned["user"]).cumprod() * 100
    ref_indexed = (1 + aligned["ref"]).cumprod() * 100
    return user_indexed, ref_indexed, n_days


def project_scenario(beta_ai: float, beta_rest: float, ai_shock: float, rest_shock: float) -> float:
    """The scenario projection formula, in exactly one place.

    projected outcome ~= beta_AI x AI_shock + beta_rest x rest_shock (linear, no
    alpha/drift term -- see outputs/m3_methodology.md and LIMITATIONS.md).
    """
    return beta_ai * ai_shock + beta_rest * rest_shock


# ============================================================================
# Crash-conditional (piecewise) betas -- added to answer this project's own
# loudest self-flagged limitation: a single symmetric OLS beta can't
# distinguish "moves with the basket on the way up" from "moves with it on
# the way down", and cross-asset correlations are well documented to rise
# specifically during drawdowns. LIMITATIONS.md previously only confessed
# this; these functions measure it instead.
#
# Specification (Henriksson-Merton / Bawa-Lindenberg form -- still LINEAR in
# the factor, deliberately):
#
#     y = alpha + beta_up * x + beta_extra * (x * 1{x < 0}) + e
#
# so the down-day slope is beta_up + beta_extra. A quadratic (x^2) term was
# considered and rejected: the scenario engine extrapolates ~25x outside the
# daily fitting range (a -77.9% shock against +/-3% typical daily moves), and
# a squared term extrapolated that far would dominate the projection entirely
# while having no interpretable "% AI" reading. Piecewise-linear keeps both
# the interpretation and a bounded extrapolation.
# ============================================================================

MIN_STATE_OBS = 30  # minimum up-days and down-days needed before a piecewise fit is trustworthy


def downside_regress(y_log: pd.Series, x_log: pd.Series, window: int = WINDOW) -> dict:
    """Single-factor piecewise regression: separate up-day and down-day betas.

    Returns beta_up (slope on days the factor rose), beta_down (slope on days
    it fell), and asymmetry = beta_down - beta_up -- positive means the
    portfolio tracks the basket MORE closely when the basket is falling, which
    is exactly the effect a symmetric beta averages away.

    Raises ValueError (not a statsmodels crash) when either state has fewer
    than MIN_STATE_OBS observations in the window; callers should fall back to
    the symmetric beta and say so rather than showing an unstable split.
    """
    aligned = pd.concat([y_log, x_log], axis=1, keys=["y", "x"]).dropna().tail(window)
    down_flag = (aligned["x"] < 0).astype(float)
    n_down = int(down_flag.sum())
    n_up = len(aligned) - n_down
    if n_down < MIN_STATE_OBS or n_up < MIN_STATE_OBS:
        raise ValueError(
            f"Piecewise fit needs at least {MIN_STATE_OBS} up-days and {MIN_STATE_OBS} down-days; "
            f"this window has {n_up} up and {n_down} down."
        )
    x_down = (aligned["x"] * down_flag).rename("x_down")
    X = sm.add_constant(pd.concat([aligned["x"], x_down], axis=1))
    model = sm.OLS(aligned["y"], X).fit()
    beta_up = float(model.params["x"])
    beta_down = float(model.params["x"] + model.params["x_down"])
    return {
        "beta_up": beta_up,
        "beta_down": beta_down,
        "asymmetry": beta_down - beta_up,
        "alpha": float(model.params["const"]),
        "r_squared": float(model.rsquared),
        "n_obs": int(model.nobs),
        "n_down_days": n_down,
        "n_up_days": n_up,
    }


def two_factor_downside_regress(y_log: pd.Series, ai_log: pd.Series, rest_factor: pd.Series,
                                window: int = WINDOW) -> dict:
    """Two-factor version of downside_regress -- each factor gets its own down-state slope.

        y = a + b_ai*ai + b_ai_dn*ai*1{ai<0} + b_rest*rest + b_rest_dn*rest*1{rest<0}

    This is what the scenario engine needs: a crash scenario plugs a NEGATIVE
    shock into both factors, so it should be multiplying the down-state slopes,
    while the trend-continuation scenario plugs in a positive AI shock and
    should be multiplying the up-state slope. Same MIN_STATE_OBS guard as the
    single-factor version, applied to both factors.
    """
    aligned = pd.concat([y_log, ai_log, rest_factor], axis=1, keys=["y", "ai", "rest"]).dropna().tail(window)
    ai_dn_flag = (aligned["ai"] < 0).astype(float)
    rest_dn_flag = (aligned["rest"] < 0).astype(float)
    n_ai_down, n_rest_down = int(ai_dn_flag.sum()), int(rest_dn_flag.sum())
    n_ai_up, n_rest_up = len(aligned) - n_ai_down, len(aligned) - n_rest_down
    if min(n_ai_down, n_ai_up, n_rest_down, n_rest_up) < MIN_STATE_OBS:
        raise ValueError(
            f"Piecewise two-factor fit needs at least {MIN_STATE_OBS} observations in every state; "
            f"got AI {n_ai_up} up / {n_ai_down} down, rest {n_rest_up} up / {n_rest_down} down."
        )
    regressors = pd.concat(
        [
            aligned["ai"],
            (aligned["ai"] * ai_dn_flag).rename("ai_dn"),
            aligned["rest"],
            (aligned["rest"] * rest_dn_flag).rename("rest_dn"),
        ],
        axis=1,
    )
    model = sm.OLS(aligned["y"], sm.add_constant(regressors)).fit()
    return {
        "beta_ai_up": float(model.params["ai"]),
        "beta_ai_down": float(model.params["ai"] + model.params["ai_dn"]),
        "beta_rest_up": float(model.params["rest"]),
        "beta_rest_down": float(model.params["rest"] + model.params["rest_dn"]),
        "alpha": float(model.params["const"]),
        "r_squared": float(model.rsquared),
        "n_obs": int(model.nobs),
    }


def project_scenario_conditional(betas: dict, ai_shock: float, rest_shock: float) -> float:
    """Scenario projection using the state-matched betas from two_factor_downside_regress.

    A negative shock is multiplied by that factor's DOWN-state beta, a positive
    shock by its up-state beta -- so a crash scenario is projected with the
    co-movement actually measured on down days, and the trend-continuation
    scenario with the up-day slope. Reduces exactly to project_scenario() when
    the up and down betas are equal.
    """
    beta_ai = betas["beta_ai_down"] if ai_shock < 0 else betas["beta_ai_up"]
    beta_rest = betas["beta_rest_down"] if rest_shock < 0 else betas["beta_rest_up"]
    return beta_ai * ai_shock + beta_rest * rest_shock


# ============================================================================
# Uncertainty on the headline number. The app's hero card previously showed a
# point estimate with no error band anywhere in the UI -- the single most
# standard thing a model-validation reviewer looks for. A moving-block
# bootstrap is used rather than textbook OLS standard errors because daily
# financial returns are autocorrelated and heteroskedastic (volatility
# clusters), which biases classical standard errors down; resampling in
# blocks preserves that local dependence structure.
# ============================================================================

BOOTSTRAP_DRAWS = 400
BOOTSTRAP_BLOCK = 20    # trading days (~1 month) -- long enough to carry a volatility cluster
BOOTSTRAP_CI = 0.90


def bootstrap_beta_ci(y_log: pd.Series, x_log: pd.Series, window: int = WINDOW,
                      n_draws: int = BOOTSTRAP_DRAWS, block: int = BOOTSTRAP_BLOCK,
                      ci: float = BOOTSTRAP_CI, seed: int = 0) -> dict:
    """Moving-block bootstrap confidence interval for the single-factor beta.

    Resamples contiguous blocks of (y, x) pairs with replacement from the same
    trailing window single_factor_regress uses, recomputing the OLS slope as
    Cov(x,y)/Var(x) on each draw (algebraically the same slope, without the
    statsmodels overhead, since only the slope is needed here).

    Returns {"beta", "lo", "hi", "ci", "n_draws", "se_boot"} with beta the point
    estimate on the actual window -- so callers can render "68% (61-76%)" without
    a second regression call. se_boot is the bootstrap draws' standard deviation
    (a Monte Carlo SE on the slope, distinct from the percentile interval width).
    Raises ValueError if the window is shorter than one block.
    """
    aligned = pd.concat([y_log, x_log], axis=1, keys=["y", "x"]).dropna().tail(window)
    n = len(aligned)
    if n < block * 2:
        raise ValueError(f"Need at least {block * 2} overlapping observations to block-bootstrap; got {n}.")
    y = aligned["y"].to_numpy()
    x = aligned["x"].to_numpy()

    def slope(yy, xx):
        xc = xx - xx.mean()
        return float((xc * (yy - yy.mean())).sum() / (xc * xc).sum())

    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(n_draws, n_blocks))
    offsets = np.arange(block)
    # (n_draws, n_blocks, block) -> (n_draws, n_blocks*block), trimmed back to n
    idx = (starts[:, :, None] + offsets[None, None, :]).reshape(n_draws, -1)[:, :n]
    draws = np.array([slope(y[row], x[row]) for row in idx])

    tail = (1.0 - ci) / 2.0
    return {
        "beta": slope(y, x),
        "lo": float(np.quantile(draws, tail)),
        "hi": float(np.quantile(draws, 1.0 - tail)),
        "ci": ci,
        "n_draws": n_draws,
        "se_boot": float(draws.std(ddof=1)),
    }


# Tickers the app's math actually depends on: the AI basket (every regression's
# x-variable) plus the reference portfolios every user beta is displayed next to.
# Deliberately NOT "every ticker in the panel" -- see data_through() below.
CORE_TICKERS_FOR_DATA_THROUGH = AI_BASKET + ["SPY", "QQQ", "VT", "RSP", "TLT"]


def data_through(prices: pd.DataFrame, core_tickers: list = CORE_TICKERS_FOR_DATA_THROUGH) -> dict:
    """Date through which the app's math actually has real data, not just
    whichever ticker in the panel happens to be most current.

    `prices.index.max()` is the UNION of every ticker's dates -- one recently
    added, frequently-updated ticker can push it forward while the tickers the
    regression actually uses (the AI basket, plus the reference portfolios a
    user's beta is compared against) are weeks behind. Pandas' `pct_change()`
    forward-fills that gap by default, fabricating a 0.00% return for every
    stale ticker on every day after its real data ends -- see LIMITATIONS.md's
    forward-fill entry for the incident this caused. Reporting the panel's max
    date as "data through" would have certified freshness that didn't exist.

    Returns a dict:
      - "date": the conservative date -- min(last_valid_index()) across
        `core_tickers` -- safe to print as "this is how current the math is".
      - "panel_max": the panel's raw max date, for comparison.
      - "stale": True when panel_max is ahead of "date", meaning some
        non-core ticker is more current than the app's actual math.

    Raises ValueError if none of `core_tickers` are present in `prices`.
    """
    core_dates = [prices[t].last_valid_index() for t in core_tickers if t in prices.columns]
    core_dates = [d for d in core_dates if d is not None]
    if not core_dates:
        raise ValueError("None of the core tickers (AI basket + reference portfolios) are present in the price panel.")
    core_through = min(core_dates)
    panel_max = prices.index.max()
    return {
        "date": core_through.strftime("%Y-%m-%d"),
        "panel_max": panel_max.strftime("%Y-%m-%d"),
        "stale": bool(core_through < panel_max),
    }
