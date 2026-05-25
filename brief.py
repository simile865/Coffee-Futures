#!/usr/bin/env python3
"""
Coffee C Futures - Daily Research Brief
Powered by Anthropic Claude (no web search, stays within free tier limits)
"""

import anthropic
import json
import os
import re
import smtplib
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# -- Config -------------------------------------------------------------------
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1500
HISTORY_FILE = Path("output/history.json")
OUTPUT_DIR = Path("output")

# -- Prompts ------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a coffee futures research analyst. "
    "Respond ONLY with a valid JSON object. "
    "No markdown fences, no preamble, no explanation. "
    "Use your knowledge of recent coffee market conditions. "
    "All string values must be concise (under 200 chars). "
    "All fields required."
)

def build_prompt(today: str, prev: str) -> str:
    return (
        f"Date: {today}. {prev}\n"
        "Write a coffee C futures daily research brief as JSON.\n"
        "Include: current price estimate, ICE stocks, Brazil/Vietnam weather outlook, "
        "freight risk (Hormuz/Red Sea), USD/BRL, bullish/bearish factors, key news, risk level.\n"
        "JSON structure:\n"
        '{"date":"STR","price":"$X.XX","priceChange":"X%","priceMTD":"X%",'
        '"priceRange52w":"$X-$X","priceContext":"STR",'
        '"iceStocks":"STR","iceStocksChange":"STR",'
        '"usdBrl":"X.XX","usdBrlContext":"STR",'
        '"risk":"High|Medium|Low","summary":"STR",'
        '"bullish":["STR","STR","STR"],'
        '"bearish":["STR","STR","STR"],'
        '"inventory":[{"label":"STR","value":"STR"},{"label":"STR","value":"STR"},'
        '{"label":"STR","value":"STR"},{"label":"STR","value":"STR"}],'
        '"weather":["STR","STR","STR"],'
        '"freight":"STR",'
        '"freightHormuz":INT,"freightRedSea":INT,"freightInsurance":INT,"freightBrazil":INT,'
        '"news":[{"tag":"Bearish|Bullish|Risk|Neutral","text":"STR"},'
        '{"tag":"Bearish|Bullish|Risk|Neutral","text":"STR"},'
        '{"tag":"Bearish|Bullish|Risk|Neutral","text":"STR"}],'
        '"changed":["STR","STR"],'
        '"watch":[{"title":"STR","desc":"STR"},{"title":"STR","desc":"STR"},'
        '{"title":"STR","desc":"STR"}]}'
    )

# -- History ------------------------------------------------------------------
def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_history(entry: dict, history: list) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    history.insert(0, entry)
    HISTORY_FILE.write_text(
        json.dumps(history[:30], ensure_ascii=False, indent=2), encoding="utf-8"
    )

# -- API call -----------------------------------------------------------------
def fetch_brief(today: str, prev_context: str) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(today, prev_context)}],
    )

    raw = re.sub(r"```json|```", "", response.content[0].text).strip()
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError(f"No JSON in response: {raw[:200]}")

    json_str = re.sub(r",\s*([}\]])", r"\1", match.group())
    return json.loads(json_str)

# -- HTML renderer ------------------------------------------------------------
def render_html(b: dict, prev: dict | None) -> str:
    risk_color = {"High": "#A32D2D", "Medium": "#BA7517", "Low": "#3B6D11"}.get(b.get("risk", "Medium"), "#BA7517")
    risk_bg    = {"High": "#FCEBEB", "Medium": "#FAEEDA", "Low": "#EAF3DE"}.get(b.get("risk", "Medium"), "#FAEEDA")

    def tag_style(tag: str) -> str:
        t = (tag or "").lower()
        if t in ("bearish", "bear"): return "background:#FCEBEB;color:#791F1F"
        if t in ("bullish", "bull"): return "background:#EAF3DE;color:#27500A"
        if t == "risk":              return "background:#FAEEDA;color:#633806"
        return "background:#F0EFE8;color:#5F5E5A"

    def rows(items: list, dot: str) -> str:
        return "".join(
            f'<tr><td style="padding:6px 0;border-bottom:1px solid #eee;font-size:13px">'
            f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
            f'background:{dot};margin-right:8px;vertical-align:middle"></span>{i}</td></tr>'
            for i in items
        )

    prev_note = ""
    if prev and prev.get("price"):
        try:
            cp = float(re.sub(r"[^0-9.]", "", b.get("price", "0")))
            pp = float(re.sub(r"[^0-9.]", "", prev["price"]))
            if pp:
                d = (cp - pp) / pp * 100
                c = "#3B6D11" if d > 0 else "#A32D2D"
                prev_note = f' <span style="font-size:12px;color:{c}">vs prev: {"+" if d>0 else ""}{d:.1f}%</span>'
        except Exception:
            pass

    news_rows = "".join(
        f'<tr><td style="padding:7px 0;border-bottom:1px solid #eee;font-size:13px">'
        f'<span style="font-size:10px;font-weight:600;padding:2px 7px;border-radius:4px;'
        f'{tag_style(n.get("tag",""))};margin-right:8px">{n.get("tag","")}</span>'
        f'{n.get("text","")}</td></tr>'
        for n in b.get("news", [])
    )

    def bar(label: str, val: int) -> str:
        color = "#E24B4A" if val >= 70 else "#EF9F27" if val >= 40 else "#639922"
        sev   = "Critical" if val >= 70 else "Elevated" if val >= 40 else "Moderate"
        sc    = "#A32D2D" if val >= 70 else "#BA7517" if val >= 40 else "#3B6D11"
        return (
            f'<div style="margin-bottom:10px">'
            f'<div style="display:flex;justify-content:space-between;font-size:12px;'
            f'color:#888;margin-bottom:4px"><span>{label}</span>'
            f'<span style="font-weight:600;color:{sc}">{sev}</span></div>'
            f'<div style="background:#F0EFE8;border-radius:4px;height:8px">'
            f'<div style="height:100%;border-radius:4px;width:{min(100,val)}%;background:{color}"></div>'
            f'</div></div>'
        )

    inv = "".join(
        f'<tr><td style="padding:5px 0;border-bottom:1px solid #eee;font-size:13px;color:#888">'
        f'{r.get("label","")}</td>'
        f'<td style="padding:5px 0;border-bottom:1px solid #eee;font-size:13px;'
        f'font-weight:600;text-align:right">{r.get("value","")}</td></tr>'
        for r in b.get("inventory", [])
    )

    watch = "".join(
        f'<div style="background:#F8F7F2;border-radius:8px;padding:10px 12px;min-width:150px">'
        f'<strong style="display:block;font-size:13px;margin-bottom:2px">{w.get("title","")}</strong>'
        f'<span style="font-size:12px;color:#888">{w.get("desc","")}</span></div>'
        for w in b.get("watch", [])
    )

    changed_title = f'What changed vs {prev["date"]}' if prev else "What changed today"
    changed = "".join(
        f'<tr><td style="padding:5px 0;border-bottom:1px solid #eee;font-size:13px">- {c}</td></tr>'
        for c in b.get("changed", [])
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coffee Brief - {b.get('date','')}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#F8F7F2;margin:0;padding:24px;color:#1a1a18}}
.card{{background:#fff;border-radius:12px;border:1px solid #E8E6DF;padding:20px 24px;margin-bottom:16px}}
h2{{font-size:12px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:.05em;margin:0 0 12px}}
table{{width:100%;border-collapse:collapse}}
.mg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px}}
.m{{background:#F8F7F2;border-radius:8px;padding:12px 14px}}
.tc{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
.wg{{display:flex;flex-wrap:wrap;gap:10px}}
@media(max-width:560px){{.tc{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div style="max-width:720px;margin:0 auto">

<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:20px">
  <div>
    <h1 style="font-size:20px;font-weight:600;margin:0">Coffee C - Daily Brief</h1>
    <p style="font-size:13px;color:#888;margin:4px 0 0">{b.get('date','')} - ICE Arabica</p>
  </div>
  <span style="padding:6px 14px;border-radius:8px;font-size:13px;font-weight:600;background:{risk_bg};color:{risk_color}">
    Risk: {b.get('risk','')}
  </span>
</div>

<div class="mg">
  <div class="m">
    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px">Futures price</div>
    <div style="font-size:20px;font-weight:600">{b.get('price','--')}{prev_note}</div>
    <div style="font-size:11px;color:#888;margin-top:3px">{b.get('priceChange','')} today - {b.get('priceMTD','')} MTD</div>
  </div>
  <div class="m">
    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px">52-week range</div>
    <div style="font-size:15px;font-weight:600">{b.get('priceRange52w','--')}</div>
    <div style="font-size:11px;color:#888;margin-top:3px">{b.get('priceContext','')}</div>
  </div>
  <div class="m">
    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px">ICE certified stocks</div>
    <div style="font-size:15px;font-weight:600">{b.get('iceStocks','--')}</div>
    <div style="font-size:11px;color:#888;margin-top:3px">{b.get('iceStocksChange','')}</div>
  </div>
  <div class="m">
    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px">USD / BRL</div>
    <div style="font-size:20px;font-weight:600">{b.get('usdBrl','--')}</div>
    <div style="font-size:11px;color:#888;margin-top:3px">{b.get('usdBrlContext','')}</div>
  </div>
</div>

<div class="card">
  <h2>Market summary</h2>
  <p style="font-size:14px;line-height:1.65;margin:0">{b.get('summary','')}</p>
</div>

<div class="tc">
  <div class="card" style="margin-bottom:0">
    <h2 style="color:#3B6D11">Bullish factors</h2>
    <table>{rows(b.get('bullish',[]), '#639922')}</table>
  </div>
  <div class="card" style="margin-bottom:0">
    <h2 style="color:#A32D2D">Bearish factors</h2>
    <table>{rows(b.get('bearish',[]), '#E24B4A')}</table>
  </div>
</div>
<div style="margin-bottom:16px"></div>

<div class="card"><h2>Inventory analysis</h2><table>{inv}</table></div>

<div class="card">
  <h2>Weather risk</h2>
  <table>{rows(b.get('weather',[]), '#888780')}</table>
</div>

<div class="card">
  <h2>Transportation and logistics</h2>
  {bar('Hormuz closure impact', b.get('freightHormuz', 0))}
  {bar('Red Sea / Bab el-Mandeb', b.get('freightRedSea', 0))}
  {bar('War risk insurance', b.get('freightInsurance', 0))}
  {bar('Brazil port operations', b.get('freightBrazil', 0))}
  <p style="font-size:13px;line-height:1.65;margin:8px 0 0;color:#555">{b.get('freight','')}</p>
</div>

<div class="card"><h2>Key news</h2><table>{news_rows}</table></div>

<div class="card"><h2>{changed_title}</h2><table>{changed}</table></div>

<div class="card">
  <h2>What to watch tomorrow</h2>
  <div class="wg">{watch}</div>
</div>

<p style="font-size:11px;color:#aaa;text-align:center;margin-top:24px;line-height:1.5">
  For research and informational purposes only. Not financial advice.<br>
  Generated by Claude - {b.get('date','')}
</p>
</div>
</body>
</html>"""

# -- Email sender -------------------------------------------------------------
def send_email(html: str, subject: str) -> None:
    smtp_host = os.environ.get("SMTP_HOST", "smtp.office365.com")
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
    print(f"Email sent to {to_addr}")

# -- Main ---------------------------------------------------------------------
def main() -> None:
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    print(f"Generating brief for {today}...")

    history = load_history()
    prev = history[0] if history else None
    prev_context = (
        f'Previous brief ({prev["date"]}): price={prev.get("price")}, risk={prev.get("risk")}.'
        if prev else "No previous brief."
    )

    print("Calling Claude API...")
    brief = fetch_brief(today, prev_context)
    print(f"Done - Risk: {brief.get('risk')} | Price: {brief.get('price')}")

    save_history({
        "date": brief["date"],
        "price": brief.get("price"),
        "risk": brief.get("risk"),
        "summary": brief.get("summary", "")[:300]
    }, history)

    html = render_html(brief, prev)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    (OUTPUT_DIR / f"brief-{date_slug}.html").write_text(html, encoding="utf-8")
    (OUTPUT_DIR / "latest.html").write_text(html, encoding="utf-8")
    (OUTPUT_DIR / f"brief-{date_slug}.json").write_text(
        json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved to output/brief-{date_slug}.html")

    if os.environ.get("SMTP_USER") and os.environ.get("EMAIL_TO"):
        subject = f"Coffee Brief {date_slug} | {brief.get('price','?')} | Risk: {brief.get('risk','')}"
        send_email(html, subject)
    else:
        print("Email not configured - skipping")

if __name__ == "__main__":
    main()
