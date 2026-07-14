CREATE TABLE IF NOT EXISTS prices (
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    adj_close REAL NOT NULL,
    PRIMARY KEY (date, ticker)
);

CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices (ticker);
