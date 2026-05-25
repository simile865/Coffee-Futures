#!/usr/bin/env python3

import html
import json
import os
import re
import smtplib
import csv
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.utils import parsedate_to_datetime

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


MODEL = "claude-sonnet-4-6"

OUTPUT_DIR = Path("output")
HISTORY_FILE = OUTPUT_DIR / "history.json"
MARKET_FILE = Path("data/market.json")
HISTORY_CSV_FILE = Path("data/history.csv")
FUNDAMENTALS_FILE = Path("data/fundamentals.json")

CHART_START_DATE = "2026-01-01"
YAHOO_SYMBOL = os.environ.get("YAHOO_SYMBOL", "KC=F")
MACRO_SYMBOLS = {
    "usd_brl": os.environ.get("YAHOO_USD_BRL_SYMBOL", "BRL=X"),
    "dxy": os.environ.get("YAHOO_DXY_SYMBOL", "DX-Y.NYB"),
}
BARCHART_ICE_STOCK_URL = (
    "https://www.barchart.com/cmdty/data/fundamental/explore/IC2QY5DOB.CS"
)
CFTC_DISAGG_FUTURES_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
CFTC_COFFEE_FILTER = os.environ.get(
    "CFTC_COFFEE_FILTER",
    "upper(market_and_exchange_names) like '%COFFEE C%'",
)
EVENT_LOOKAHEAD_DAYS = int(os.environ.get("EVENT_LOOKAHEAD_DAYS", "30"))
NEWS_LOOKBACK_DAYS = int(os.environ.get("NEWS_LOOKBACK_DAYS", "7"))
MAX_NEWS_ITEMS = int(os.environ.get("MAX_NEWS_ITEMS", "8"))
NEWS_FETCH_DEADLINE_SECONDS = int(os.environ.get("NEWS_FETCH_DEADLINE_SECONDS", "25"))
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
NEWS_QUERIES = [
    (
        "coffee futures OR arabica coffee OR robusta coffee OR "
        "Brazil coffee harvest OR Vietnam coffee exports OR "
        "coffee weather OR coffee production OR ICE coffee stocks"
    ),
    (
        "Brazil coffee exports OR Cecafe coffee OR Santos port coffee OR "
        "Brazil coffee logistics OR Brazil arabica harvest"
    ),
    (
        "Colombia coffee exports OR Colombia coffee harvest OR "
        "Peru coffee exports OR South America coffee logistics"
    ),
    "domain:reuters.com coffee futures OR arabica coffee OR robusta coffee",
    "domain:bloomberg.com coffee futures OR arabica coffee OR robusta coffee",
]
PRIORITY_NEWS_DOMAINS = ("reuters.com", "bloomberg.com")
SOUTH_AMERICA_KEYWORDS = (
    "brazil",
    "brasil",
    "santos",
    "cecafe",
    "cecafé",
    "conab",
    "cepea",
    "safras",
    "colombia",
    "colombian",
    "peru",
    "peruvian",
    "south america",
    "latin america",
)

EVENTS = [
    {
        "date": "2026-05-28",
        "title": "USDA FAS PSD data release",
        "impact": "更新全球供需数据库；若咖啡产量、出口或库存假设变化，可能影响中期基本面判断。",
        "source": "USDA FAS",
    },
    {
        "date": "2026-05-29",
        "title": "CFTC COT持仓报告",
        "impact": "观察Managed Money是否继续减多或加空；资金方向会影响短线情绪。",
        "source": "CFTC",
    },
    {
        "date": "2026-06-05",
        "title": "美国非农就业",
        "impact": "影响美元和利率预期；强美元通常压制以美元计价的大宗商品。",
        "source": "BLS",
    },
    {
        "date": "2026-06-05",
        "title": "CFTC COT持仓报告",
        "impact": "关注基金净持仓是否延续下降。",
        "source": "CFTC",
    },
    {
        "date": "2026-06-10",
        "title": "美国CPI",
        "impact": "通胀数据会影响美元、利率和大宗商品风险偏好。",
        "source": "BLS",
    },
    {
        "date": "2026-06-11",
        "title": "美国PPI",
        "impact": "与CPI共同影响通胀预期和美元走势。",
        "source": "BLS",
    },
    {
        "date": "2026-06-11",
        "title": "NOAA ENSO诊断讨论",
        "impact": "影响巴西、越南、哥伦比亚天气风险预期，尤其是产量和品质风险。",
        "source": "NOAA CPC",
    },
    {
        "date": "2026-06-12",
        "title": "CFTC COT持仓报告",
        "impact": "验证资金是否在宏观数据后重新调整咖啡仓位。",
        "source": "CFTC",
    },
    {
        "date": "2026-06-17",
        "title": "FOMC利率决议",
        "impact": "重点看美元方向、点阵图/经济预测和鲍威尔表态。",
        "source": "Federal Reserve",
    },
    {
        "date": "2026-06-22",
        "title": "Coffee C Jul26第一通知日",
        "impact": "交割窗口临近，近月流动性、价差和库存敏感度可能上升。",
        "source": "ICE",
    },
    {
        "date": "2026-06-22",
        "title": "CFTC COT持仓报告",
        "impact": "美国假期导致延后发布；注意报告数据仍截至前一周二。",
        "source": "CFTC",
    },
    {
        "date": "2026-06-26",
        "title": "CFTC COT持仓报告",
        "impact": "跟踪FND后资金是否继续移仓或降风险。",
        "source": "CFTC",
    },
    {
        "date": "2026-07-01",
        "title": "Coffee C Jul26第一交割日",
        "impact": "库存、交割意愿和仓单变化对近月价格更敏感。",
        "source": "ICE",
    },
    {
        "date": "2026-07-02",
        "title": "美国非农就业",
        "impact": "因假期提前发布；关注美元和风险资产反应。",
        "source": "BLS",
    },
    {
        "date": "2026-07-06",
        "title": "CFTC COT持仓报告",
        "impact": "美国假期导致延后发布。",
        "source": "CFTC",
    },
    {
        "date": "2026-07-09",
        "title": "NOAA ENSO诊断讨论",
        "impact": "更新夏季ENSO路径，对咖啡产区天气风险定价重要。",
        "source": "NOAA CPC",
    },
    {
        "date": "2026-07-10",
        "title": "CFTC COT持仓报告",
        "impact": "观察基金在7月合约交割期内的持仓变化。",
        "source": "CFTC",
    },
    {
        "date": "2026-07-15",
        "title": "美国PPI",
        "impact": "影响美元和美债收益率。",
        "source": "BLS",
    },
    {
        "date": "2026-07-17",
        "title": "CFTC COT持仓报告",
        "impact": "临近Jul26最后交易日，关注资金移仓和降风险。",
        "source": "CFTC",
    },
    {
        "date": "2026-07-21",
        "title": "Coffee C Jul26最后交易日",
        "impact": "近月合约退出交易，价差和连续合约切换需特别注意。",
        "source": "ICE",
    },
    {
        "date": "2026-07-29",
        "title": "FOMC利率决议",
        "impact": "影响美元、利率预期和大宗商品风险偏好。",
        "source": "Federal Reserve",
    },
]

SYSTEM_PROMPT = """
You are a professional coffee futures analyst.

Write ALL analysis in Simplified Chinese.

DO NOT use markdown.

Keep analysis concise but professional.

Use only the provided market and fundamental data for specific claims.

If a category lacks reliable data, say "暂无可验证更新" instead of inventing details.

Always mention the actual data date when discussing delayed reports such as CFTC COT.
"""


def load_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_history():
    if HISTORY_FILE.exists():
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    return []


def get_first(row, names):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def load_history_csv():
    if not HISTORY_CSV_FILE.exists():
        return []

    rows = []

    with HISTORY_CSV_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            date = get_first(row, ("Date", "date", "Trade Date", "trade_date"))
            open_price = get_first(row, ("Open", "open"))
            high = get_first(row, ("High", "high"))
            low = get_first(row, ("Low", "low"))
            close = get_first(row, ("Close", "close", "Settle", "settle", "Last", "last"))
            volume = get_first(row, ("Volume", "volume", "Vol.", "vol"))

            if not date:
                continue

            rows.append(
                {
                    "date": str(date)[:10],
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )

    return clean_history(rows)


def fetch_yahoo_history(symbol=YAHOO_SYMBOL, start_date=CHART_START_DATE):
    start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    period1 = int(start_dt.timestamp())
    period2 = int(time.time()) + 86400

    query = urllib.parse.urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    encoded_symbol = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 coffee-futures-brief/1.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))

    result = payload.get("chart", {}).get("result", [None])[0]
    if not result:
        return []

    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]

    rows = []
    for index, timestamp in enumerate(timestamps):
        open_price = (quote.get("open") or [None])[index]
        high = (quote.get("high") or [None])[index]
        low = (quote.get("low") or [None])[index]
        close = (quote.get("close") or [None])[index]
        volume = (quote.get("volume") or [None])[index]

        if None in (open_price, high, low, close):
            continue

        rows.append(
            {
                "date": datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d"),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

    return clean_history(rows)


def fetch_yahoo_quote_history(symbol, days=7):
    period2 = int(time.time()) + 86400
    period1 = period2 - days * 86400

    query = urllib.parse.urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    encoded_symbol = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 coffee-futures-brief/1.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))

    result = payload.get("chart", {}).get("result", [None])[0]
    if not result:
        return []

    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []

    rows = []
    for index, timestamp in enumerate(timestamps):
        close = closes[index] if index < len(closes) else None
        if close is None:
            continue

        rows.append(
            {
                "date": datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d"),
                "close": float(close),
            }
        )

    return rows


def latest_quote_snapshot(symbol, label):
    rows = fetch_yahoo_quote_history(symbol)
    if not rows:
        raise ValueError(f"No Yahoo data for {symbol}")

    latest = rows[-1]
    prior = rows[-2] if len(rows) >= 2 else None
    change = latest["close"] - prior["close"] if prior else None
    change_pct = change / prior["close"] * 100 if prior and prior["close"] else None

    return {
        "symbol": symbol,
        "label": label,
        "date": latest["date"],
        "value": latest["close"],
        "prior_value": prior["close"] if prior else None,
        "prior_date": prior["date"] if prior else None,
        "change": change,
        "change_pct": change_pct,
        "source": "Yahoo Finance",
    }


def latest_history_market(history):
    cleaned = clean_history(history)
    if not cleaned:
        return None
    return sorted(cleaned, key=lambda item: item["date"])[-1]


def html_to_text(value):
    text = re.sub(r"<script.*?</script>", " ", value, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_int(value):
    number = parse_number(value)
    if number is None:
        return None
    return int(round(number))


def pick_value(row, names):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def fetch_ice_inventory():
    request = urllib.request.Request(
        BARCHART_ICE_STOCK_URL,
        headers={
            "User-Agent": "Mozilla/5.0 coffee-futures-brief/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        page = response.read().decode("utf-8", errors="replace")

    text = html_to_text(page)

    value_match = re.search(r"Most Recent Value\s+([\d,]+)", text, re.I)
    date_match = re.search(r"Most Recent Date\s+(\d{2}-\d{2}-\d{4})", text, re.I)
    prior_match = re.search(
        r"Prior Value\s+([\d,]+)\s+Prior Value Date\s+(\d{2}-\d{2}-\d{4})",
        text,
        re.I,
    )

    current_value = parse_int(value_match.group(1)) if value_match else None
    prior_value = parse_int(prior_match.group(1)) if prior_match else None

    if current_value is None:
        raise ValueError("Could not find ICE certified stocks value")

    change = current_value - prior_value if prior_value is not None else None
    change_pct = change / prior_value * 100 if prior_value else None

    history = []
    history_start = text.find("Historical Data")
    history_end = text.find("Get access to full historical data", history_start)
    history_text = text[history_start:history_end] if history_start != -1 else ""

    for date, value in re.findall(r"(\d{2}-\d{2}-\d{4})\s+([\d,]+)", history_text):
        parsed_value = parse_int(value)
        if parsed_value is None:
            continue
        history.append({"date": date, "value": parsed_value})

    if date_match and not any(item["date"] == date_match.group(1) for item in history):
        history.insert(0, {"date": date_match.group(1), "value": current_value})

    history = sorted(
        {item["date"]: item for item in history}.values(),
        key=lambda item: datetime.strptime(item["date"], "%m-%d-%Y"),
    )

    return {
        "ice_inventory": {
            "certified_stocks": current_value,
            "date": date_match.group(1) if date_match else None,
            "prior_value": prior_value,
            "prior_date": prior_match.group(2) if prior_match else None,
            "change": change,
            "change_pct": change_pct,
            "unit": "bags",
            "history": history,
            "source": "ICE via Barchart",
            "url": BARCHART_ICE_STOCK_URL,
        }
    }


def fetch_macro_data():
    return {
        "usd_brl": latest_quote_snapshot(MACRO_SYMBOLS["usd_brl"], "USD/BRL"),
        "dxy": latest_quote_snapshot(MACRO_SYMBOLS["dxy"], "U.S. Dollar Index"),
    }


def parse_gdelt_date(value):
    if not value:
        return ""
    try:
        return datetime.strptime(str(value)[:15], "%Y%m%dT%H%M%S").strftime("%Y-%m-%d")
    except ValueError:
        return str(value)[:10]


def news_impact_hint(title, domain):
    text = f"{title} {domain}".lower()

    if any(word in text for word in ("harvest", "crop", "production", "yield", "record")):
        return "产量/收成相关，可能改变市场对供应宽松或偏紧的预期。"
    if any(
        word in text
        for word in (
            "weather",
            "drought",
            "rain",
            "rainfall",
            "dry",
            "frost",
            "heat",
            "el nino",
            "el niño",
            "la nina",
            "la niña",
        )
    ):
        return "天气相关，需关注是否影响巴西、越南或哥伦比亚产区产量与品质。"
    if re.search(r"\b(exports?|shipments?|ports?|freight|logistics)\b", text):
        return "出口或物流相关，可能影响现货流通和近月供应节奏。"
    if any(word in text for word in ("stock", "inventory", "certified", "warehouse")):
        return "库存相关，可能影响近月支撑、价差和交割预期。"
    if any(word in text for word in ("fund", "speculator", "cftc", "position")):
        return "资金持仓相关，可能影响短线情绪和趋势延续性。"
    if any(word in text for word in ("brazil", "vietnam", "colombia", "honduras", "ethiopia")):
        return "主产国相关，需结合出口、天气和产量数据确认影响方向。"

    return "咖啡市场相关更新，需结合价格、库存和持仓数据交叉验证。"


def fetch_gdelt_articles(query):
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": "10",
        "timespan": f"{NEWS_LOOKBACK_DAYS}d",
        "sort": "HybridRel",
    }
    request = urllib.request.Request(
        f"{GDELT_DOC_URL}?{urllib.parse.urlencode(params)}",
        headers={
            "User-Agent": "Mozilla/5.0 coffee-futures-brief/1.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return payload.get("articles") or []


def fetch_google_news_articles(query):
    google_query = (
        query.replace("domain:reuters.com", "site:reuters.com")
        .replace("domain:bloomberg.com", "site:bloomberg.com")
    )
    params = {
        "q": google_query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }
    request = urllib.request.Request(
        f"https://news.google.com/rss/search?{urllib.parse.urlencode(params)}",
        headers={
            "User-Agent": "Mozilla/5.0 coffee-futures-brief/1.0",
            "Accept": "application/rss+xml,application/xml,text/xml",
        },
    )

    with urllib.request.urlopen(request, timeout=8) as response:
        root = ET.fromstring(response.read())

    articles = []
    for item in root.findall("./channel/item")[:20]:
        title = item.findtext("title") or ""
        url = item.findtext("link") or ""
        source = item.findtext("source") or ""
        pub_date = item.findtext("pubDate") or ""

        date = ""
        if pub_date:
            try:
                date = parsedate_to_datetime(pub_date).astimezone(timezone.utc).strftime(
                    "%Y-%m-%d"
                )
            except (TypeError, ValueError):
                date = pub_date[:16]

        if not title or not url:
            continue

        domain = source or urllib.parse.urlparse(url).netloc
        articles.append(
            {
                "date": date,
                "title": title.strip(),
                "domain": domain,
                "source_country": "",
                "url": url,
                "impact": news_impact_hint(title, domain),
                "discovered_by": "Google News RSS",
            }
        )

    return articles


def fetch_news_reports():
    articles = {}
    deadline = time.monotonic() + NEWS_FETCH_DEADLINE_SECONDS

    for query in NEWS_QUERIES:
        if time.monotonic() >= deadline or len(articles) >= MAX_NEWS_ITEMS:
            break

        try:
            for article in fetch_gdelt_articles(query):
                url = article.get("url")
                title = article.get("title")
                if not url or not title:
                    continue

                domain = article.get("domain") or urllib.parse.urlparse(url).netloc
                date = parse_gdelt_date(article.get("seendate"))
                key = url.split("?")[0]
                articles[key] = {
                    "date": date,
                    "title": title.strip(),
                    "domain": domain,
                    "source_country": article.get("sourcecountry") or "",
                    "url": url,
                    "impact": news_impact_hint(title, domain),
                    "discovered_by": "GDELT",
                }
                if len(articles) >= MAX_NEWS_ITEMS:
                    break
        except Exception as exc:
            print(f"News query failed ({query}): {exc}")

        if time.monotonic() >= deadline or len(articles) >= MAX_NEWS_ITEMS:
            break

        if len(articles) < MAX_NEWS_ITEMS:
            try:
                for article in fetch_google_news_articles(query):
                    key = article["url"].split("?")[0]
                    articles[key] = article
                    if len(articles) >= MAX_NEWS_ITEMS:
                        break
            except Exception as exc:
                print(f"Google News RSS query failed ({query}): {exc}")

    def news_rank(item):
        domain = (item.get("domain") or "").lower()
        priority = 1 if any(source in domain for source in PRIORITY_NEWS_DOMAINS) else 0
        return (priority, item.get("date") or "", domain)

    ranked = sorted(
        articles.values(),
        key=news_rank,
        reverse=True,
    )

    return ranked[:MAX_NEWS_ITEMS]


def fetch_cftc_cot():
    query = urllib.parse.urlencode(
        {
            "$limit": "80",
            "$where": CFTC_COFFEE_FILTER,
            "$order": "report_date_as_yyyy_mm_dd DESC",
        }
    )
    request = urllib.request.Request(
        f"{CFTC_DISAGG_FUTURES_URL}?{query}",
        headers={
            "User-Agent": "Mozilla/5.0 coffee-futures-brief/1.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        rows = json.loads(response.read().decode("utf-8"))

    if not rows:
        raise ValueError("No CFTC COT rows found for Coffee C")

    latest = rows[0]
    prior = rows[1] if len(rows) > 1 else {}

    long_value = parse_int(
        pick_value(
            latest,
            (
                "m_money_positions_long_all",
                "m_money_positions_long",
                "managed_money_positions_long_all",
            ),
        )
    )
    short_value = parse_int(
        pick_value(
            latest,
            (
                "m_money_positions_short_all",
                "m_money_positions_short",
                "managed_money_positions_short_all",
            ),
        )
    )
    spread_value = parse_int(
        pick_value(
            latest,
            (
                "m_money_positions_spread_all",
                "m_money_positions_spread",
                "managed_money_positions_spread_all",
            ),
        )
    )
    open_interest = parse_int(
        pick_value(latest, ("open_interest_all", "open_interest"))
    )

    if long_value is None or short_value is None:
        raise ValueError("Could not parse CFTC Managed Money long/short fields")

    prior_long = parse_int(
        pick_value(
            prior,
            (
                "m_money_positions_long_all",
                "m_money_positions_long",
                "managed_money_positions_long_all",
            ),
        )
    )
    prior_short = parse_int(
        pick_value(
            prior,
            (
                "m_money_positions_short_all",
                "m_money_positions_short",
                "managed_money_positions_short_all",
            ),
        )
    )

    net = long_value - short_value
    prior_net = prior_long - prior_short if None not in (prior_long, prior_short) else None
    net_change = net - prior_net if prior_net is not None else None
    net_pct_oi = net / open_interest * 100 if open_interest else None

    cot_history = []
    for row in rows:
        row_long = parse_int(
            pick_value(
                row,
                (
                    "m_money_positions_long_all",
                    "m_money_positions_long",
                    "managed_money_positions_long_all",
                ),
            )
        )
        row_short = parse_int(
            pick_value(
                row,
                (
                    "m_money_positions_short_all",
                    "m_money_positions_short",
                    "managed_money_positions_short_all",
                ),
            )
        )
        row_oi = parse_int(pick_value(row, ("open_interest_all", "open_interest")))

        if row_long is None or row_short is None:
            continue

        row_net = row_long - row_short
        cot_history.append(
            {
                "date": str(row.get("report_date_as_yyyy_mm_dd", ""))[:10],
                "long": row_long,
                "short": row_short,
                "net": row_net,
                "open_interest": row_oi,
                "net_pct_oi": row_net / row_oi * 100 if row_oi else None,
            }
        )

    cot_history = sorted(cot_history, key=lambda item: item["date"])

    return {
        "market": latest.get("market_and_exchange_names"),
        "report_date": str(latest.get("report_date_as_yyyy_mm_dd", ""))[:10],
        "open_interest": open_interest,
        "managed_money_long": long_value,
        "managed_money_short": short_value,
        "managed_money_spread": spread_value,
        "managed_money_net": net,
        "managed_money_prior_net": prior_net,
        "managed_money_net_change": net_change,
        "managed_money_net_pct_oi": net_pct_oi,
        "prior_report_date": str(prior.get("report_date_as_yyyy_mm_dd", ""))[:10]
        if prior
        else None,
        "history": cot_history,
        "source": "CFTC Disaggregated Futures Only",
        "url": "https://publicreporting.cftc.gov/Commitments-of-Traders/Disaggregated-Futures-Only/72hh-3qpy",
    }


def load_fundamentals():
    cached = load_json(FUNDAMENTALS_FILE)

    try:
        latest = fetch_ice_inventory()
    except Exception as exc:
        print(f"ICE inventory fetch failed: {exc}")
        latest = {}

    try:
        latest.update({"macro": fetch_macro_data()})
    except Exception as exc:
        print(f"Macro data fetch failed: {exc}")

    try:
        latest.update({"cftc_cot": fetch_cftc_cot()})
    except Exception as exc:
        print(f"CFTC COT fetch failed: {exc}")

    try:
        news_reports = fetch_news_reports()
        if news_reports:
            latest.update({"news_reports": news_reports})
    except Exception as exc:
        print(f"News/report fetch failed: {exc}")

    merged = dict(cached)
    merged.update(latest)

    FUNDAMENTALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    FUNDAMENTALS_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return merged


def upcoming_events(today=None, days=EVENT_LOOKAHEAD_DAYS):
    today = today or today_utc()
    end_date = today + timedelta(days=days)
    selected = []

    for event in EVENTS:
        event_date = parse_date(event.get("date"))
        if event_date is None:
            continue
        if today <= event_date <= end_date:
            selected.append({**event, "days_until": (event_date - today).days})

    return sorted(selected, key=lambda item: (item["date"], item["title"]))


def data_warnings(market, fundamentals, history):
    warnings = []
    today = today_utc()

    market_age = days_old(market.get("date"), today)
    if market_age is None:
        warnings.append("价格数据缺少有效日期。")
    elif market_age > 5:
        warnings.append(f"价格数据日期为 {market.get('date')}，距今 {market_age} 天，可能不是最新交易日。")

    inventory = (fundamentals or {}).get("ice_inventory") or {}
    inventory_age = days_old(inventory.get("date"), today)
    if inventory.get("certified_stocks") is None:
        warnings.append("ICE库存数据未成功更新。")
    elif inventory_age is not None and inventory_age > 7:
        warnings.append(f"ICE库存日期为 {inventory.get('date')}，已超过 7 天未更新。")

    cot = (fundamentals or {}).get("cftc_cot") or {}
    cot_age = days_old(cot.get("report_date"), today)
    if cot.get("managed_money_net") is None:
        warnings.append("CFTC持仓数据未成功更新。")
    elif cot_age is not None and cot_age > 12:
        warnings.append(f"CFTC报告日期为 {cot.get('report_date')}，可能落后于最新发布。")

    macro = (fundamentals or {}).get("macro") or {}
    for key, label in (("usd_brl", "USD/BRL"), ("dxy", "DXY")):
        item = macro.get(key) or {}
        macro_age = days_old(item.get("date"), today)
        if item.get("value") is None:
            warnings.append(f"{label} 数据未成功更新。")
        elif macro_age is not None and macro_age > 5:
            warnings.append(f"{label} 日期为 {item.get('date')}，可能不是最新数据。")

    cleaned_history = clean_history(history)
    if len(cleaned_history) < 20:
        warnings.append("OHLC历史记录少于20条，趋势图参考价值有限。")

    inventory_history = inventory.get("history") or []
    if len(inventory_history) < 10:
        warnings.append("库存趋势图仅使用公开页面的短期历史点；长期库存历史需ICE官方订阅或导出。")

    return warnings


def price_position_label(market):
    high = parse_number(market.get("high"))
    low = parse_number(market.get("low"))
    close = parse_number(market.get("close"))

    if None in (high, low, close) or high == low:
        return "区间位置不明"

    position = (close - low) / (high - low)
    if position >= 0.66:
        return "收盘靠近日内高位"
    if position <= 0.33:
        return "收盘靠近日内低位"
    return "收盘位于日内区间中部"


def build_top_view(market, fundamentals, history):
    close = parse_number(market.get("close"))
    high = parse_number(market.get("high"))
    low = parse_number(market.get("low"))
    cleaned_history = clean_history(history)

    latest_close = close
    prior_close = None
    if len(cleaned_history) >= 2:
        prior_close = cleaned_history[-2]["close"]

    close_change = latest_close - prior_close if None not in (latest_close, prior_close) else None
    close_change_pct = close_change / prior_close * 100 if prior_close else None

    inventory = (fundamentals or {}).get("ice_inventory") or {}
    inventory_change = inventory.get("change")
    cot = (fundamentals or {}).get("cftc_cot") or {}
    cot_change = cot.get("managed_money_net_change")
    macro = (fundamentals or {}).get("macro") or {}
    usd_brl_change = ((macro.get("usd_brl") or {}).get("change_pct"))
    dxy_change = ((macro.get("dxy") or {}).get("change_pct"))

    bullish = []
    bearish = []
    watch = []

    if inventory_change is not None:
        if inventory_change < 0:
            bullish.append(f"ICE库存下降 {abs(inventory_change):,} bags")
        elif inventory_change > 0:
            bearish.append(f"ICE库存增加 {inventory_change:,} bags")

    if cot_change is not None:
        if cot_change > 0:
            bullish.append(f"Managed Money净持仓增加 {cot_change:,} 手")
        elif cot_change < 0:
            bearish.append(f"Managed Money净持仓减少 {abs(cot_change):,} 手")

    if dxy_change is not None:
        if dxy_change < 0:
            bullish.append(f"DXY下跌 {abs(dxy_change):.2f}%")
        elif dxy_change > 0:
            bearish.append(f"DXY上涨 {dxy_change:.2f}%")

    if usd_brl_change is not None:
        if usd_brl_change > 0:
            bearish.append(f"USD/BRL上涨 {usd_brl_change:.2f}%，巴西出口销售意愿可能增强")
        elif usd_brl_change < 0:
            bullish.append(f"USD/BRL下跌 {abs(usd_brl_change):.2f}%，巴西雷亚尔走强")

    if high is not None:
        watch.append(f"上方阻力 {format_price(high)}")
    if low is not None:
        watch.append(f"下方支撑 {format_price(low)}")
    if cot_change is not None:
        watch.append("关注下一期CFTC是否延续当前资金方向")
    if inventory_change is not None:
        watch.append("关注ICE库存是否继续下降")

    if close_change is not None:
        price_text = f"最新收盘 {format_price(close)}，较前值 {close_change:+.2f} / {close_change_pct:+.2f}%"
    else:
        price_text = f"最新收盘 {format_price(close)}"

    score = 0
    score += 1 if inventory_change is not None and inventory_change < 0 else 0
    score -= 1 if inventory_change is not None and inventory_change > 0 else 0
    score += 1 if cot_change is not None and cot_change > 0 else 0
    score -= 1 if cot_change is not None and cot_change < 0 else 0
    score += 1 if dxy_change is not None and dxy_change < 0 else 0
    score -= 1 if dxy_change is not None and dxy_change > 0 else 0
    score += 1 if usd_brl_change is not None and usd_brl_change < 0 else 0
    score -= 1 if usd_brl_change is not None and usd_brl_change > 0 else 0

    if score >= 2:
        bias = "偏多"
    elif score <= -2:
        bias = "偏空"
    else:
        bias = "中性震荡"

    return {
        "bias": bias,
        "price_text": price_text,
        "position": price_position_label(market),
        "bullish": bullish[:3] or ["暂无明确利多数据"],
        "bearish": bearish[:3] or ["暂无明确利空数据"],
        "watch": watch[:4],
    }


def parse_number(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace(",", "")
    if not text:
        return None

    multiplier = 1
    if text[-1:].upper() == "K":
        multiplier = 1_000
        text = text[:-1]
    elif text[-1:].upper() == "M":
        multiplier = 1_000_000
        text = text[:-1]

    try:
        return float(text) * multiplier
    except ValueError:
        return None


def format_price(value):
    number = parse_number(value)
    if number is None:
        return "N/A"
    return f"{number:.2f}".rstrip("0").rstrip(".")


def format_volume(value):
    number = parse_number(value)
    if number is None:
        return "N/A"
    if number >= 1_000_000:
        return f"{number / 1_000_000:.2f}M"
    if number >= 1_000:
        return f"{number / 1_000:.2f}K"
    return f"{number:.0f}"


def market_date(market):
    for key in ("date", "trade_date", "as_of", "asOf"):
        value = market.get(key)
        if value:
            return str(value)[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def parse_date(value):
    if not value:
        return None

    text = str(value)[:10]

    for pattern in ("%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue

    return None


def today_utc():
    return datetime.now(timezone.utc).date()


def days_old(value, today=None):
    parsed = parse_date(value)
    if parsed is None:
        return None
    return ((today or today_utc()) - parsed).days


def normalize_market(market):
    normalized = dict(market)
    normalized["date"] = market_date(market)

    for key in ("open", "high", "low", "close"):
        number = parse_number(market.get(key))
        if number is None:
            raise ValueError(f"Missing or invalid market field: {key}")
        normalized[key] = number

    normalized["volume"] = parse_number(market.get("volume"))

    low = normalized["low"]
    high = normalized["high"]
    open_price = normalized["open"]
    close = normalized["close"]

    if high < low:
        raise ValueError(f"Invalid OHLC data: high {high} is below low {low}")

    if not low <= open_price <= high:
        raise ValueError(
            f"Invalid OHLC data: open {open_price} is outside low/high range {low}-{high}"
        )

    if not low <= close <= high:
        raise ValueError(
            f"Invalid OHLC data: close {close} is outside low/high range {low}-{high}"
        )

    return normalized


def history_entry(market):
    return {
        "date": market["date"],
        "open": market["open"],
        "high": market["high"],
        "low": market["low"],
        "close": market["close"],
        "volume": market.get("volume"),
    }


def clean_history(history):
    cleaned = []

    for item in history:
        if not isinstance(item, dict):
            continue

        date = str(item.get("date", ""))[:10]
        if not date or date < CHART_START_DATE:
            continue

        open_price = parse_number(item.get("open"))
        high = parse_number(item.get("high"))
        low = parse_number(item.get("low"))
        close = parse_number(item.get("close"))

        if None in (open_price, high, low, close):
            continue

        if high < low or not low <= open_price <= high or not low <= close <= high:
            continue

        cleaned.append(
            {
                "date": date,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": parse_number(item.get("volume")),
            }
        )

    return cleaned


def save_history(entry, history, imported_history=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    merged = {item["date"]: item for item in clean_history(history)}

    for item in clean_history(imported_history or []):
        merged[item["date"]] = item

    merged[entry["date"]] = entry

    updated = sorted(merged.values(), key=lambda item: item["date"])

    HISTORY_FILE.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return updated


def fetch_analysis(market, fundamentals=None):
    try:
        import anthropic
    except ImportError:
        return """
市场总结:
Anthropic SDK未安装，暂时无法生成AI分析。

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

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""
Coffee market data:

{json.dumps(market, ensure_ascii=False)}

Fundamental data:

{json.dumps(fundamentals or {}, ensure_ascii=False)}

Please write:

1. 市场总结（150字）
2. ICE库存分析
3. 美元与巴西雷亚尔
4. 天气风险
5. 三个利多因素
6. 三个利空因素
7. 物流风险
8. CFTC持仓分析
9. 风险等级（High/Medium/Low）

Rules:

- 市场总结 must mention the latest close, daily range, and whether close is near high/mid/low of the range.
- ICE库存 must cite certified stocks, date, and change if available.
- 美元 must cite USD/BRL and DXY values and changes if available.
- CFTC must cite report date, Managed Money net, and weekly net change if available.
- News/report items are discovery signals. Do not treat headlines as confirmed facts unless they are official reports.
- 天气 and 物流 must say 暂无可验证更新 unless the provided data contains specific weather or logistics facts.
- Do not claim broad demand growth, weather damage, port disruption, or crop loss unless the provided data explicitly supports it.
- 风险 must be one of High, Medium, Low and include one short reason.

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

CFTC:
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
            messages=[{"role": "user", "content": prompt}],
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

CFTC:
暂无数据。

风险:
Medium
"""


def extract_section(text, title):
    pattern = rf"{title}:(.*?)(?:\n[A-Za-z\u4e00-\u9fa5]+:|$)"
    match = re.search(pattern, text, re.S)

    if match:
        return match.group(1).strip()

    return ""


def extract_list(text, title):
    section = extract_section(text, title)
    lines = []

    for line in section.splitlines():
        line = line.strip()

        if line:
            line = re.sub(r"^\d+\.", "", line).strip()
            lines.append(line)

    return lines


def escape_text(value):
    return html.escape(str(value if value is not None else ""))


def render_ohlc_chart(history):
    points = clean_history(history)

    if not points:
        return """
<div class="empty-chart">
暂无可用历史数据。请从 2026-01-01 起每日保存 open/high/low/close。
</div>
"""

    width = 1000
    height = 360
    left = 58
    right = 24
    top = 24
    bottom = 46
    plot_width = width - left - right
    plot_height = height - top - bottom

    min_price = min(item["low"] for item in points)
    max_price = max(item["high"] for item in points)
    price_range = max_price - min_price

    if price_range == 0:
        price_range = max_price * 0.02 or 1
        min_price -= price_range / 2
        max_price += price_range / 2

    padding = price_range * 0.08
    min_price -= padding
    max_price += padding
    price_range = max_price - min_price

    def x_at(index):
        if len(points) == 1:
            return left + plot_width / 2
        return left + (index / (len(points) - 1)) * plot_width

    def y_at(price):
        return top + (max_price - price) / price_range * plot_height

    grid_lines = []
    for i in range(5):
        price = min_price + price_range * i / 4
        y = y_at(price)
        grid_lines.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="grid"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" class="axis-label" text-anchor="end">{price:.0f}</text>'
        )

    range_lines = []
    close_points = []
    open_points = []

    candle_width = max(4, min(12, plot_width / max(len(points), 1) * 0.38))

    for index, item in enumerate(points):
        x = x_at(index)
        y_high = y_at(item["high"])
        y_low = y_at(item["low"])
        y_open = y_at(item["open"])
        y_close = y_at(item["close"])
        color_class = "up" if item["close"] >= item["open"] else "down"

        range_lines.append(
            f'<line x1="{x:.1f}" y1="{y_high:.1f}" x2="{x:.1f}" y2="{y_low:.1f}" class="range {color_class}"/>'
            f'<line x1="{x - candle_width:.1f}" y1="{y_open:.1f}" x2="{x:.1f}" y2="{y_open:.1f}" class="open-tick {color_class}"/>'
        )
        close_points.append(f"{x:.1f},{y_close:.1f}")
        open_points.append(f"{x:.1f},{y_open:.1f}")

    first = points[0]["date"]
    last = points[-1]["date"]
    latest = points[-1]

    return f"""
<svg class="ohlc-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Coffee C OHLC trend chart">
<rect x="0" y="0" width="{width}" height="{height}" class="chart-bg"/>
{''.join(grid_lines)}
<line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" class="axis"/>
<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" class="axis"/>
{''.join(range_lines)}
<polyline points="{' '.join(open_points)}" class="open-line"/>
<polyline points="{' '.join(close_points)}" class="close-line"/>
<text x="{left}" y="{height - 14}" class="axis-label">{first}</text>
<text x="{width - right}" y="{height - 14}" class="axis-label" text-anchor="end">{last}</text>
<text x="{width - right}" y="{top + 18}" class="latest-label" text-anchor="end">
Latest Close {latest["close"]:.2f}
</text>
</svg>
<div class="chart-legend">
<span><i class="legend-range"></i>High-Low 区间</span>
<span><i class="legend-open"></i>Open 淡线</span>
<span><i class="legend-close"></i>Close 主线</span>
</div>
"""


def inventory_snapshot_html(fundamentals):
    inventory = (fundamentals or {}).get("ice_inventory") or {}
    stocks = inventory.get("certified_stocks")

    if stocks is None:
        return ""

    change = inventory.get("change")
    change_pct = inventory.get("change_pct")
    date = inventory.get("date") or "latest"

    change_text = "N/A"
    change_class = "neutral"
    if change is not None:
        sign = "+" if change > 0 else ""
        pct_text = f"{change_pct:+.2f}%" if change_pct is not None else "N/A"
        change_text = f"{sign}{change:,} bags / {pct_text}"
        change_class = "up" if change > 0 else "down" if change < 0 else "neutral"

    return f"""
<div class="inventory-snapshot">
<div>
<span class="mini-label">ICE Certified Stocks</span>
<strong>{stocks:,}</strong>
<span class="mini-label">bags · {escape_text(date)}</span>
</div>
<div class="inventory-change {change_class}">
{escape_text(change_text)}
</div>
</div>
"""


def render_inventory_chart(fundamentals):
    inventory = (fundamentals or {}).get("ice_inventory") or {}
    history = inventory.get("history") or []
    points = [
        item
        for item in history
        if item.get("date") and parse_number(item.get("value")) is not None
    ]

    if len(points) < 2:
        return ""

    width = 1000
    height = 240
    left = 70
    right = 24
    top = 24
    bottom = 42
    plot_width = width - left - right
    plot_height = height - top - bottom

    values = [float(item["value"]) for item in points]
    min_value = min(values)
    max_value = max(values)
    value_range = max_value - min_value

    if value_range == 0:
        value_range = max_value * 0.02 or 1
        min_value -= value_range / 2
        max_value += value_range / 2

    padding = value_range * 0.15
    min_value -= padding
    max_value += padding
    value_range = max_value - min_value

    def x_at(index):
        return left + (index / (len(points) - 1)) * plot_width

    def y_at(value):
        return top + (max_value - value) / value_range * plot_height

    grid_lines = []
    for i in range(4):
        value = min_value + value_range * i / 3
        y = y_at(value)
        grid_lines.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="grid"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" class="axis-label" text-anchor="end">{value / 1000:.0f}K</text>'
        )

    area_points = [f"{x_at(index):.1f},{y_at(float(item['value'])):.1f}" for index, item in enumerate(points)]
    baseline_y = height - bottom
    area_polygon = (
        f"{left:.1f},{baseline_y:.1f} "
        + " ".join(area_points)
        + f" {width - right:.1f},{baseline_y:.1f}"
    )
    dots = []
    for index, item in enumerate(points):
        dots.append(
            f'<circle cx="{x_at(index):.1f}" cy="{y_at(float(item["value"])):.1f}" r="4" class="inventory-dot"/>'
        )

    first = points[0]["date"]
    last = points[-1]["date"]
    latest = float(points[-1]["value"])

    return f"""
<svg class="inventory-chart" viewBox="0 0 {width} {height}" role="img" aria-label="ICE certified stocks trend">
<rect x="0" y="0" width="{width}" height="{height}" class="chart-bg"/>
{''.join(grid_lines)}
<polygon points="{area_polygon}" class="inventory-area"/>
<polyline points="{' '.join(area_points)}" class="inventory-line"/>
{''.join(dots)}
<line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" class="axis"/>
<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" class="axis"/>
<text x="{left}" y="{height - 12}" class="axis-label">{first}</text>
<text x="{width - right}" y="{height - 12}" class="axis-label" text-anchor="end">{last}</text>
<text x="{width - right}" y="{top + 18}" class="latest-label" text-anchor="end">
Latest {latest:,.0f} bags
</text>
</svg>
<div class="chart-legend">
<span><i class="legend-inventory"></i>ICE Certified Stocks</span>
</div>
"""


def macro_snapshot_html(fundamentals):
    macro = (fundamentals or {}).get("macro") or {}
    items = []

    for key in ("usd_brl", "dxy"):
        item = macro.get(key) or {}
        value = item.get("value")
        if value is None:
            continue

        change = item.get("change")
        change_pct = item.get("change_pct")
        change_text = "N/A"
        change_class = "neutral"

        if change is not None:
            change_text = f"{change:+.4f} / {change_pct:+.2f}%" if change_pct is not None else f"{change:+.4f}"
            change_class = "up" if change > 0 else "down" if change < 0 else "neutral"

        items.append(
            f"""
<div class="macro-item">
<span class="mini-label">{escape_text(item.get("label", key))}</span>
<strong>{value:.4f}</strong>
<span class="mini-label">{escape_text(item.get("date", "latest"))}</span>
<span class="macro-change {change_class}">{escape_text(change_text)}</span>
</div>
"""
        )

    if not items:
        return ""

    return f"""
<div class="macro-snapshot">
{''.join(items)}
</div>
"""


def cot_snapshot_html(fundamentals):
    cot = (fundamentals or {}).get("cftc_cot") or {}
    net = cot.get("managed_money_net")

    if net is None:
        return ""

    net_change = cot.get("managed_money_net_change")
    pct_oi = cot.get("managed_money_net_pct_oi")
    long_value = cot.get("managed_money_long")
    short_value = cot.get("managed_money_short")
    report_date = cot.get("report_date") or "latest"

    change_text = "N/A"
    change_class = "neutral"
    if net_change is not None:
        sign = "+" if net_change > 0 else ""
        change_text = f"{sign}{net_change:,} contracts"
        change_class = "up" if net_change > 0 else "down" if net_change < 0 else "neutral"

    pct_text = f"{pct_oi:+.1f}% of OI" if pct_oi is not None else "N/A"

    return f"""
<div class="cot-snapshot">
<div>
<span class="mini-label">Managed Money Net</span>
<strong>{net:+,}</strong>
<span class="mini-label">report date · {escape_text(report_date)}</span>
</div>
<div>
<span class="mini-label">Long / Short</span>
<strong>{long_value:,} / {short_value:,}</strong>
<span class="mini-label">{escape_text(pct_text)}</span>
</div>
<div class="cot-change {change_class}">
{escape_text(change_text)}
</div>
</div>
"""


def render_cot_chart(fundamentals):
    history = ((fundamentals or {}).get("cftc_cot") or {}).get("history") or []
    points = [
        item
        for item in history
        if item.get("date") and parse_number(item.get("net")) is not None
    ]

    if len(points) < 2:
        return ""

    width = 1000
    height = 260
    left = 62
    right = 24
    top = 24
    bottom = 42
    plot_width = width - left - right
    plot_height = height - top - bottom

    values = [float(item["net"]) for item in points]
    min_value = min(values + [0])
    max_value = max(values + [0])
    value_range = max_value - min_value

    if value_range == 0:
        value_range = abs(max_value) * 0.2 or 1
        min_value -= value_range / 2
        max_value += value_range / 2

    padding = value_range * 0.12
    min_value -= padding
    max_value += padding
    value_range = max_value - min_value

    def x_at(index):
        return left + (index / (len(points) - 1)) * plot_width

    def y_at(value):
        return top + (max_value - value) / value_range * plot_height

    zero_y = y_at(0)
    line_points = []
    bars = []

    bar_width = max(3, min(10, plot_width / len(points) * 0.45))

    for index, item in enumerate(points):
        value = float(item["net"])
        x = x_at(index)
        y = y_at(value)
        bar_y = min(y, zero_y)
        bar_height = abs(zero_y - y)
        bar_class = "positive" if value >= 0 else "negative"
        bars.append(
            f'<rect x="{x - bar_width / 2:.1f}" y="{bar_y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" class="cot-bar {bar_class}"/>'
        )
        line_points.append(f"{x:.1f},{y:.1f}")

    grid_lines = []
    for i in range(5):
        value = min_value + value_range * i / 4
        y = y_at(value)
        grid_lines.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="grid"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" class="axis-label" text-anchor="end">{value / 1000:.0f}K</text>'
        )

    first = points[0]["date"]
    last = points[-1]["date"]
    latest = float(points[-1]["net"])

    return f"""
<svg class="cot-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Managed Money net position trend">
<rect x="0" y="0" width="{width}" height="{height}" class="chart-bg"/>
{''.join(grid_lines)}
<line x1="{left}" y1="{zero_y:.1f}" x2="{width - right}" y2="{zero_y:.1f}" class="zero-axis"/>
{''.join(bars)}
<polyline points="{' '.join(line_points)}" class="cot-line"/>
<line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" class="axis"/>
<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" class="axis"/>
<text x="{left}" y="{height - 12}" class="axis-label">{first}</text>
<text x="{width - right}" y="{height - 12}" class="axis-label" text-anchor="end">{last}</text>
<text x="{width - right}" y="{top + 18}" class="latest-label" text-anchor="end">
Latest Net {latest:+,.0f}
</text>
</svg>
<div class="chart-legend">
<span><i class="legend-cot-positive"></i>净多</span>
<span><i class="legend-cot-negative"></i>净空</span>
<span><i class="legend-cot-line"></i>Managed Money Net</span>
</div>
"""


def render_alerts_html(warnings):
    if not warnings:
        return ""

    items = "".join(f"<li>{escape_text(item)}</li>" for item in warnings)
    return f"""
<div class="alert-card">
<h2>数据警告</h2>
<ul>
{items}
</ul>
</div>
"""


def render_events_html(events):
    if not events:
        return ""

    rows = []
    for event in events:
        days = event.get("days_until")
        timing = "今天" if days == 0 else f"{days}天后"
        rows.append(
            f"""
<tr>
<td>{escape_text(event.get("date"))}<br><span>{escape_text(timing)}</span></td>
<td>{escape_text(event.get("title"))}</td>
<td>{escape_text(event.get("impact"))}</td>
<td>{escape_text(event.get("source"))}</td>
</tr>
"""
        )

    return f"""
<div class="card events-card">
<h2>未来重点事件</h2>
<table>
<thead>
<tr>
<th>日期</th>
<th>事件</th>
<th>影响</th>
<th>来源</th>
</tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</div>
"""


def render_news_reports_html(fundamentals):
    items = (fundamentals or {}).get("news_reports") or []
    if not items:
        return ""

    cards = []
    for item in items:
        url = html.escape(str(item.get("url") or ""), quote=True)
        title = escape_text(item.get("title"))
        domain = escape_text(item.get("domain"))
        date = escape_text(item.get("date"))
        impact = escape_text(item.get("impact"))
        country = escape_text(item.get("source_country"))
        country_text = f" · {country}" if country else ""

        cards.append(
            f"""
<div class="news-item">
<div class="news-meta">{date} · {domain}{country_text}</div>
<a href="{url}">{title}</a>
<p>{impact}</p>
</div>
"""
        )

    return f"""
<div class="card news-card">
<h2>新闻与报告摘要</h2>
<div class="news-note">近 {NEWS_LOOKBACK_DAYS} 天公开新闻/报告索引；用于发现线索，重要结论需结合官方数据确认。</div>
<div class="news-grid">
{''.join(cards)}
</div>
</div>
"""


def is_south_america_item(item):
    text = f"{item.get('title', '')} {item.get('domain', '')} {item.get('impact', '')}".lower()
    return any(keyword in text for keyword in SOUTH_AMERICA_KEYWORDS)


def render_south_america_html(fundamentals):
    items = [
        item
        for item in ((fundamentals or {}).get("news_reports") or [])
        if is_south_america_item(item)
    ][:6]

    if not items:
        return """
<div class="card south-america-card">
<h2>南美产区与港口物流</h2>
<p class="muted">近 7 天未发现明确的南美咖啡产区、出口或港口物流公开线索。</p>
</div>
"""

    cards = []
    for item in items:
        url = html.escape(str(item.get("url") or ""), quote=True)
        title = escape_text(item.get("title"))
        domain = escape_text(item.get("domain"))
        date = escape_text(item.get("date"))
        impact = escape_text(item.get("impact"))

        cards.append(
            f"""
<div class="south-america-item">
<div class="news-meta">{date} · {domain}</div>
<a href="{url}">{title}</a>
<p>{impact}</p>
</div>
"""
        )

    return f"""
<div class="card south-america-card">
<h2>南美产区与港口物流</h2>
<div class="news-note">重点关注巴西、哥伦比亚、秘鲁等产区，以及Santos港、出口节奏、运输异常和当地收成情况。</div>
<div class="south-america-grid">
{''.join(cards)}
</div>
</div>
"""


def render_top_view_html(top_view):
    bullish = "".join(f"<li>{escape_text(item)}</li>" for item in top_view.get("bullish", []))
    bearish = "".join(f"<li>{escape_text(item)}</li>" for item in top_view.get("bearish", []))
    watch = "".join(f"<li>{escape_text(item)}</li>" for item in top_view.get("watch", []))

    return f"""
<div class="card top-view-card">
<div class="top-view-head">
<div>
<h2>顶部交易结论</h2>
<p>{escape_text(top_view.get("price_text"))}；{escape_text(top_view.get("position"))}。</p>
</div>
<div class="bias-pill">{escape_text(top_view.get("bias"))}</div>
</div>
<div class="top-view-grid">
<div>
<h3>利多驱动</h3>
<ul>{bullish}</ul>
</div>
<div>
<h3>利空驱动</h3>
<ul>{bearish}</ul>
</div>
<div>
<h3>今日重点</h3>
<ul>{watch}</ul>
</div>
</div>
</div>
"""


def render_html(market, analysis, history, fundamentals=None, warnings=None, events=None):
    summary = extract_section(analysis, "市场总结")
    inventory = extract_section(analysis, "ICE库存")
    usd = extract_section(analysis, "美元")
    freight = extract_section(analysis, "物流")
    cftc = extract_section(analysis, "CFTC")
    risk = extract_section(analysis, "风险")

    weather = extract_list(analysis, "天气")
    bullish = extract_list(analysis, "利多")
    bearish = extract_list(analysis, "利空")

    weather_html = "".join(f"<li>{escape_text(x)}</li>" for x in weather)
    bullish_html = "".join(f"<li>{escape_text(x)}</li>" for x in bullish)
    bearish_html = "".join(f"<li>{escape_text(x)}</li>" for x in bearish)

    risk_color = {
        "High": "#EF5350",
        "Medium": "#FFA726",
        "Low": "#66BB6A",
    }.get(risk, "#FFA726")

    ohlc_chart = render_ohlc_chart(history)
    inventory_snapshot = inventory_snapshot_html(fundamentals)
    inventory_chart = render_inventory_chart(fundamentals)
    macro_snapshot = macro_snapshot_html(fundamentals)
    cot_snapshot = cot_snapshot_html(fundamentals)
    cot_chart = render_cot_chart(fundamentals)
    alerts_html = render_alerts_html(warnings or [])
    events_html = render_events_html(events or [])
    news_reports_html = render_news_reports_html(fundamentals)
    south_america_html = render_south_america_html(fundamentals)
    top_view_html = render_top_view_html(build_top_view(market, fundamentals, history))

    return f"""
<html>

<head>

<meta charset="UTF-8">

<style>

body {{
    background: #101217;
    color: #EAECEF;
    font-family: Arial, "Microsoft YaHei", sans-serif;
    padding: 30px;
}}

.container {{
    max-width: 1100px;
    margin: auto;
}}

.kicker {{
    color: #9AA4B2;
    margin-top: -18px;
    margin-bottom: 26px;
}}

h1 {{
    margin-bottom: 22px;
}}

.card {{
    background: #1A1D25;
    border: 1px solid #2A2E39;
    border-radius: 8px;
    padding: 22px;
    margin-bottom: 20px;
}}

.alert-card {{
    background: #2A1D1D;
    border: 1px solid #6A3434;
    border-radius: 8px;
    padding: 18px 22px;
    margin-bottom: 20px;
}}

.alert-card h2 {{
    margin-top: 0;
    color: #FFAB91;
}}

.events-card {{
    overflow-x: auto;
}}

.events-card table {{
    width: 100%;
    border-collapse: collapse;
    min-width: 760px;
}}

.events-card th,
.events-card td {{
    border-bottom: 1px solid #2A2E39;
    padding: 12px 10px;
    text-align: left;
    vertical-align: top;
    line-height: 1.55;
}}

.events-card th {{
    color: #9AA4B2;
    font-size: 13px;
    font-weight: 700;
}}

.events-card td:first-child {{
    white-space: nowrap;
    color: #EAECEF;
    font-weight: 700;
}}

.events-card td:first-child span {{
    color: #9AA4B2;
    font-size: 12px;
    font-weight: 400;
}}

.news-card {{
    overflow: hidden;
}}

.news-note {{
    color: #9AA4B2;
    font-size: 13px;
    line-height: 1.6;
    margin-bottom: 14px;
}}

.news-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}}

.news-item {{
    border: 1px solid #2A2E39;
    border-radius: 8px;
    background: #151821;
    padding: 14px 16px;
}}

.news-meta {{
    color: #9AA4B2;
    font-size: 12px;
    margin-bottom: 8px;
}}

.news-item a {{
    color: #EAECEF;
    font-size: 15px;
    line-height: 1.45;
    font-weight: 700;
    text-decoration: none;
}}

.news-item a:hover {{
    color: #4FC3F7;
}}

.news-item p {{
    margin-bottom: 0;
    color: #C7CDD8;
    font-size: 13px;
    line-height: 1.6;
}}

.muted {{
    color: #9AA4B2;
}}

.south-america-card {{
    overflow: hidden;
}}

.south-america-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}}

.south-america-item {{
    border: 1px solid #2A2E39;
    border-radius: 8px;
    background: #151821;
    padding: 14px 16px;
}}

.south-america-item a {{
    color: #EAECEF;
    font-size: 15px;
    line-height: 1.45;
    font-weight: 700;
    text-decoration: none;
}}

.south-america-item a:hover {{
    color: #4FC3F7;
}}

.south-america-item p {{
    margin-bottom: 0;
    color: #C7CDD8;
    font-size: 13px;
    line-height: 1.6;
}}

.price-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}}

.price-card {{
    background: #1A1D25;
    border: 1px solid #2A2E39;
    border-radius: 8px;
    padding: 20px;
}}

.price-card h3 {{
    margin: 0;
    color: #9AA4B2;
    font-size: 13px;
}}

.price-card p {{
    margin-top: 10px;
    margin-bottom: 0;
    font-size: 34px;
    font-weight: bold;
}}

.top-view-card {{
    border-color: #3D495C;
}}

.top-view-head {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 18px;
    margin-bottom: 12px;
}}

.top-view-head h2 {{
    margin-top: 0;
}}

.top-view-head p {{
    margin: 0;
    color: #C7CDD8;
}}

.bias-pill {{
    border-radius: 8px;
    padding: 10px 14px;
    background: #151821;
    border: 1px solid #4FC3F7;
    color: #4FC3F7;
    font-size: 20px;
    font-weight: 800;
    white-space: nowrap;
}}

.top-view-grid {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
}}

.top-view-grid h3 {{
    color: #9AA4B2;
    font-size: 13px;
    margin-bottom: 8px;
}}

.top-view-grid ul {{
    margin: 0;
    padding-left: 18px;
}}

.section-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}}

.chart-card {{
    overflow-x: auto;
}}

.ohlc-chart {{
    display: block;
    width: 100%;
    min-width: 760px;
    height: auto;
}}

.chart-bg {{
    fill: #151821;
}}

.grid {{
    stroke: #2A2E39;
    stroke-width: 1;
}}

.axis {{
    stroke: #535B6B;
    stroke-width: 1.2;
}}

.axis-label {{
    fill: #9AA4B2;
    font-size: 13px;
}}

.latest-label {{
    fill: #EAECEF;
    font-size: 16px;
    font-weight: 700;
}}

.range {{
    stroke-width: 2;
    opacity: 0.52;
}}

.range.up,
.open-tick.up {{
    stroke: #66BB6A;
}}

.range.down,
.open-tick.down {{
    stroke: #EF5350;
}}

.open-tick {{
    stroke-width: 2;
    opacity: 0.75;
}}

.open-line {{
    fill: none;
    stroke: #FFA726;
    stroke-width: 1.8;
    stroke-dasharray: 5 6;
    opacity: 0.75;
}}

.close-line {{
    fill: none;
    stroke: #4FC3F7;
    stroke-width: 3;
}}

.chart-legend {{
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    color: #C7CDD8;
    font-size: 13px;
    margin-top: 12px;
}}

.chart-legend i {{
    display: inline-block;
    width: 22px;
    height: 3px;
    margin-right: 7px;
    vertical-align: middle;
}}

.inventory-snapshot {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    border: 1px solid #2A2E39;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 14px;
    background: #151821;
}}

.macro-snapshot {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 14px;
}}

.cot-snapshot {{
    display: grid;
    grid-template-columns: 1.1fr 1.1fr auto;
    align-items: center;
    gap: 14px;
    border: 1px solid #2A2E39;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 14px;
    background: #151821;
}}

.cot-snapshot strong {{
    display: block;
    font-size: 25px;
    margin: 4px 0;
}}

.cot-change {{
    font-weight: 700;
    white-space: nowrap;
}}

.cot-change.up {{
    color: #66BB6A;
}}

.cot-change.down {{
    color: #EF5350;
}}

.cot-change.neutral {{
    color: #C7CDD8;
}}

.cot-chart {{
    display: block;
    width: 100%;
    min-width: 760px;
    height: auto;
    margin-top: 12px;
}}

.zero-axis {{
    stroke: #8A93A6;
    stroke-width: 1.3;
    stroke-dasharray: 4 5;
}}

.cot-bar {{
    opacity: 0.48;
}}

.cot-bar.positive {{
    fill: #66BB6A;
}}

.cot-bar.negative {{
    fill: #EF5350;
}}

.cot-line {{
    fill: none;
    stroke: #FFD54F;
    stroke-width: 2.5;
}}

.legend-cot-positive {{
    background: #66BB6A;
}}

.legend-cot-negative {{
    background: #EF5350;
}}

.legend-cot-line {{
    background: #FFD54F;
}}

.macro-item {{
    border: 1px solid #2A2E39;
    border-radius: 8px;
    padding: 14px 16px;
    background: #151821;
}}

.macro-item strong {{
    display: block;
    font-size: 25px;
    margin: 4px 0;
}}

.macro-change {{
    display: block;
    margin-top: 8px;
    font-weight: 700;
}}

.macro-change.up {{
    color: #66BB6A;
}}

.macro-change.down {{
    color: #EF5350;
}}

.macro-change.neutral {{
    color: #C7CDD8;
}}

.inventory-snapshot strong {{
    display: block;
    font-size: 28px;
    margin: 4px 0;
}}

.mini-label {{
    display: block;
    color: #9AA4B2;
    font-size: 12px;
}}

.inventory-change {{
    font-weight: 700;
    white-space: nowrap;
}}

.inventory-change.up {{
    color: #66BB6A;
}}

.inventory-change.down {{
    color: #EF5350;
}}

.inventory-change.neutral {{
    color: #C7CDD8;
}}

.inventory-chart {{
    display: block;
    width: 100%;
    min-width: 760px;
    height: auto;
    margin-top: 12px;
    margin-bottom: 8px;
}}

.inventory-area {{
    fill: #4FC3F7;
    opacity: 0.12;
}}

.inventory-line {{
    fill: none;
    stroke: #4FC3F7;
    stroke-width: 3;
}}

.inventory-dot {{
    fill: #4FC3F7;
    stroke: #151821;
    stroke-width: 2;
}}

.legend-inventory {{
    background: #4FC3F7;
}}

.legend-range {{
    background: #66BB6A;
    opacity: 0.55;
}}

.legend-open {{
    background: #FFA726;
}}

.legend-close {{
    background: #4FC3F7;
}}

.empty-chart {{
    color: #9AA4B2;
    line-height: 1.8;
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
    body {{
        padding: 16px;
    }}

    .section-grid {{
        grid-template-columns: 1fr;
    }}

    .cot-snapshot {{
        grid-template-columns: 1fr;
    }}

    .news-grid {{
        grid-template-columns: 1fr;
    }}

    .south-america-grid {{
        grid-template-columns: 1fr;
    }}

    .top-view-head {{
        display: block;
    }}

    .bias-pill {{
        display: inline-block;
        margin-top: 14px;
    }}

    .top-view-grid {{
        grid-template-columns: 1fr;
    }}
}}

</style>

</head>

<body>

<div class="container">

<h1>咖啡C期货每日简报</h1>
<div class="kicker">截至 {escape_text(market["date"])} 收盘</div>

{alerts_html}

<div class="price-grid">

<div class="price-card">
<h3>OPEN</h3>
<p>{format_price(market.get("open"))}</p>
</div>

<div class="price-card">
<h3>HIGH</h3>
<p>{format_price(market.get("high"))}</p>
</div>

<div class="price-card">
<h3>LOW</h3>
<p>{format_price(market.get("low"))}</p>
</div>

<div class="price-card">
<h3>CLOSE</h3>
<p>{format_price(market.get("close"))}</p>
</div>

<div class="price-card">
<h3>VOLUME</h3>
<p>{format_volume(market.get("volume"))}</p>
</div>

</div>

<div class="card chart-card">
<h2>OHLC趋势图</h2>
{ohlc_chart}
</div>

{top_view_html}

{events_html}

{south_america_html}

{news_reports_html}

<div class="card">

<h2>市场总结</h2>

<p>{escape_text(summary)}</p>

</div>

<div class="section-grid">

<div class="card">

<h2>ICE库存</h2>

{inventory_snapshot}

{inventory_chart}

<p>{escape_text(inventory)}</p>

</div>

<div class="card">

<h2>美元 / 巴西雷亚尔</h2>

{macro_snapshot}

<p>{escape_text(usd)}</p>

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

<p>{escape_text(freight)}</p>

</div>

</div>

<div class="section-grid">

<div class="card">

<h2 style="color:#66BB6A">利多因素</h2>

<ul>
{bullish_html}
</ul>

</div>

<div class="card">

<h2 style="color:#EF5350">利空因素</h2>

<ul>
{bearish_html}
</ul>

</div>

</div>

<div class="card">

<h2>CFTC持仓</h2>

{cot_snapshot}

{cot_chart}

<p>{escape_text(cftc)}</p>

</div>

<div class="card">

<h2>风险等级</h2>

<div class="risk">
{escape_text(risk)}
</div>

</div>

</div>

</body>

</html>
"""


def send_email(html_content, subject):
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    to_addr = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.sendmail(smtp_user, to_addr, msg.as_string())


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    history = load_history()
    imported_history = load_history_csv()
    fundamentals = load_fundamentals()
    yahoo_history = []

    try:
        yahoo_history = fetch_yahoo_history()
    except Exception as exc:
        print(f"Yahoo history fetch failed: {exc}")

    auto_market = latest_history_market(yahoo_history)
    if auto_market:
        market = normalize_market(auto_market)
    else:
        raw_market = load_json(MARKET_FILE)
        market = normalize_market(raw_market)

    imported_history = clean_history(imported_history) + clean_history(yahoo_history)
    updated_history = save_history(history_entry(market), history, imported_history)
    analysis = fetch_analysis(market, fundamentals)
    warnings = data_warnings(market, fundamentals, updated_history)
    events = upcoming_events()
    html_content = render_html(
        market,
        analysis,
        updated_history,
        fundamentals,
        warnings,
        events,
    )

    (OUTPUT_DIR / "latest.html").write_text(html_content, encoding="utf-8")

    if os.environ.get("SMTP_USER"):
        send_email(html_content, "Coffee Futures Daily Brief")

    print("Done")


if __name__ == "__main__":
    main()
