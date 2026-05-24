#!/usr/bin/env python3
"""
Coffee C Futures - Daily Research Brief (Chinese output)
"""

import anthropic
import json
import os
import re
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1500

HISTORY_FILE = Path("output/history.json")
OUTPUT_DIR = Path("output")

SYSTEM_PROMPT = (
    "You are a coffee futures research analyst. "
    "Respond ONLY with valid JSON. "
    "No markdown fences. "
    "All text values must be in Simplified Chinese. "
    "Keep High/Medium/Low/Bullish/Bearish/Risk in English."
)

def build_prompt(today: str, prev: str) -> str:
    return (
        f"Date: {today}. {prev}\n"
        "Write a coffee C futures daily research brief as JSON.\n"
        "Include market summary, ICE stocks, weather, freight risk, USD/BRL, "
        "bullish and bearish factors.\n"
        "JSON structure:\n"
        '{"date":"STR","price":"$X.XX","priceChange":"X%",'
        '"priceMTD":"X%","priceRange52w":"$X-$X","priceContext":"STR",'
        '"iceStocks":"STR","iceStocksChange":"STR",'
        '"usdBrl":"X.XX","usdBrlContext":"STR",'
        '"risk":"High|Medium|Low","summary":"STR",'
        '"bullish":["STR","STR","STR"],'
        '"bearish":["STR","STR","STR"],'
        '"weather":["STR","STR","STR"],'
        '"freight":"STR",'
        '"freightHormuz":INT,"freightRedSea":INT,'
        '"freightInsurance":INT,"freightBrazil":INT}'
    )

def load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_history(entry, history):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    history.insert(0, entry)

    HISTORY_FILE.write_text(
        json.dumps(history[:30], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def fetch_brief(today, prev_context):

    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"]
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": build_prompt(today, prev_context)
            }
        ],
    )

    raw = response.content[0].text.strip()

    raw = re.sub(r"```json|```", "", raw)

    match = re.search(r"\{[\s\S]*\}", raw)

    if not match:
        raise ValueError("Claude did not return JSON")

    json_str = re.sub(r",\s*([}\]])", r"\1", match.group())

    return json.loads(json_str)

def render_html(b):

    risk_color = {
        "High": "#A32D2D",
        "Medium": "#BA7517",
        "Low": "#3B6D11"
    }.get(b.get("risk", "Medium"))

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>咖啡期货日报</title>

<style>

body {{
    font-family: Arial, sans-serif;
    background: #F5F5F5;
    margin: 0;
    padding: 20px;
}}

.container {{
    max-width: 900px;
    margin: auto;
    background: white;
    padding: 30px;
    border-radius: 12px;
}}

.card {{
    background: #FAFAFA;
    padding: 16px;
    border-radius: 10px;
    margin-bottom: 16px;
}}

h1 {{
    margin-top: 0;
}}

.price {{
    font-size: 32px;
    font-weight: bold;
}}

.risk {{
    color: {risk_color};
    font-weight: bold;
}}

ul {{
    line-height: 1.8;
}}

</style>

</head>

<body>

<div class="container">

<h1>咖啡C期货每日简报</h1>

<div class="card">
    <div>日期：{b.get("date")}</div>
    <div class="price">{b.get("price")}</div>
    <div>日变化：{b.get("priceChange")}</div>
    <div>月变化：{b.get("priceMTD")}</div>
    <div>52周区间：{b.get("priceRange52w")}</div>
</div>

<div class="card">
    <h2>市场总结</h2>
    <p>{b.get("summary")}</p>
</div>

<div class="card">
    <h2>ICE库存</h2>
    <p>{b.get("iceStocks")}</p>
    <p>{b.get("iceStocksChange")}</p>
</div>

<div class="card">
    <h2>美元 / 巴西雷亚尔</h2>
    <p>{b.get("usdBrl")}</p>
    <p>{b.get("usdBrlContext")}</p>
</div>

<div class="card">
    <h2>天气风险</h2>

    <ul>
        {''.join(f"<li>{x}</li>" for x in b.get("weather", []))}
    </ul>
</div>

<div class="card">
    <h2>利多因素</h2>

    <ul>
        {''.join(f"<li>{x}</li>" for x in b.get("bullish", []))}
    </ul>
</div>

<div class="card">
    <h2>利空因素</h2>

    <ul>
        {''.join(f"<li>{x}</li>" for x in b.get("bearish", []))}
    </ul>
</div>

<div class="card">
    <h2>物流风险</h2>

    <p>{b.get("freight")}</p>

    <p>Hormuz: {b.get("freightHormuz")}</p>
    <p>Red Sea: {b.get("freightRedSea")}</p>
    <p>Insurance: {b.get("freightInsurance")}</p>
    <p>Brazil Port: {b.get("freightBrazil")}</p>
</div>

<div class="card">
    <h2>风险等级</h2>

    <div class="risk">{b.get("risk")}</div>
</div>

</div>

</body>
</html>
"""

def send_email(html, subject):

    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    to_addr = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")

    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr

    msg.attach(
        MIMEText(html, "html", "utf-8")
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as s:

        s.starttls()

        s.login(smtp_user, smtp_pass)

        s.sendmail(
            smtp_user,
            to_addr,
            msg.as_string()
        )

def main():

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    print("Generating coffee brief...")

    history = load_history()

    prev = history[0] if history else None

    prev_context = (
        f'Previous price={prev.get("price")}'
        if prev else "No previous brief"
    )

    brief = fetch_brief(
        today,
        prev_context
    )

    save_history(
        {
            "date": brief["date"],
            "price": brief.get("price"),
            "risk": brief.get("risk")
        },
        history
    )

    html = render_html(brief)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    date_slug = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    html_file = OUTPUT_DIR / f"brief-{date_slug}.html"

    html_file.write_text(
        html,
        encoding="utf-8"
    )

    latest = OUTPUT_DIR / "latest.html"

    latest.write_text(
        html,
        encoding="utf-8"
    )

    json_file = OUTPUT_DIR / f"brief-{date_slug}.json"

    json_file.write_text(
        json.dumps(
            brief,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("Files generated successfully")

    if os.environ.get("SMTP_USER"):

        subject = (
            f"咖啡期货日报 {date_slug} "
            f"| {brief.get('price')} "
            f"| 风险: {brief.get('risk')}"
        )

        send_email(
            html,
            subject
        )

        print("Email sent")

if __name__ == "__main__":
    main()
