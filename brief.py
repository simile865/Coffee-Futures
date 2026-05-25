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

EVENTS_FILE = Path("data/events.json")

SYSTEM_PROMPT = """
You are a professional coffee futures analyst.

Respond ONLY with valid JSON.

All narrative text must be in Simplified Chinese.

Keep High/Medium/Low/Bullish/Bearish/Risk in English.
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

def build_prompt(today, market, events, prev):

    return f"""
Date: {today}

Market Data:
{json.dumps(market, ensure_ascii=False)}

Upcoming Events:
{json.dumps(events, ensure_ascii=False)}

Previous Context:
{prev}

Write a rich professional coffee futures report.

Return ONLY JSON.

JSON structure:

{{
"summary":"STR",

"risk":"High|Medium|Low",

"inventory":"STR",

"usd":"STR",

"weather":[
"STR",
"STR",
"STR"
],

"bullish":[
"STR",
"STR",
"STR"
],

"bearish":[
"STR",
"STR",
"STR"
],

"freight":"STR"
}}
"""

def fetch_brief(today, market, events, prev):

    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"]
    )

    try:

        response = client.messages.create(

            model=MODEL,
            temperature=0,

            max_tokens=900,

            temperature=0,

            system=SYSTEM_PROMPT,

            messages=[
                {
                    "role": "user",

                    "content": build_prompt(
                        today,
                        market,
                        events,
                        prev
                    )
                }
            ]
        )

        raw = response.content[0].text.strip()

        print("===== CLAUDE RAW OUTPUT =====")
        print(raw)

        raw = re.sub(
            r"```json|```",
            "",
            raw
        ).strip()

        match = re.search(
            r"\{[\s\S]*\}",
            raw
        )

        if not match:

            print("No JSON detected.")

            return {

                "summary":
                "Claude 未返回有效JSON，系统已自动使用备用分析。",

                "risk":
                "Medium",

                "inventory":
                "ICE库存数据暂不可用。",

                "usd":
                "美元走势数据暂不可用。",

                "weather": [
                    "巴西天气维持正常。",
                    "越南产区降雨偏多。",
                    "哥伦比亚天气风险有限。"
                ],

                "bullish": [
                    "库存仍低于长期均值。",
                    "全球需求保持稳定。",
                    "部分产区天气存在不确定性。"
                ],

                "bearish": [
                    "巴西丰产预期持续。",
                    "美元阶段性走强。",
                    "ICE库存近期回升。"
                ],

                "freight":
                "全球航运风险维持中等水平。"
            }

        json_text = match.group()

        json_text = re.sub(
            r",\s*([}\]])",
            r"\1",
            json_text
        )

        try:

            parsed = json.loads(json_text)

            return parsed

        except Exception as e:

            print("JSON parsing failed.")
            print(e)

            print(json_text)

            return {

                "summary":
                "JSON解析失败，系统已自动使用备用分析。",

                "risk":
                "Medium",

                "inventory":
                "库存数据暂不可用。",

                "usd":
                "美元数据暂不可用。",

                "weather": [
                    "暂无天气数据"
                ],

                "bullish": [
                    "暂无数据"
                ],

                "bearish": [
                    "暂无数据"
                ],

                "freight":
                "暂无物流数据"
            }

    except Exception as e:

        print("Claude API failed.")
        print(e)

        return {

            "summary":
            "Claude API 调用失败，系统已自动生成备用简报。",

            "risk":
            "Medium",

            "inventory":
            "暂无库存数据。",

            "usd":
            "暂无美元数据。",

            "weather": [
                "暂无天气数据"
            ],

            "bullish": [
                "暂无利多数据"
            ],

            "bearish": [
                "暂无利空数据"
            ],

            "freight":
            "暂无物流数据"
        }

def render_html(brief, market, events, history):

    bullish_html = "".join(
        f"<li>{x}</li>"
        for x in brief.get("bullish", [])
    )

    bearish_html = "".join(
        f"<li>{x}</li>"
        for x in brief.get("bearish", [])
    )

    weather_html = "".join(
        f"<li>{x}</li>"
        for x in brief.get("weather", [])
    )

    events_html = "".join(
        f"""
        <li>
        <strong>{e.get("date")}</strong>
        |
        {e.get("event")}
        |
        {e.get("impact")}
        <br>
        {e.get("desc")}
        </li>
        """
        for e in events
    )

    history_json = json.dumps(history)

    html = f"""
<html>

<head>

<meta charset="UTF-8">

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>

body {{
    font-family: Arial;
    background: #F5F5F5;
    padding: 20px;
}}

.container {{
    max-width: 1000px;
    margin: auto;
}}

.card {{
    background: white;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
}}

h1 {{
    margin-top: 0;
}}

canvas {{
    margin-top: 10px;
}}

</style>

</head>

<body>

<div class="container">

<h1>咖啡C期货每日简报</h1>

<div class="card">

<h2>OHLC</h2>

<p>Open: {market.get("open")}</p>

<p>High: {market.get("high")}</p>

<p>Low: {market.get("low")}</p>

<p>Close: {market.get("close")}</p>

<p>Volume: {market.get("volume")}</p>

</div>

<div class="card">

<h2>Open Trend</h2>

<canvas id="openChart"></canvas>

</div>

<div class="card">

<h2>High Trend</h2>

<canvas id="highChart"></canvas>

</div>

<div class="card">

<h2>Low Trend</h2>

<canvas id="lowChart"></canvas>

</div>

<div class="card">

<h2>Close Trend</h2>

<canvas id="closeChart"></canvas>

</div>

<div class="card">

<h2>市场总结</h2>

<p>{brief.get("summary")}</p>

</div>

<div class="card">

<h2>库存分析</h2>

<p>{brief.get("inventory")}</p>

</div>

<div class="card">

<h2>美元与汇率</h2>

<p>{brief.get("usd")}</p>

</div>

<div class="card">

<h2>天气风险</h2>

<ul>

{weather_html}

</ul>

</div>

<div class="card">

<h2>利多因素</h2>

<ul>

{bullish_html}

</ul>

</div>

<div class="card">

<h2>利空因素</h2>

<ul>

{bearish_html}

</ul>

</div>

<div class="card">

<h2>物流风险</h2>

<p>{brief.get("freight")}</p>

</div>

<div class="card">

<h2>未来重要事件</h2>

<ul>

{events_html}

</ul>

</div>

<div class="card">

<h2>风险等级</h2>

<p>{brief.get("risk")}</p>

</div>

</div>

<script>

const history = %HISTORY_JSON%;

const labels = history.map(
    x => x.date
).reverse();

function buildChart(id, field, label) {{

    new Chart(
        document.getElementById(id),
        {{
            type: 'line',

            data: {{
                labels: labels,

                datasets: [
                    {{
                        label: label,

                        data: history.map(
                            x => x[field]
                        ).reverse(),

                        tension: 0.3
                    }}
                ]
            }}
        }}
    );
}}

buildChart(
    'openChart',
    'open',
    'Open'
);

buildChart(
    'highChart',
    'high',
    'High'
);

buildChart(
    'lowChart',
    'low',
    'Low'
);

buildChart(
    'closeChart',
    'close',
    'Close'
);

</script>

</body>

</html>
"""

    return html.replace(
        "%HISTORY_JSON%",
        history_json
    )

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

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    market = load_json(
        MARKET_FILE
    )

    events = load_json(
        EVENTS_FILE
    )

    history = load_history()

    prev = history[0] if history else {}

    brief = fetch_brief(
        today,
        market,
        events,
        str(prev)
    )

    save_history({

        "date": today,

        "open": market.get("open"),

        "high": market.get("high"),

        "low": market.get("low"),

        "close": market.get("close"),

        "volume": market.get("volume"),

        "risk": brief.get("risk")

    }, history)

    html = render_html(
        brief,
        market,
        events,
        history
    )

    html_file = OUTPUT_DIR / "latest.html"

    html_file.write_text(
        html,
        encoding="utf-8"
    )

    if os.environ.get("SMTP_USER"):

        subject = (
            f"Coffee Brief "
            f"{today} "
            f"{market.get('close')}"
        )

        send_email(
            html,
            subject
        )

    print("Done")

if __name__ == "__main__":
    main()
