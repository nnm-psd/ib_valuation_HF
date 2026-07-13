from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
import yfinance as yf


@dataclass
class CompanySnapshot:
    name:               str
    ticker:             str
    sector:             str | None
    country:            str | None
    currency:           str | None
    price:              float | None
    shares_outstanding: float | None
    market_cap:         float | None
    beta:               float | None
    total_debt:         float | None
    cash:               float | None


def fetch_snapshot(ticker: str) -> CompanySnapshot:
    info = yf.Ticker(ticker).info
    return CompanySnapshot(
        name               = info.get("longName") or info.get("shortName") or ticker,
        ticker             = ticker,
        sector             = info.get("sector"),
        country            = info.get("country"),
        currency           = info.get("currency"),
        price              = info.get("currentPrice") or info.get("regularMarketPrice"),
        shares_outstanding = info.get("sharesOutstanding"),
        market_cap         = info.get("marketCap"),
        beta               = info.get("beta"),
        total_debt         = info.get("totalDebt"),
        cash               = info.get("totalCash"),
    )


def fetch_financials(ticker: str) -> dict[str, pd.DataFrame]:
    t = yf.Ticker(ticker)
    return {
        "income_stmt":   t.income_stmt,
        "balance_sheet": t.balance_sheet,
        "cash_flow":     t.cash_flow,
    }


def extract_field(df: pd.DataFrame, candidates: list[str]) -> dict[int, float | None]:
    """Try candidate row names in order; return {fiscal_year: value} for the first match."""
    for name in candidates:
        if name in df.index:
            row = df.loc[name]
            return {
                col.year: (float(row[col]) if pd.notna(row[col]) else None)
                for col in df.columns
            }
    return {}


# canonical field -> yfinance row names to try, in priority order
FIELD_MAP: dict[str, list[str]] = {
    # Income statement
    "revenue":          ["Total Revenue", "Operating Revenue"],
    "cogs":             ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
    "gross_profit":     ["Gross Profit"],
    "sga":              ["Selling General And Administration"],
    "rd":               ["Research And Development"],
    "ebit":             ["EBIT", "Operating Income", "Total Operating Income As Reported"],
    "ebitda":           ["EBITDA", "Normalized EBITDA"],
    "d_and_a":          ["Reconciled Depreciation"],
    "interest_expense": ["Interest Expense", "Interest Expense Non Operating"],
    "pretax_income":    ["Pretax Income"],
    "tax_expense":      ["Tax Provision"],
    "net_income":       ["Net Income", "Net Income Common Stockholders"],
    # Balance sheet
    "cash":             ["Cash And Cash Equivalents",
                         "Cash Cash Equivalents And Short Term Investments"],
    "total_assets":     ["Total Assets"],
    "short_term_debt":  ["Current Debt", "Current Debt And Capital Lease Obligation"],
    "long_term_debt":   ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
    "total_debt":       ["Total Debt"],
    "total_equity":     ["Stockholders Equity", "Common Stock Equity"],
    "total_liabilities":["Total Liabilities Net Minority Interest"],
    # Cash flow
    "cfo":              ["Operating Cash Flow"],
    "capex":            ["Capital Expenditure"],
    "free_cash_flow":   ["Free Cash Flow"],
    "dividends_paid":   ["Common Stock Dividend Paid", "Payment Of Dividends"],
}

STATEMENT_MAP: dict[str, list[str]] = {
    "income_stmt":   ["revenue","cogs","gross_profit","sga","rd","ebit","ebitda",
                      "d_and_a","interest_expense","pretax_income","tax_expense","net_income"],
    "balance_sheet": ["cash","total_assets","short_term_debt","long_term_debt",
                      "total_debt","total_equity","total_liabilities"],
    "cash_flow":     ["cfo","capex","free_cash_flow","dividends_paid"],
}
