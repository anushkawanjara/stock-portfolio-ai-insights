# AI-powered Portfolio Intelligence Platform

This project is a Python app that helps beginners track, analyze, and understand their current stock holdings in plain English. Rather than just having technical indicators, this platform combines real-time market data, computed portfolio metrics with explanations, and an AI chat layer for users to ask any questions about their own portfolio holdings. 

The platform pulls live data from Yahoo Finance, a News API, and Groq which is an AI platform, calculates portfolio-level metrics and technical indicators, and adds results to a local database.

Built with **Streamlit** (UI), **SQLite** (persistence), and **FastAPI** (read-only API over the same database).

> Educational tool only. Not financial advice. Does **not** pick stocks or promise the best day to invest.

---
## Video
https://www.loom.com/share/68115235a2164d6a8618173fc653433a

---

## What it does

| Area | Features |
| --- | --- |
| **Portfolio** | Holdings input, period returns, P&L vs cost basis, performance chart, Sharpe & volatility |
| **Beginner guidance** | Concentration check, portfolio trend context, DCA-style notes for adding money |
| **Indicators** | RSI, MACD, Bollinger %B, ticker Sharpe — explained in plain English |
| **News** | Optional NewsAPI headlines + sentiment; earnings/valuation from Yahoo Finance |
| **AI Insights** | Optional Groq-powered briefing + chat grounded in the latest analysis |
| **Data layer** | SQLite stores holdings & metrics; fresh metrics (under 1 day) are reused |
| **API** | FastAPI exposes holdings and metrics as JSON for other tools |

**Not a TradingView clone.** Charts are optional visual proof under the plain-English read.

---

## Stack

- Python, Streamlit, Plotly
- yfinance, `ta`, pandas, numpy
- SQLite (`database.py` → `data.db`)
- FastAPI + Uvicorn
- Optional: NewsAPI, Groq (LLM)

---

## Detailed Setup Guide

```bash
pip install -r requirements.txt
python -m textblob.download_corpora
```

### API keys (optional)

Copy the example secrets file and add your own keys:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

```toml
NEWS_API_KEY = "your-newsapi-key"   # https://newsapi.org
GROQ_API_KEY = "your-groq-key"      # https://console.groq.com/keys
```

| Without keys | Still works |
| --- | --- |
| Prices, returns, risk, indicators, beginner guidance | Yes |
| News sentiment | Needs `NEWS_API_KEY` |
| AI coach | Needs `GROQ_API_KEY` |

**`.streamlit/secrets.toml` is gitignored** — your keys never get committed.

---

## Run

**Streamlit UI** (writes to the database):

```bash
streamlit run app.py
```

Opens at http://localhost:8501

**FastAPI** (read-only; same `data.db`):

```bash
uvicorn api:app --reload
```

Opens at http://localhost:8000 · docs at http://localhost:8000/docs

Run **Analyze Portfolio** in the UI at least once before calling the API.

---

## API endpoints

| Endpoint | Returns |
| --- | --- |
| `GET /portfolio/holdings` | Saved holdings (`ticker`, `shares`, `buy_price`, `date_added`) |
| `GET /portfolio/metrics` | Latest metrics per holding (`returns`, `volatility`, `sharpe_ratio`, `rsi`, `macd`, `is_stale`). Optional `?period=` |
| `GET /stock/{ticker}/indicators` | RSI, MACD, Sharpe for one ticker. `404` if never analyzed |

```bash
curl http://localhost:8000/portfolio/metrics
curl http://localhost:8000/stock/AAPL/indicators?period=6mo
```

---

## Project layout

```
app.py          # Streamlit UI + analysis
theme.py        # Fintech styling (CSS, Plotly charts, metric cards)
database.py     # SQLite schema + read/write helpers
api.py          # FastAPI read-only service
data.db         # Local DB (gitignored; created on first run)
.streamlit/
  config.toml           # Theme
  secrets.toml.example  # Template for keys
  secrets.toml          # Your keys (gitignored)
```

### SQLite tables

- **`holdings`** — ticker, shares, buy price, date added
- **`portfolio_metrics`** — returns, volatility, Sharpe, RSI, MACD, period, calculated_at

Metrics older than a day (for the same period window) are recomputed on Analyze. Tick **Recalculate from scratch** to force a refresh.

---

## Disclaimer

This project is for learning and demonstration. Nothing here is investment advice.
