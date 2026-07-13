"""
Precedent Transactions — manual data entry only.
No free structured European M&A database exists.
Add deals to data/processed/precedent_deals.csv by hand.
"""
from __future__ import annotations
from dataclasses import dataclass
import csv
from pathlib import Path


@dataclass
class PrecedentDeal:
    target_name:       str
    acquirer_name:     str
    announcement_date: str
    deal_value_ev:     float
    target_ebitda_ltm: float
    target_revenue_ltm: float
    sector:            str
    deal_premium_pct:  float | None = None


def load_precedent_deals(csv_path: Path) -> list[PrecedentDeal]:
    deals = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            deals.append(PrecedentDeal(
                target_name        = row["target_name"],
                acquirer_name      = row["acquirer_name"],
                announcement_date  = row["announcement_date"],
                deal_value_ev      = float(row["deal_value_ev"]),
                target_ebitda_ltm  = float(row["target_ebitda_ltm"]),
                target_revenue_ltm = float(row["target_revenue_ltm"]),
                sector             = row["sector"],
                deal_premium_pct   = float(row["deal_premium_pct"]) if row.get("deal_premium_pct") else None,
            ))
    return deals


def deal_multiples(deal: PrecedentDeal) -> dict:
    return {
        "ev_ebitda": deal.deal_value_ev / deal.target_ebitda_ltm  if deal.target_ebitda_ltm  else None,
        "ev_sales":  deal.deal_value_ev / deal.target_revenue_ltm if deal.target_revenue_ltm else None,
    }
