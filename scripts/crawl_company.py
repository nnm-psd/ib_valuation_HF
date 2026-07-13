"""
Crawl a single company from yfinance and store in SQLite.

Usage:
    python scripts/crawl_company.py --ticker STM --name "STMicroelectronics"
    python scripts/crawl_company.py --ticker AIR.PA --name "Airbus"
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.crawler.yfinance_fetcher import (
    fetch_snapshot, fetch_financials, extract_field, FIELD_MAP, STATEMENT_MAP
)
from src.db.models import init_db, SessionLocal, Company, FinancialLine, MarketDataPoint


def crawl(ticker: str, name: str | None = None) -> None:
    init_db()
    session = SessionLocal()

    print(f"  Fetching snapshot for {ticker} ...")
    snap = fetch_snapshot(ticker)
    display_name = name or snap.name

    company = session.query(Company).filter_by(ticker=ticker).first()
    if company is None:
        company = Company(
            name    = display_name,
            ticker  = ticker,
            country = snap.country or "?",
            sector  = snap.sector,
        )
        session.add(company)
        session.commit()
        print(f"  Created: {display_name} | {snap.sector} | {snap.country}")
    else:
        print(f"  Updating: {display_name}")

    print("  Fetching financial statements ...")
    dfs = fetch_financials(ticker)

    stored = 0
    for stmt_key, fields in STATEMENT_MAP.items():
        df = dfs.get(stmt_key)
        if df is None or df.empty:
            print(f"  WARNING: {stmt_key} empty for {ticker}")
            continue
        for field in fields:
            year_values = extract_field(df, FIELD_MAP.get(field, []))
            for year, value in year_values.items():
                if value is None:
                    continue
                # upsert
                session.query(FinancialLine).filter_by(
                    company_id=company.id, fiscal_year=year, field_name=field,
                ).delete()
                session.add(FinancialLine(
                    company_id=company.id, fiscal_year=year,
                    statement=stmt_key, field_name=field, value=value,
                ))
                stored += 1

    # market snapshot
    if snap.price:
        from datetime import date
        session.query(MarketDataPoint).filter_by(
            company_id=company.id, date=str(date.today())
        ).delete()
        session.add(MarketDataPoint(
            company_id         = company.id,
            date               = str(date.today()),
            close_price        = snap.price,
            shares_outstanding = snap.shares_outstanding,
        ))

    session.commit()
    session.close()
    print(f"  ✓ {stored} line items stored | price={snap.price} | beta={snap.beta}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--name",   default=None)
    args = parser.parse_args()
    crawl(args.ticker, args.name)
