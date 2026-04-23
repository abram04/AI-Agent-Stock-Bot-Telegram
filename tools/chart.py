import asyncio
import io
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import yfinance as yf


def _chart_sync(ticker: str) -> Optional[bytes]:
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if hist.empty or len(hist) < 5:
            return None

        close = hist["Close"]

        # Use Figure API directly — thread-safe, no shared plt global state
        fig = Figure(figsize=(12, 7), facecolor="#0d1117")
        canvas = FigureCanvasAgg(fig)

        gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.35)
        ax1 = fig.add_subplot(gs[0])
        ax2 = fig.add_subplot(gs[1])

        for ax in (ax1, ax2):
            ax.set_facecolor("#161b22")
            ax.tick_params(colors="#8b949e", labelsize=8)
            ax.grid(True, alpha=0.15, linestyle="--", color="#30363d")
            ax.yaxis.tick_right()
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
            for spine in ax.spines.values():
                spine.set_edgecolor("#30363d")

        # Price line + fill
        ax1.plot(hist.index, close, color="#58a6ff", linewidth=1.5, label="Close")
        ax1.fill_between(hist.index, close, float(close.min()) * 0.97,
                         alpha=0.12, color="#58a6ff")

        if len(close) >= 20:
            ax1.plot(hist.index, close.rolling(20).mean(),
                     color="#f0b429", linewidth=1.0, label="MA20", alpha=0.85)
        if len(close) >= 50:
            ax1.plot(hist.index, close.rolling(50).mean(),
                     color="#ff7b72", linewidth=1.0, label="MA50", alpha=0.85)

        ax1.set_title(f"{ticker} — 1 Year Price", fontsize=13,
                      fontweight="bold", color="#e6edf3", pad=10)
        legend = ax1.legend(loc="upper left", fontsize=8, framealpha=0.25,
                            facecolor="#1c2128", edgecolor="#30363d")
        for text in legend.get_texts():
            text.set_color("#c9d1d9")

        # Volume bars (green/red)
        colors = ["#3fb950" if c >= o else "#f85149"
                  for c, o in zip(hist["Close"], hist["Open"])]
        ax2.bar(hist.index, hist["Volume"], color=colors, alpha=0.75, width=0.8)
        ax2.set_ylabel("Volume", color="#8b949e", fontsize=8)

        buf = io.BytesIO()
        canvas.print_figure(buf, format="png", dpi=110, bbox_inches="tight",
                            facecolor="#0d1117", edgecolor="none")
        buf.seek(0)
        return buf.read()

    except Exception:
        return None


async def generate_chart(ticker: str) -> Optional[bytes]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _chart_sync, ticker)
