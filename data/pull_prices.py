"""Pull daily adjusted close prices for all project tickers into SQLite.

Source: yfinance, max available history, auto-adjusted close (splits + dividends).
Run: python data/pull_prices.py
"""

import argparse
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
    # Enterprise/infrastructure names the AI trade actually runs through --
    # networking, hybrid-cloud/hardware, and the security/data/workflow
    # software AI deployments depend on -- as distinct from the consumer-
    # facing/pure-growth names already in "Mega-cap / Growth Stocks" below.
    # Priority addition: this app's whole premise is measuring AI exposure,
    # and these were some of the most directly AI-exposed names missing from
    # the universe.
    "AI Infrastructure": ["IBM", "CSCO", "ANET", "DELL", "SNOW", "CRWD", "PANW", "NOW"],
    # Chip-design/fab-equipment names -- distinct from AI Infrastructure's
    # software/networking angle and from the handful of chipmakers already
    # scattered in the AI basket/Mega-cap group (AVGO, MU, QCOM, AMD): these
    # are the analog/equipment side of the same trade (ASML makes the
    # lithography machines the whole industry depends on).
    "Semiconductors": ["TXN", "LRCX", "KLAC", "ASML"],
    "Mega-cap / Growth Stocks": [
        "TSLA", "AMD", "PLTR", "NFLX", "ORCL", "CRM", "INTC", "MU", "QCOM",
        "ADBE", "UBER", "SHOP", "COIN", "PYPL", "SOFI", "RBLX",
    ],
    # BRK-B: Yahoo Finance's own symbol for Berkshire Hathaway Class B is "BRK-B"
    # (hyphen, not the NYSE-style "BRK.B" or a plain "BRKB") -- used as-is below.
    "Financials": ["JPM", "BAC", "V", "MA", "BRK-B", "GS", "WFC", "C", "AXP", "MS", "SCHW", "BLK"],
    "Energy": ["XOM", "CVX", "COP"],
    "Healthcare": ["JNJ", "UNH", "LLY", "PFE", "MRK", "ABBV", "ABT", "TMO", "CVS", "AMGN"],
    "Consumer": [
        "WMT", "COST", "HD", "MCD", "NKE", "DIS", "KO", "PG", "PEP", "SBUX", "TGT",
        "LOW", "CMG", "BKNG", "ABNB",
    ],
    "Industrials": ["BA", "CAT", "GE", "HON", "UPS", "LMT"],
    # Popular household-name carriers, missing entirely from the universe
    # until now despite being some of the most widely held income/value
    # stocks a self-directed investor would search for.
    "Communication Services": ["T", "VZ", "TMUS"],
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


def refresh_ticker(conn: sqlite3.Connection, ticker: str) -> dict | None:
    """Extend one already-cached ticker's series up to the latest available date.

    Fetches only the tail from its current last date forward (not a full
    re-pull), so this is cheap and idempotent. Returns None on a download
    error; otherwise a dict with new_rows == 0 for a ticker that has nothing
    newer than what's cached (already current, or delisted/no longer trading
    -- both look the same from here, so callers should say so rather than
    treating it as a failure).
    """
    last_date = conn.execute(
        "SELECT MAX(date) FROM prices WHERE ticker = ?", (ticker,)
    ).fetchone()[0]
    try:
        hist = yf.Ticker(ticker).history(start=last_date, auto_adjust=True)
    except Exception as e:  # same rationale as pull_ticker: one bad symbol can't crash the run
        print(f"  SKIPPED {ticker}: refresh download error ({e})")
        return None
    if hist.empty:
        return {"new_rows": 0, "last_date": last_date}
    rows = [
        (idx.strftime("%Y-%m-%d"), ticker, float(row["Close"]))
        for idx, row in hist.iterrows()
    ]
    new_rows = [r for r in rows if r[0] > last_date]
    if new_rows:
        # Write the whole fetched tail, including the overlapping last_date row
        # (INSERT OR REPLACE on the (date, ticker) primary key), not just the
        # new_rows slice -- cheap insurance against yfinance revising a recent
        # close (e.g. a late dividend/split adjustment).
        conn.executemany(
            "INSERT OR REPLACE INTO prices (date, ticker, adj_close) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()
        last_date = rows[-1][0]
    return {"new_rows": len(new_rows), "last_date": last_date}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true",
        help="Also extend every ticker already cached in the DB up to the latest "
             "available date, before pulling any genuinely new tickers. Default "
             "(no flag): cached tickers are left untouched, exactly as before -- "
             "nothing silently re-downloads.",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    # Tickers already cached from a prior run are left untouched by default, not
    # re-fetched. Re-pulling an existing ticker with a fresh yfinance call could
    # append newer trading days to its series -- that would shift the trailing
    # 252/756-day windows m1/m3 use ("tail(window)" of whatever's latest) and
    # silently break the byte-identical-output guarantee this task requires.
    # Universe expansion must be strictly additive at the data layer, not just
    # at the code layer -- UNLESS --refresh is explicitly passed, which exists
    # precisely to bring already-cached tickers back in sync with newer ones
    # (see LIMITATIONS.md's forward-fill entry for why that sync matters).
    already_cached = {row[0] for row in conn.execute("SELECT DISTINCT ticker FROM prices")}

    if args.refresh:
        print(f"[refresh] extending {len(already_cached)} already-cached ticker(s) to latest available date...")
        extended, unchanged, failed = [], [], []
        for ticker in sorted(already_cached):
            result = refresh_ticker(conn, ticker)
            if result is None:
                failed.append(ticker)
            elif result["new_rows"] == 0:
                print(f"  {ticker}: no data newer than {result['last_date']} "
                      f"(already current, or no longer trading)")
                unchanged.append(ticker)
            else:
                print(f"  {ticker}: +{result['new_rows']} row(s), now through {result['last_date']}")
                extended.append(ticker)
            time.sleep(0.3)  # be polite to the API
        print(f"[refresh] done: {len(extended)} extended, {len(unchanged)} already current/delisted, "
              f"{len(failed)} failed.\n")

    all_groups = dict(TICKER_GROUPS)
    all_groups.update(XRAY_UNIVERSE)

    seen: set[str] = set()
    skipped: list[str] = []

    for group, tickers in all_groups.items():
        print(f"[{group}]")
        for ticker in tickers:
            if ticker in already_cached:
                note = " (refreshed above)" if args.refresh else ""
                print(f"  {ticker}: already cached from a prior run, leaving untouched{note}")
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

    print_last_date_distribution(conn)
    conn.close()


def print_last_date_distribution(conn: sqlite3.Connection) -> None:
    """Per-ticker last date (MAX(date) grouped by ticker), not the panel's
    overall max -- the panel's max is the union across tickers and hides any
    ticker still lagging behind (that gap is exactly what silently corrupted
    every regression via pandas' forward-filling pct_change default; see
    LIMITATIONS.md). A single date here means the DB is genuinely in sync.
    """
    rows = conn.execute("SELECT ticker, MAX(date) AS last_date FROM prices GROUP BY ticker").fetchall()
    by_date: dict[str, list[str]] = {}
    for ticker, last_date in rows:
        by_date.setdefault(last_date, []).append(ticker)

    print(f"\nPer-ticker last date, {len(rows)} ticker(s):")
    for date in sorted(by_date, reverse=True):
        tickers = sorted(by_date[date])
        print(f"  {date}: {len(tickers)} ticker(s)" + (f" -- {', '.join(tickers)}" if len(tickers) <= 8 else ""))

    if len(by_date) == 1:
        print("  All tickers end on the same date -- panel is in sync.")
    else:
        majority_date = max(by_date, key=lambda d: len(by_date[d]))
        print(f"  NOT in sync. Majority date: {majority_date}. "
              f"Laggard ticker(s) not on that date: {', '.join(sorted(t for d, ts in by_date.items() if d != majority_date for t in ts))}")


if __name__ == "__main__":
    main()
