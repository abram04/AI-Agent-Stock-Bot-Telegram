from typing import List

from graph.state import StockAnalysisState

AGENT_LABELS = {
    "buffett": "Warren Buffett Agent",
    "greenblatt": "Joel Greenblatt Agent",
    "graham": "Benjamin Graham Agent",
    "veteran": "25-Year Veteran Analyst",
    "quant_news": "Quant + News Analyst",
}

AGENT_ICONS = {
    "buffett": "🎩",
    "greenblatt": "🧮",
    "graham": "📚",
    "veteran": "👔",
    "quant_news": "📊",
}

SEP = "━" * 20


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_price(val, currency: str = "USD") -> str:
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if v >= 1_000:
            return f"{currency} {v:,.0f}"
        return f"{currency} {v:.2f}"
    except Exception:
        return str(val)


def _fmt(val, mult: float = 1, dec: int = 2, suffix: str = "") -> str:
    if val is None:
        return "N/A"
    try:
        return f"{float(val) * mult:.{dec}f}{suffix}"
    except Exception:
        return str(val)


def _split(text: str, max_len: int = 4000) -> List[str]:
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, max_len)
        if cut <= 0:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


def _stock_message(ticker: str, fin: dict, agents: dict, synthesis: str) -> str:
    name = fin.get("name", ticker)
    currency = fin.get("currency", "USD")
    price = _fmt_price(fin.get("current_price"), currency)
    target = _fmt_price(fin.get("target_price"), currency)
    high = _fmt_price(fin.get("52_week_high"), currency)
    low = _fmt_price(fin.get("52_week_low"), currency)
    pe = _fmt(fin.get("pe_ratio_trailing"))
    pb = _fmt(fin.get("pb_ratio"))
    roe = _fmt(fin.get("roe"), 100, 1, "%")
    change = _fmt(fin.get("price_1y_change_pct"), suffix="%")
    rec = fin.get("recommendation", "N/A") or "N/A"

    parts = [
        f"<b>📊 {_esc(name)} ({_esc(ticker)})</b>",
        "",
        f"<b>Harga:</b> {price}  <b>Target:</b> {target}",
        f"<b>52W:</b> {low} — {high}  <b>1Y Change:</b> {change}",
        f"<b>P/E:</b> {pe}  <b>P/B:</b> {pb}  <b>ROE:</b> {roe}  <b>Analyst:</b> {_esc(rec.upper())}",
        "",
        SEP,
    ]

    for key, label in AGENT_LABELS.items():
        icon = AGENT_ICONS[key]
        analysis = agents.get(key, "Analysis not available.")
        parts += [
            f"\n{icon} <b>{label}</b>",
            _esc(analysis),
            f"\n{SEP}",
        ]

    if synthesis:
        parts += [
            "\n🔮 <b>SINTESIS &amp; PREDIKSI AKHIR</b>",
            _esc(synthesis),
        ]

    return "\n".join(parts)


def format_all(state: StockAnalysisState) -> List[str]:
    if state.get("error"):
        return [f"❌ <b>Error:</b> {_esc(str(state['error']))}"]

    messages: List[str] = []

    for ticker in state.get("tickers", []):
        fin = state.get("financial_data", {}).get(ticker, {})
        agents = state.get("agent_results", {}).get(ticker, {})
        synthesis = state.get("synthesis", {}).get(ticker, "")

        if fin.get("error"):
            messages.append(
                f"⚠️ <b>{_esc(ticker)}</b>: Data tidak tersedia — {_esc(fin['error'])}"
            )
            continue

        full = _stock_message(ticker, fin, agents, synthesis)
        messages.extend(_split(full))

    if not messages:
        return ["⚠️ Tidak ada hasil yang bisa ditampilkan."]

    return messages


# ── Comparison table ─────────────────────────────────────────────────────────

import re as _re

def _extract_verdict(synthesis: str):
    rec = "N/A"
    conf = "N/A"
    m = _re.search(r"Recommendation[:\s*]+\**(BUY|HOLD|SELL)\**", synthesis, _re.IGNORECASE)
    if m:
        rec = m.group(1).upper()
    m2 = _re.search(r"Confidence[:\s*]+\**(HIGH|MEDIUM|LOW)\**", synthesis, _re.IGNORECASE)
    if m2:
        conf = m2.group(1).upper()
    return rec, conf


def format_comparison(state) -> str:
    tickers = state.get("tickers", [])
    if len(tickers) < 2:
        return ""

    ICONS = {"BUY": "🟢", "HOLD": "🟡", "SELL": "🔴", "N/A": "⚪"}

    rows = []
    for ticker in tickers:
        fin = state.get("financial_data", {}).get(ticker, {})
        synthesis = state.get("synthesis", {}).get(ticker, "")
        rec, conf = _extract_verdict(synthesis)

        price = fin.get("current_price")
        target = fin.get("target_price")
        currency = fin.get("currency", "")
        pe = fin.get("pe_ratio_trailing")
        roe = fin.get("roe")
        rsi = fin.get("technical_indicators", {}).get("rsi_14")
        dcf = fin.get("dcf", {}).get("dcf_intrinsic_value")
        mos = fin.get("dcf", {}).get("dcf_margin_of_safety_pct")

        def fp(v):
            if v is None: return "N/A"
            try: return f"{float(v):,.0f}" if float(v) >= 100 else f"{float(v):.2f}"
            except: return str(v)

        def ff(v, suf=""):
            if v is None: return "N/A"
            try: return f"{float(v):.1f}{suf}"
            except: return str(v)

        rows.append({
            "ticker": ticker,
            "name": fin.get("name", ticker),
            "rec": rec,
            "conf": conf,
            "icon": ICONS.get(rec, "⚪"),
            "price": fp(price),
            "target": fp(target),
            "currency": currency,
            "pe": ff(pe),
            "roe": ff(roe, "%") if roe is None else ff(float(roe)*100, "%"),
            "rsi": ff(rsi),
            "dcf": fp(dcf),
            "mos": ff(mos, "%"),
        })

    lines = ["📊 <b>RINGKASAN PERBANDINGAN</b>\n"]
    for r in rows:
        lines.append(
            f"{r['icon']} <b>{_esc(r['ticker'])}</b> — <b>{r['rec']}</b> ({r['conf']})\n"
            f"   Harga: {r['price']} | Target: {r['target']} {r['currency']}\n"
            f"   P/E: {r['pe']} | ROE: {r['roe']} | RSI: {r['rsi']}\n"
            f"   DCF Value: {r['dcf']} | Margin of Safety: {r['mos']}"
        )

    buy_list = [r["ticker"] for r in rows if r["rec"] == "BUY"]
    sell_list = [r["ticker"] for r in rows if r["rec"] == "SELL"]

    lines.append("")
    if buy_list:
        lines.append(f"🏆 <b>Rekomendasi Terkuat:</b> {', '.join(buy_list)}")
    if sell_list:
        lines.append(f"⚠️ <b>Hindari:</b> {', '.join(sell_list)}")

    return "\n".join(lines)
