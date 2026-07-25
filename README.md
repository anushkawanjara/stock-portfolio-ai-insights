# Portfolio Intelligence

A Streamlit app that analyzes a stock portfolio: returns, risk metrics,
technical indicators, chart patterns, news sentiment, and an AI coach that
explains it all in plain English.

Results are saved to a local SQLite database, and a small read-only FastAPI
service exposes them over HTTP.

## Setup

```bash
pip install -r requirements.txt
python -m textblob.download_corpora
```

Create `.streamlit/secrets.toml` with your API keys (this file is gitignored):

```toml
NEWS_API_KEY = "your-newsapi-key"   # optional — https://newsapi.org
GROQ_API_KEY = "your-groq-key"      # optional — https://console.groq.com/keys
```

Both keys are optional. Without them, the app still does all price, risk, and
pattern analysis; it just skips news sentiment and the AI coach.

## Running the two services

They are independent processes and can run at the same time. `data.db` is
created automatically on first launch.

**Streamlit app** — the UI, and the only thing that writes to the database:

```bash
streamlit run app.py
```

Opens at http://localhost:8501

**FastAPI service** — read-only access to whatever the app has saved:

```bash
uvicorn api:app --reload
```

Opens at http://localhost:8000, with interactive docs at
http://localhost:8000/docs

## API endpoints

All endpoints are read-only `GET` requests that return JSON. The API never
fetches market data or recalculates anything — it only reads rows the
Streamlit app has already written, so run **Analyze Portfolio** in the app at
least once before calling it.

| Endpoint | Returns |
| --- | --- |
| `/portfolio/holdings` | Every saved holding: `ticker`, `shares`, `buy_price`, `date_added`. |
| `/portfolio/metrics` | The most recent metrics row per holding: `returns`, `volatility`, `sharpe_ratio`, `rsi`, `macd`, plus the `date`/`period` they cover and an `is_stale` flag. Accepts an optional `?period=` filter (`1mo`, `3mo`, `6mo`, `1y`, `ytd`, `2y`). |
| `/stock/{ticker}/indicators` | `rsi`, `macd`, and `sharpe_ratio` for one ticker, with `period`, `date`, `calculated_at`, and `is_stale`. Returns `404` if that ticker has never been analyzed. Also accepts `?period=`. |

Example:

```bash
curl http://localhost:8000/portfolio/metrics
curl http://localhost:8000/stock/AAPL/indicators?period=6mo
```

## How data is stored

`database.py` owns a local SQLite file, `data.db`, with two tables:

- **`holdings`** — `id`, `ticker`, `shares`, `buy_price`, `date_added`. Kept in
  sync with the holdings form each time you analyze, so your portfolio is
  still there after a restart.
- **`portfolio_metrics`** — `id`, `ticker`, `date`, `period`, `returns`,
  `volatility`, `sharpe_ratio`, `rsi`, `macd`, `calculated_at`. One row per
  ticker per trading date per time window; re-analyzing overwrites the
  matching row instead of appending duplicates.

`period` is stored alongside each metrics row because indicators are only
meaningful for the window they were computed over — a 1-month RSI should never
be reused for a 2-year view.

### When cached values get reused

On startup the app loads your saved holdings and shows a **Last saved
snapshot** table straight from the database, with no network calls.

When you hit **Analyze Portfolio**, any ticker whose saved metrics are less
than a day old (for that same time window) reuses the stored RSI, MACD,
volatility, and Sharpe instead of recomputing them. Stale or missing rows are
recalculated and written back. Tick **Recalculate from scratch** to bypass this.

Price history itself is not stored in the database; it is fetched from Yahoo
Finance and cached in memory for an hour, since the charts and pattern
detection need the full series.

`data.db` is gitignored — it is local state, not source code.

## Disclaimer

Educational tool only. Nothing here is financial advice.
