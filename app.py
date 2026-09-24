import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Hybrid PFOS Mobile",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed"
)


# ============================================================
# MOBILE-FIRST CSS
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            padding-left: 0.8rem;
            padding-right: 0.8rem;
        }

        h1 {
            font-size: 24px !important;
            font-weight: 800 !important;
        }

        h2 {
            font-size: 19px !important;
        }

        h3 {
            font-size: 17px !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# HEADER
# ============================================================

st.title("🛡️ Hybrid PFOS Mobile")
st.caption(
    "Mortgage elimination + MF wealth engine + EPF hybrid reserve + NPS"
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def money(value):
    if value is None or pd.isna(value):
        return "₹ 0"
    return f"₹ {value:,.0f}"


def financial_year(dt):
    if dt.month >= 4:
        return f"{dt.year}-{str(dt.year + 1)[-2:]}"
    return f"{dt.year - 1}-{str(dt.year)[-2:]}"


def month_difference(start_dt, end_dt):
    return (
        (end_dt.year - start_dt.year) * 12
        + (end_dt.month - start_dt.month)
    )


def is_march(dt):
    return dt.month == 3


def fmt_date(dt):
    return dt.strftime("%d %b %Y")


# ============================================================
# MF LOT ENGINE
# ============================================================

def add_mf_lot(lots, contribution, dt):
    if contribution <= 0:
        return
    lots.append(
        {
            "date": dt,
            "principal": float(contribution),
            "value": float(contribution)
        }
    )


def grow_mf_lots(lots, monthly_return):
    for lot in lots:
        lot["value"] *= (1.0 + monthly_return)


def mf_total_value(lots):
    return sum(lot["value"] for lot in lots)


def mf_total_cost(lots):
    return sum(lot["principal"] for lot in lots)


def mf_total_gain(lots):
    return sum(
        max(0.0, lot["value"] - lot["principal"])
        for lot in lots
    )


def harvest_mf_tax_efficient(
    lots,
    harvest_date,
    required_amount,
    annual_ltcg_limit,
    fy_ltcg_used
):
    if required_amount <= 0:
        return lots, 0.0, 0.0, fy_ltcg_used

    available_ltcg = max(0.0, annual_ltcg_limit - fy_ltcg_used)
    if available_ltcg <= 0:
        return lots, 0.0, 0.0, fy_ltcg_used

    harvested = 0.0
    realized_gain = 0.0
    new_lots = []

    for lot in lots:
        age_months = month_difference(lot["date"], harvest_date)
        value = lot["value"]
        principal = lot["principal"]
        gain = max(0.0, value - principal)

        if (
            age_months >= 12
            and value > 0
            and harvested < required_amount
            and available_ltcg > 0
            and gain > 0
        ):
            remaining_need = required_amount - harvested
            gain_ratio = gain / value if value > 0 else 0.0
            amount_by_tax = available_ltcg / gain_ratio if gain_ratio > 0 else value

            sale_amount = min(value, remaining_need, amount_by_tax)

            if sale_amount > 0:
                gain_realized = sale_amount * gain_ratio
                principal_removed = sale_amount * principal / value if value > 0 else 0.0

                lot["value"] -= sale_amount
                lot["principal"] -= principal_removed

                harvested += sale_amount
                realized_gain += gain_realized
                available_ltcg -= gain_realized

        if lot["value"] > 0.01:
            new_lots.append(lot)

    fy_ltcg_used += realized_gain
    return new_lots, harvested, realized_gain, fy_ltcg_used


# ============================================================
# RATE ENGINE
# ============================================================

def get_rate_for_date(
    current_date,
    base_rate,
    stress_rate,
    rate_change_date,
    use_stress
):
    if use_stress and current_date >= rate_change_date:
        return stress_rate
    return base_rate


# ============================================================
# CORE PFOS SIMULATION
# ============================================================

def run_pfos_simulation(
    start_date,
    loan_start,
    loan_rate,
    emi,
    annual_bonus,
    target_date,
    mf_sip,
    mf_return,
    opening_mf,
    epf_start,
    epf_monthly_inflow,
    epf_hike_pct,
    epf_interest_rate,
    epf_harvest_pct,
    nps_start,
    nps_return,
    ltcg_limit,
    first_mf_harvest_date,
    mf_harvest_interval_months,
    stress_rate=None,
    stress_date=None,
    max_months=120,
    extra_initial_prepayment=0.0
):
    loan = float(loan_start)
    epf = float(epf_start)
    nps = float(nps_start)
    mf_lots = []

    if opening_mf > 0:
        add_mf_lot(mf_lots, opening_mf, start_date)

    epf_monthly_rate = epf_interest_rate / 12.0
    mf_monthly_return = (1.0 + mf_return) ** (1.0 / 12.0) - 1.0
    nps_monthly_return = (1.0 + nps_return) ** (1.0 / 12.0) - 1.0

    initial_prepayment = min(max(0.0, extra_initial_prepayment), loan)
    loan -= initial_prepayment

    rows = []
    fy_ltcg_used = 0.0
    current_fy = financial_year(start_date)
    debt_free_date = None

    harvest_dates = []
    d = first_mf_harvest_date
    while d <= start_date + relativedelta(months=max_months):
        harvest_dates.append(d)
        d = d + relativedelta(months=mf_harvest_interval_months)

    for month_number in range(1, max_months + 1):
        current_date = start_date + relativedelta(months=month_number)
        this_fy = financial_year(current_date)

        if this_fy != current_fy:
            current_fy = this_fy
            fy_ltcg_used = 0.0

        # Compounding core assets
        hike_cycles = max(0, (month_number - 1) // 12)
        current_epf_inflow = epf_monthly_inflow * ((1.0 + epf_hike_pct) ** hike_cycles)

        epf = epf * (1.0 + epf_monthly_rate) + current_epf_inflow
        nps = nps * (1.0 + nps_monthly_return)  # No new inflows, pure compounding
        
        grow_mf_lots(mf_lots, mf_monthly_return)

        if current_date <= date(2029, 7, 31):
            add_mf_lot(mf_lots, mf_sip, current_date)

        rate_used = get_rate_for_date(
            current_date,
            loan_rate,
            stress_rate if stress_rate is not None else loan_rate,
            stress_date if stress_date is not None else current_date,
            stress_rate is not None
        )

        monthly_interest = 0.0
        principal_from_emi = 0.0

        if loan > 0:
            monthly_interest = loan * rate_used / 12.0
            principal_from_emi = min(max(0.0, emi - monthly_interest), loan)
            loan -= principal_from_emi

        bonus_paid = 0.0
        if is_march(current_date) and current_date >= date(2027, 3, 1) and loan > 0:
            bonus_paid = min(annual_bonus, loan)
            loan -= bonus_paid

        is_harvest_date = any(
            current_date.year == hd.year and current_date.month == hd.month
            for hd in harvest_dates
        )

        # ----------------------------------------------------
        # EPF HYBRID HARVEST (PRIORITY 1)
        # ----------------------------------------------------
        epf_harvest = 0.0
        if is_harvest_date and current_date >= first_mf_harvest_date and loan > 0 and epf_harvest_pct > 0:
            available_epf = epf * epf_harvest_pct
            epf_harvest = min(available_epf, loan)
            epf -= epf_harvest
            loan -= epf_harvest

        # ----------------------------------------------------
        # MF HARVEST EVENT (PRIORITY 2)
        # ----------------------------------------------------
        mf_harvest = 0.0
        realized_ltcg = 0.0
        if is_harvest_date and current_date >= first_mf_harvest_date and loan > 0:
            mf_lots, mf_harvest, realized_ltcg, fy_ltcg_used = harvest_mf_tax_efficient(
                mf_lots, current_date, loan, ltcg_limit, fy_ltcg_used
            )
            loan -= mf_harvest

        loan = max(0.0, loan)
        epf = max(0.0, epf)

        mf_value = mf_total_value(mf_lots)
        mf_cost = mf_total_cost(mf_lots)
        mf_gain = mf_total_gain(mf_lots)

        if loan <= 0.01 and debt_free_date is None:
            debt_free_date = current_date

        rows.append(
            {
                "Month": month_number,
                "Date": pd.to_datetime(current_date),
                "Calendar Date": current_date.strftime("%b %Y"),
                "FY": this_fy,
                "Rate": rate_used,
                "Opening Loan": loan + principal_from_emi + bonus_paid + mf_harvest + epf_harvest,
                "EMI": emi if loan > 0 or principal_from_emi > 0 else 0,
                "Interest": monthly_interest,
                "Principal from EMI": principal_from_emi,
                "Bonus": bonus_paid,
                "MF Harvest": mf_harvest,
                "MF Realized LTCG": realized_ltcg,
                "FY LTCG Used": fy_ltcg_used,
                "EPF Harvest": epf_harvest,
                "Loan": loan,
                "EPF": epf,
                "MF": mf_value,
                "NPS": nps,
                "MF Cost": mf_cost,
                "MF Gain": mf_gain,
                "Net Worth": mf_value + epf + nps - loan,
                "Total Assets": mf_value + epf + nps,
                "Hybrid Event": is_harvest_date or bonus_paid > 0
            }
        )

    return pd.DataFrame(rows), debt_free_date


# ============================================================
# SIDEBAR — MASTER INPUTS
# ============================================================

with st.sidebar:
    st.header("⚙️ Loan Inputs")
    start_date = st.date_input("PFOS As-of Date", value=date(2026, 9, 30))
    loan_start = st.number_input("HDFC Principal Outstanding (₹)", min_value=0, value=3457730, step=10000)
    loan_rate_pct = st.number_input("Current HDFC Rate (%)", min_value=0.0, max_value=20.0, value=7.10, step=0.05)
    loan_rate = loan_rate_pct / 100.0
    emi = st.number_input("Monthly EMI (₹)", min_value=0, value=31354, step=500)
    annual_bonus = st.number_input("Annual March Bonus Prepayment (₹)", min_value=0, value=200000, step=10000)

    st.divider()
    st.header("🎯 Target")
    target_date = st.date_input("Debt-Free Target", value=date(2029, 8, 31))

    st.divider()
    st.header("📈 MF Engine")
    mf_sip = st.number_input("Monthly MF SIP (₹)", min_value=0, value=70000, step=5000)
    mf_return_pct = st.number_input("Planning MF CAGR (%)", min_value=-50.0, max_value=100.0, value=13.0, step=0.5)
    mf_return = mf_return_pct / 100.0
    opening_mf = st.number_input("MF Corpus Already Invested (₹)", min_value=0, value=0, step=10000)

    st.divider()
    st.header("🇮🇳 NPS Engine (75E/25C)")
    nps_start = st.number_input("Opening NPS Balance (₹)", min_value=0, value=232244, step=10000)
    nps_return_pct = st.number_input("Planning NPS CAGR (%)", min_value=-50.0, max_value=100.0, value=11.0, step=0.5)
    nps_return = nps_return_pct / 100.0

    st.divider()
    st.header("🧾 Tax Engine")
    ltcg_limit = st.number_input("Annual LTCG Planning Allowance (₹)", min_value=0, value=125000, step=5000)

    st.divider()
    st.header("🏦 EPF Engine")
    epf_start = st.number_input("Opening EPF Balance (₹)", min_value=0, value=471347, step=5000)
    epf_monthly_inflow = st.number_input("Current Monthly EPF Inflow (₹)", min_value=0, value=17232, step=500)
    epf_hike_pct = st.number_input("Annual EPF Contribution Hike (%)", min_value=0.0, max_value=50.0, value=10.0, step=0.5) / 100.0
    epf_interest_pct = st.number_input("EPF Interest Rate (%)", min_value=0.0, max_value=20.0, value=8.25, step=0.25)
    epf_interest_rate = epf_interest_pct / 100.0
    epf_harvest_pct = st.slider("EPF Harvest % at Hybrid Events", min_value=0, max_value=100, value=75, step=5) / 100.0

    st.divider()
    st.header("📅 Hybrid Harvest")
    first_mf_harvest_date = st.date_input("First MF/EPF Harvest", value=date(2027, 3, 30))
    harvest_interval = st.selectbox("Harvest Frequency", options=[3, 6, 12], index=1, format_func=lambda x: f"Every {x} months")

    st.divider()
    st.header("📊 Rate Stress")
    stress_rate_pct = st.number_input("Stress Rate (%)", min_value=0.0, max_value=20.0, value=8.10, step=0.05)
    stress_rate = stress_rate_pct / 100.0
    stress_date = st.date_input("Stress Rate Starts", value=date(2027, 4, 1))

    st.divider()
    st.header("🧪 Advanced")
    extra_initial_prepayment = st.number_input("Extra Prepayment Today (₹)", min_value=0, value=0, step=10000)
    horizon_months = st.slider("Simulation Horizon", min_value=36, max_value=180, value=120, step=12)


# ============================================================
# RUN SIMULATIONS
# ============================================================

df_base, debt_free_base = run_pfos_simulation(
    start_date=start_date,
    loan_start=loan_start,
    loan_rate=loan_rate,
    emi=emi,
    annual_bonus=annual_bonus,
    target_date=target_date,
    mf_sip=mf_sip,
    mf_return=mf_return,
    opening_mf=opening_mf,
    epf_start=epf_start,
    epf_monthly_inflow=epf_monthly_inflow,
    epf_hike_pct=epf_hike_pct,
    epf_interest_rate=epf_interest_rate,
    epf_harvest_pct=epf_harvest_pct,
    nps_start=nps_start,
    nps_return=nps_return,
    ltcg_limit=ltcg_limit,
    first_mf_harvest_date=first_mf_harvest_date,
    mf_harvest_interval_months=harvest_interval,
    max_months=horizon_months,
    extra_initial_prepayment=extra_initial_prepayment
)


# ============================================================
# TARGET SNAPSHOT
# ============================================================

target_rows = df_base[df_base["Date"] >= pd.Timestamp(target_date)]
target_row = target_rows.iloc[0] if not target_rows.empty else df_base.iloc[-1]

target_loan = float(target_row["Loan"])
target_mf = float(target_row["MF"])
target_epf = float(target_row["EPF"])
target_nps = float(target_row["NPS"])
target_net_worth = float(target_row["Net Worth"])


# ============================================================
# UI DASHBOARD & OUTPUTS
# ============================================================

if debt_free_base is not None:
    debt_free_text = fmt_date(debt_free_base)
    if debt_free_base <= target_date:
        st.success(f"🟢 Target protected — debt-free by {debt_free_text}.")
    else:
        st.warning(f"🟡 Debt-free date is {debt_free_text}, after target date.")
else:
    st.error("🔴 Loan is not cleared within the simulation horizon.")

st.subheader("📊 PFOS Dashboard")
c1, c2 = st.columns(2)
c1.metric("Current Loan", money(loan_start))
c2.metric("Target Loan", money(target_loan))

c3, c4 = st.columns(2)
c3.metric("Target Date", fmt_date(target_date))
c4.metric("Target Net Worth", money(target_net_worth))

# ============================================================
# ASSET VS DEBT CHART 
# ============================================================

st.divider()
st.subheader("🔥 Asset vs Debt Burn")

chart_data = df_base.set_index("Date")[
    ["Loan", "MF", "EPF", "NPS"]
]

st.line_chart(
    chart_data,
    height=280
)

# ============================================================
# EXECUTION SCHEDULE 
# ============================================================

st.divider()
st.subheader("🗓️ Execution Schedule & Wealth Building")

event_rows = df_base[
    df_base["Hybrid Event"] | (df_base["MF Harvest"] > 0) | (df_base["EPF Harvest"] > 0) | (df_base["Bonus"] > 0)
].copy()

if not event_rows.empty:
    event_display = event_rows[["Calendar Date", "Month", "Loan", "EPF", "MF", "NPS", "Net Worth", "Bonus", "MF Harvest", "EPF Harvest"]].copy()
    event_display.columns = ["Date", "M", "Loan", "EPF Bal", "MF Bal", "NPS Bal", "Net Worth", "Bonus", "MF Sale", "EPF Harv"]
    st.dataframe(event_display.style.format({
        "Loan": "₹{:,.0f}", 
        "EPF Bal": "₹{:,.0f}", 
        "MF Bal": "₹{:,.0f}", 
        "NPS Bal": "₹{:,.0f}",
        "Net Worth": "₹{:,.0f}", 
        "Bonus": "₹{:,.0f}", 
        "MF Sale": "₹{:,.0f}", 
        "EPF Harv": "₹{:,.0f}"
    }), use_container_width=True, hide_index=True)
else:
    st.info("No hybrid events present.")

st.divider()
st.caption("Hybrid PFOS Mobile • Live Engine Active")
