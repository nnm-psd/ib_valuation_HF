from __future__ import annotations
from dataclasses import dataclass


@dataclass
class WaccInputs:
    risk_free_rate:       float
    beta:                 float
    market_risk_premium:  float
    cost_of_debt:         float
    tax_rate:             float
    market_value_equity:  float
    market_value_debt:    float


def compute_wacc(inputs: WaccInputs) -> float:
    ke = inputs.risk_free_rate + inputs.beta * inputs.market_risk_premium
    kd = inputs.cost_of_debt * (1 - inputs.tax_rate)
    total = inputs.market_value_equity + inputs.market_value_debt
    return (inputs.market_value_equity / total) * ke + (inputs.market_value_debt / total) * kd


def project_fcff(
    base_ebit: float,
    tax_rate: float,
    base_d_and_a: float,
    base_capex: float,
    base_delta_nwc: float,
    revenue_growth_rates: list[float],
    fcff_margin_decay: float = 0.0,
) -> list[float]:
    projections = []
    ebit, d_and_a, capex, nwc = base_ebit, base_d_and_a, base_capex, base_delta_nwc
    for i, g in enumerate(revenue_growth_rates):
        factor = (1 - fcff_margin_decay) ** i
        ebit   *= (1 + g) * factor
        d_and_a *= (1 + g)
        capex   *= (1 + g)
        nwc     *= (1 + g)
        projections.append(ebit * (1 - tax_rate) + d_and_a - capex - nwc)
    return projections


def terminal_value_gordon(last_fcff: float, wacc: float, terminal_growth: float) -> float:
    if wacc <= terminal_growth:
        raise ValueError("WACC must exceed terminal growth rate.")
    return last_fcff * (1 + terminal_growth) / (wacc - terminal_growth)


def run_dcf(
    fcff_projections: list[float],
    wacc: float,
    terminal_growth: float,
    total_debt: float,
    cash: float,
    shares_outstanding: float,
) -> dict:
    discounted = [cf / (1 + wacc) ** (i + 1) for i, cf in enumerate(fcff_projections)]
    tv          = terminal_value_gordon(fcff_projections[-1], wacc, terminal_growth)
    discounted_tv = tv / (1 + wacc) ** len(fcff_projections)
    ev          = sum(discounted) + discounted_tv
    equity      = ev - total_debt + cash
    per_share   = equity / shares_outstanding if shares_outstanding else None
    return {
        "enterprise_value": ev,
        "equity_value":     equity,
        "value_per_share":  per_share,
        "pv_explicit_fcff": sum(discounted),
        "pv_terminal_value": discounted_tv,
    }
