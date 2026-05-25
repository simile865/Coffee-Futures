#!/usr/bin/env python3

import anthropic
import json
import os
import re
import smtplib

from datetime import datetime, timezone
from pathlib import Path

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

MODEL = "claude-sonnet-4-6"

OUTPUT_DIR = Path("output")

HISTORY_FILE = OUTPUT_DIR / "history.json"

MARKET_FILE = Path("data/market.json")

SYSTEM_PROMPT = """
You are a professional coffee futures analyst.

Write ALL analysis in Simplified Chinese.

DO NOT use markdown.

Keep analysis concise but professional.
"""


def load_json(path):

    if path.exists():

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    return {}


def load_history():

    if HISTORY_FILE.exists():

        return json.loads(
            HISTORY_FILE.read_text(
                encoding="utf-8"
            )
        )

    return []


def save_history(entry, history):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    history.insert(0, entry)

    HISTORY_FILE.write_text(
        json.dumps(
            history[:30],
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def fetch_analysis(market):

    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"]
    )

    prompt = f"""
Coffee market data:

{json.dumps(market, ensure_ascii=False)}

Please write:

1. 市场总结（150字）
2. ICE库存分析
3. 美元与巴西雷亚尔
4. 天气风险
5. 三个利多因素
6. 三个利空因素
7. 物流风险
8. 风险等级（High/Medium/Low）

Format:

市场总结:
...

ICE库存:
...

美元:
...

天气:
1.
2.
3.

利多:
1.
2.
3.

利空:
1.
2.
3.

物流:
...

风险:
...
"""

    try:

        response = client.messages.create(

            model=MODEL,

            max_tokens=1000,

            temperature=0,

            system=SYSTEM_PROMPT,

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.content[0].text.strip()

    except Exception:

        return """
市场总结:
Claude API调用失败。

ICE库存:
暂无数据。

美元:
暂无数据。

天气:
1. 暂无数据
2. 暂无数据
3. 暂无数据

利多:
1. 暂无数据
2. 暂无数据
3. 暂无数据

利空:
1. 暂无数据
2. 暂无数据
3. 暂无数据

物流:
暂无数据。

风险:
Medium
"""


def extract_section(text, title):

    pattern = rf"{title}:(.*?)(?:\n[A-Za-z\u4e00-\u9fa5]+:|$)"

    match = re.search(
        pattern,
        text,
        re.S
    )

    if match:

        return match.group(1).strip()

    return ""


def extract_list(text, title):

    section = extract_section(
        text,
        title
    )

    lines = []

    for line in section.splitlines():

        line = line.strip()

        if line:

            line = re.sub(
                r"^\d+\.",
                "",
                line
            ).strip()

            lines.append(line)

    return lines


def render_html(
    market,
    analysis
):

    summary = extract_section(
        analysis,
        "市场总结"
    )

    inventory = extract_section(
        analysis,
        "ICE库存"
    )

    usd = extract_section(
        analysis,
        "美元"
    )

    freight = extract_section(
        analysis,
        "物流"
    )

    risk = extract_section(
        analysis,
        "风险"
    )

    weather = extract_list(
        analysis,
        "天气"
    )

    bullish = extract_list(
        analysis,
        "利多"
    )

    bearish = extract_list(
        analysis,
        "利空"
    )

    weather_html = "".join(
        f"<li>{x}</li>"
        for x in weather
    )

    bullish_html = "".join(
        f"<li>{x}</li>"
        for x in bullish
    )

    bearish_html = "".join(
        f"<li>{x}</li>"
        for x in bearish
    )

    risk_color = {
        "High": "#EF5350",
        "Medium": "#FFA726",
        "Low": "#66BB6A"
    }.get(risk, "#FFA726")

    return f"""
<html>

<head>

<meta charset="UTF-8">

<style>

body {{

    background: #0F1116;

    color: #EAECEF;

    font-family: Arial;

    padding: 30px;
}}

.container {{

    max-width: 1100px;

    margin: auto;
}}

h1 {{

    margin-bottom: 30px;
}}

.card {{

    background: #1A1D25;

    border: 1px solid #2A2E39;

    border-radius: 14px;

    padding: 22px;

    margin-bottom: 20px;
}}

.price-grid {{

    display: grid;

    grid-template-columns:
    repeat(auto-fit, minmax(180px,1fr));

    gap: 16px;

    margin-bottom: 24px;
}}

.price-card {{

    background: #1A1D25;

    border: 1px solid #2A2E39;

    border-radius: 14px;

    padding: 20px;
}}

.price-card h3 {{

    margin: 0;

    color: #9AA4B2;

    font-size: 13px;
}}

.price-card p {{

    margin-top: 10px;

    font-size: 34px;

    font-weight: bold;
}}

.section-grid {{

    display: grid;

    grid-template-columns:
    1fr 1fr;

    gap: 20px;
}}

li {{

    margin-bottom: 10px;

    line-height: 1.6;
}}

.risk {{

    color: {risk_color};

    font-size: 28px;

    font-weight: bold;
}}

p {{

    line-height: 1.8;
}}

@media(max-width:768px) {{

.section-grid {{

    grid-template-columns:1fr;
}}

}}

</style>

</head>

<body>

<div class="container">

<h1>咖啡C期货每日简报</h1>

<div class="price-grid">

<div class="price-card">
<h3>OPEN</h3>
<p>{market.get("open")}</p>
</div>

<div class="price-card">
<h3>HIGH</h3>
<p>{market.get("high")}</p>
</div>

<div class="price-card">
<h3>LOW</h3>
<p>{market.get("low")}</p>
</div>

<div class="price-card">
<h3>CLOSE</h3>
<p>{market.get("close")}</p>
</div>

<div class="price-card">
<h3>VOLUME</h3>
<p>{market.get("volume")}</p>
</div>

</div>

<div class="card">

<h2>市场总结</h2>

<p>{summary}</p>

</div>

<div class="section-grid">

<div class="card">

<h2>ICE库存</h2>

<p>{inventory}</p>

</div>

<div class="card">

<h2>美元 / 巴西雷亚尔</h2>

<p>{usd}</p>

</div>

</div>

<div class="section-grid">

<div class="card">

<h2>天气风险</h2>

<ul>

{weather_html}

</ul>

</div>

<div class="card">

<h2>物流风险</h2>

<p>{freight}</p>

</div>

</div>

<div class="section-grid">

<div class="card">

<h2 style="color:#66BB6A">

利多因素

</h2>

<ul>

{bullish_html}

</ul>

</div>

<div class="card">

<h2 style="color:#EF5350">

利空因素

</h2>

<ul>

{bearish_html}

</ul>

</div>

</div>

<div class="card">

<h2>风险等级</h2>

<div class="risk">

{risk}

</div>

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
        MIMEText(
            html,
            "html",
            "utf-8"
        )
    )

    with smtplib.SMTP(
        "smtp.gmail.com",
        587
    ) as s:

        s.starttls()

        s.login(
            smtp_user,
            smtp_pass
        )

        s.sendmail(
            smtp_user,
            to_addr,
            msg.as_string()
        )


def main():

    OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    market = load_json(
        MARKET_FILE
    )

    history = load_history()

    analysis = fetch_analysis(
        market
    )

    save_history({

        "date":
        datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d"),

        "close":
        market.get("close")

    }, history)

    html = render_html(
        market,
        analysis
    )

    (OUTPUT_DIR / "latest.html").write_text(
        html,
        encoding="utf-8"
    )

    if os.environ.get("SMTP_USER"):

        send_email(
            html,
            "Coffee Futures Daily Brief"
        )

    print("Done")


if __name__ == "__main__":
    main()
