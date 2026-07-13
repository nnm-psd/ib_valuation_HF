# IB Valuation Lab

Full investment banking valuation suite for European (CAC40/SBF120) and
US-listed companies. Built in Python + Streamlit. Deployed on Hugging Face Spaces.

## Models

| Model | What it answers |
|---|---|
| **DCF** | Intrinsic value based on projected free cash flows + WACC |
| **Comps** | Relative value via peer EV/EBITDA, EV/Sales, P/E multiples |
| **LBO** | Max entry price a PE buyer can pay to hit a target IRR/MOIC |
| **Precedent Transactions** | Historical M&A deal multiples (manual dataset) |

## Data strategy

- Financial data comes from **yfinance** (free, no API key needed)
- Data is crawled **locally** and stored in SQLite (`data/processed/valuation_lab.db`)
- The DB is **committed to git** so Hugging Face Spaces reads from it at build time
- To refresh: crawl locally → commit updated DB → push

## Local setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Crawl companies

```powershell
# Single company
python scripts/crawl_company.py --ticker STM --name "STMicroelectronics"
python scripts/crawl_company.py --ticker AIR.PA --name "Airbus"

# Full CAC 40
python scripts/crawl_cac40.py

# Slower if rate-limited
python scripts/crawl_cac40.py --delay 5

# Only new tickers
python scripts/crawl_cac40.py --skip-existing
```

## Run locally

```powershell
streamlit run src/app/streamlit_app.py
```

## Deploy to Hugging Face Spaces

1. Create a new Space → SDK: **Docker**
2. Make sure `data/processed/valuation_lab.db` is committed
3. Push this repo — HF builds automatically from the Dockerfile

## Refresh data after deploy

```powershell
python scripts/crawl_cac40.py --skip-existing
git add data/processed/valuation_lab.db
git commit -m "Refresh financials"
git push
```

## Ticker conventions (Yahoo Finance)

| Exchange | Suffix | Example |
|---|---|---|
| Euronext Paris | `.PA` | `AIR.PA`, `MC.PA` |
| NYSE / NASDAQ | none | `STM`, `ASML` |
| Euronext Amsterdam | `.AS` | `MT.AS` |
| Xetra (Germany) | `.DE` | `BMW.DE` |
| LSE (UK) | `.L` | `SHEL.L` |
