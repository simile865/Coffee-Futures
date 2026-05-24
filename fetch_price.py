import yfinance as yf
import json
from pathlib import Path

OUTPUT = Path("data")

OUTPUT.mkdir(exist_ok=True)

ticker = yf.Ticker("KC=F")

hist = ticker.history(period="5d")

latest = hist.iloc[-1]

data = {
    "open": round(float(latest["Open"]), 2),
    "high": round(float(latest["High"]), 2),
    "low": round(float(latest["Low"]), 2),
    "close": round(float(latest["Close"]), 2),
    "volume": int(latest["Volume"])
}

(Path("data/market.json")).write_text(
    json.dumps(data, indent=2),
    encoding="utf-8"
)

print(data)
