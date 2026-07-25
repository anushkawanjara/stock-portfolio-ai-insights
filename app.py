import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta
import requests
from textblob import TextBlob
from datetime import datetime, timedelta
from streamlit_searchbox import st_searchbox

import database as db
import theme as ui

st.set_page_config(
    page_title="Portfolio Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

db.init_db()
ui.inject_theme()
ui.masthead()


def get_news_api_key() -> str:
    """Server-side only — never shown to users in the browser."""
    try:
        return st.secrets.get("NEWS_API_KEY", "") or ""
    except Exception:
        return ""


def get_groq_api_key() -> str:
    """Server-side only — never shown to users in the browser."""
    try:
        return st.secrets.get("GROQ_API_KEY", "") or ""
    except Exception:
        return ""


def build_coach_context(
    portfolio_data: dict,
    total_value: float,
    total_cost: float,
    period_label: str,
    sharpe: float,
    volatility: float,
    guidance: dict | None = None,
) -> str:
    lines = [
        f"Time frame: {period_label}",
        f"Total portfolio value: ${total_value:,.2f}",
        f"Total cost basis: ${total_cost:,.2f}" if total_cost > 0 else "Cost basis: not provided",
        f"Sharpe ratio: {sharpe:.2f}",
        f"Annual volatility: {volatility:.1f}%",
        "Holdings:",
    ]
    for ticker, d in portfolio_data.items():
        weight = (d["value"] / total_value * 100) if total_value else 0
        your_ret = (
            f"{d['your_return']:.2f}%"
            if d.get("your_return") is not None
            else "n/a"
        )
        lines.append(
            f"- {ticker}: {d['shares']} shares @ ${d['current_price']:.2f}, "
            f"value ${d['value']:,.2f} ({weight:.1f}% of portfolio), "
            f"{period_label} return {d['period_return']:.2f}%, "
            f"your return {your_ret}, "
            f"RSI {d['rsi']:.1f}, MACD diff {d['macd_diff']:.3f}, "
            f"Bollinger %B {d['bb_pct']:.2f}, "
            f"signals: {', '.join(d['signals'])}"
        )
    if guidance:
        lines.append("Beginner guidance snapshot:")
        lines.append(
            f"- Concentration: {guidance['concentration']['label']} — "
            f"{guidance['concentration']['blurb']}"
        )
        lines.append(
            f"- Portfolio trend: {guidance['trend']['label']} — "
            f"{guidance['trend']['blurb']}"
        )
        lines.append(
            f"- Adding money: {guidance['entry']['label']} — "
            f"{guidance['entry']['blurb']}"
        )
    return "\n".join(lines)


def ask_coach(system: str, user_message: str, history: list | None = None) -> str:
    from groq import Groq

    client = Groq(api_key=get_groq_api_key())

    messages = [{"role": "system", "content": system}]
    for msg in history or []:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1200,
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("Groq returned an empty response.")
    return text


COACH_SYSTEM = """You are a calm, plain-English investing coach for beginners.
You only use the portfolio facts provided in the conversation.
Explain jargon when you use it. Be specific to THEIR holdings.
Give balanced takeaways and what to watch — not hype, not fear.
Never claim certainty. Always note this is educational, not financial advice.
Keep answers concise (short paragraphs or bullets)."""


news_api_key = get_news_api_key()
groq_api_key = get_groq_api_key()

TICKER_CSV = (
    "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/tickers/all.csv"
)

PERIOD_OPTIONS = {
    "1 Month": "1mo",
    "3 Months": "3mo",
    "6 Months": "6mo",
    "1 Year": "1y",
    "YTD": "ytd",
    "2 Years": "2y",
}

PERIOD_LABELS = {code: label for label, code in PERIOD_OPTIONS.items()}


@st.cache_data(show_spinner="Loading stock list…")
def load_tickers() -> pd.DataFrame:
    df = pd.read_csv(TICKER_CSV)
    df = df.dropna(subset=["symbol", "name"]).copy()
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    df["label"] = df["symbol"] + " — " + df["name"].astype(str)
    return df.sort_values("symbol").reset_index(drop=True)


tickers = load_tickers()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_close_history(ticker: str, period: str) -> pd.Series:
    hist = yf.Ticker(ticker).history(period=period)
    if hist.empty:
        return pd.Series(dtype="float64")
    return hist["Close"]


def search_stocks(searchterm: str) -> list[str]:
    if not searchterm or not searchterm.strip():
        return []

    q = searchterm.strip().lower()
    matches = tickers[
        tickers["symbol"].str.lower().str.startswith(q)
        | tickers["name"].str.lower().str.contains(q, na=False)
    ]
    return matches["label"].head(15).tolist()


def label_for_symbol(symbol: str) -> str | None:
    if not symbol:
        return None
    rows = tickers.loc[tickers["symbol"] == symbol.upper(), "label"]
    return rows.iloc[0] if not rows.empty else symbol.upper()


def ticker_from_selection(selected: str | None) -> str:
    if not selected:
        return ""
    return selected.split(" — ", 1)[0].upper().strip()


def _fmt_date(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and value:
        value = value[0]
    if hasattr(value, "strftime"):
        return value.strftime("%b %d, %Y")
    text = str(value)
    if text.startswith("datetime.date"):
        try:
            parts = text.replace("datetime.date(", "").replace(")", "")
            y, m, d = [int(x.strip()) for x in parts.split(",")]
            return datetime(y, m, d).strftime("%b %d, %Y")
        except Exception:
            return text
    return text


def _fmt_money(value):
    if not isinstance(value, (int, float)):
        return None
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.2f}"


def build_patterns(close: pd.Series, period_label: str) -> dict:
    """Keep only a short trend read — skip noisy chart-pattern spam."""
    patterns_found = []
    note = None
    sma50 = close.rolling(window=50).mean()
    sma20 = close.rolling(window=20).mean()

    if len(close) >= 50:
        prev_diff = sma20.iloc[-2] - sma50.iloc[-2]
        curr_diff = sma20.iloc[-1] - sma50.iloc[-1]

        if prev_diff < 0 and curr_diff > 0:
            patterns_found.append({
                "pattern": "Short-term trend just turned up",
                "meaning": "The 20-day average crossed above the 50-day average.",
                "action": "Momentum improved recently — still not a buy signal by itself.",
                "tone": "pos",
            })
        elif prev_diff > 0 and curr_diff < 0:
            patterns_found.append({
                "pattern": "Short-term trend just turned down",
                "meaning": "The 20-day average crossed below the 50-day average.",
                "action": "Momentum cooled — review size before adding more.",
                "tone": "neg",
            })
        elif curr_diff > 0:
            patterns_found.append({
                "pattern": "Uptrend bias",
                "meaning": "Short-term average is above the longer-term average.",
                "action": "Trend is supportive; avoid chasing if RSI is stretched.",
                "tone": "pos",
            })
        else:
            patterns_found.append({
                "pattern": "Downtrend bias",
                "meaning": "Short-term average is below the longer-term average.",
                "action": "Trend is against you — averaging in slowly is usually safer than all-in.",
                "tone": "neg",
            })
    else:
        note = (
            "Need a longer window (about 50+ trading days) for a trend read "
            f"— try a longer time frame than {period_label}."
        )

    return {"patterns": patterns_found, "note": note}


def build_beginner_guidance(
    portfolio_data: dict,
    total_value: float,
    combined_total: pd.Series,
    sharpe: float,
    volatility: float,
) -> dict:
    """Portfolio-level guidance for beginners — context, not timing advice."""
    weights = []
    stretched = []
    washed = []
    for ticker, d in portfolio_data.items():
        w = (d["value"] / total_value * 100) if total_value else 0
        weights.append((ticker, w))
        if d["rsi"] > 70 or d["bb_pct"] > 0.8:
            stretched.append(ticker)
        if d["rsi"] < 30 or d["bb_pct"] < 0.2:
            washed.append(ticker)

    weights.sort(key=lambda x: x[1], reverse=True)
    top_ticker, top_weight = weights[0] if weights else ("—", 0.0)

    if top_weight >= 70:
        concentration = {
            "label": "High concentration",
            "tone": "neg",
            "blurb": (
                f"{top_ticker} is {top_weight:.0f}% of the portfolio — "
                "one stock can swing everything."
            ),
        }
    elif top_weight >= 40:
        concentration = {
            "label": "Moderate concentration",
            "tone": "neu",
            "blurb": (
                f"{top_ticker} is {top_weight:.0f}% — meaningful, but not extreme."
            ),
        }
    else:
        concentration = {
            "label": "More balanced",
            "tone": "pos",
            "blurb": (
                f"Largest position is {top_ticker} at {top_weight:.0f}%."
            ),
        }

    series = combined_total.dropna()
    if len(series) >= 2:
        start, end = float(series.iloc[0]), float(series.iloc[-1])
        period_move = ((end - start) / start) * 100 if start else 0.0
        peak = float(series.max())
        drawdown = ((end - peak) / peak) * 100 if peak else 0.0
    else:
        period_move = 0.0
        drawdown = 0.0

    if len(series) >= 50:
        s20 = series.rolling(20).mean().iloc[-1]
        s50 = series.rolling(50).mean().iloc[-1]
        if end >= s20 >= s50:
            trend_label, trend_tone = "Uptrend", "pos"
            trend_blurb = f"Above short & longer averages · {period_move:+.1f}% this window."
        elif end <= s20 <= s50:
            trend_label, trend_tone = "Downtrend", "neg"
            trend_blurb = f"Below both averages · {period_move:+.1f}% this window."
        else:
            trend_label, trend_tone = "Mixed / sideways", "neu"
            trend_blurb = f"Choppy path · {period_move:+.1f}% · drawdown {drawdown:.1f}%."
    elif period_move > 5:
        trend_label, trend_tone = "Up over window", "pos"
        trend_blurb = f"Up {period_move:.1f}% over this window."
    elif period_move < -5:
        trend_label, trend_tone = "Down over window", "neg"
        trend_blurb = f"Down {abs(period_move):.1f}% over this window."
    else:
        trend_label, trend_tone = "Mostly flat", "neu"
        trend_blurb = f"Little net move ({period_move:+.1f}%) this window."

    if stretched and not washed:
        entry = {
            "label": "Prefer DCA",
            "tone": "neu",
            "blurb": (
                f"{', '.join(stretched)} look stretched — "
                "spread new buys over time instead of all at once."
            ),
        }
    elif washed and not stretched:
        entry = {
            "label": "Averaging zone",
            "tone": "pos",
            "blurb": (
                f"{', '.join(washed)} look washed out — "
                "size small and check news before adding."
            ),
        }
    elif drawdown <= -10:
        entry = {
            "label": "Off recent highs",
            "tone": "neu",
            "blurb": (
                f"{abs(drawdown):.0f}% below the window peak — "
                "steady DCA usually beats catching the bottom."
            ),
        }
    else:
        entry = {
            "label": "No extreme signal",
            "tone": "neu",
            "blurb": (
                "Nothing extreme — a fixed monthly amount beats timing the week."
            ),
        }

    checklist = [
        f"Largest: {top_ticker} ({top_weight:.0f}%)",
        f"Move {period_move:+.1f}% · Drawdown {drawdown:.1f}%",
        f"Sharpe {sharpe:.2f} · Vol {volatility:.1f}%",
    ]
    if stretched:
        checklist.append("Stretched: " + ", ".join(stretched))
    if washed:
        checklist.append("Washed out: " + ", ".join(washed))

    return {
        "concentration": concentration,
        "trend": {
            "label": trend_label,
            "tone": trend_tone,
            "blurb": trend_blurb,
            "period_move": period_move,
            "drawdown": drawdown,
        },
        "entry": entry,
        "checklist": checklist,
        "top_ticker": top_ticker,
        "top_weight": top_weight,
    }


def build_momentum_read(ticker: str, data: dict) -> dict:
    rsi = data["rsi"]
    macd_diff = data["macd_diff"]
    bb_pct = data["bb_pct"]

    if rsi > 70:
        rsi_take = (
            f"{ticker} has run hard lately. RSI at {rsi:.0f} usually means the "
            "stock may be stretched (“overbought”)."
        )
        rsi_label = "Stretched"
    elif rsi < 30:
        rsi_take = (
            f"{ticker} looks beaten down lately. RSI at {rsi:.0f} often means "
            "sellers have been aggressive (“oversold”)."
        )
        rsi_label = "Washed out"
    else:
        rsi_take = (
            f"{ticker}'s recent momentum looks balanced (RSI {rsi:.0f})."
        )
        rsi_label = "Normal"

    if macd_diff > 0:
        macd_take = "Short-term trend momentum is leaning up (bullish)."
        macd_label = "Up"
    else:
        macd_take = "Short-term trend momentum is leaning down (bearish)."
        macd_label = "Down"

    if bb_pct > 0.8:
        bb_take = "Price is near the top of its recent range (upper Bollinger Band)."
        bb_label = "Near high"
    elif bb_pct < 0.2:
        bb_take = "Price is near the bottom of its recent range (lower Bollinger Band)."
        bb_label = "Near low"
    else:
        bb_take = "Price is sitting in the middle of its recent range."
        bb_label = "Mid"

    hot_flags = (rsi > 70) + (bb_pct > 0.8)
    cold_flags = (rsi < 30) + (bb_pct < 0.2)
    if hot_flags >= 2 and macd_diff > 0:
        overall = (
            f"**Coach take on {ticker}:** strong with upward momentum, but "
            "pricey short-term. Fine to hold; consider waiting for a dip to add."
        )
    elif hot_flags >= 2:
        overall = (
            f"**Coach take on {ticker}:** short-term signals say it may be "
            "stretched. Pausing on new buys is the cautious move."
        )
    elif cold_flags >= 2 and macd_diff < 0:
        overall = (
            f"**Coach take on {ticker}:** weak and near recent lows. Read news "
            "and earnings before acting."
        )
    elif cold_flags >= 1 and macd_diff > 0:
        overall = (
            f"**Coach take on {ticker}:** soft, but momentum is trying to turn "
            "up. Worth watching — not an automatic buy."
        )
    else:
        overall = (
            f"**Coach take on {ticker}:** nothing extreme. Focus on valuation, "
            "news, and position size."
        )

    return {
        "overall": overall,
        "rsi_label": rsi_label,
        "macd_label": macd_label,
        "bb_label": bb_label,
        "rsi": rsi,
        "rsi_take": rsi_take,
        "macd_take": macd_take,
        "bb_take": bb_take,
    }


def fetch_news_bundle(ticker: str) -> dict:
    bundle: dict = {"ticker": ticker, "error": None, "news": None, "fundamentals": None}
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        company_name = info.get("longName", ticker)

        news_block = {"skipped": False, "error": None, "articles": [], "avg": None, "label": None, "explanation": None}
        if news_api_key:
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            url = (
                "https://newsapi.org/v2/everything"
                f"?q={company_name}&from={week_ago}"
                "&sortBy=relevancy&language=en&pageSize=5"
                f"&apiKey={news_api_key}"
            )
            news_data = requests.get(url, timeout=15).json()
            if news_data.get("status") == "error":
                news_block["error"] = news_data.get("message", "NewsAPI returned an error.")
            elif news_data.get("articles"):
                articles = news_data["articles"]
                sentiments = [
                    TextBlob(a["title"]).sentiment.polarity
                    for a in articles
                    if a.get("title")
                ]
                avg_sentiment = float(np.mean(sentiments)) if sentiments else 0.0
                if avg_sentiment > 0.1:
                    label, explanation = "Mostly Positive", (
                        f"Recent news about {ticker} has been mostly positive this week."
                    )
                elif avg_sentiment < -0.1:
                    label, explanation = "Mostly Negative", (
                        f"Recent news about {ticker} has been mostly negative this week."
                    )
                else:
                    label, explanation = "Neutral", (
                        f"News about {ticker} this week looks mixed or neutral."
                    )
                parsed = []
                for article in articles:
                    title = article.get("title") or ""
                    polarity = TextBlob(title).sentiment.polarity
                    if polarity > 0.1:
                        tag = "Positive"
                    elif polarity < -0.1:
                        tag = "Negative"
                    else:
                        tag = "Neutral"
                    parsed.append({
                        "title": title,
                        "tag": tag,
                        "source": (article.get("source", {}) or {}).get("name") or "Unknown",
                        "published": (article.get("publishedAt") or "")[:10],
                    })
                news_block.update({
                    "articles": parsed,
                    "avg": avg_sentiment,
                    "label": label,
                    "explanation": explanation,
                })
            else:
                news_block["error"] = "No recent news found for this stock."
        else:
            news_block["skipped"] = True

        pe = info.get("trailingPE", "N/A")
        valuation = None
        if isinstance(pe, (int, float)):
            if pe < 15:
                valuation = (
                    f"{ticker} looks potentially undervalued with a P/E of {pe:.1f}x."
                )
            elif pe < 25:
                valuation = (
                    f"{ticker} looks fairly valued with a P/E of {pe:.1f}x."
                )
            elif pe < 40:
                valuation = (
                    f"{ticker} looks somewhat expensive with a P/E of {pe:.1f}x."
                )
            else:
                valuation = (
                    f"{ticker} has a high P/E of {pe:.1f}x — dig into why before adding."
                )

        calendar = stock.calendar
        cal_notes = []
        if isinstance(calendar, dict) and calendar:
            earnings_date = _fmt_date(calendar.get("Earnings Date"))
            if earnings_date:
                cal_notes.append(f"Next report date: {earnings_date}")
            eps_avg = calendar.get("Earnings Average")
            eps_low = calendar.get("Earnings Low")
            eps_high = calendar.get("Earnings High")
            if isinstance(eps_avg, (int, float)):
                if isinstance(eps_low, (int, float)) and isinstance(eps_high, (int, float)):
                    cal_notes.append(
                        f"Expected EPS: {eps_avg:.2f} "
                        f"(range {eps_low:.2f}–{eps_high:.2f})"
                    )
                else:
                    cal_notes.append(f"Expected EPS: {eps_avg:.2f}")
            rev_txt = _fmt_money(calendar.get("Revenue Average"))
            if rev_txt:
                cal_notes.append(f"Expected revenue: {rev_txt.lstrip('$')}")
            ex_div = _fmt_date(calendar.get("Ex-Dividend Date"))
            div_date = _fmt_date(calendar.get("Dividend Date"))
            if ex_div:
                cal_notes.append(f"Ex-dividend date: {ex_div}")
            if div_date:
                cal_notes.append(f"Dividend paid on: {div_date}")

        eps = info.get("trailingEps", "N/A")
        forward_pe = info.get("forwardPE", "N/A")
        bundle["news"] = news_block
        bundle["fundamentals"] = {
            "eps": f"${eps:.2f}" if isinstance(eps, (int, float)) else eps,
            "pe": f"{pe:.1f}x" if isinstance(pe, (int, float)) else pe,
            "forward_pe": (
                f"{forward_pe:.1f}x"
                if isinstance(forward_pe, (int, float))
                else forward_pe
            ),
            "valuation": valuation,
            "calendar": cal_notes,
        }
    except Exception as e:
        bundle["error"] = str(e)
    return bundle


def run_portfolio_analysis(period: str, period_label: str, force_refresh: bool) -> dict | None:
    portfolio_data = {}
    total_value = 0.0
    total_cost = 0.0

    for holding in st.session_state.holdings:
        ticker = holding["ticker"]
        shares = holding["shares"]
        cost_basis = float(holding.get("cost_basis", 0.0) or 0.0)

        if not (ticker and shares > 0):
            continue
        try:
            close = fetch_close_history(ticker, period)
            if close.empty:
                st.error(f"No price data for {ticker}")
                continue

            current_price = float(close.iloc[-1])
            value = current_price * shares
            total_value += value

            start_price = float(close.iloc[0])
            period_return = ((current_price - start_price) / start_price) * 100

            your_return = None
            gain_loss = None
            if cost_basis > 0:
                your_return = ((current_price - cost_basis) / cost_basis) * 100
                cost_value = cost_basis * shares
                gain_loss = value - cost_value
                total_cost += cost_value

            cached = (
                None
                if force_refresh
                else db.get_latest_metrics_for_ticker(ticker, period)
            )
            cache_usable = db.is_fresh(cached) and all(
                cached[field] is not None
                for field in ("rsi", "macd", "volatility", "sharpe_ratio")
            )

            if cache_usable:
                rsi_value = cached["rsi"]
                macd_diff = cached["macd"]
                ticker_volatility = cached["volatility"]
                ticker_sharpe = cached["sharpe_ratio"]
                from_cache = True
            else:
                rsi = ta.momentum.RSIIndicator(close, window=14)
                rsi_value = float(rsi.rsi().iloc[-1])
                macd = ta.trend.MACD(close)
                macd_value = macd.macd().iloc[-1]
                macd_signal = macd.macd_signal().iloc[-1]
                macd_diff = float(macd_value - macd_signal)
                ticker_daily = close.pct_change().dropna()
                ticker_volatility = float(ticker_daily.std() * np.sqrt(252) * 100)
                ticker_sharpe = float(
                    (ticker_daily.mean() / ticker_daily.std()) * np.sqrt(252)
                )
                from_cache = False

            bb = ta.volatility.BollingerBands(close, window=20)
            bb_upper = float(bb.bollinger_hband().iloc[-1])
            bb_lower = float(bb.bollinger_lband().iloc[-1])
            bb_pct = (current_price - bb_lower) / (bb_upper - bb_lower)

            signals = []
            if rsi_value > 70:
                signals.append("Overbought")
            elif rsi_value < 30:
                signals.append("Oversold")
            else:
                signals.append("RSI Neutral")
            signals.append("MACD Bullish" if macd_diff > 0 else "MACD Bearish")
            if bb_pct > 0.8:
                signals.append("Near BB Upper")
            elif bb_pct < 0.2:
                signals.append("Near BB Lower")
            else:
                signals.append("BB Neutral")

            portfolio_data[ticker] = {
                "shares": shares,
                "current_price": current_price,
                "value": value,
                "period_return": period_return,
                "your_return": your_return,
                "cost_basis": cost_basis,
                "gain_loss": gain_loss,
                "history": close,
                "rsi": rsi_value,
                "macd_diff": macd_diff,
                "bb_pct": bb_pct,
                "volatility": ticker_volatility,
                "sharpe": ticker_sharpe,
                "from_cache": from_cache,
                "signals": signals,
                "patterns": build_patterns(close, period_label),
                "momentum": None,
            }
            portfolio_data[ticker]["momentum"] = build_momentum_read(
                ticker, portfolio_data[ticker]
            )
        except Exception as e:
            st.error(f"Could not fetch {ticker}: {e}")

    if not portfolio_data:
        return None

    try:
        db.save_holdings([
            {
                "ticker": ticker,
                "shares": data["shares"],
                "buy_price": data["cost_basis"],
            }
            for ticker, data in portfolio_data.items()
        ])
        db.save_metrics([
            {
                "ticker": ticker,
                "date": data["history"].index[-1].date().isoformat(),
                "period": period,
                "returns": data["period_return"],
                "volatility": data["volatility"],
                "sharpe_ratio": data["sharpe"],
                "rsi": data["rsi"],
                "macd": data["macd_diff"],
            }
            for ticker, data in portfolio_data.items()
        ])
    except Exception as e:
        st.warning(f"Could not save to the local database: {e}")

    combined = pd.DataFrame()
    for ticker, data in portfolio_data.items():
        combined[ticker] = data["history"] * data["shares"]
    combined["Total"] = combined.sum(axis=1)
    daily_returns = combined["Total"].pct_change().dropna()
    sharpe = float((daily_returns.mean() / daily_returns.std()) * np.sqrt(252))
    volatility = float(daily_returns.std() * np.sqrt(252) * 100)
    avg_period = float(np.mean([d["period_return"] for d in portfolio_data.values()]))

    news_by_ticker = {
        ticker: fetch_news_bundle(ticker) for ticker in portfolio_data
    }

    guidance = build_beginner_guidance(
        portfolio_data,
        total_value,
        combined["Total"],
        sharpe,
        volatility,
    )

    coach_context = build_coach_context(
        portfolio_data,
        total_value,
        total_cost,
        period_label,
        sharpe,
        volatility,
        guidance=guidance,
    )

    briefing = None
    briefing_error = None
    if groq_api_key:
        try:
            briefing = ask_coach(
                COACH_SYSTEM,
                (
                    "Analyze this portfolio for a beginner investor. "
                    "Cover: overall health, concentration, whether averaging "
                    "in slowly makes more sense than a lump sum right now, "
                    "what's looking strong vs stretched, and 2-3 practical "
                    f"things to watch next.\n\n{coach_context}"
                ),
            )
        except Exception as e:
            briefing_error = str(e)

    return {
        "portfolio_data": portfolio_data,
        "total_value": total_value,
        "total_cost": total_cost,
        "period": period,
        "period_label": period_label,
        "combined_total": combined["Total"],
        "sharpe": sharpe,
        "volatility": volatility,
        "avg_period": avg_period,
        "reused": [t for t, d in portfolio_data.items() if d["from_cache"]],
        "news_by_ticker": news_by_ticker,
        "guidance": guidance,
        "coach_context": coach_context,
        "coach_briefing": briefing,
        "briefing_error": briefing_error,
    }


# ---------------------------------------------------------------------------
# Holdings state
# ---------------------------------------------------------------------------
if "holdings" not in st.session_state:
    saved_holdings = db.get_holdings()
    st.session_state.holdings = [
        {
            "ticker": h["ticker"],
            "shares": float(h["shares"]),
            "cost_basis": float(h["buy_price"]),
        }
        for h in saved_holdings
    ] or [{"ticker": "AAPL", "shares": 10.0, "cost_basis": 0.0}]


def add_stock():
    st.session_state.holdings.append(
        {"ticker": "", "shares": 0.0, "cost_basis": 0.0}
    )


def remove_stock():
    if len(st.session_state.holdings) > 1:
        i = len(st.session_state.holdings) - 1
        st.session_state.holdings.pop()
        for key in (f"search_{i}", f"shares_{i}", f"cost_{i}"):
            if key in st.session_state:
                del st.session_state[key]


def render_empty_state(message: str) -> None:
    st.markdown(
        f"""
<div class="pi-panel">
  <p style="margin:0;color:#6B7280;">{message}</p>
</div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_portfolio, tab_indicators, tab_news, tab_ai = st.tabs(
    ["Portfolio", "Indicators", "News", "AI Insights"]
)

with tab_portfolio:
    ui.section("Holdings", "Add positions, choose a window, then run analysis.")

    period_label = st.selectbox(
        "Performance time frame",
        list(PERIOD_OPTIONS.keys()),
        index=2,
        help="Used for charts, period returns, and technical indicators",
    )
    period = PERIOD_OPTIONS[period_label]

    c1, c2 = st.columns(2)
    with c1:
        st.button("+ Add Stock", on_click=add_stock)
    with c2:
        st.button("− Remove Last", on_click=remove_stock)

    for i, holding in enumerate(st.session_state.holdings):
        col1, col2, col3 = st.columns(3)
        with col1:
            selected = st_searchbox(
                search_stocks,
                label=f"Stock {i+1}",
                placeholder="Type ticker or company name…",
                default=label_for_symbol(holding["ticker"]),
                key=f"search_{i}",
            )
            ticker = ticker_from_selection(selected) or holding["ticker"]
        with col2:
            shares = st.number_input(
                "Shares Owned",
                value=float(holding.get("shares", 0.0)),
                min_value=0.0,
                key=f"shares_{i}",
            )
        with col3:
            cost_basis = st.number_input(
                "Your avg buy price ($)",
                value=float(holding.get("cost_basis", 0.0)),
                min_value=0.0,
                key=f"cost_{i}",
                help="What you paid per share. Leave 0 if unknown.",
            )
        st.session_state.holdings[i] = {
            "ticker": ticker,
            "shares": shares,
            "cost_basis": cost_basis,
        }

    a1, a2 = st.columns([2, 3])
    with a1:
        analyze_clicked = st.button("Analyze Portfolio", type="primary")
    with a2:
        force_refresh = st.checkbox(
            "Recalculate from scratch",
            help=(
                "Ignore saved metrics and recompute every indicator, even if "
                "the stored values are still less than a day old."
            ),
        )

    if analyze_clicked:
        if any(h["ticker"] for h in st.session_state.holdings):
            with st.spinner("Running portfolio analysis…"):
                result = run_portfolio_analysis(period, period_label, force_refresh)
            if result:
                st.session_state.analysis = result
                st.session_state.coach_context = result["coach_context"]
                st.session_state.coach_briefing = result["coach_briefing"]
                st.session_state.coach_messages = []
        else:
            st.warning("Add at least one ticker before analyzing.")

    analysis = st.session_state.get("analysis")

    if not analysis and not analyze_clicked:
        saved_metrics = db.get_latest_metrics()
        if saved_metrics:
            ui.section(
                "Last saved snapshot",
                "Loaded from the local database — run Analyze for full charts and tabs.",
            )
            snapshot_rows = []
            for m in saved_metrics:
                age = db.age_of(m)
                if age is None:
                    age_text = "unknown"
                elif age.total_seconds() < 3600:
                    age_text = f"{int(age.total_seconds() // 60)} min ago"
                elif age.days < 1:
                    age_text = f"{int(age.total_seconds() // 3600)} hr ago"
                else:
                    age_text = f"{age.days}d ago"
                snapshot_rows.append({
                    "Ticker": m["ticker"],
                    "Window": PERIOD_LABELS.get(m["period"], m["period"]),
                    "Return": f"{m['returns']:.2f}%" if m["returns"] is not None else "—",
                    "Volatility": (
                        f"{m['volatility']:.1f}%" if m["volatility"] is not None else "—"
                    ),
                    "Sharpe": (
                        f"{m['sharpe_ratio']:.2f}"
                        if m["sharpe_ratio"] is not None
                        else "—"
                    ),
                    "RSI": f"{m['rsi']:.1f}" if m["rsi"] is not None else "—",
                    "MACD": f"{m['macd']:.3f}" if m["macd"] is not None else "—",
                    "Calculated": age_text,
                    "Fresh": "Yes" if db.is_fresh(m) else "Stale",
                })
            st.dataframe(
                ui.style_signed_columns(
                    pd.DataFrame(snapshot_rows),
                    ["Return"],
                ),
                use_container_width=True,
            )

    if analysis:
        if analysis.get("reused"):
            st.caption(
                "Reused saved indicators (under a day old) for: "
                f"{', '.join(analysis['reused'])}. Tick “Recalculate from scratch” "
                "to force a full recompute."
            )

        ui.section("Portfolio summary")
        total_value = analysis["total_value"]
        total_cost = analysis["total_cost"]
        pnl_cards = [
            {
                "label": "Total Value",
                "value": f"${total_value:,.2f}",
            },
            {
                "label": f"Avg Return ({analysis['period_label']})",
                "value": f"{analysis['avg_period']:+.2f}%",
                "tone": ui.signed_tone(analysis["avg_period"]),
            },
        ]
        if total_cost > 0:
            total_pnl = total_value - total_cost
            pnl_pct = (total_pnl / total_cost) * 100
            pnl_cards.append({
                "label": "Your P&L",
                "value": f"${total_pnl:,.2f}",
                "delta": f"{pnl_pct:+.2f}%",
                "tone": ui.signed_tone(total_pnl),
                "delta_tone": ui.signed_tone(pnl_pct),
            })
        else:
            pnl_cards.append({
                "label": "Your P&L",
                "value": "—",
                "delta": "Add buy prices",
                "delta_tone": "neu",
            })
        pnl_cards.append({
            "label": "Holdings",
            "value": str(len(analysis["portfolio_data"])),
        })
        ui.metric_cards(pnl_cards)

        ui.section("Holdings breakdown")
        rows = []
        for ticker, data in analysis["portfolio_data"].items():
            row = {
                "Ticker": ticker,
                "Shares": data["shares"],
                "Price": f"${data['current_price']:.2f}",
                "Value": f"${data['value']:,.2f}",
                "Weight": f"{(data['value']/total_value*100):.1f}%",
                f"{analysis['period_label']} Return": f"{data['period_return']:.2f}%",
            }
            if data["your_return"] is not None:
                row["Your Return"] = f"{data['your_return']:.2f}%"
                row["Gain/Loss"] = f"${data['gain_loss']:,.2f}"
            else:
                row["Your Return"] = "—"
                row["Gain/Loss"] = "—"
            rows.append(row)
        st.dataframe(
            ui.style_signed_columns(
                pd.DataFrame(rows),
                [
                    f"{analysis['period_label']} Return",
                    "Your Return",
                    "Gain/Loss",
                ],
            ),
            use_container_width=True,
        )
        st.caption(
            f"**{analysis['period_label']} Return** = stock move over that window. "
            "**Your Return** = vs your avg buy price. "
            "Green = gain, red = loss."
        )

        ui.section(f"Performance ({analysis['period_label']})")
        ui.line_chart({"Total": analysis["combined_total"]}, signed_fill=True)

        ui.section("Risk")
        ui.metric_cards([
            {
                "label": "Sharpe Ratio",
                "value": f"{analysis['sharpe']:.2f}",
                "delta": "Above 1.0 is solid",
                "delta_tone": "neu",
            },
            {
                "label": "Annual Volatility",
                "value": f"{analysis['volatility']:.1f}%",
                "delta": "Lower is less risky",
                "delta_tone": "neu",
            },
        ])

        guidance = analysis.get("guidance")
        if guidance:
            ui.section(
                "Beginner guidance",
                "Not a buy/sell signal — just concentration, trend, and how to add money.",
            )
            ui.metric_cards(
                [
                    {
                        "label": "Concentration",
                        "value": guidance["concentration"]["label"],
                        "delta": guidance["concentration"]["blurb"],
                        "tone": guidance["concentration"]["tone"],
                        "delta_tone": guidance["concentration"]["tone"],
                    },
                    {
                        "label": "Portfolio trend",
                        "value": guidance["trend"]["label"],
                        "delta": guidance["trend"]["blurb"],
                        "tone": guidance["trend"]["tone"],
                        "delta_tone": guidance["trend"]["tone"],
                    },
                    {
                        "label": "If adding money",
                        "value": guidance["entry"]["label"],
                        "delta": guidance["entry"]["blurb"],
                        "tone": guidance["entry"]["tone"],
                        "delta_tone": guidance["entry"]["tone"],
                    },
                ],
                compact=True,
            )
            with st.expander("Checklist details"):
                st.write(" · ".join(guidance["checklist"]))
                st.caption(
                    "DCA = investing a fixed amount on a schedule. Usually beats "
                    "trying to pick the perfect day."
                )

with tab_indicators:
    analysis = st.session_state.get("analysis")
    if not analysis:
        render_empty_state(
            "Run Analyze Portfolio on the Portfolio tab to unlock indicators, "
            "patterns, and momentum reads."
        )
    else:
        ui.section(
            "What the numbers mean for your holdings",
            (
                f"Window: {analysis['period_label']}. This isn’t a charting terminal — "
                "we translate RSI, MACD, and range into a plain-English read for "
                "each stock you own, then show a small chart only as visual proof."
            ),
        )
        with st.expander("Quick glossary (RSI, MACD, Bollinger, Sharpe)"):
            st.markdown(
                """
**RSI (Relative Strength Index)** — How hard the stock has run lately, on a 0–100 scale.
- High (about **70+**) = *stretched / overbought*: it’s run hot; chasing can mean paying a hot price.
- Low (about **30−**) = *washed out / oversold*: it’s been sold hard; that can be a bargain *or* a warning.
- Middle = nothing extreme on momentum alone.

**MACD** — Short-term trend momentum (are recent buyers or sellers winning?).
- **Positive / “Up”** = buying pressure has been stronger lately (bullish lean).
- **Negative / “Down”** = selling pressure has been stronger (bearish lean).

**Bollinger %B** — Where price sits inside its recent high–low “envelope.”
- Near **1.0 / upper band** = *stretched* toward the top of the recent range.
- Near **0.0 / lower band** = *washed out* toward the bottom of the recent range.
- Middle = trading in a normal part of its recent range.

**Sharpe ratio** — Return you got for the volatility you took (roughly “bang for the risk buck”).
- Higher is generally better (many people treat **above ~1** as solid).
- It’s about risk-adjusted performance — not a buy/sell signal by itself.

**Stretched vs washed out (on the charts)**
- **Stretched zone (upper band)** = price hugging the top of its recent range — often a pause/pullback area, not “guaranteed drop.”
- **Washed-out zone (lower band)** = price hugging the bottom — often a bounce *or* further slide; check news before assuming it’s cheap.
                """
            )
        for ticker, data in analysis["portfolio_data"].items():
            with st.expander(f"{ticker} — plain-English read", expanded=True):
                ui.metric_cards([
                    {
                        "label": "RSI (14)",
                        "value": f"{data['rsi']:.1f}",
                        "tone": (
                            "neg" if data["rsi"] > 70
                            else "pos" if data["rsi"] < 30
                            else "neu"
                        ),
                    },
                    {
                        "label": "MACD Diff",
                        "value": f"{data['macd_diff']:.3f}",
                        "tone": ui.signed_tone(data["macd_diff"]),
                    },
                    {
                        "label": "Bollinger %B",
                        "value": f"{data['bb_pct']:.2f}",
                        "tone": (
                            "neg" if data["bb_pct"] > 0.8
                            else "pos" if data["bb_pct"] < 0.2
                            else "neu"
                        ),
                    },
                    {
                        "label": "Ticker Sharpe",
                        "value": f"{data['sharpe']:.2f}",
                    },
                ])
                st.caption("Signals: " + " · ".join(data["signals"]))

                mom = data["momentum"]
                st.markdown(mom["overall"])
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("Recent run", mom["rsi_label"], f"{mom['rsi']:.0f}")
                with m2:
                    st.metric("Momentum", mom["macd_label"])
                with m3:
                    st.metric("Price range", mom["bb_label"])
                st.write(f"**Recent run:** {mom['rsi_take']}")
                st.write(f"**Trend momentum:** {mom['macd_take']}")
                st.write(f"**Price vs range:** {mom['bb_take']}")

                close = data["history"]
                patterns = data["patterns"]
                if patterns.get("note"):
                    st.caption(patterns["note"])
                if patterns["patterns"]:
                    ui.subsection("Trend read")
                    for p in patterns["patterns"]:
                        tag = p.get("tone", "neu")
                        tag_label = (
                            "constructive" if tag == "pos"
                            else "caution" if tag == "neg"
                            else "note"
                        )
                        st.markdown(
                            f'<span class="pi-tag {tag}">{tag_label}</span> '
                            f"**{p['pattern']}**",
                            unsafe_allow_html=True,
                        )
                        st.write(f"What it means: {p['meaning']}")
                        st.write(f"What to watch: {p['action']}")
                else:
                    ui.subsection("Trend read")
                    st.caption(
                        f"No trend read available for this window "
                        f"({analysis['period_label']}). Try a longer time frame."
                    )

                with st.expander("Show supporting charts (optional)"):
                    st.caption(
                        "Green = shorter trend (20-day); blue = longer trend (50-day). "
                        "If green is above blue, short-term momentum is stronger."
                    )
                    ui.line_chart(
                        {
                            "Price": close,
                            "20-day trend": close.rolling(window=20).mean(),
                            "50-day trend": close.rolling(window=50).mean(),
                        },
                        title=f"{ticker}: price vs short & long trend",
                    )

                    st.caption(
                        "**Stretched** = price near the top of its recent range "
                        "(upper band) — it’s run toward a typical high. "
                        "**Washed out** = near the bottom (lower band) — it’s "
                        "been pushed toward a typical low. Neither one means "
                        "“buy” or “sell” by itself."
                    )
                    bb = ta.volatility.BollingerBands(close, window=20)
                    ui.line_chart(
                        {
                            "Price": close,
                            "Upper (stretched zone)": bb.bollinger_hband(),
                            "Middle": bb.bollinger_mavg(),
                            "Lower (washed-out zone)": bb.bollinger_lband(),
                        },
                        title=f"{ticker}: price vs recent range",
                    )

with tab_news:
    analysis = st.session_state.get("analysis")
    if not analysis:
        render_empty_state(
            "Run Analyze Portfolio on the Portfolio tab to load news and fundamentals."
        )
    else:
        ui.section(
            "News & fundamentals",
            "Headlines use NewsAPI when configured; valuation still works without it.",
        )
        if not news_api_key:
            st.info(
                "Add NEWS_API_KEY to `.streamlit/secrets.toml` for headlines and "
                "sentiment. Earnings/valuation below still work."
            )

        for ticker, bundle in analysis["news_by_ticker"].items():
            with st.expander(f"{ticker} — news & valuation", expanded=True):
                if bundle.get("error") and not bundle.get("fundamentals"):
                    st.error(f"Could not fetch news for {ticker}: {bundle['error']}")
                    continue

                news = bundle.get("news") or {}
                if news.get("skipped"):
                    st.caption("News headlines skipped (no NewsAPI key).")
                elif news.get("error") and not news.get("articles"):
                    st.warning(news["error"])
                elif news.get("articles"):
                    sent_tone = (
                        "pos" if news["avg"] > 0.1
                        else "neg" if news["avg"] < -0.1
                        else "neu"
                    )
                    ui.metric_cards(
                        [
                            {
                                "label": "News Sentiment",
                                "value": news["label"],
                                "tone": sent_tone,
                            },
                            {
                                "label": "Sentiment Score",
                                "value": f"{news['avg']:.2f}",
                                "tone": sent_tone,
                            },
                        ],
                        compact=True,
                    )
                    st.write(f"**What this means:** {news['explanation']}")
                    st.divider()
                    ui.subsection("Recent headlines")
                    for article in news["articles"]:
                        tag_class = (
                            "pos" if article["tag"] == "Positive"
                            else "neg" if article["tag"] == "Negative"
                            else "neu"
                        )
                        st.markdown(
                            f'<span class="pi-tag {tag_class}">{article["tag"]}</span> '
                            f'{article["title"]}',
                            unsafe_allow_html=True,
                        )
                        st.caption(f"{article['source']} — {article['published']}")

                fund = bundle.get("fundamentals")
                if fund:
                    st.divider()
                    ui.subsection("Earnings & valuation")
                    ui.metric_cards(
                        [
                            {
                                "label": "EPS",
                                "value": str(fund["eps"]).replace("$", ""),
                            },
                            {"label": "P/E", "value": str(fund["pe"])},
                            {
                                "label": "Forward P/E",
                                "value": str(fund["forward_pe"]),
                            },
                        ],
                        compact=True,
                    )
                    if fund.get("valuation"):
                        # Escape $ so Streamlit doesn't render KaTeX math
                        st.write(
                            "Valuation check: "
                            + fund["valuation"].replace("$", r"\$")
                        )
                    if fund.get("calendar"):
                        ui.subsection("Upcoming calendar")
                        for note in fund["calendar"]:
                            st.write(f"• {note}")

with tab_ai:
    analysis = st.session_state.get("analysis")
    ui.section(
        "AI coach",
        "Educational commentary on your latest analysis — not financial advice.",
    )

    if not analysis:
        render_empty_state(
            "Run Analyze Portfolio first. The coach needs a saved analysis snapshot."
        )
    elif not groq_api_key:
        st.warning(
            "Add GROQ_API_KEY to `.streamlit/secrets.toml` to unlock the AI coach. "
            "Free key: https://console.groq.com/keys"
        )
    else:
        if analysis.get("briefing_error"):
            st.error(f"Could not generate AI briefing: {analysis['briefing_error']}")
        elif analysis.get("coach_briefing"):
            ui.section("Briefing")
            with st.container(border=True):
                st.write(analysis["coach_briefing"])

        st.caption("Ask anything about your portfolio. Answers use your latest analysis.")

        if "coach_messages" not in st.session_state:
            st.session_state.coach_messages = []

        for msg in st.session_state.coach_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        prompt = st.chat_input("e.g. Should I buy more of my largest holding?")
        if prompt:
            st.session_state.coach_messages.append(
                {"role": "user", "content": prompt}
            )
            with st.chat_message("user"):
                st.write(prompt)

            history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.coach_messages[:-1]
            ]
            try:
                with st.spinner("Thinking…"):
                    answer = ask_coach(
                        COACH_SYSTEM,
                        (
                            "Portfolio facts:\n"
                            f"{st.session_state.get('coach_context', '')}\n\n"
                            f"User question: {prompt}"
                        ),
                        history=history if history else None,
                    )
            except Exception as e:
                answer = f"Sorry — the coach hit an error: {e}"

            st.session_state.coach_messages.append(
                {"role": "assistant", "content": answer}
            )
            with st.chat_message("assistant"):
                st.write(answer)
