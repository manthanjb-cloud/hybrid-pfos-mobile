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

        div[data-testid="stMetric"] {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            padding: 10px 12px;
            border-radius: 12px;
            margin-bottom: 8px;
        }

        div[data-testid="stMetric"] label {
            font-size: 12px !important;
            color: #6c757d !important;
        }

        div[data-testid="stMetricValue"] {
            font-size: 19px !important;
            font-weight: 700 !important;
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

        .small-note {
            font-size: 12px;
            color: #6c757d;
        }

        .status-box {
            padding: 12px;
            border-radius: 10px;
            border: 1px solid #dee2e6;
            margin-bottom: 10px;
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
    "Mortgage elimination + MF wealth engine + EPF hybrid reserve"
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def money(value):
    if value is None or pd.isna(value):
        return "₹ 0"
    return f"₹ {value:,.0f}"


def financial_year(dt):
    """
    Indian financial year.
    Apr-Mar.
    Example:
    Sep 2026 -> FY 2026-27
    Mar 2027 -> FY 2026-27
    Apr 2027 -> FY 2027-28
    """
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


def is_after_or_equal(dt, target):
    return dt >= target


def fmt_date(dt):
    return dt.strftime("%d %b %Y")


def calculate_monthly_emi_interest(principal, annual_rate):
    return principal * annual_rate / 12.0


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
    """
    Harvest only lots that have crossed 12 months.

    Uses FIFO order.

    The model treats the LTCG exemption as a planning allowance
    and does NOT intentionally realize STCG.

    Returns:
        updated lots,
        amount harvested,
        realized LTCG,
        updated FY LTCG usage
    """

    if required_amount <= 0:
        return lots, 0.0, 0.0, fy_ltcg_used

    available_ltcg = max(
        0.0,
        annual_ltcg_limit - fy_ltcg_used
    )

    if available_ltcg <= 0:
        return lots, 0.0, 0.0, fy_ltcg_used

    harvested = 0.0
    realized_gain = 0.0

    new_lots = []

    for lot in lots:

        age_months = month_difference(
            lot["date"],
            harvest_date
        )

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

            # Maximum amount that can be sold from this lot
            amount_by_need = remaining_need

            # Maximum sale allowed by remaining LTCG exemption.
            gain_ratio = gain / value

            if gain_ratio > 0:
                amount_by_tax = available_ltcg / gain_ratio
            else:
                amount_by_tax = 0.0

            sale_amount = min(
                value,
                amount_by_need,
                amount_by_tax
            )

            if sale_amount > 0:

                gain_realized = sale_amount * gain_ratio

                principal_removed = (
                    sale_amount * principal / value
                    if value > 0
                    else 0.0
                )

                lot["value"] -= sale_amount
                lot["principal"] -= principal_removed

                harvested += sale_amount
                realized_gain += gain_realized
                available_ltcg -= gain_realized

        if lot["value"] > 0.01:
            new_lots.append(lot)

    fy_ltcg_used += realized_gain

    return (
        new_lots,
        harvested,
        realized_gain,
        fy_ltcg_used
    )


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

    # MF lots
    mf_lots = []

    # Existing MF corpus is treated as an opening lot.
    if opening_mf > 0:
        add_mf_lot(
            mf_lots,
            opening_mf,
            start_date
        )

    loan_monthly_rate = loan_rate / 12.0
    epf_monthly_rate = epf_interest_rate / 12.0
    mf_monthly_return = (1.0 + mf_return) ** (1.0 / 12.0) - 1.0

    # Apply optional extra initial prepayment
    initial_prepayment = min(
        max(0.0, extra_initial_prepayment),
        loan
    )

    loan -= initial_prepayment

    rows = []

    fy_ltcg_used = 0.0
    current_fy = financial_year(start_date)

    debt_free_date = None

    # Harvest dates
    harvest_dates = []

    d = first_mf_harvest_date

    while d <= start_date + relativedelta(months=max_months):
        harvest_dates.append(d)
        d = d + relativedelta(
            months=mf_harvest_interval_months
        )

    for month_number in range(1, max_months + 1):

        current_date = start_date + relativedelta(
            months=month_number
        )

        # ----------------------------------------------------
        # FINANCIAL YEAR RESET
        # ----------------------------------------------------

        this_fy = financial_year(current_date)

        if this_fy != current_fy:
            current_fy = this_fy
            fy_ltcg_used = 0.0

        # ----------------------------------------------------
        # EPF CONTRIBUTION
        # ----------------------------------------------------

        # Base inflow during first 12 months.
        # First hike applies after the first 12 months.
        hike_cycles = max(
            0,
            (month_number - 1) // 12
        )

        current_epf_inflow = (
            epf_monthly_inflow
            * ((1.0 + epf_hike_pct) ** hike_cycles)
        )

        # Monthly approximation of EPF interest.
        epf *= (1.0 + epf_monthly_rate)
        epf += current_epf_inflow

        # ----------------------------------------------------
        # MF GROWTH + SIP
        # ----------------------------------------------------

        grow_mf_lots(
            mf_lots,
            mf_monthly_return
        )

        # SIP continues while the plan is active through
        # July 2029. After that, no new SIP is assumed.
        if current_date <= date(2029, 7, 31):
            add_mf_lot(
                mf_lots,
                mf_sip,
                current_date
            )

        # ----------------------------------------------------
        # LOAN EMI
        # ----------------------------------------------------

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

            monthly_interest = (
                loan * rate_used / 12.0
            )

            principal_from_emi = max(
                0.0,
                emi - monthly_interest
            )

            principal_from_emi = min(
                principal_from_emi,
                loan
            )

            loan -= principal_from_emi

        # ----------------------------------------------------
        # MARCH BONUS
        # ----------------------------------------------------

        bonus_paid = 0.0

        if (
            is_march(current_date)
            and current_date >= date(2027, 3, 1)
            and loan > 0
        ):
            bonus_paid = min(
                annual_bonus,
                loan
            )

            loan -= bonus_paid

        # ----------------------------------------------------
        # MF HARVEST EVENT
        # ----------------------------------------------------

        mf_harvest = 0.0
        realized_ltcg = 0.0

        is_harvest_date = any(
            current_date.year == hd.year
            and current_date.month == hd.month
            for hd in harvest_dates
        )

        # Harvest only from Aug-2027 onward and only while
        # there is still a loan.
        if (
            is_harvest_date
            and current_date >= first_mf_harvest_date
            and loan > 0
        ):

            (
                mf_lots,
                mf_harvest,
                realized_ltcg,
                fy_ltcg_used
            ) = harvest_mf_tax_efficient(
                mf_lots,
                current_date,
                loan,
                ltcg_limit,
                fy_ltcg_used
            )

            loan -= mf_harvest

        # ----------------------------------------------------
        # EPF HYBRID HARVEST
        # ----------------------------------------------------

        epf_harvest = 0.0

        # EPF is used at the same 6-month hybrid events,
        # but only after the MF tax-efficient sale.
        #
        # This percentage is a MODEL ASSUMPTION.
        # Actual EPFO withdrawal eligibility must be verified
        # separately before executing.
        if (
            is_harvest_date
            and current_date >= first_mf_harvest_date
            and loan > 0
            and epf_harvest_pct > 0
        ):

            available_epf = epf * epf_harvest_pct

            epf_harvest = min(
                available_epf,
                loan
            )

            epf -= epf_harvest
            loan -= epf_harvest

        # ----------------------------------------------------
        # CLEANUP
        # ----------------------------------------------------

        loan = max(0.0, loan)
        epf = max(0.0, epf)

        mf_value = mf_total_value(mf_lots)
        mf_cost = mf_total_cost(mf_lots)
        mf_gain = mf_total_gain(mf_lots)

        if loan <= 0.01 and debt_free_date is None:
            debt_free_date = current_date

        # ----------------------------------------------------
        # LEDGER ROW
        # ----------------------------------------------------

        rows.append(
            {
                "Month": month_number,
                "Date": current_date,
                "Calendar Date": current_date.strftime("%b %Y"),
                "FY": this_fy,
                "Rate": rate_used,
                "Opening Loan": loan
                + principal_from_emi
                + bonus_paid
                + mf_harvest
                + epf_harvest,
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
                "MF Cost": mf_cost,
                "MF Gain": mf_gain,
                "Net Worth": mf_value + epf - loan,
                "Total Assets": mf_value + epf,
                "Hybrid Event": (
                    is_harvest_date
                    or bonus_paid > 0
                )
            }
        )

        # ----------------------------------------------------
        # STOP IF LOAN IS CLEARED
        # ----------------------------------------------------

        if loan <= 0.01:

            # Continue the model for wealth tracking only.
            # We don't break here because the user may want
            # to see the portfolio trajectory.

            pass

    return (
        pd.DataFrame(rows),
        debt_free_date
    )


# ============================================================
# SIDEBAR — MASTER INPUTS
# ============================================================

with st.sidebar:

    st.header("⚙️ Loan Inputs")

    start_date = st.date_input(
        "PFOS As-of Date",
        value=date(2026, 9, 30)
    )

    loan_start = st.number_input(
        "HDFC Principal Outstanding (₹)",
        min_value=0,
        value=3457730,
        step=10000
    )

    loan_rate_pct = st.number_input(
        "Current HDFC Rate (%)",
        min_value=0.0,
        max_value=20.0,
        value=7.10,
        step=0.05
    )

    loan_rate = loan_rate_pct / 100.0

    emi = st.number_input(
        "Monthly EMI (₹)",
        min_value=0,
        value=31354,
        step=500
    )

    annual_bonus = st.number_input(
        "Annual March Bonus Prepayment (₹)",
        min_value=0,
        value=200000,
        step=10000
    )

    st.divider()

    st.header("🎯 Target")

    target_date = st.date_input(
        "Debt-Free Target",
        value=date(2029, 8, 31)
    )

    st.divider()

    st.header("📈 MF Engine")

    mf_sip = st.number_input(
        "Monthly MF SIP (₹)",
        min_value=0,
        value=70000,
        step=5000
    )

    mf_return_pct = st.number_input(
        "Planning MF CAGR (%)",
        min_value=-50.0,
        max_value=100.0,
        value=13.0,
        step=0.5
    )

    mf_return = mf_return_pct / 100.0

    opening_mf = st.number_input(
        "MF Corpus Already Invested (₹)",
        min_value=0,
        value=0,
        step=10000,
        help=(
            "Enter the actual MF value already invested as of "
            "the PFOS start date. This prevents the model from "
            "inventing an opening corpus."
        )
    )

    st.divider()

    st.header("🧾 Tax Engine")

    ltcg_limit = st.number_input(
        "Annual LTCG Planning Allowance (₹)",
        min_value=0,
        value=125000,
        step=5000
    )

    st.caption(
        "The model tracks this by Indian financial year "
        "(Apr-Mar), not per withdrawal event."
    )

    st.divider()

    st.header("🏦 EPF Engine")

    epf_start = st.number_input(
        "Opening EPF Balance (₹)",
        min_value=0,
        value=471347,
        step=5000
    )

    epf_monthly_inflow = st.number_input(
        "Current Monthly EPF Inflow (₹)",
        min_value=0,
        value=17232,
        step=500
    )

    epf_hike_pct = st.number_input(
        "Annual EPF Contribution Hike (%)",
        min_value=0.0,
        max_value=50.0,
        value=10.0,
        step=0.5
    ) / 100.0

    epf_interest_pct = st.number_input(
        "EPF Interest Rate (%)",
        min_value=0.0,
        max_value=20.0,
        value=8.25,
        step=0.25
    )

    epf_interest_rate = epf_interest_pct / 100.0

    epf_harvest_pct = st.slider(
        "EPF Harvest % at Hybrid Events",
        min_value=0,
        max_value=100,
        value=75,
        step=5
    ) / 100.0

    st.warning(
        "EPF harvest is a planning assumption. "
        "Verify actual EPFO withdrawal eligibility before execution."
    )

    st.divider()

    st.header("📅 Hybrid Harvest")

    first_mf_harvest_date = st.date_input(
        "First MF/EPF Harvest",
        value=date(2027, 8, 31)
    )

    harvest_interval = st.selectbox(
        "Harvest Frequency",
        options=[3, 6, 12],
        index=1,
        format_func=lambda x: f"Every {x} months"
    )

    st.divider()

    st.header("📊 Rate Stress")

    stress_rate_pct = st.number_input(
        "Stress Rate (%)",
        min_value=0.0,
        max_value=20.0,
        value=8.10,
        step=0.05
    )

    stress_rate = stress_rate_pct / 100.0

    stress_date = st.date_input(
        "Stress Rate Starts",
        value=date(2027, 4, 1)
    )

    st.divider()

    st.header("🧪 Advanced")

    extra_initial_prepayment = st.number_input(
        "Extra Prepayment Today (₹)",
        min_value=0,
        value=0,
        step=10000
    )

    horizon_months = st.slider(
        "Simulation Horizon",
        min_value=36,
        max_value=180,
        value=120,
        step=12
    )


# ============================================================
# RUN BASE SIMULATION
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
    ltcg_limit=ltcg_limit,
    first_mf_harvest_date=first_mf_harvest_date,
    mf_harvest_interval_months=harvest_interval,
    max_months=horizon_months,
    extra_initial_prepayment=extra_initial_prepayment
)


# ============================================================
# RUN STRESS SIMULATION
# ============================================================

df_stress, debt_free_stress = run_pfos_simulation(
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
    ltcg_limit=ltcg_limit,
    first_mf_harvest_date=first_mf_harvest_date,
    mf_harvest_interval_months=harvest_interval,
    stress_rate=stress_rate,
    stress_date=stress_date,
    max_months=horizon_months,
    extra_initial_prepayment=extra_initial_prepayment
)


# ============================================================
# TARGET SNAPSHOT
# ============================================================

target_rows = df_base[
    df_base["Date"] >= pd.Timestamp(target_date)
]

if target_rows.empty:
    target_row = df_base.iloc[-1]
else:
    target_row = target_rows.iloc[0]


target_loan = float(target_row["Loan"])
target_mf = float(target_row["MF"])
target_epf = float(target_row["EPF"])
target_net_worth = float(target_row["Net Worth"])


# ============================================================
# DEBT-FREE STATUS
# ============================================================

if debt_free_base is not None:

    debt_free_text = fmt_date(debt_free_base)

    if debt_free_base <= target_date:

        st.success(
            f"🟢 Target protected — debt-free by "
            f"{debt_free_text}."
        )

    else:

        st.warning(
            f"🟡 Debt-free date is {debt_free_text}, "
            f"which is after the {fmt_date(target_date)} target."
        )

else:

    st.error(
        "🔴 Loan is not cleared within the simulation horizon."
    )


# ============================================================
# TOP DASHBOARD
# ============================================================

st.subheader("📊 PFOS Dashboard")

c1, c2 = st.columns(2)

with c1:
    st.metric(
        "Current Loan",
        money(loan_start)
    )

with c2:
    st.metric(
        "Current Rate",
        f"{loan_rate_pct:.2f}%"
    )

c3, c4 = st.columns(2)

with c3:
    st.metric(
        "Target Loan",
        money(target_loan)
    )

with c4:
    st.metric(
        "Target Date",
        fmt_date(target_date)
    )

c5, c6 = st.columns(2)

with c5:
    st.metric(
        "Target MF",
        money(target_mf)
    )

with c6:
    st.metric(
        "Target EPF",
        money(target_epf)
    )


# ============================================================
# TARGET GAP
# ============================================================

st.divider()
st.subheader("🎯 August 2029 Target Protection")

if target_loan <= 0.01:

    st.success(
        f"🟢 ON TRACK — projected loan balance at target "
        f"date is {money(target_loan)}."
    )

else:

    st.warning(
        f"🟡 Target gap — approximately "
        f"{money(target_loan)} remains at the target date "
        f"under the current plan."
    )


# ============================================================
# RATE STRESS SUMMARY
# ============================================================

st.divider()
st.subheader("📈 Interest-Rate Stress")

stress_target_rows = df_stress[
    df_stress["Date"] >= pd.Timestamp(target_date)
]

if stress_target_rows.empty:
    stress_target_row = df_stress.iloc[-1]
else:
    stress_target_row = stress_target_rows.iloc[0]

stress_target_loan = float(
    stress_target_row["Loan"]
)

stress_target_mf = float(
    stress_target_row["MF"]
)

stress_target_epf = float(
    stress_target_row["EPF"]
)

stress_net_worth = float(
    stress_target_row["Net Worth"]
)

rate_table = pd.DataFrame(
    [
        {
            "Scenario": "Current Rate",
            "Rate": f"{loan_rate_pct:.2f}%",
            "Loan at Target": target_loan,
            "MF at Target": target_mf,
            "EPF at Target": target_epf,
            "Net Worth at Target": target_net_worth,
            "Debt-Free": (
                fmt_date(debt_free_base)
                if debt_free_base is not None
                else "Beyond horizon"
            )
        },
        {
            "Scenario": "Stress Rate",
            "Rate": f"{stress_rate_pct:.2f}%",
            "Rate Starts": fmt_date(stress_date),
            "Loan at Target": stress_target_loan,
            "MF at Target": stress_target_mf,
            "EPF at Target": stress_target_epf,
            "Net Worth at Target": stress_net_worth,
            "Debt-Free": (
                fmt_date(debt_free_stress)
                if debt_free_stress is not None
                else "Beyond horizon"
            )
        }
    ]
)

display_cols = [
    "Scenario",
    "Rate",
    "Loan at Target",
    "MF at Target",
    "EPF at Target",
    "Net Worth at Target",
    "Debt-Free"
]

st.dataframe(
    rate_table[display_cols].style.format(
        {
            "Loan at Target": "₹{:,.0f}",
            "MF at Target": "₹{:,.0f}",
            "EPF at Target": "₹{:,.0f}",
            "Net Worth at Target": "₹{:,.0f}"
        }
    ),
    use_container_width=True,
    hide_index=True
)


# ============================================================
# ASSET VS DEBT CHART
# ============================================================

st.divider()
st.subheader("🔥 Asset vs Debt Burn")

chart_data = df_base.set_index("Date")[
    ["Loan", "MF", "EPF"]
]

st.line_chart(
    chart_data,
    height=280
)


# ============================================================
# NET WORTH CHART
# ============================================================

st.subheader("📈 PFOS Net Worth")

net_worth_chart = df_base.set_index("Date")[
    ["Net Worth"]
]

st.line_chart(
    net_worth_chart,
    height=220
)


# ============================================================
# HYBRID EVENT SCHEDULE
# ============================================================

st.divider()
st.subheader("🗓️ Execution Schedule")

event_rows = df_base[
    (
        df_base["Hybrid Event"]
    )
    |
    (
        df_base["MF Harvest"] > 0
    )
    |
    (
        df_base["EPF Harvest"] > 0
    )
    |
    (
        df_base["Bonus"] > 0
    )
].copy()

if not event_rows.empty:

    event_display = event_rows[
        [
            "Calendar Date",
            "Month",
            "Rate",
            "Loan",
            "Bonus",
            "MF Harvest",
            "MF Realized LTCG",
            "FY LTCG Used",
            "EPF Harvest"
        ]
    ].copy()

    event_display.columns = [
        "Date",
        "M",
        "Rate",
        "Loan Left",
        "Bonus",
        "MF Sale",
        "Realized LTCG",
        "FY LTCG Used",
        "EPF Harvest"
    ]

    st.dataframe(
        event_display.style.format(
            {
                "Rate": "{:.2%}",
                "Loan Left": "₹{:,.0f}",
                "Bonus": "₹{:,.0f}",
                "MF Sale": "₹{:,.0f}",
                "Realized LTCG": "₹{:,.0f}",
                "FY LTCG Used": "₹{:,.0f}",
                "EPF Harvest": "₹{:,.0f}"
            }
        ),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "No hybrid events are present in the selected horizon."
    )


# ============================================================
# TAX MONITOR
# ============================================================

st.divider()
st.subheader("🧾 LTCG Tax Monitor")

tax_rows = df_base[
    df_base["MF Realized LTCG"] > 0
].copy()

if not tax_rows.empty:

    tax_display = tax_rows[
        [
            "Calendar Date",
            "FY",
            "MF Realized LTCG",
            "FY LTCG Used"
        ]
    ].copy()

    tax_display.columns = [
        "Date",
        "Financial Year",
        "LTCG Realized",
        "FY LTCG Used"
    ]

    st.dataframe(
        tax_display.style.format(
            {
                "LTCG Realized": "₹{:,.0f}",
                "FY LTCG Used": "₹{:,.0f}"
            }
        ),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "No LTCG has been realized yet under the current model."
    )


# ============================================================
# TARGET-DATE ASSET BREAKDOWN
# ============================================================

st.divider()
st.subheader("🎯 Target-Date Snapshot")

snapshot = pd.DataFrame(
    {
        "Component": [
            "Loan",
            "MF",
            "EPF",
            "Total Assets",
            "Net Worth"
        ],
        "Value": [
            target_loan,
            target_mf,
            target_epf,
            target_mf + target_epf,
            target_net_worth
        ]
    }
)

st.dataframe(
    snapshot.style.format(
        {"Value": "₹{:,.0f}"}
    ),
    use_container_width=True,
    hide_index=True
)


# ============================================================
# LOAN AMORTIZATION
# ============================================================

st.divider()
st.subheader("🏦 Loan Engine")

loan_display = df_base[
    [
        "Calendar Date",
        "Rate",
        "Interest",
        "Principal from EMI",
        "Bonus",
        "MF Harvest",
        "EPF Harvest",
        "Loan"
    ]
].copy()

loan_display.columns = [
    "Date",
    "Rate",
    "Interest",
    "EMI Principal",
    "Bonus",
    "MF Prepayment",
    "EPF Prepayment",
    "Loan Balance"
]

st.dataframe(
    loan_display.style.format(
        {
            "Rate": "{:.2%}",
            "Interest": "₹{:,.0f}",
            "EMI Principal": "₹{:,.0f}",
            "Bonus": "₹{:,.0f}",
            "MF Prepayment": "₹{:,.0f}",
            "EPF Prepayment": "₹{:,.0f}",
            "Loan Balance": "₹{:,.0f}"
        }
    ),
    use_container_width=True,
    hide_index=True
)


# ============================================================
# FULL LEDGER
# ============================================================

st.divider()
st.subheader("📚 Full PFOS Ledger")

st.dataframe(
    df_base.style.format(
        {
            "Rate": "{:.2%}",
            "Opening Loan": "₹{:,.0f}",
            "EMI": "₹{:,.0f}",
            "Interest": "₹{:,.0f}",
            "Principal from EMI": "₹{:,.0f}",
            "Bonus": "₹{:,.0f}",
            "MF Harvest": "₹{:,.0f}",
            "MF Realized LTCG": "₹{:,.0f}",
            "FY LTCG Used": "₹{:,.0f}",
            "EPF Harvest": "₹{:,.0f}",
            "Loan": "₹{:,.0f}",
            "EPF": "₹{:,.0f}",
            "MF": "₹{:,.0f}",
            "MF Cost": "₹{:,.0f}",
            "MF Gain": "₹{:,.0f}",
            "Net Worth": "₹{:,.0f}",
            "Total Assets": "₹{:,.0f}"
        }
    ),
    use_container_width=True,
    hide_index=True
)


# ============================================================
# PFOS ASSUMPTIONS
# ============================================================

st.divider()
st.subheader("⚠️ Model Assumptions")

st.markdown(
    """
    - MF returns are a planning assumption, not a guaranteed return.
    - MF harvesting is restricted to lots that have reached 12 months.
    - LTCG usage is tracked by Indian financial year.
    - SIPs continue through July 2029.
    - March bonuses are treated as direct principal prepayments.
    - EPF growth is modelled monthly using the selected annual rate.
    - EPF contribution hikes are applied annually.
    - EPF harvesting is a model assumption and must be checked against
      actual EPFO withdrawal rules before execution.
    - Loan interest is modelled monthly.
    - The EMI is kept constant in the simulation. If HDFC changes the
      EMI or tenure after an actual rate revision, update the EMI input.
    - The stress scenario changes the loan rate from the selected
      stress date onward while keeping the other planning assumptions
      unchanged.
    """
)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "PFOS Hybrid Engine • Loan + MF + EPF + Tax + Rate Stress"
)

st.caption(
    "Planning model only — reconcile against HDFC, EPFO and actual "
    "MF/tax statements before executing transactions."
)
