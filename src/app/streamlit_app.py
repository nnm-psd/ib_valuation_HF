"""
IB Valuation Lab
DB-first: reads from committed SQLite DB, no live yfinance calls.
Works on Hugging Face Spaces, Railway, and localhost.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.db.models import SessionLocal, Company, FinancialLine, MarketDataPoint, init_db
from src.models.dcf import WaccInputs, compute_wacc, project_fcff, run_dcf
from src.models.comps import compute_multiples, peer_set_summary_stats, implied_valuation_from_multiple
from src.models.lbo import build_sources_and_uses, build_debt_schedule, compute_returns
from config.settings import DEFAULT_MARKET_RISK_PREMIUM, DEFAULT_TERMINAL_GROWTH_RATE, DEFAULT_TAX_RATE_FR

st.set_page_config(page_title="IB Valuation Lab", layout="wide", page_icon="💼")

# ── DB session ────────────────────────────────────────────────────────────────

@st.cache_resource
def get_session():
    init_db()
    return SessionLocal()

session = get_session()

# ── data helpers ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_all_companies() -> list[dict]:
    return [
        {"id": c.id, "name": c.name, "ticker": c.ticker,
         "sector": c.sector, "country": c.country}
        for c in session.query(Company).order_by(Company.name).all()
    ]

@st.cache_data(ttl=300)
def get_financials(company_id: int) -> pd.DataFrame:
    rows = session.query(FinancialLine).filter_by(company_id=company_id).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([{"year": r.fiscal_year, "field": r.field_name, "value": r.value} for r in rows])
    return df.pivot_table(index="field", columns="year", values="value").sort_index(axis=1)

@st.cache_data(ttl=300)
def get_market_data(company_id: int) -> dict:
    mkt = (session.query(MarketDataPoint)
           .filter_by(company_id=company_id)
           .order_by(MarketDataPoint.date.desc())
           .first())
    return {"price": mkt.close_price, "shares": mkt.shares_outstanding} if mkt else {}

def latest(df: pd.DataFrame, field: str) -> float | None:
    if df.empty or field not in df.index:
        return None
    row = df.loc[field].dropna()
    return float(row.iloc[-1]) if len(row) else None

def fmt(v, scale=1e9, suffix="B"):
    return f"${v/scale:.2f}{suffix}" if v is not None else "N/A"

# ── sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("💼 IB Valuation Lab")
companies = get_all_companies()

if not companies:
    st.title("💼 IB Valuation Lab")
    st.error("No companies in the database.")
    st.code("python scripts/crawl_cac40.py\n# then commit data/processed/valuation_lab.db")
    st.stop()

selected_name = st.sidebar.selectbox("Company", [c["name"] for c in companies])
company = next(c for c in companies if c["name"] == selected_name)

fin    = get_financials(company["id"])
mkt    = get_market_data(company["id"])
price  = mkt.get("price")
shares = mkt.get("shares")
market_cap  = (price * shares) if (price and shares) else None

revenue      = latest(fin, "revenue")
gross_profit = latest(fin, "gross_profit")
ebitda       = latest(fin, "ebitda")
ebit         = latest(fin, "ebit")
net_income   = latest(fin, "net_income")
d_and_a      = latest(fin, "d_and_a")
capex        = latest(fin, "capex")
fcf          = latest(fin, "free_cash_flow")
cash_bs      = latest(fin, "cash")
total_debt   = latest(fin, "total_debt") or 0
target_ev    = (market_cap or 0) + total_debt - (cash_bs or 0)

# ── header ────────────────────────────────────────────────────────────────────

st.title(f"💼 {selected_name}")
st.caption(f"`{company['ticker']}` · {company.get('sector') or 'N/A'} · {company.get('country') or 'N/A'}")

tab_overview, tab_dcf, tab_comps, tab_lbo = st.tabs(
    ["📊 Overview", "📈 DCF", "🔍 Comps", "🏦 LBO"]
)

# ─── OVERVIEW ─────────────────────────────────────────────────────────────────
with tab_overview:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Price",      f"${price:,.2f}" if price else "N/A")
    c2.metric("Market Cap", fmt(market_cap))
    c3.metric("EV",         fmt(target_ev))
    c4.metric("Revenue",    fmt(revenue))
    c5.metric("EBITDA",     fmt(ebitda))
    st.divider()

    if fin.empty:
        st.warning("No financial data. Run the crawler locally and commit the DB.")
    else:
        key_fields = {
            "Revenue": "revenue", "Gross Profit": "gross_profit",
            "EBITDA": "ebitda", "EBIT": "ebit",
            "Net Income": "net_income", "Free Cash Flow": "free_cash_flow",
        }
        rows = {label: fin.loc[fld] / 1e9
                for label, fld in key_fields.items() if fld in fin.index}
        if rows:
            display = pd.DataFrame(rows).T
            display.columns = [str(c) for c in display.columns]
            st.subheader("Financial summary ($B)")
            st.dataframe(
                display.style.format("{:.2f}")
                       .highlight_max(axis=1, color="#d4edda")
                       .highlight_min(axis=1, color="#f8d7da"),
                use_container_width=True,
            )

        if "revenue" in fin.index and "ebitda" in fin.index:
            years = [str(c) for c in fin.columns]
            fig = go.Figure()
            fig.add_bar(name="Revenue", x=years, y=fin.loc["revenue"]/1e9, marker_color="#4C72B0")
            fig.add_bar(name="EBITDA",  x=years, y=fin.loc["ebitda"]/1e9,  marker_color="#55A868")
            fig.update_layout(barmode="group", title="Revenue & EBITDA ($B)",
                              yaxis_title="$B", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

# ─── DCF ──────────────────────────────────────────────────────────────────────
with tab_dcf:
    st.subheader("DCF — Discounted Cash Flow")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**WACC**")
        rfr  = st.number_input("Risk-free rate",         value=0.033, step=0.001, format="%.3f")
        beta = st.number_input("Beta",                   value=1.2,   step=0.05)
        mrp  = st.number_input("Market risk premium",    value=DEFAULT_MARKET_RISK_PREMIUM, step=0.005, format="%.3f")
        cod  = st.number_input("Cost of debt (pre-tax)", value=0.04,  step=0.005, format="%.3f")
        tax  = st.number_input("Tax rate",               value=DEFAULT_TAX_RATE_FR, step=0.01)
    with col2:
        st.markdown("**Growth**")
        g1 = st.number_input("Revenue growth yr 1–3 (%)", value=5.0, step=0.5) / 100
        g2 = st.number_input("Revenue growth yr 4–5 (%)", value=3.0, step=0.5) / 100
        tg = st.number_input("Terminal growth (%)", value=DEFAULT_TERMINAL_GROWTH_RATE * 100, step=0.1) / 100
    with col3:
        st.markdown("**Balance sheet**")
        debt_in = st.number_input("Total debt ($B)", value=round(total_debt / 1e9, 2), step=0.1)
        cash_in = st.number_input("Cash ($B)",       value=round((cash_bs or 0) / 1e9, 2), step=0.1)

    wacc = compute_wacc(WaccInputs(
        risk_free_rate=rfr, beta=beta, market_risk_premium=mrp,
        cost_of_debt=cod, tax_rate=tax,
        market_value_equity=market_cap or 1,
        market_value_debt=debt_in * 1e9,
    ))

    try:
        fcff_proj = project_fcff(
            base_ebit=ebit or 0, tax_rate=tax,
            base_d_and_a=d_and_a or 0, base_capex=abs(capex or 0),
            base_delta_nwc=0, revenue_growth_rates=[g1, g1, g1, g2, g2],
        )
        result = run_dcf(fcff_proj, wacc=wacc, terminal_growth=tg,
                         total_debt=debt_in * 1e9, cash=cash_in * 1e9,
                         shares_outstanding=shares or 1)
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("WACC",               f"{wacc*100:.2f}%")
        c2.metric("Enterprise Value",   fmt(result["enterprise_value"]))
        c3.metric("Equity Value",       fmt(result["equity_value"]))
        c4.metric("Implied Price/Share",
                  f"${result['value_per_share']:.2f}" if result["value_per_share"] else "N/A")
        if price and result["value_per_share"]:
            updown = (result["value_per_share"] / price - 1) * 100
            st.metric("Upside / Downside vs current price", f"{updown:+.1f}%")

        st.subheader("Sensitivity — Implied Price/Share")
        wacc_range = [wacc + d for d in [-0.02, -0.01, 0.0, 0.01, 0.02]]
        tg_range   = [tg   + d for d in [-0.01, -0.005, 0.0, 0.005, 0.01]]
        sens = {}
        for w in wacc_range:
            row = {}
            for t in tg_range:
                try:
                    r = run_dcf(fcff_proj, wacc=w, terminal_growth=t,
                                total_debt=debt_in*1e9, cash=cash_in*1e9,
                                shares_outstanding=shares or 1)
                    row[f"TG {t*100:.1f}%"] = f"${r['value_per_share']:.1f}" if r["value_per_share"] else "err"
                except Exception:
                    row[f"TG {t*100:.1f}%"] = "err"
            sens[f"WACC {w*100:.1f}%"] = row
        st.dataframe(pd.DataFrame(sens).T, use_container_width=True)
        st.caption("Rows = WACC · Columns = terminal growth rate")
    except Exception as e:
        st.error(f"DCF error: {e}")

# ─── COMPS ────────────────────────────────────────────────────────────────────
with tab_comps:
    st.subheader("Comparable Companies Analysis")
    other_companies = [c for c in companies if c["name"] != selected_name]

    if not other_companies:
        st.info("Crawl more companies locally to enable comps.")
    else:
        peer_names = st.multiselect(
            "Select peers from DB", [c["name"] for c in other_companies]
        )
        if peer_names:
            target_m = compute_multiples(
                enterprise_value=target_ev, market_cap=market_cap or 0,
                ebitda=ebitda or 1, revenue=revenue or 1, net_income=net_income or 1,
            )
            target_m.company_name = selected_name

            peer_multiples = []
            for pname in peer_names:
                pc   = next(c for c in other_companies if c["name"] == pname)
                pfin = get_financials(pc["id"])
                pmkt = get_market_data(pc["id"])
                p_price  = pmkt.get("price")
                p_shares = pmkt.get("shares")
                p_mc     = (p_price * p_shares) if (p_price and p_shares) else 0
                p_debt   = latest(pfin, "total_debt") or 0
                p_cash   = latest(pfin, "cash") or 0
                p_ev     = p_mc + p_debt - p_cash
                pm = compute_multiples(
                    enterprise_value=p_ev, market_cap=p_mc,
                    ebitda=latest(pfin, "ebitda") or 1,
                    revenue=latest(pfin, "revenue") or 1,
                    net_income=latest(pfin, "net_income") or 1,
                )
                pm.company_name = pname
                peer_multiples.append(pm)

            stats = peer_set_summary_stats(peer_multiples)
            rows = []
            for m in [target_m] + peer_multiples:
                rows.append({
                    "Company":   ("⭐ " if m.company_name == selected_name else "") + m.company_name,
                    "EV/EBITDA": f"{m.ev_ebitda:.1f}x" if m.ev_ebitda else "N/A",
                    "EV/Sales":  f"{m.ev_sales:.2f}x"  if m.ev_sales  else "N/A",
                    "P/E":       f"{m.pe:.1f}x"         if m.pe        else "N/A",
                })
            rows.append({
                "Company":   "── Peer Median ──",
                "EV/EBITDA": f"{stats['ev_ebitda']['median']:.1f}x" if stats['ev_ebitda']['median'] else "N/A",
                "EV/Sales":  f"{stats['ev_sales']['median']:.2f}x"  if stats['ev_sales']['median']  else "N/A",
                "P/E":       f"{stats['pe']['median']:.1f}x"         if stats['pe']['median']         else "N/A",
            })
            st.dataframe(pd.DataFrame(rows).set_index("Company"), use_container_width=True)
            st.divider()
            st.markdown("**Implied equity value — peer median multiples**")
            ca, cb = st.columns(2)
            if stats["ev_ebitda"]["median"] and ebitda:
                ca.metric("via EV/EBITDA", fmt(implied_valuation_from_multiple(
                    ebitda, stats["ev_ebitda"]["median"], total_debt, cash_bs or 0)))
            if stats["ev_sales"]["median"] and revenue:
                cb.metric("via EV/Sales", fmt(implied_valuation_from_multiple(
                    revenue, stats["ev_sales"]["median"], total_debt, cash_bs or 0)))
        else:
            st.caption("Select at least one peer from the list above.")

# ─── LBO ──────────────────────────────────────────────────────────────────────
with tab_lbo:
    st.subheader("LBO — Leveraged Buyout")
    base_ebitda_b = (ebitda or 0) / 1e9
    base_fcf_b    = (fcf    or 0) / 1e9

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Entry**")
        entry_mult = st.number_input("Entry EV/EBITDA",        value=8.0,  step=0.5)
        lev_mult   = st.number_input("Leverage (Debt/EBITDA)", value=4.0,  step=0.25)
        interest_r = st.number_input("Interest rate on debt",  value=0.06, step=0.005, format="%.3f")
    with col2:
        st.markdown("**Exit**")
        exit_mult   = st.number_input("Exit EV/EBITDA",        value=8.0, step=0.5)
        holding_yrs = st.number_input("Holding period (years)",value=5,   step=1, min_value=1, max_value=10)
        ebitda_cagr = st.number_input("EBITDA CAGR (%)",       value=5.0, step=0.5) / 100

    su = build_sources_and_uses(base_ebitda_b, entry_mult, lev_mult)
    exit_ebitda_b = base_ebitda_b * (1 + ebitda_cagr) ** holding_yrs
    fcf_sweep = [base_fcf_b * (1 + ebitda_cagr) ** y for y in range(1, int(holding_yrs) + 1)]
    schedule  = build_debt_schedule(su.new_debt, interest_r, fcf_sweep)
    exit_net_debt = schedule[-1].ending_debt if schedule else su.new_debt
    returns = compute_returns(su.sponsor_equity, exit_ebitda_b, exit_mult, exit_net_debt, int(holding_yrs))

    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Entry EV",       f"${su.entry_ev:.1f}B")
    c2.metric("New Debt",       f"${su.new_debt:.1f}B")
    c3.metric("Sponsor Equity", f"${su.sponsor_equity:.1f}B")
    c4.metric("IRR",  f"{returns['irr']*100:.1f}%"  if returns["irr"]  else "N/A")
    c5.metric("MOIC", f"{returns['moic']:.2f}x"     if returns["moic"] else "N/A")

    if schedule:
        sched_df = pd.DataFrame([{
            "Year":                int(s.year),
            "Beginning Debt ($B)": round(s.beginning_debt, 2),
            "Interest ($B)":       round(s.interest_expense, 2),
            "Cash Sweep ($B)":     round(s.cash_sweep, 2),
            "Ending Debt ($B)":    round(s.ending_debt, 2),
        } for s in schedule]).set_index("Year")
        st.subheader("Debt schedule")
        st.dataframe(sched_df, use_container_width=True)

        fig2 = go.Figure()
        fig2.add_bar(name="Ending Debt", x=sched_df.index,
                     y=sched_df["Ending Debt ($B)"], marker_color="#d9534f")
        fig2.update_layout(title="Debt Paydown ($B)", yaxis_title="$B",
                           xaxis_title="Year", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)
