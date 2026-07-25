"""Visual theme for Portfolio Intelligence — fintech product styling."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Brand palette
NAVY = "#0A2540"
NAVY_MID = "#1B3A5C"
GREEN = "#0B7A4B"       # gains / constructive — bright enough to read as green
GREEN_SOFT = "#1A9B63"
GREEN_BG = "#E8F6EF"
RED = "#C62828"         # losses / caution
RED_SOFT = "#E53935"
RED_BG = "#FDECEA"
BG = "#F8F9FA"
WHITE = "#FFFFFF"
BORDER = "#E5E7EB"
TEXT = "#1F2937"
MUTED = "#6B7280"

CHART_COLORS = [NAVY, GREEN, "#3B6D9C", GREEN_SOFT, "#8B9DC3", RED]


def inject_theme() -> None:
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
  font-family: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, sans-serif;
  color: {TEXT};
}}

.stApp {{
  background: {BG};
}}

/* Hide Streamlit chrome clutter */
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
header[data-testid="stHeader"] {{
  background: {WHITE};
  border-bottom: 1px solid {BORDER};
}}

.block-container {{
  padding-top: 1.25rem !important;
  padding-bottom: 3rem !important;
  max-width: 1180px;
}}

/* Brand masthead */
.pi-masthead {{
  background: linear-gradient(135deg, {NAVY} 0%, {NAVY_MID} 100%);
  color: {WHITE};
  border-radius: 12px;
  padding: 1.35rem 1.6rem 1.25rem;
  margin-bottom: 1.35rem;
  box-shadow: 0 8px 24px rgba(10, 37, 64, 0.18);
}}
.pi-masthead .pi-brand {{
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.82;
  margin: 0 0 0.35rem 0;
}}
.pi-masthead h1 {{
  font-family: "IBM Plex Sans", sans-serif;
  font-size: 1.85rem;
  font-weight: 700;
  color: {WHITE} !important;
  margin: 0 0 0.35rem 0;
  letter-spacing: -0.02em;
}}
.pi-masthead p {{
  margin: 0;
  font-size: 0.95rem;
  opacity: 0.9;
  max-width: 42rem;
}}

/* Section titles */
.pi-section {{
  font-family: "IBM Plex Sans", sans-serif;
  font-size: 1.15rem;
  font-weight: 700;
  color: {NAVY};
  margin: 0.4rem 0 0.85rem 0;
  letter-spacing: -0.01em;
}}
.pi-section-sub {{
  color: {MUTED};
  font-size: 0.9rem;
  margin: -0.5rem 0 1rem 0;
}}
.pi-subsection {{
  font-family: "IBM Plex Sans", sans-serif;
  font-size: 1.02rem;
  font-weight: 700;
  color: {NAVY};
  margin: 0.85rem 0 0.45rem 0;
  letter-spacing: -0.01em;
}}

/* Metric cards */
.pi-card-row {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.85rem;
  margin-bottom: 1.1rem;
}}
@media (max-width: 900px) {{
  .pi-card-row {{ grid-template-columns: repeat(2, 1fr); }}
}}
.pi-card {{
  background: {WHITE};
  border: 1px solid {BORDER};
  border-radius: 10px;
  padding: 1rem 1.1rem;
  box-shadow: 0 1px 3px rgba(10, 37, 64, 0.04);
}}
.pi-card .label {{
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: {MUTED};
  margin-bottom: 0.35rem;
}}
.pi-card .value {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 1.35rem;
  font-weight: 600;
  color: {NAVY};
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}}
.pi-card.compact .value {{
  font-size: 1.05rem;
  font-weight: 600;
  word-break: break-word;
}}
.pi-card.compact {{
  padding: 0.85rem 1rem;
}}
.pi-card.compact .delta {{
  font-family: "IBM Plex Sans", sans-serif;
  font-size: 0.78rem;
  font-weight: 450;
  line-height: 1.35;
  margin-top: 0.45rem;
  color: {TEXT};
}}
.pi-card.compact .delta.pos,
.pi-card.compact .delta.neg,
.pi-card.compact .delta.neu {{
  color: {TEXT};
}}
.pi-card .delta {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 0.82rem;
  font-weight: 500;
  margin-top: 0.3rem;
  font-variant-numeric: tabular-nums;
}}
.pi-card .delta.pos {{ color: {GREEN}; }}
.pi-card .delta.neg {{ color: {RED}; }}
.pi-card .delta.neu {{ color: {MUTED}; }}
.pi-card.tone-pos {{
  border-color: #B7E0C8;
  border-left: 4px solid {GREEN};
  background: {GREEN_BG};
}}
.pi-card.tone-pos .value {{ color: {GREEN}; }}
.pi-card.tone-neg {{
  border-color: #F0C4C1;
  border-left: 4px solid {RED};
  background: {RED_BG};
}}
.pi-card.tone-neg .value {{ color: {RED}; }}

/* Streamlit metric deltas */
div[data-testid="stMetricDelta"] svg {{ display: none; }}
div[data-testid="stMetricDelta"] > div {{
  font-family: "IBM Plex Mono", ui-monospace, monospace !important;
}}
/* Force green/red on Streamlit's delta classes when present */
[data-testid="stMetricDelta"] [style*="color: rgb(9"] {{
  color: {GREEN} !important;
}}
[data-testid="stMetricDelta"] [style*="color: rgb(255"] {{
  color: {RED} !important;
}}

/* Native bordered containers (st.container(border=True)) */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div[data-testid="stVerticalBlock"]) {{
  border-radius: 12px;
}}
div[data-testid="stVerticalBlockBorderWrapper"][style*="border"] {{
  background: {WHITE};
  border-color: {BORDER} !important;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(10, 37, 64, 0.04);
}}

/* Soft panels */
.pi-panel {{
  background: {WHITE};
  border: 1px solid {BORDER};
  border-radius: 12px;
  padding: 1.15rem 1.25rem;
  margin-bottom: 1rem;
  box-shadow: 0 1px 3px rgba(10, 37, 64, 0.04);
}}

/* Tabs */
button[data-baseweb="tab"] {{
  font-family: "IBM Plex Sans", sans-serif !important;
  font-weight: 600 !important;
  color: {MUTED} !important;
  font-size: 0.92rem !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
  color: {NAVY} !important;
}}
div[data-baseweb="tab-highlight"] {{
  background-color: {NAVY} !important;
}}
div[data-testid="stTabs"] {{
  background: {WHITE};
  border: 1px solid {BORDER};
  border-radius: 12px;
  padding: 0.5rem 0.85rem 1rem;
  box-shadow: 0 1px 3px rgba(10, 37, 64, 0.04);
}}

/* Primary buttons */
div.stButton > button[kind="primary"],
div.stButton > button[data-testid="baseButton-primary"] {{
  background-color: {NAVY} !important;
  border: 1px solid {NAVY} !important;
  color: {WHITE} !important;
  font-weight: 600 !important;
  border-radius: 8px !important;
  padding: 0.45rem 1.1rem !important;
}}
div.stButton > button[kind="primary"]:hover,
div.stButton > button[data-testid="baseButton-primary"]:hover {{
  background-color: {NAVY_MID} !important;
  border-color: {NAVY_MID} !important;
}}
div.stButton > button {{
  border-radius: 8px !important;
  font-weight: 500 !important;
  border-color: {BORDER} !important;
  color: {NAVY} !important;
}}

/* Inputs */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] {{
  border-radius: 8px !important;
}}

/* Metrics fallback (st.metric) */
div[data-testid="stMetric"] {{
  background: {WHITE};
  border: 1px solid {BORDER};
  border-radius: 10px;
  padding: 0.85rem 1rem;
  box-shadow: 0 1px 3px rgba(10, 37, 64, 0.04);
}}
div[data-testid="stMetricLabel"] {{
  color: {MUTED} !important;
  font-weight: 600 !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.72rem !important;
}}
div[data-testid="stMetricValue"] {{
  font-family: "IBM Plex Mono", ui-monospace, monospace !important;
  color: {NAVY} !important;
  font-variant-numeric: tabular-nums;
}}
div[data-testid="stMetricDelta"] svg {{
  display: none;
}}

/* Dataframes */
div[data-testid="stDataFrame"] {{
  border: 1px solid {BORDER};
  border-radius: 10px;
  overflow: hidden;
}}

/* Expanders */
div[data-testid="stExpander"] {{
  background: {WHITE};
  border: 1px solid {BORDER};
  border-radius: 10px;
  margin-bottom: 0.65rem;
}}

/* Dividers */
hr {{
  border: none !important;
  border-top: 1px solid {BORDER} !important;
  margin: 1.1rem 0 !important;
}}

/* Chat */
div[data-testid="stChatMessage"] {{
  background: {WHITE};
  border: 1px solid {BORDER};
  border-radius: 10px;
}}

/* Caption / help text */
.stCaption, small {{
  color: {MUTED} !important;
}}

/* Positive / negative utility classes for markdown */
.pi-pos {{ color: {GREEN}; font-family: "IBM Plex Mono", monospace; font-weight: 600; }}
.pi-neg {{ color: {RED}; font-family: "IBM Plex Mono", monospace; font-weight: 600; }}
.pi-tag {{
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  margin-right: 0.35rem;
}}
.pi-tag.pos {{ background: {GREEN_BG}; color: {GREEN}; }}
.pi-tag.neg {{ background: {RED_BG}; color: {RED}; }}
.pi-tag.neu {{ background: #F3F4F6; color: {MUTED}; }}
</style>
        """,
        unsafe_allow_html=True,
    )


def masthead() -> None:
    st.markdown(
        """
<div class="pi-masthead">
  <h1>Portfolio Intelligence</h1>
  <p>Returns, risk, indicators, news, and an AI coach — in one clean workspace.</p>
</div>
        """,
        unsafe_allow_html=True,
    )


def section(title: str, subtitle: str | None = None) -> None:
    st.markdown(f'<div class="pi-section">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(
            f'<div class="pi-section-sub">{subtitle}</div>',
            unsafe_allow_html=True,
        )


def subsection(title: str) -> None:
    """Smaller in-panel header (e.g. Trend read, Recent headlines)."""
    st.markdown(
        f'<div class="pi-subsection">{title}</div>',
        unsafe_allow_html=True,
    )


def metric_cards(cards: list[dict], *, compact: bool = False) -> None:
    """Render a row of metric cards.

    Each card: label, value, optional delta, optional tone ('pos'|'neg'|'neu').
    """
    size_class = " compact" if compact else ""
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        tone = card.get("tone", "neu")
        delta = card.get("delta")
        delta_tone = card.get("delta_tone", tone)
        delta_html = (
            f'<div class="delta {delta_tone}">{delta}</div>' if delta else ""
        )
        with col:
            st.markdown(
                f"""
<div class="pi-card{size_class} tone-{tone}">
  <div class="label">{card["label"]}</div>
  <div class="value">{card["value"]}</div>
  {delta_html}
</div>
                """,
                unsafe_allow_html=True,
            )


def _base_layout(*, has_title: bool = False) -> dict:
    # Legend sits under the plot so it never overlaps a title.
    top = 28 if not has_title else 48
    return dict(
        paper_bgcolor=WHITE,
        plot_bgcolor=WHITE,
        font=dict(family="IBM Plex Sans, sans-serif", color=TEXT, size=12),
        margin=dict(l=48, r=24, t=top, b=72),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,
            xanchor="left",
            x=0,
            font=dict(size=11, color=MUTED),
            bgcolor="rgba(0,0,0,0)",
        ),
    )


def _axes() -> dict:
    grid = dict(
        showgrid=True,
        gridcolor=BORDER,
        zeroline=False,
        linecolor=BORDER,
        tickfont=dict(family="IBM Plex Mono, monospace", size=11, color=MUTED),
    )
    return {"xaxis": {**grid}, "yaxis": {**grid}}


def line_chart(
    series_map: dict[str, pd.Series],
    *,
    title: str | None = None,
    height: int = 340,
    signed_fill: bool = False,
) -> None:
    fig = go.Figure()
    for i, (name, series) in enumerate(series_map.items()):
        clean = series.dropna()
        color = CHART_COLORS[i % len(CHART_COLORS)]
        width = 2.6 if i == 0 and len(series_map) == 1 else 1.8
        fill = None
        fillcolor = None

        if name.lower() in {"total", "price"}:
            if signed_fill and len(clean) >= 2:
                up = float(clean.iloc[-1]) >= float(clean.iloc[0])
                color = GREEN if up else RED
                fill = "tozeroy"
                fillcolor = "rgba(11,122,75,0.12)" if up else "rgba(198,40,40,0.10)"
            else:
                color = NAVY
            width = 2.6
        elif "upper" in name.lower() or "lower" in name.lower() or "stretched" in name.lower() or "washed" in name.lower():
            color = MUTED
            width = 1.2
        elif "20" in name or "short" in name.lower():
            color = GREEN
        elif "50" in name or "long" in name.lower():
            color = "#3B6D9C"
        elif "middle" in name.lower():
            color = NAVY_MID

        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                name=name,
                mode="lines",
                line=dict(color=color, width=width),
                fill=fill,
                fillcolor=fillcolor,
                hovertemplate="%{y:.2f}<extra>" + name + "</extra>",
            )
        )
    layout = _base_layout(has_title=False)
    layout.update(_axes())
    layout["height"] = height + 40  # room for bottom legend
    # Titles live outside the Plotly canvas (Streamlit caption/section)
    # so they never collide with the legend.
    fig.update_layout(**layout)
    if title:
        st.markdown(
            f'<div style="font-weight:600;color:{NAVY};font-size:0.95rem;'
            f'margin:0.35rem 0 0.15rem 0;">{title}</div>',
            unsafe_allow_html=True,
        )
    st.plotly_chart(fig, use_container_width=True)


def signed_tone(value: float | None) -> str:
    if value is None:
        return "neu"
    if value > 0:
        return "pos"
    if value < 0:
        return "neg"
    return "neu"


def _parse_signed_cell(value) -> float | None:
    if value is None or value == "—":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def style_signed_columns(df: pd.DataFrame, columns: list[str]):
    """Color gain/loss-style columns green/red in a dataframe."""

    def colorize(col: pd.Series):
        styles = []
        for value in col:
            parsed = _parse_signed_cell(value)
            if parsed is None:
                styles.append("")
            elif parsed > 0:
                styles.append(f"color: {GREEN}; font-weight: 600;")
            elif parsed < 0:
                styles.append(f"color: {RED}; font-weight: 600;")
            else:
                styles.append("")
        return styles

    present = [c for c in columns if c in df.columns]
    if not present:
        return df
    return df.style.apply(colorize, subset=present)
