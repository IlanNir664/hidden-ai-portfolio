"""Tests for analysis/factor_lib.py -- the shared machinery behind Modules 1, 3, and 4.

Run: pytest tests/ -v
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import factor_lib as fl

M1_TABLE_PATH = Path(__file__).parent.parent / "outputs" / "m1_beta_table.csv"


@pytest.fixture(scope="module")
def prices() -> pd.DataFrame:
    return fl.load_prices()


@pytest.fixture(scope="module")
def simple_returns(prices) -> pd.DataFrame:
    return prices.pct_change(fill_method=None)


@pytest.fixture(scope="module")
def ai_log(simple_returns) -> pd.Series:
    return fl.to_log_returns(fl.ai_basket_simple_returns(simple_returns))


@pytest.fixture(scope="module")
def m1_table() -> pd.DataFrame:
    return pd.read_csv(M1_TABLE_PATH).set_index("portfolio")


def test_gate_check_passes(prices):
    """SPY's 2022 max drawdown must reproduce the known ~-24.5% figure."""
    drawdown = fl.gate_check(prices)
    assert abs(drawdown - fl.GATE_CHECK_EXPECTED) <= fl.GATE_CHECK_TOLERANCE


def test_gate_check_raises_on_bad_expectation(prices):
    """gate_check must raise, not silently pass, when the expectation is wrong."""
    with pytest.raises(AssertionError):
        fl.gate_check(prices, expected=0.0, tolerance=0.01)


def test_qqq_has_highest_beta_ai(simple_returns, ai_log):
    """Per METHODOLOGY.md T1.2: QQQ should show the highest single-factor beta."""
    portfolios = ["SPY", "VT", "QQQ", "RSP"]
    betas = {}
    for p in portfolios:
        y_log = fl.to_log_returns(simple_returns[p])
        betas[p] = fl.single_factor_regress(y_log, ai_log)["beta"]
    assert betas["QQQ"] == max(betas.values())


def test_tlt_beta_ai_near_zero(simple_returns, ai_log):
    """TLT (long-term Treasuries) should show ~zero AI exposure."""
    y_log = fl.to_log_returns(simple_returns["TLT"])
    beta = fl.single_factor_regress(y_log, ai_log)["beta"]
    assert beta < 0.1


def test_100pct_spy_user_portfolio_matches_m1_beta(simple_returns, ai_log, m1_table):
    """A user portfolio of 100% SPY must reproduce SPY's Module 1 beta to 4 decimals."""
    user_simple = fl.build_portfolio_simple_returns(simple_returns, {"SPY": 1.0})
    user_log = fl.to_log_returns(user_simple)
    user_beta = fl.single_factor_regress(user_log, ai_log)["beta"]
    assert user_beta == pytest.approx(m1_table.loc["SPY", "beta"], abs=1e-4)


def test_60_40_user_portfolio_matches_synthetic_60_40_row(simple_returns, ai_log, m1_table):
    """A user portfolio of 60% SPY / 40% TLT must reproduce the synthetic 60/40 row."""
    user_simple = fl.build_portfolio_simple_returns(simple_returns, {"SPY": 0.6, "TLT": 0.4})
    user_log = fl.to_log_returns(user_simple)
    user_beta = fl.single_factor_regress(user_log, ai_log)["beta"]
    assert user_beta == pytest.approx(m1_table.loc["60/40", "beta"], abs=1e-4)


def test_two_factor_beta_ai_matches_single_factor(simple_returns, ai_log):
    """The two-factor beta_AI should match the single-factor beta almost exactly,
    since the rest factor is constructed to be orthogonal to the AI factor."""
    rsp_log = fl.to_log_returns(simple_returns["RSP"])
    _, _, rest_factor = fl.build_rest_factor(rsp_log, ai_log, fl.WINDOW)

    y_log = fl.to_log_returns(simple_returns["QQQ"])
    single = fl.single_factor_regress(y_log, ai_log)["beta"]
    two_factor = fl.two_factor_regress(y_log, ai_log, rest_factor)["beta_ai"]
    assert two_factor == pytest.approx(single, abs=0.05)


def test_indexed_cumulative_returns_basic_compounding():
    """Values compound off a 100 base via SIMPLE returns, same convention as
    m2_replay.py's window_series() for raw prices."""
    dates = pd.date_range("2026-01-01", periods=3, freq="B")
    user = pd.Series([0.10, -0.10, 0.05], index=dates)
    ref = pd.Series([0.02, 0.02, 0.02], index=dates)
    user_indexed, ref_indexed, n_days = fl.indexed_cumulative_returns(user, ref, window=10)
    assert n_days == 3
    assert user_indexed.iloc[0] == pytest.approx(110.0)
    assert user_indexed.iloc[1] == pytest.approx(110.0 * 0.90)
    assert user_indexed.iloc[2] == pytest.approx(110.0 * 0.90 * 1.05)
    assert ref_indexed.iloc[-1] == pytest.approx(100 * 1.02 ** 3)


def test_indexed_cumulative_returns_respects_window_truncation():
    """A shorter window than the available history truncates to the trailing N days."""
    dates = pd.date_range("2026-01-01", periods=5, freq="B")
    user = pd.Series([0.01] * 5, index=dates)
    ref = pd.Series([0.01] * 5, index=dates)
    _, _, n_days = fl.indexed_cumulative_returns(user, ref, window=3)
    assert n_days == 3


def test_indexed_cumulative_returns_reports_actual_days_for_short_history():
    """A portfolio with fewer overlapping days than the window must report the
    real count, not silently claim a full window -- this is what lets the app
    tell a short-history portfolio apart from a full trailing-year one."""
    dates = pd.date_range("2026-01-01", periods=5, freq="B")
    user = pd.Series([0.01] * 5, index=dates)
    ref = pd.Series([0.01] * 5, index=dates)
    _, _, n_days = fl.indexed_cumulative_returns(user, ref, window=fl.WINDOW)
    assert n_days == 5


def test_indexed_cumulative_returns_aligns_on_overlapping_dates_only():
    """A reference date the user portfolio has no data for (e.g. before a
    short-history ticker was listed) must not sneak into the indexed path."""
    dates_user = pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07"])
    dates_ref = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"])
    user = pd.Series([0.01, 0.02, -0.01], index=dates_user)
    ref = pd.Series([0.50, 0.03, 0.01, 0.02], index=dates_ref)  # 0.50 on 01-02, before user has data
    user_indexed, ref_indexed, n_days = fl.indexed_cumulative_returns(user, ref, window=10)
    assert n_days == 3
    assert ref_indexed.iloc[0] == pytest.approx(100 * 1.03)


def test_project_scenario_formula():
    """The scenario formula is exactly beta_AI x AI_shock + beta_rest x rest_shock."""
    result = fl.project_scenario(beta_ai=0.5, beta_rest=0.3, ai_shock=-0.5, rest_shock=-0.2)
    assert result == pytest.approx(0.5 * -0.5 + 0.3 * -0.2)


def test_load_m2_shocks_reads_real_file():
    shocks = fl.load_m2_shocks()
    assert shocks["dotcom_ai_shock"] < 0
    assert shocks["dotcom_rest_shock"] < 0
    assert shocks["2022_ai_shock"] < 0
    assert shocks["2022_rest_shock"] < 0
    assert shocks["gfc_ai_shock"] < 0
    assert shocks["gfc_rest_shock"] < 0


def test_m2_table_has_gfc_window_and_m3_shocks_are_read_not_hardcoded():
    """The GFC window must be present in m2_drawdown_table.csv with all six roles,
    fully covered (no truncation), TLT's window return positive (flight to
    quality), and load_m2_shocks()'s gfc_ai_shock/gfc_rest_shock must equal
    whatever is CURRENTLY in that CSV -- proving they're read programmatically,
    not hand-typed constants that could drift out of sync with Module 2.
    """
    m2 = pd.read_csv(Path(__file__).parent.parent / "outputs" / "m2_drawdown_table.csv")
    gfc = m2[m2["window"] == "gfc"].set_index("role")

    for role in ["cap_weighted", "nasdaq", "value", "international", "bonds", "gold"]:
        assert role in gfc.index, f"GFC window is missing the '{role}' role."
    assert not gfc["truncated_start"].any(), "GFC window should have zero truncated series."
    assert gfc.loc["bonds", "window_return_pct"] > 0, "TLT's GFC window return must be positive."

    shocks = fl.load_m2_shocks()
    qqq_gfc_dd = gfc.loc["nasdaq", "max_drawdown_pct"] / 100
    iwd_gfc_dd = gfc.loc["value", "max_drawdown_pct"] / 100
    assert shocks["gfc_ai_shock"] == pytest.approx(qqq_gfc_dd)
    assert shocks["gfc_rest_shock"] == pytest.approx(iwd_gfc_dd)


def test_single_factor_regress_raises_cleanly_on_degenerate_input():
    """A 1-observation alignment must raise a clean ValueError, not crash inside
    statsmodels with a KeyError (add_constant silently skips the constant column
    when it sees only one row) -- this is the guard the X-ray app relies on to
    handle a too-short user portfolio without crashing."""
    dates = pd.date_range("2026-01-01", periods=1, freq="B")
    y1 = pd.Series([0.01], index=dates)
    x1 = pd.Series([0.02], index=dates)
    assert fl.overlapping_obs_count(y1, x1) == 1
    with pytest.raises(ValueError):
        fl.single_factor_regress(y1, x1)


def test_available_tickers_includes_full_universe(prices):
    tickers = fl.available_tickers(prices)
    for expected in ["SPY", "QQQ", "TLT", "NVDA"]:
        assert expected in tickers


def test_zero_direct_weight_tickers_exists_and_nonempty():
    """Regression test for the app crashing on a missing constant: this set must
    exist and contain at least the bond/Treasury/commodity funds the X-ray app
    treats as a known-zero direct AI weight."""
    assert fl.ZERO_DIRECT_WEIGHT_TICKERS
    for expected in ["TLT", "GLD", "BND"]:
        assert expected in fl.ZERO_DIRECT_WEIGHT_TICKERS


def test_compute_direct_weight_pct_60_40_matches_module1():
    """The default 60/40 (SPY/TLT) app portfolio must reproduce Module 1's own
    20.26% figure, not report 'not computable' -- TLT's direct AI weight is a
    known 0%, not an unknown, since it holds no equities at all."""
    direct_pct, unresolvable = fl.compute_direct_weight_pct({"SPY": 0.6, "TLT": 0.4})
    assert unresolvable == []
    assert direct_pct == pytest.approx(0.6 * fl.DIRECT_WEIGHT_PCT["SPY"], abs=1e-6)
    assert direct_pct == pytest.approx(20.26, abs=0.01)


def test_compute_direct_weight_pct_none_for_genuinely_unknown_ticker():
    """A portfolio containing a ticker with no sourced holdings weight (e.g. a
    single stock outside the AI basket) must report 'not computable' and name
    the responsible ticker(s), not silently guess a number."""
    direct_pct, unresolvable = fl.compute_direct_weight_pct({"SPY": 0.5, "TSLA": 0.5})
    assert direct_pct is None
    assert unresolvable == ["TSLA"]


def test_compute_direct_weight_pct_spy_gld_counts_gld_as_known_zero():
    """SPY + GLD: GLD should contribute a known 0%, not make the mix unresolvable."""
    direct_pct, unresolvable = fl.compute_direct_weight_pct({"SPY": 0.7, "GLD": 0.3})
    assert unresolvable == []
    assert direct_pct == pytest.approx(0.7 * fl.DIRECT_WEIGHT_PCT["SPY"], abs=1e-6)


# --- merge_selected_weights / equal_split_weights: the X-ray app's weight-editor
# ticker-add/remove logic, extracted out of the Streamlit widget layer specifically
# so it's unit-testable -- see app/xray_app.py Step 1 and the revert-bug fix there.

def test_equal_split_weights_sums_to_100_for_non_dividing_n():
    """3 tickers -> 33.33/33.33/33.34, not 33.33 x 3 = 99.99 (regression test for
    the earlier 33.33x3 remainder fix -- must not spuriously trigger the sum error)."""
    weights = fl.equal_split_weights(["A", "B", "C"])
    assert sum(weights.values()) == pytest.approx(100.0)
    assert weights["A"] == pytest.approx(33.33)
    assert weights["B"] == pytest.approx(33.33)
    assert weights["C"] == pytest.approx(33.34)


def test_equal_split_weights_empty():
    assert fl.equal_split_weights([]) == {}


def test_merge_selected_weights_preserves_weights_on_ticker_addition():
    """Adding a ticker to an existing selection must leave the other rows' weights
    untouched -- the exact bug the earlier equal-split-everything logic had."""
    merged = fl.merge_selected_weights(["A", "B", "C"], {"A": 50.0, "B": 50.0})
    assert merged == {"A": 50.0, "B": 50.0, "C": 0.0}


def test_merge_selected_weights_preserves_weights_on_ticker_removal():
    """Removing a ticker must leave the remaining rows' weights untouched."""
    merged = fl.merge_selected_weights(["A"], {"A": 30.0, "B": 70.0})
    assert merged == {"A": 30.0}


def test_merge_selected_weights_does_not_overwrite_user_edited_values():
    """A user-edited (non-round) weight must pass through the merge unchanged."""
    merged = fl.merge_selected_weights(["A", "B"], {"A": 37.5, "B": 62.5})
    assert merged == {"A": 37.5, "B": 62.5}


def test_merge_selected_weights_falls_back_to_equal_split_when_nothing_to_preserve():
    """A selection with zero overlap with existing_weights (e.g. the very first
    pick from empty) gets an equal split instead of an unhelpful wall of zeros."""
    merged = fl.merge_selected_weights(["A", "B", "C"], {})
    assert merged == fl.equal_split_weights(["A", "B", "C"])


# --- validate_weights: defensive checks on individual weight VALUES, not just
# whether the map is empty or sums to 100 -- these can only be reached via the
# shareable-link path, since the app's own number_input widgets already enforce
# [0, 100] and can't produce NaN/inf. ---

def test_validate_weights_rejects_nan():
    weights, errors, _ = fl.validate_weights({"AAPL": float("nan"), "SPY": 50.0})
    assert weights is None
    assert any("AAPL" in e for e in errors)


def test_validate_weights_rejects_negative():
    weights, errors, _ = fl.validate_weights({"AAPL": -10.0, "SPY": 110.0})
    assert weights is None
    assert any("AAPL" in e for e in errors)


def test_validate_weights_accepts_a_clean_portfolio():
    weights, errors, _ = fl.validate_weights({"AAPL": 60.0, "SPY": 40.0})
    assert errors == []
    assert weights == {"AAPL": 0.6, "SPY": 0.4}


# --- decode_portfolio_query: the shareable-link parser. Any single malformed
# pair invalidates the WHOLE link (returns None) rather than silently dropping
# just that pair or building a partial portfolio -- see the function's own
# docstring for the incident (NaN sailing through both bounds checks) this
# guards against. Ticker-universe membership is deliberately out of scope here
# (the app's caller filters against `universe` afterward). ---

def test_decode_portfolio_query_valid_link_round_trips():
    raw = fl.encode_portfolio_query({"SPY": 60.0, "TLT": 40.0})
    assert fl.decode_portfolio_query(raw) == {"SPY": 60.0, "TLT": 40.0}


def test_decode_portfolio_query_rejects_negative_weight():
    assert fl.decode_portfolio_query("AAPL:-50") is None


def test_decode_portfolio_query_rejects_weight_over_100():
    assert fl.decode_portfolio_query("AAPL:150") is None


def test_decode_portfolio_query_rejects_nan():
    assert fl.decode_portfolio_query("AAPL:nan") is None


def test_decode_portfolio_query_rejects_inf():
    assert fl.decode_portfolio_query("AAPL:inf") is None
    assert fl.decode_portfolio_query("AAPL:-inf") is None


def test_decode_portfolio_query_drops_unknown_ticker_but_keeps_the_rest():
    """Ticker validity isn't this function's job -- it should pass an unknown
    ticker through like any other, leaving the universe filter to the caller."""
    assert fl.decode_portfolio_query("ZZZZ:100") == {"ZZZZ": 100.0}


def test_decode_portfolio_query_rejects_empty_string():
    assert fl.decode_portfolio_query("") is None


def test_decode_portfolio_query_rejects_garbage():
    assert fl.decode_portfolio_query(";;;") is None


# ============================================================================
# Crash-conditional (piecewise) betas, the bootstrap band, and the data stamp.
# These use SYNTHETIC series wherever a known answer is needed -- a test that
# asserts a specific beta on live market data would start failing the next
# time the price DB is refreshed, which is a broken test, not a caught
# regression. The live-data tests below only assert relationships that must
# hold by construction.
# ============================================================================


def _synthetic_factor(n: int = 500, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.Series(rng.normal(0, 0.012, n), index=idx, name="x")


def test_downside_regress_recovers_a_symmetric_beta():
    """A series built with one constant slope must show up-beta == down-beta."""
    x = _synthetic_factor()
    y = 0.6 * x
    result = fl.downside_regress(y, x, window=len(x))
    assert result["beta_up"] == pytest.approx(0.6, abs=1e-6)
    assert result["beta_down"] == pytest.approx(0.6, abs=1e-6)
    assert result["asymmetry"] == pytest.approx(0.0, abs=1e-6)


def test_downside_regress_recovers_a_known_asymmetry():
    """A series built with a steeper down-day slope must recover both slopes."""
    x = _synthetic_factor()
    y = np.where(x < 0, 0.9 * x, 0.4 * x)
    y = pd.Series(y, index=x.index)
    result = fl.downside_regress(y, x, window=len(x))
    assert result["beta_up"] == pytest.approx(0.4, abs=1e-6)
    assert result["beta_down"] == pytest.approx(0.9, abs=1e-6)
    assert result["asymmetry"] == pytest.approx(0.5, abs=1e-6)


def test_downside_regress_raises_when_a_state_is_too_thin():
    """Too few down-days must raise a clear ValueError, not return a wild slope."""
    x = _synthetic_factor(n=200)
    x = x.abs()                      # no down days at all
    x.iloc[:5] = -0.01               # five, still under MIN_STATE_OBS
    with pytest.raises(ValueError):
        fl.downside_regress(0.5 * x, x, window=len(x))


def test_two_factor_downside_recovers_known_state_betas():
    x_ai = _synthetic_factor(seed=11)
    x_rest = _synthetic_factor(seed=12).rename("rest")
    y = pd.Series(
        np.where(x_ai < 0, 0.8, 0.3) * x_ai + np.where(x_rest < 0, 0.5, 0.2) * x_rest,
        index=x_ai.index,
    )
    result = fl.two_factor_downside_regress(y, x_ai, x_rest, window=len(x_ai))
    assert result["beta_ai_up"] == pytest.approx(0.3, abs=1e-6)
    assert result["beta_ai_down"] == pytest.approx(0.8, abs=1e-6)
    assert result["beta_rest_up"] == pytest.approx(0.2, abs=1e-6)
    assert result["beta_rest_down"] == pytest.approx(0.5, abs=1e-6)


def test_conditional_projection_reduces_to_symmetric_when_betas_match():
    """With equal up/down betas the conditional formula IS project_scenario."""
    betas = {"beta_ai_up": 0.5, "beta_ai_down": 0.5, "beta_rest_up": 0.4, "beta_rest_down": 0.4}
    assert fl.project_scenario_conditional(betas, -0.5, -0.3) == pytest.approx(
        fl.project_scenario(0.5, 0.4, -0.5, -0.3)
    )


def test_conditional_projection_picks_the_state_matched_beta():
    """Negative shocks must use down-betas, positive shocks up-betas."""
    betas = {"beta_ai_up": 0.3, "beta_ai_down": 0.9, "beta_rest_up": 0.2, "beta_rest_down": 0.6}
    assert fl.project_scenario_conditional(betas, -1.0, -1.0) == pytest.approx(-1.5)   # 0.9 + 0.6
    assert fl.project_scenario_conditional(betas, 1.0, 1.0) == pytest.approx(0.5)      # 0.3 + 0.2
    # mixed: a falling AI basket alongside a rising rest-of-market factor
    assert fl.project_scenario_conditional(betas, -1.0, 1.0) == pytest.approx(-0.7)    # -0.9 + 0.2


def test_bootstrap_band_brackets_the_point_estimate():
    x = _synthetic_factor()
    rng = np.random.default_rng(3)
    y = 0.6 * x + pd.Series(rng.normal(0, 0.004, len(x)), index=x.index)
    result = fl.bootstrap_beta_ci(y, x, window=len(x), n_draws=200)
    assert result["lo"] < result["beta"] < result["hi"]
    assert result["beta"] == pytest.approx(
        fl.single_factor_regress(y, x, window=len(x))["beta"], abs=1e-9
    )
    assert result["lo"] < 0.6 < result["hi"]


def test_bootstrap_is_reproducible_for_a_given_seed():
    x = _synthetic_factor()
    y = 0.6 * x
    first = fl.bootstrap_beta_ci(y, x, window=len(x), n_draws=100, seed=42)
    second = fl.bootstrap_beta_ci(y, x, window=len(x), n_draws=100, seed=42)
    assert first == second


def test_bootstrap_raises_on_a_window_too_short_to_block():
    x = _synthetic_factor(n=10)
    with pytest.raises(ValueError):
        fl.bootstrap_beta_ci(0.5 * x, x, window=10)


def test_data_through_reports_the_conservative_core_ticker_date():
    """data_through must report the date through which the tickers the app's math
    actually depends on (the AI basket + reference portfolios) ALL have real data --
    not the panel's raw max, which is just whichever ticker happens to be most
    current and can be a completely unrelated one. This is the exact shape of bug
    that let forward-filled pct_change() silently fabricate zero returns for stale
    tickers (see LIMITATIONS.md): a synthetic panel here with a recently-added
    ticker two days ahead of the core tickers must NOT be reported as "current".
    """
    dates = pd.date_range("2026-01-01", periods=5, freq="B")
    panel = pd.DataFrame(
        {
            "SPY": [100.0, 101.0, 102.0, np.nan, np.nan],   # core, stale 2 days
            "NVDA": [50.0, 51.0, 52.0, 53.0, np.nan],       # core, stale 1 day
            "RECENTLY_ADDED": [10.0, 11.0, 12.0, 13.0, 14.0],  # non-core, most current ticker in the panel
        },
        index=dates,
    )
    result = fl.data_through(panel, core_tickers=["SPY", "NVDA"])
    assert result["date"] == dates[2].strftime("%Y-%m-%d")  # min(last_valid_index) across SPY/NVDA
    assert result["panel_max"] == dates[4].strftime("%Y-%m-%d")
    assert result["stale"] is True


def test_data_through_not_stale_when_core_tickers_are_current():
    """When the core tickers ARE the panel's most current data, stale must be False
    and "date" must equal "panel_max" -- the non-degraded case."""
    dates = pd.date_range("2026-01-01", periods=3, freq="B")
    panel = pd.DataFrame({"SPY": [100.0, 101.0, 102.0], "NVDA": [50.0, 51.0, 52.0]}, index=dates)
    result = fl.data_through(panel, core_tickers=["SPY", "NVDA"])
    assert result["date"] == result["panel_max"] == dates[-1].strftime("%Y-%m-%d")
    assert result["stale"] is False


def test_data_through_raises_when_no_core_tickers_present():
    dates = pd.date_range("2026-01-01", periods=2, freq="B")
    panel = pd.DataFrame({"UNRELATED": [1.0, 2.0]}, index=dates)
    with pytest.raises(ValueError):
        fl.data_through(panel, core_tickers=["SPY", "NVDA"])


def test_live_downside_split_is_consistent_with_the_symmetric_beta(simple_returns, ai_log):
    """On real data the symmetric beta must sit between the up- and down-day betas.

    A relationship that holds by construction (the pooled slope is a weighted
    blend of the two state slopes), so this catches a wiring error without
    pinning any number that a data refresh would move.
    """
    y_log = fl.to_log_returns(simple_returns["SPY"])
    symmetric = fl.single_factor_regress(y_log, ai_log)["beta"]
    split = fl.downside_regress(y_log, ai_log)
    lo, hi = sorted((split["beta_up"], split["beta_down"]))
    assert lo - 0.05 <= symmetric <= hi + 0.05
