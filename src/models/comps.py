from __future__ import annotations
from dataclasses import dataclass
import statistics


@dataclass
class PeerMultiples:
    company_name: str
    ev_ebitda:    float | None
    ev_sales:     float | None
    pe:           float | None


def compute_multiples(
    enterprise_value: float, market_cap: float,
    ebitda: float, revenue: float, net_income: float,
) -> PeerMultiples:
    return PeerMultiples(
        company_name = "",
        ev_ebitda    = enterprise_value / ebitda     if ebitda     else None,
        ev_sales     = enterprise_value / revenue    if revenue    else None,
        pe           = market_cap       / net_income if net_income else None,
    )


def peer_set_summary_stats(peers: list[PeerMultiples]) -> dict:
    def _stat(values):
        clean = [v for v in values if v is not None and v > 0]
        if not clean:
            return {"median": None, "mean": None, "min": None, "max": None}
        return {"median": statistics.median(clean), "mean": statistics.mean(clean),
                "min": min(clean), "max": max(clean)}
    return {
        "ev_ebitda": _stat([p.ev_ebitda for p in peers]),
        "ev_sales":  _stat([p.ev_sales  for p in peers]),
        "pe":        _stat([p.pe        for p in peers]),
    }


def implied_valuation_from_multiple(
    target_metric: float, peer_multiple: float,
    total_debt: float = 0.0, cash: float = 0.0,
    is_equity_multiple: bool = False,
) -> float:
    raw = target_metric * peer_multiple
    return raw if is_equity_multiple else raw - total_debt + cash
