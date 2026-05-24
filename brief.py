#!/usr/bin/env python3
"""
Coffee C Futures — Daily Research Brief
Powered by Anthropic Claude with web search
"""

import anthropic
import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2000
HISTORY_FILE = Path("output/history.json")
OUTPUT_DIR = Path("output")

# ── Prompt ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a coffee futures research analyst.
Respond ONLY with a valid JSON object — no markdown fences, no preamble, no explanation.
All fields are required. Use "N/A" or 0 if data is unavailable."""

def build_user_prompt(today: str, prev_context: str) -> str:
    return f"""Today is {today}.

Search the web for the LATEST data on all of the following, then return a structured JSON research brief:
1. Coffee C futures (KCN26 or nearest active contract) — price, daily % change, MTD % change, 52-week range
2. ICE certified arabica warehouse stocks — bags count and weekly change
3. Weather in Brazil (Minas Gerais, São Paulo, Espírito Santo) and Vietnam affecting coffee crops
4. USDA / CONAB / ICO latest supply-demand reports
5. News headlines affecting coffee in the last 48 hours
6. Strait of Hormuz and Red Sea shipping situation impact on coffee freight
7. USD/BRL exchange rate and recent direction

{prev_context}

Return this exact JSON structure (no other text):
{{
  "date": "string",
  "price": "string e.g. $2.70",
  "priceChange": "string e.g. -3.5%",
  "priceMTD": "string e.g. -7.7%",
  "priceRange52w": "string e.g. $2.63–$4.38",
  "priceContext": "string 1 sentence",
  "iceStocks": "string e.g. ~458,107 bags",
  "iceStocksChange": "string e.g. +7,380 bags",
  "usdBrl": "string e.g. 5.06",
  "usdBrlContext": "string 1 sentence",
  "risk": "High|Medium|Low",
  "summary": "string 3-4 sentences",
  "bullish": ["4-5 concise strings"],
  "bearish": ["4-5 concise strings"],
  "inventory": [
    {{"label": "string", "value": "string"}},
    {{"label": "string", "value": "string"}},
    {{"label": "string", "value": "string"}},
    {{"label": "string", "value": "string"}}
  ],
  "weather": ["4-5 strings, prefix each with bull/bear/neutral"],
  "freight": "string 3-4 sentences",
  "freightHormuz": 0,
  "freightRedSea": 0,
  "freightInsurance": 0,
  "freightBrazil": 0,
  "news": [
    {{"tag": "Bearish|Bullish|Risk|Neutral", "text": "string"}},
    {{"tag": "Bearish|Bullish|Risk|Neutral", "text": "string"}},
    {{"tag": "Bearish|Bullish|Risk|Neutral", "text": "string"}},
    {{"tag": "Bearish|Bullish|Risk|Neutral", "text": "string"}},
    {{"tag": "Bearish|Bullish|Risk|Neutral", "text": "string"}}
  ],
  "changed": ["3-4 strings vs previous brief or recent days"],
  "watch": [
    {{"title": "string", "desc": "string"}},
    {{"title": "string", "desc": "string"}},
    {{"title": "string", "desc": "string"}},
    {{"title": "string", "desc": "string"}},
    {{"title": "string", "desc": "string"}},
    {{"title": "string", "desc": "string"}}
  ]
}}"""


# ── History ───────────────────────────────────────────────────────────────────
def load_history() -> list[dict]:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_history(entry: dict, history: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    history.insert(0, entry)
    history = history[:30]  # keep 30 days
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


# ── API call ──────────────────────────────────────────────────────────────────
def fetch_brief(today: str, prev_context: str) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": build_user_prompt(today, prev_context)}],
    )

    # Extract text from all content blocks
    text_parts = [b.text for b in response.content if hasattr(b, "text")]
    raw = "\n".join(text_parts)

    # Strip markdown fences if present
    raw = re.sub(r"```json|```", "", raw).strip()

    # Extract first JSON object
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError(f"No JSON found in response:\n{raw[:500]}")

    return json.loads(match.group())


# ── HTML renderer ─────────────────────────────────────────────────────────────
def render_html(b: dict, prev: dict | None) -> str:
    risk_color = {"High": "#A32D2D", "Medium": "#BA7517", "Low": "#3B6D11"}.get(b.get("risk", "Medium"), "#BA7517")
    risk_bg    = {"High": "#FCEBEB", "Medium": "#FAEEDA", "Low": "#EAF3DE"}.get(b.get("risk", "Medium"), "#FAEEDA")

    def tag_style(tag: str) -> str:
        t = (tag or "").lower()
        if t in ("bearish", "bear"): return "background:#FCEBEB;color:#791F1F"
        if t in ("bullish", "bull"): return "background:#EAF3DE;color:#27500A"
        if t == "risk":              return "background:#FAEEDA;color:#633806"
        return "background:#F0EFE8;color:#5F5E5A"

    def factor_rows(items: list, dot_color: str) -> str:
        rows = ""
        for item in items:
            rows += f"""<tr><td style="padding:6px 0;border-bottom:1px solid #eee;font-size:13px;vertical-align:top">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dot_color};margin-right:8px;margin-top:4px;flex-shrink:0"></span>
                {item}</td></tr>"""
        return rows

    prev_price_note = ""
    if prev and prev.get("price"):
        try:
            cp = float(re.sub(r"[^0-9.]", "", b.get("price", "0")))
            pp = float(re.sub(r"[^0-9.]", "", prev["price"]))
            if pp:
                diff = (cp - pp) / pp * 100
                sign = "+" if diff > 0 else ""
                color = "#3B6D11" if diff > 0 else "#A32D2D"
                prev_price_note = f' <span style="font-size:12px;color:{color}">vs prev: {sign}{diff:.1f}%</span>'
        except Exception:
            pass

    news_rows = ""
    for n in b.get("news", []):
        news_rows += f"""<tr><td style="padding:7px 0;border-bottom:1px solid #eee;font-size:13px;vertical-align:top">
            <span style="font-size:10px;font-weight:600;padding:2px 8px;border-radius:4px;{tag_style(n.get('tag',''))}margin-right:8px">{n.get('tag','')}</span>
            {n.get('text','')}</td></tr>"""

    def bar(label: str, val: int) -> str:
        color = "#E24B4A" if val >= 70 else "#EF9F27" if val >= 40 else "#639922"
        severity = "Critical" if val >= 70 else "Elevated" if val >= 40 else "Moderate"
        sev_color = "#A32D2D" if val >= 70 else "#BA7517" if val >= 40 else "#3B6D11"
        return f"""<div style="margin-bottom:10px">
            <div style="display:flex;justify-content:space-between;font-size:12px;color:#888;margin-bottom:4px">
                <span>{label}</span><span style="font-weight:600;color:{sev_color}">{severity}</span>
            </div>
            <div style="background:#F0EFE8;border-radius:4px;height:8px">
                <div style="height:100%;border-radius:4px;width:{min(100,val)}%;background:{color}"></div>
            </div></div>"""

    watch_cards = ""
    for w in b.get("watch", []):
        watch_cards += f"""<div style="background:#F8F7F2;border-radius:8px;padding:10px 12px;min-width:160px">
            <strong style="display:block;font-size:13px;margin-bottom:2px">{w.get('title','')}</strong>
            <span style="font-size:12px;color:#888">{w.get('desc','')}</span></div>"""

    inv_rows = ""
    for row in b.get("inventory", []):
        inv_rows += f"""<tr>
            <td style="padding:5px 0;border-bottom:1px solid #eee;font-size:13px;color:#888">{row.get('label','')}</td>
            <td style="padding:5px 0;border-bottom:1px solid #eee;font-size:13px;font-weight:600;text-align:right">{row.get('value','')}</td>
        </tr>"""

    changed_section_title = f"What changed vs previous brief ({prev['date']})" if prev else "What changed today"
    changed_rows = "".join(
        f'<tr><td style="padding:5px 0;border-bottom:1px solid #eee;font-size:13px">• {c}</td></tr>'
        for c in b.get("changed", [])
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coffee Brief — {b.get('date','')}</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#F8F7F2;margin:0;padding:24px;color:#1a1a18}}
  .card{{background:#fff;border-radius:12px;border:1px solid #E8E6DF;padding:20px 24px;margin-bottom:16px}}
  h2{{font-size:13px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:.05em;margin:0 0 12px}}
  table{{width:100%;border-collapse:collapse}}
  .metric-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px}}
  .metric{{background:#F8F7F2;border-radius:8px;padding:12px 14px}}
  .metric-label{{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}}
  .metric-value{{font-size:20px;font-weight:600}}
  .metric-delta{{font-size:11px;margin-top:3px;color:#888}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
  .watch-grid{{display:flex;flex-wrap:wrap;gap:10px}}
  @media(max-width:560px){{.two-col{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div style="max-width:720px;margin:0 auto">

  <!-- Header -->
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:20px">
    <div>
      <h1 style="font-size:20px;font-weight:600;margin:0">☕ Coffee C — Daily Brief</h1>
      <p style="font-size:13px;color:#888;margin:4px 0 0">{b.get('date','')} &nbsp;·&nbsp; ICE Arabica (KCN26)</p>
    </div>
    <span style="padding:6px 14px;border-radius:8px;font-size:13px;font-weight:600;background:{risk_bg};color:{risk_color};border:1px solid {risk_color}40">
      ⚠ Risk: {b.get('risk','')}
    </span>
  </div>

  <!-- Metrics -->
  <div class="metric-grid">
    <div class="metric">
      <div class="metric-label">Futures price</div>
      <div class="metric-value">{b.get('price','—')}{prev_price_note}</div>
      <div class="metric-delta">{b.get('priceChange','')} today · {b.get('priceMTD','')} MTD</div>
    </div>
    <div class="metric">
      <div class="metric-label">52-week range</div>
      <div class="metric-value" style="font-size:15px">{b.get('priceRange52w','—')}</div>
      <div class="metric-delta">{b.get('priceContext','')}</div>
    </div>
    <div class="metric">
      <div class="metric-label">ICE certified stocks</div>
      <div class="metric-value" style="font-size:15px">{b.get('iceStocks','—')}</div>
      <div class="metric-delta">{b.get('iceStocksChange','')}</div>
    </div>
    <div class="metric">
      <div class="metric-label">USD / BRL</div>
      <div class="metric-value">{b.get('usdBrl','—')}</div>
      <div class="metric-delta">{b.get('usdBrlContext','')}</div>
    </div>
  </div>

  <!-- Summary -->
  <div class="card">
    <h2>📊 Market summary</h2>
    <p style="font-size:14px;line-height:1.65;margin:0">{b.get('summary','')}</p>
  </div>

  <!-- Bull / Bear -->
  <div class="two-col">
    <div class="card" style="margin-bottom:0">
      <h2 style="color:#3B6D11">▲ Bullish factors</h2>
      <table>{factor_rows(b.get('bullish',[]), '#639922')}</table>
    </div>
    <div class="card" style="margin-bottom:0">
      <h2 style="color:#A32D2D">▼ Bearish factors</h2>
      <table>{factor_rows(b.get('bearish',[]), '#E24B4A')}</table>
    </div>
  </div>
  <div style="margin-bottom:16px"></div>

  <!-- Inventory -->
  <div class="card">
    <h2>🏭 Inventory analysis</h2>
    <table>{inv_rows}</table>
  </div>

  <!-- Weather -->
  <div class="card">
    <h2>🌧 Weather risk</h2>
    <table>{factor_rows(b.get('weather',[]), '#888780')}</table>
  </div>

  <!-- Freight -->
  <div class="card">
    <h2>🚢 Transportation & logistics</h2>
    {bar('Hormuz closure impact', b.get('freightHormuz', 0))}
    {bar('Red Sea / Bab el-Mandeb', b.get('freightRedSea', 0))}
    {bar('War risk insurance premium', b.get('freightInsurance', 0))}
    {bar('Brazil port operations', b.get('freightBrazil', 0))}
    <p style="font-size:13px;line-height:1.65;margin:8px 0 0;color:#555">{b.get('freight','')}</p>
  </div>

  <!-- News -->
  <div class="card">
    <h2>📰 Key news</h2>
    <table>{news_rows}</table>
  </div>

  <!-- Changed -->
  <div class="card">
    <h2>🔄 {changed_section_title}</h2>
    <table>{changed_rows}</table>
  </div>

  <!-- Watch -->
  <div class="card">
    <h2>👁 What to watch tomorrow</h2>
    <div class="watch-grid">{watch_cards}</div>
  </div>

  <!-- Disclaimer -->
  <p style="font-size:11px;color:#aaa;text-align:center;margin-top:24px;line-height:1.5">
    For research and informational purposes only. Not financial advice.<br>
    Generated by Claude + web search · {b.get('date','')}
  </p>

</div>
</body>
</html>"""


# ── Email sender ──────────────────────────────────────────────────────────────
def send_email(html: str, subject: str) -> None:
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    to_addr   = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = to_addr
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.ehlo()
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.sendmail(smtp_user, to_addr, msg.as_string())
    print(f"✉  Email sent to {to_addr}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    print(f"📅 Generating brief for {today}...")

    history = load_history()
    prev = history[0] if history else None
    prev_context = (
        f'Previous brief ({prev["date"]}): price={prev.get("price")}, risk={prev.get("risk")}, '
        f'summary="{prev.get("summary","")[:200]}"'
        if prev else "No previous brief available."
    )

    print("🔍 Fetching market data via web search...")
    brief = fetch_brief(today, prev_context)
    print(f"✅ Brief generated — Risk: {brief.get('risk')} | Price: {brief.get('price')}")

    # Save to history
    save_history({"date": brief["date"], "price": brief.get("price"), "risk": brief.get("risk"),
                  "summary": brief.get("summary", "")[:300]}, history)

    # Render HTML
    html = render_html(brief, prev)

    # Save HTML file
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = OUTPUT_DIR / f"brief-{date_slug}.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"💾 Saved to {out_file}")

    # Also save latest.html for easy access
    (OUTPUT_DIR / "latest.html").write_text(html, encoding="utf-8")

    # Save raw JSON
    (OUTPUT_DIR / f"brief-{date_slug}.json").write_text(
        json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Send email if configured
    if os.environ.get("SMTP_USER") and os.environ.get("EMAIL_TO"):
        risk = brief.get("risk", "")
        subject = f"☕ Coffee Brief {date_slug} | {brief.get('price','?')} | Risk: {risk}"
        send_email(html, subject)
    else:
        print("📧 Email not configured — skipping send (set SMTP_USER, SMTP_PASS, EMAIL_TO)")


if __name__ == "__main__":
    main()
