"""Read-only HTTP API over the Portfolio Intelligence database.

Runs independently of the Streamlit app and shares the same data.db file.
All numbers here were computed by app.py — this service performs no market
data fetching and no indicator math of its own.

    uvicorn api:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import database as db


class Holding(BaseModel):
    ticker: str
    shares: float
    buy_price: float
    date_added: str


class Metrics(BaseModel):
    ticker: str
    date: str
    period: str
    returns: float | None = None
    volatility: float | None = None
    sharpe_ratio: float | None = None
    rsi: float | None = None
    macd: float | None = None
    calculated_at: str
    is_stale: bool


class Indicators(BaseModel):
    ticker: str
    rsi: float | None = None
    macd: float | None = None
    sharpe_ratio: float | None = None
    period: str
    date: str
    calculated_at: str
    is_stale: bool


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Portfolio Intelligence API",
    description=(
        "Read-only access to holdings and metrics saved by the Streamlit app. "
        "Metrics are snapshots — run Analyze in the app to refresh them."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", summary="List available endpoints")
def index() -> dict[str, str]:
    return {
        "/portfolio/holdings": "All saved holdings",
        "/portfolio/metrics": "Latest saved metrics for every holding",
        "/stock/{ticker}/indicators": "RSI, MACD and Sharpe for one ticker",
        "/docs": "Interactive API documentation",
    }


@app.get(
    "/portfolio/holdings",
    response_model=list[Holding],
    summary="All saved holdings",
)
def read_holdings() -> list[Holding]:
    return [Holding(**row) for row in db.get_holdings()]


@app.get(
    "/portfolio/metrics",
    response_model=list[Metrics],
    summary="Latest saved metrics for every holding",
)
def read_metrics(period: str | None = None) -> list[Metrics]:
    """Most recent metrics row per ticker, optionally limited to one window
    (`1mo`, `3mo`, `6mo`, `1y`, `ytd`, `2y`)."""
    return [_to_metrics(row) for row in db.get_latest_metrics(period=period)]


@app.get(
    "/stock/{ticker}/indicators",
    response_model=Indicators,
    summary="RSI, MACD and Sharpe for one ticker",
)
def read_indicators(ticker: str, period: str | None = None) -> Indicators:
    row = db.get_latest_metrics_for_ticker(ticker, period=period)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No saved metrics for {ticker.upper()}. Add it in the "
                "Streamlit app and run Analyze first."
            ),
        )
    return Indicators(
        ticker=row["ticker"],
        rsi=row["rsi"],
        macd=row["macd"],
        sharpe_ratio=row["sharpe_ratio"],
        period=row["period"],
        date=row["date"],
        calculated_at=row["calculated_at"],
        is_stale=not db.is_fresh(row),
    )


def _to_metrics(row: dict) -> Metrics:
    return Metrics(**{k: v for k, v in row.items() if k != "id"}, is_stale=not db.is_fresh(row))
