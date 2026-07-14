"""Pull daily adjusted close prices for all project tickers into SQLite.

Source: yfinance, max available history, auto-adjusted close (splits + dividends).
Run: python data/pull_prices.py
"""

import sqlite3
import time
from pathlib import Path

import yfinance as yf

DB_PATH = Path(__file__).parent / "prices.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

TICKER_GROUPS = {
    "ai_basket": ["NVDA", "MSFT", "GOOGL", "META", "AMZN", "AAPL", "AVGO", "TSM"],
    "diversified": ["SPY", "VT", "QQQ", "RSP"],
    "alternatives": ["VTV", "EFA", "TLT", "GLD"],
    "dotcom_indices": ["^GSPC", "^IXIC", "^NDX"],
    # IWD (Russell 1000 Value, inception 2000-05-26) -- VTV doesn't reach back to the
    # dot-com crash (starts 2004), so IWD stands in as the Module 2 value proxy for
    # that window. Covers all but the first ~2.5 months of the Mar 2000-Oct 2002 replay.
    "dotcom_value_proxy": ["IWD"],
    # Low/near-zero AI exposure reference ETFs, added for the X-ray app (Module 4) so
    # users can build a portfolio genuinely light on AI/mega-cap tech, not just ones
    # already in the research modules' fixed ticker set. Sector/style picks chosen
    # for minimal overlap with the AI basket's names: defensive sectors, real estate,
    # dividend/value tilt, and small-cap (dilutes mega-cap concentration by construction,
    # same logic as RSP).
    "low_ai_reference": [
        "XLU",   # Utilities Select Sector SPDR -- defensive, minimal tech
        "XLP",   # Consumer Staples Select Sector SPDR -- defensive, minimal tech
        "XLV",   # Health Care Select Sector SPDR -- low tech overlap
        "VNQ",   # Vanguard Real Estate ETF -- minimal tech/AI overlap
        "SCHD",  # Schwab US Dividend Equity ETF -- value/dividend tilt
        "IJR",   # iShares Core S&P Small-Cap ETF -- small-cap, dilutes mega-cap concentration
    ],
}

# X-ray app universe expansion (app v2): popular, high-recognition ETFs and single
# stocks so users can build a portfolio out of names they actually recognize/hold,
# not just this project's original research tickers. Purely additive -- none of the
# research modules (m1/m2/m3) read this dict, so adding to it cannot change their
# output. Organized by category for the app's grouped ticker picker. Some tickers
# already exist in TICKER_GROUPS above (SCHD, IWD, XLV) and are intentionally
# repeated here so the app's category display is complete; main() below dedupes
# before pulling so nothing is downloaded twice.
XRAY_UNIVERSE = {
    "Broad US": ["VOO", "IVV", "VTI", "ITOT", "SCHB"],
    "Nasdaq / Growth": ["QQQM", "VUG", "SCHG", "IWF"],
    "Dividend / Value": ["SCHD", "VIG", "VYM", "DVY", "IWD"],
    "Small / Mid Cap": ["IWM", "IJH", "VB"],
    "Sector / Theme": ["XLK", "SMH", "SOXX", "XLE", "XLF", "XLV", "XLI", "ARKK"],
    "International": ["VXUS", "VEA", "VWO", "IEFA", "IEMG"],
    "Bonds / Income": ["BND", "AGG", "IEF", "SHY", "LQD", "HYG", "JEPI"],
    "Commodities / Alt": ["IAU", "SLV", "DBC"],
    "Mega-cap / Growth Stocks": [
        "TSLA", "AMD", "PLTR", "NFLX", "ORCL", "CRM", "INTC", "MU", "QCOM",
        "ADBE", "UBER", "SHOP", "COIN",
    ],
    # BRK-B: Yahoo Finance's own symbol for Berkshire Hathaway Class B is "BRK-B"
    # (hyphen, not the NYSE-style "BRK.B" or a plain "BRKB") -- used as-is below.
    "Financials": ["JPM", "BAC", "V", "MA", "BRK-B", "GS"],
    "Energy": ["XOM", "CVX"],
    "Healthcare": ["JNJ", "UNH", "LLY", "PFE"],
    "Consumer": ["WMT", "COST", "HD", "MCD", "NKE", "DIS", "KO", "PG", "PEP"],
    "Industrials": ["BA", "CAT", "GE"],
}

ALL_TICKERS = [t for group in TICKER_GROUPS.values() for t in group]

# A minimum row count below which a "successful" pull is treated as too short to be
# useful (e.g. a brand-new listing or a data glitch) and is skipped rather than
# stored -- distinct from MIN_REGRESSION_OBS in factor_lib.py, which guards the
# regression step itself.
MIN_HISTORY_ROWS = 10


def categories_for_app() -> dict:
    """Category -> ticker list, for the app's grouped ticker picker.

    Combines the original research groups (labeled) with XRAY_UNIVERSE. Callers
    should still filter against `factor_lib.available_tickers()` -- this just
    describes how to group whatever's actually in the DB, it doesn't guarantee
    every ticker listed here downloaded successfully.
    """
    cats = {
        "AI Basket": TICKER_GROUPS["ai_basket"],
        "Diversified (research)": TICKER_GROUPS["diversified"],
        "Alternatives (research)": TICKER_GROUPS["alternatives"],
        "Low/No-AI Reference": TICKER_GROUPS["low_ai_reference"],
        "Indices (reference only)": TICKER_GROUPS["dotcom_indices"],
    }
    cats.update(XRAY_UNIVERSE)
    return cats


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())


def pull_ticker(ticker: str) -> list[tuple[str, str, float]]:
    """Fetch one ticker's max-history daily closes. Never raises -- any failure
    (network error, bad symbol, empty/short response) is caught by the caller via
    the returned (rows, reason) not being clean; this function itself just returns
    an empty list and prints why, so one bad symbol can't crash the whole pull.
    """
    try:
        hist = yf.Ticker(ticker).history(period="max", auto_adjust=True)
    except Exception as e:  # yfinance can raise on network errors, bad symbols, etc.
        print(f"  SKIPPED {ticker}: download error ({e})")
        return []
    if hist.empty:
        print(f"  SKIPPED {ticker}: no data returned (bad symbol or delisted)")
        return []
    if len(hist) < MIN_HISTORY_ROWS:
        print(f"  SKIPPED {ticker}: only {len(hist)} row(s), below the {MIN_HISTORY_ROWS}-row minimum")
        return []
    rows = [
        (idx.strftime("%Y-%m-%d"), ticker, float(row["Close"]))
        for idx, row in hist.iterrows()
    ]
    return rows


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    # Tickers already cached from a prior run are left untouched, not re-fetched.
    # Re-pulling an existing ticker with a fresh yfinance call could append newer
    # trading days to its series -- that would shift the trailing 252/756-day
    # windows m1/m3 use ("tail(window)" of whatever's latest) and silently break
    # the byte-identical-output guarantee this task requires. Universe expansion
    # must be strictly additive at the data layer, not just at the code layer.
    already_cached = {row[0] for row in conn.execute("SELECT DISTINCT ticker FROM prices")}

    all_groups = dict(TICKER_GROUPS)
    all_groups.update(XRAY_UNIVERSE)

    seen: set[str] = set()
    skipped: list[str] = []

    for group, tickers in all_groups.items():
        print(f"[{group}]")
        for ticker in tickers:
            if ticker in already_cached:
                print(f"  {ticker}: already cached from a prior run, leaving untouched")
                continue
            if ticker in seen:
                print(f"  {ticker}: already pulled under an earlier group, skipping re-download")
                continue
            seen.add(ticker)

            rows = pull_ticker(ticker)
            if rows:
                conn.executemany(
                    "INSERT OR REPLACE INTO prices (date, ticker, adj_close) VALUES (?, ?, ?)",
                    rows,
                )
                conn.commit()
                print(f"  {ticker}: {len(rows)} rows, {rows[0][0]} -> {rows[-1][0]}")
            else:
                skipped.append(ticker)
            time.sleep(0.3)  # be polite to the API

    total = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    distinct_tickers = conn.execute("SELECT COUNT(DISTINCT ticker) FROM prices").fetchone()[0]
    print(f"\nDone. {total} total rows across {distinct_tickers} tickers in {DB_PATH}")
    if skipped:
        print(f"Skipped ({len(skipped)}): {', '.join(skipped)}")
    else:
        print("Skipped: none")
    conn.close()


if __name__ == "__main__":
    main()
