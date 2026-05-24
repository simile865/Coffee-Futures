# ☕ Coffee C Futures — Daily Research Brief

An automated daily research brief for Coffee C futures, powered by **Anthropic Claude** with live web search. Runs on GitHub Actions every weekday morning and optionally emails the HTML report.

---

## What it generates

Each run produces a structured HTML brief covering:

| Section | Data |
|---|---|
| 📊 Market summary | Price, daily/MTD change, 52-week range |
| ▲▼ Bull / Bear factors | 4–5 points each |
| 🏭 Inventory | ICE certified stocks + weekly change |
| 🌧 Weather risk | Brazil & Vietnam crop conditions |
| 🚢 Freight & logistics | Hormuz, Red Sea, insurance, Brazil ports |
| 📰 Key news | Last 48h headlines with sentiment tags |
| 🔄 What changed | Auto-compared to the previous brief |
| 👁 Watch tomorrow | 6 key items to monitor |

Output files saved to `output/`:
- `brief-YYYY-MM-DD.html` — styled HTML report
- `brief-YYYY-MM-DD.json` — raw JSON data
- `latest.html` — always the most recent brief
- `history.json` — rolling 30-day history (used for day-over-day comparison)

---

## Quick start

### 1. Fork or clone this repo

```bash
git clone https://github.com/YOUR_USERNAME/coffee-brief.git
cd coffee-brief
```

### 2. Add GitHub secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ Yes | Get from [console.anthropic.com](https://console.anthropic.com) |
| `SMTP_HOST` | Optional | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | Optional | e.g. `587` |
| `SMTP_USER` | Optional | Your sender email address |
| `SMTP_PASS` | Optional | App password (not your login password) |
| `EMAIL_TO` | Optional | Recipient email address |

> **Gmail users**: Use an [App Password](https://support.google.com/accounts/answer/185833), not your regular password.

### 3. Enable GitHub Actions

Go to **Actions** tab → enable workflows if prompted.

### 4. Run manually to test

Go to **Actions → Coffee Daily Brief → Run workflow**.

---

## Schedule

By default, runs **Monday–Friday at 07:00 UTC** (adjust in `.github/workflows/daily-brief.yml`):

```yaml
- cron: "0 7 * * 1-5"   # weekdays 07:00 UTC
```

Common timezone offsets:
- New York (ET):  `0 12 * * 1-5` (07:00 ET = 12:00 UTC)
- London (BST):   `0 6 * * 1-5`  (07:00 BST = 06:00 UTC)
- São Paulo (BRT): `0 10 * * 1-5` (07:00 BRT = 10:00 UTC)
- Shanghai (CST): `23 22 * * 0-4` (07:00 CST = 23:00 UTC prev day)

---

## Run locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
python brief.py
# HTML saved to output/latest.html
```

---

## Costs

Each run makes ~1 Claude Sonnet API call with web search enabled.

| Component | Estimate |
|---|---|
| Input tokens | ~1,000–1,500 |
| Output tokens | ~800–1,200 |
| Web search calls | ~5–8 per run |
| Approx. cost per brief | ~$0.01–0.03 USD |
| Monthly (20 weekdays) | ~$0.20–0.60 USD |

---

## Disclaimer

This tool is for **research and informational purposes only**. It does not constitute financial advice, a solicitation, or a recommendation to buy or sell any financial instrument. Coffee futures markets involve substantial risk of loss. Always verify data with official exchange sources before making decisions.
