#!/usr/bin/env python3
"""
Coffee C Futures - Daily Research Brief
Powered by Anthropic Claude with web search
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
SYSTEM_PROMPT = """You are a coffee futures research analyst.
Respond ONLY with a valid JSON object - no markdown fences, no preamble, no explanation.
All fields are required. Use "N/A" or 0 if data is unavailable."""

def build_user_prompt(today: str, prev_context: str) -> str:
    return (
        f"Today is {today}. {prev_context}\n\n"
        "Search for: Coffee C futures price, ICE certified stocks, "
        "Brazil/Vietnam weather, freight risk, USD/BRL, latest news.\n\n"
        "Return ONLY this JSON, filled with real data from your search:\n"
        '{"date":"' + today + '",'
        '"price":"$0.00","priceChange":"0%","priceMTD":"0%",'
        '"priceRange52w":"$0-$0","priceContext":"1 sentence",'
        '"iceStocks":"0 bags","iceStocksChange":"0 bags",'
        '"usdBrl":"0.00","usdBrlContext":"1 sentence",'
        '"risk":"Medium",'
        '"summary":"3-4 sentences",'
        '"bullish":["factor 1","factor 2","factor 3"],'
        '"bearish":["factor 1","factor 2","factor 3"],'
        '"inventory":['
          '{"label":"ICE stocks","value":""},'
          '{"label":"Weekly change","value":""},'
          '{"label":"Context","value":""},'
          '{"label":"Assessment","value":""}'
        '],'
        '"weather":["bull: item","bear: item","neutral: item"],'
        '"freight":"3-4 sentences",'
        '"freightHormuz":50,"freightRedSea":50,'
        '"freightInsurance":50,"freightBrazil":30,'
        '"news":['
          '{"tag":"Bearish","text":"headline"},'
          '{"tag":"Bullish","text":"headline"},'
          '{"tag":"Risk","text":"headline"}'
        '],'
        '"changed":["change 1","change 2"],'
        '"watch":['
          '{"title":"item 1","desc":"why"},'
          '{"title":"item 2","desc":"why"},'
          '{"title":"item 3","desc":"why"}'
        ']}'
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
    history = history[:30]
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

# -- API call -----------------------------------------------------------------
def fetch_brief(today: str, prev_context: str) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = build_user_prompt(today, prev_context)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    text_parts = [b.text for b in response.content if hasattr(b, "text")]
    raw = re.sub(r"```json|```", "", "\n".join(text_parts)).strip()
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError(f"No JSON in response: {raw[:300]}")

    json_str = re.sub(r",\s*([}\]])", r"\1", match.group())

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        print("JSON parse failed, waiting 70s then retrying...")
        time.sleep(70)
        response2 = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        text2 = re.sub(r"```json|```", "", "\n".join(
            b.text for b in response2.content if hasattr(b, "text")
        )).strip()
        match2 = re.search(r"\{[\s\S]*\}", text2)
        if not match2:
            raise ValueError("Retry also returned no JSON")
        return json.loads(re.sub(r",\s*([}\]])", r"\1", match2.group()))

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

    def factor_rows(items: list, dot_color: str) -> str:
        rows = ""
        for item in items:
            rows += (
                '<tr><td style="padding:6px 0;border-bottom:1px solid #eee;'
                'font-size:13px;vertical-align:top">'
                f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
                f'background:{dot_color};margin-right:8px;margin-top:4px"></span>'
                f'{item}</td></tr>'
            )
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
                prev_price_note = (
                    f' <span style="font-size:12px;color:{color}">'
                    f'vs prev: {sign}{diff:.1f}%</span>'
                )
        except Exception:
            pass

    news_rows = ""
    for n in b.get("news", []):
        news_rows += (
            '<tr><td style="padding:7px 0;border-bottom:1px solid #eee;'
            'font-size:13px;vertical-align:top">'
            f'<span style="font-size:10px;font-weight:600;padding:2px 8px;'
            f'border-radius:4px;{tag_style(n.get("tag",""))};margin-right:8px">'
            f'{n.get("tag","")}</span>{n.get("text","")}</td></tr>'
        )

    def bar(label: str, val: int) -> str:
        color = "#E24B4A" if val >= 70 else "#EF9F27" if val >= 40 else "#639922"
        severity = "Critical" if val >= 70 else "Elevated" if val >= 40 else "Moderate"
        sev_color = "#A32D2D" if val >= 70 else "#BA7517" if val >= 40 else "#3B6D11"
        return (
            f'<div style="margin-bottom:10px">'
            f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#888;margin-bottom:4px">'
            f'<span>{label}</span>'
            f'<span style="font-weight:600;color:{sev_color}">{severity}</span></div>'
            f'<div style="background:#F0EFE8;border-radius:4px;height:8px">'
            f'<div style="height:100%;border-radius:4px;width:{min(100,val)}%;background:{color}"></div>'
            f'</div></div>'
        )

    watch_cards = "".join(
        f'<div style="background:#F8F7F2;border-radius:8px;padding:10px 12px;min-width:160px">'
        f'<strong style="display:block;font-size:13px;margin-bottom:2px">{w.get("title","")}</strong>'
        f'<span style="font-size:12px;color:#888">{w.get("desc","")}</span></div>'
        for w in b.get("watch", [])
    )

    inv_rows = "".join(
        f'<tr>'
        f'<td style="padding:5px 0;border-bottom:1px solid #eee;font-size:13px;color:#888">{r.get("label","")}</td>'
        f'<td style="padding:5px 0;border-bottom:1px solid #eee;font-size:13px;font-weight:600;text-align:right">{r.get("value","")}</td>'
        f'</tr>'
        for r in b.get("inventory", [])
    )

    changed_title = f'What changed vs previous brief ({prev["date"]})' if prev else "What changed today"
    changed_rows = "".join(
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
h2{{font-size:13px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:.05em;margin:0 0 12px}}
table{{width:100%;border-collapse:collapse}}
.mg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px}}
.m{{background:#F8F7F2;border-radius:8px;padding:12px 14px}}
.ml{{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}}
.mv{{font-size:20px;font-weight:600}}
.md{{font-size:11px;margin-top:3px;color:#888}}
.tc{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
.wg{{display:flex;flex-wrap:wrap;gap:10px}}
@media(max-width:560px){{.tc{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div style="max-width:720px;margin:0 auto">
<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:20px">
  <div>
    <h1 style="font-size:20px;font-weight:600;margin:0">Coffee C - Daily Brief</h1>
    <p style="font-size:13px;color:#888;margin:4px 0 0">{b.get('date','')} - ICE Arabica (KCN26)</p>
  </div>
  <span style="padding:6px 14px;border-radius:8px;font-size:13px;font-weight:600;background:{risk_bg};color:{risk_color}">
    Risk: {b.get('risk','')}
  </span>
</div>
<div class="mg">
  <div class="m"><div class="ml">Futures price</div>
    <div class="mv">{b.get('price','--')}{prev_price_note}</div>
    <div class="md">{b.get('priceChange','')} today - {b.get('priceMTD','')} MTD</div></div>
  <div class="m"><div class="ml">52-week range</div>
    <div class="mv" style="font-size:15px">{b.get('priceRange52w','--')}</div>
    <div class="md">{b.get('priceContext','')}</div></div>
  <div class="m"><div class="ml">ICE certified stocks</div>
    <div class="mv" style="font-size:15px">{b.get('iceStocks','--')}</div>
    <div class="md">{b.get('iceStocksChange','')}</div></div>
  <div class="m"><div class="ml">USD / BRL</div>
    <div class="mv">{b.get('usdBrl','--')}</div>
    <div class="md">{b.get('usdBrlContext','')}</div></div>
</div>
<div class="card"><h2>Market summary</h2>
  <p style="font-size:14px;line-height:1.65;margin:0">{b.get('summary','')}</p></div>
<div class="tc">
  <div class="card" style="margin-bottom:0"><h2 style="color:#3B6D11">Bullish factors</h2>
    <table>{factor_rows(b.get('bullish',[]), '#639922')}</table></div>
  <div class="card" style="margin-bottom:0"><h2 style="color:#A32D2D">Bearish factors</h2>
    <table>{factor_rows(b.get('bearish',[]), '#E24B4A')}</table></div>
</div>
<div style="margin-bottom:16px"></div>
<div class="card"><h2>Inventory analysis</h2><table>{inv_rows}</table></div>
<div class="card"><h2>Weather risk</h2>
  <table>{factor_rows(b.get('weather',[]), '#888780')}</table></div>
<div class="card"><h2>Transportation and logistics</h2>
  {bar('Hormuz closure impact', b.get('freightHormuz', 0))}
  {bar('Red Sea / Bab el-Mandeb', b.get('freightRedSea', 0))}
  {bar('War risk insurance premium', b.get('freightInsurance', 0))}
  {bar('Brazil port operations', b.get('freightBrazil', 0))}
  <p style="font-size:13px;line-height:1.65;margin:8px 0 0;color:#555">{b.get('freight','')}</p></div>
<div class="card"><h2>Key news</h2><table>{news_rows}</table></div>
<div class="card"><h2>{changed_title}</h2><table>{changed_rows}</table></div>
<div class="card"><h2>What to watch tomorrow</h2><div class="wg">{watch_cards}</div></div>
<p style="font-size:11px;color:#aaa;text-align:center;margin-top:24px;line-height:1.5">
  For research and informational purposes only. Not financial advice.<br>
  Generated by Claude + web search - {b.get('date','')}
</p>
</div>
</body>
</html>"""

# -- Email sender -------------------------------------------------------------
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
    print(f"Email sent to {to_addr}")

# -- Main ---------------------------------------------------------------------
def main() -> None:
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    print(f"Generating brief for {today}...")

    history = load_history()
    prev = history[0] if history else None
    prev_context = (
        f'Previous brief ({prev["date"]}): price={prev.get("price")}, risk={prev.get("risk")}. '
        f'Summary: {prev.get("summary","")[:150]}'
        if prev else "No previous brief available."
    )

    print("Fetching market data via web search...")
    brief = fetch_brief(today, prev_context)
    print(f"Brief generated - Risk: {brief.get('risk')} | Price: {brief.get('price')}")

    save_history({
        "date": brief["date"],
        "price": brief.get("price"),
        "risk": brief.get("risk"),
        "summary": brief.get("summary", "")[:300]
    }, history)

    html = render_html(brief, prev)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = OUTPUT_DIR / f"brief-{date_slug}.html"
    out_file.write_text(html, encoding="utf-8")
    (OUTPUT_DIR / "latest.html").write_text(html, encoding="utf-8")
    (OUTPUT_DIR / f"brief-{date_slug}.json").write_text(
        json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved to {out_file}")

    if os.environ.get("SMTP_USER") and os.environ.get("EMAIL_TO"):
        subject = f"Coffee Brief {date_slug} | {brief.get('price','?')} | Risk: {brief.get('risk','')}"
        send_email(html, subject)
    else:
        print("Email not configured - skipping (set SMTP_USER, SMTP_PASS, EMAIL_TO)")

if __name__ == "__main__":
    main()
