"""SQLite persistence for Portfolio Intelligence.

The Streamlit app (app.py) writes holdings and computed metrics here.
The FastAPI service (api.py) only reads from the same file. Timestamps are
stored as UTC ISO-8601 strings so both processes agree on staleness.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

DB_PATH = Path(__file__).with_name("data.db")

MAX_METRIC_AGE = timedelta(days=1)

SCHEMA = """
CREATE TABLE IF NOT EXISTS holdings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT    NOT NULL UNIQUE,
    shares      REAL    NOT NULL,
    buy_price   REAL    NOT NULL DEFAULT 0,
    date_added  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_metrics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker        TEXT    NOT NULL,
    date          TEXT    NOT NULL,
    period        TEXT    NOT NULL DEFAULT '6mo',
    returns       REAL,
    volatility    REAL,
    sharpe_ratio  REAL,
    rsi           REAL,
    macd          REAL,
    calculated_at TEXT    NOT NULL,
    UNIQUE (ticker, date, period)
);

CREATE INDEX IF NOT EXISTS idx_metrics_lookup
    ON portfolio_metrics (ticker, period, calculated_at DESC);
"""


@contextmanager
def connect(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path or DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    with connect(db_path) as conn:
        # WAL lets the API read while Streamlit writes.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def age_of(row: Mapping[str, Any] | None) -> timedelta | None:
    """How long ago a metrics row was calculated."""
    if row is None:
        return None
    calculated_at = _parse_ts(row["calculated_at"])
    if calculated_at is None:
        return None
    return datetime.now(timezone.utc) - calculated_at


def is_fresh(
    row: Mapping[str, Any] | None,
    max_age: timedelta = MAX_METRIC_AGE,
) -> bool:
    age = age_of(row)
    return age is not None and age <= max_age


# --- holdings ---------------------------------------------------------------


def get_holdings(db_path: Path | str | None = None) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, ticker, shares, buy_price, date_added "
            "FROM holdings ORDER BY ticker"
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_holding(
    ticker: str,
    shares: float,
    buy_price: float = 0.0,
    db_path: Path | str | None = None,
) -> None:
    """Insert a holding, or update shares/buy price if the ticker exists."""
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO holdings (ticker, shares, buy_price, date_added)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (ticker) DO UPDATE SET
                shares = excluded.shares,
                buy_price = excluded.buy_price
            """,
            (ticker.upper().strip(), float(shares), float(buy_price), _utcnow()),
        )


def delete_holding(ticker: str, db_path: Path | str | None = None) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "DELETE FROM holdings WHERE ticker = ?", (ticker.upper().strip(),)
        )


def save_holdings(
    holdings: Iterable[Mapping[str, Any]],
    db_path: Path | str | None = None,
) -> None:
    """Make the stored holdings match the given list.

    Each item needs `ticker` and `shares`, and optionally `buy_price`.
    Tickers no longer present are removed; `date_added` is preserved for
    tickers that were already stored.
    """
    incoming = [
        (
            str(h["ticker"]).upper().strip(),
            float(h.get("shares") or 0.0),
            float(h.get("buy_price") or 0.0),
        )
        for h in holdings
        if str(h.get("ticker") or "").strip()
    ]
    now = _utcnow()
    with connect(db_path) as conn:
        if incoming:
            placeholders = ",".join("?" for _ in incoming)
            conn.execute(
                f"DELETE FROM holdings WHERE ticker NOT IN ({placeholders})",
                [ticker for ticker, _, _ in incoming],
            )
        else:
            conn.execute("DELETE FROM holdings")
        conn.executemany(
            """
            INSERT INTO holdings (ticker, shares, buy_price, date_added)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (ticker) DO UPDATE SET
                shares = excluded.shares,
                buy_price = excluded.buy_price
            """,
            [(ticker, shares, buy_price, now) for ticker, shares, buy_price in incoming],
        )


# --- metrics ----------------------------------------------------------------


def save_metrics(
    metrics: Iterable[Mapping[str, Any]],
    db_path: Path | str | None = None,
) -> None:
    """Insert or refresh metrics rows.

    Each item needs `ticker`, and optionally `date`, `period`, `returns`,
    `volatility`, `sharpe_ratio`, `rsi`, `macd`. Re-analyzing the same
    ticker/date/period overwrites the previous row rather than piling up
    duplicates.
    """
    now = _utcnow()
    today = datetime.now(timezone.utc).date().isoformat()
    payload = [
        (
            str(m["ticker"]).upper().strip(),
            str(m.get("date") or today),
            str(m.get("period") or "6mo"),
            _as_float(m.get("returns")),
            _as_float(m.get("volatility")),
            _as_float(m.get("sharpe_ratio")),
            _as_float(m.get("rsi")),
            _as_float(m.get("macd")),
            now,
        )
        for m in metrics
        if str(m.get("ticker") or "").strip()
    ]
    if not payload:
        return
    with connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO portfolio_metrics
                (ticker, date, period, returns, volatility, sharpe_ratio,
                 rsi, macd, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (ticker, date, period) DO UPDATE SET
                returns = excluded.returns,
                volatility = excluded.volatility,
                sharpe_ratio = excluded.sharpe_ratio,
                rsi = excluded.rsi,
                macd = excluded.macd,
                calculated_at = excluded.calculated_at
            """,
            payload,
        )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if result != result else result  # drop NaN


def get_latest_metrics(
    period: str | None = None,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Most recent metrics row per ticker, newest first."""
    inner_filter = "WHERE period = ?" if period else ""
    outer_filter = "WHERE m.period = ?" if period else ""
    params: tuple[Any, ...] = (period, period) if period else ()
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT m.* FROM portfolio_metrics m
            JOIN (
                SELECT ticker, MAX(calculated_at) AS calculated_at
                FROM portfolio_metrics {inner_filter}
                GROUP BY ticker
            ) latest
              ON m.ticker = latest.ticker
             AND m.calculated_at = latest.calculated_at
            {outer_filter}
            GROUP BY m.ticker
            ORDER BY m.calculated_at DESC, m.ticker
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def get_latest_metrics_for_ticker(
    ticker: str,
    period: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any] | None:
    clauses = ["ticker = ?"]
    params: list[Any] = [ticker.upper().strip()]
    if period:
        clauses.append("period = ?")
        params.append(period)
    with connect(db_path) as conn:
        row = conn.execute(
            f"""
            SELECT * FROM portfolio_metrics
            WHERE {' AND '.join(clauses)}
            ORDER BY calculated_at DESC, id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
    return dict(row) if row else None
