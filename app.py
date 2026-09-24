import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ============================================================
# HYBRID PFOS — MOBILE CONTROL CENTER
# Loan + MF + EPF + Bonus + Tax + Rate Scenarios
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

st.markdown("""
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

    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 19px !important;
        font-weight: 700 !important;
        color: #1b365d !important;
    }

    h1 {
        font-size: 24px !important;
        font-weight: 800 !important;
        color: #1b365d;
    }

    h2, h3 {
        font-size: 18px !important;
        color: #1b365d;
    }

    .pfos-card {
        padding: 12px;
        border-radius: 12px;
        border: 1px solid #e9ecef;
        background-color: #f8f9fa;
        margin-bottom: 10px;
    }

    .small-note {
        font-size: 12px;
        color: #6c757d;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Hybrid PFOS Mobile")
st.markdown(
    "*Dynamic mortgage elimination + MF wealth engine + EPFO hybrid strategy.*"
)

# ============================================================
# SIDEBAR — MASTER INPUTS
# ============================================================

with st.sidebar:

    st.header("🏦 Loan Master Inputs")

    baseline_date = datetime(2026, 9, 30)

    loan_start = st.number_input(
        "Current HDFC Principal (₹)",
        value=3457730,
        step=10000
    )

    loan_rate = st.number_input(
        "Current Home Loan Rate (%)",
        value=7.10,
        step=0.05
    ) / 100.0

    emi = st.number_input(
        "Monthly EMI (₹)",
        value=31354,
        step=500
    )

    bonus = st.number_input(
        "Annual March Bonus (₹)",
        value=200000,
        step=10000
    )

    st.divider()

    st.header("📈 Rate Scenario Engine")

    rate_change_month = st.number_input(
        "Rate Change Month",
        value=1,
        min_value=1,
        max_value=120,
        step=1,
        help="Month 1 = Oct 2026, Month 2 = Nov 2026, etc."
    )

    rate_change_value = st.number_input(
        "New Loan Rate After Change (%)",
        value=7.35,
        step=0.05
    ) / 100.0

    target_date = st.date_input(
        "Debt-Free Target Date",
        value=datetime(2029, 8, 31)
    )

    st.divider()

    st.header("🏦 EPFO / EPF Hybrid Engine")

    epf_start = st.number_input(
        "EPF Opening Balance (₹)",
        value=471347,
        step=5000
    )

    epf_inflow_base = st.number_input(
        "Initial EPF Monthly Inflow (₹)",
        value=17232,
        step=500
    )

    first_hike_month = st.number_input(
        "First EPF Hike Month",
        value=12,
        step=1
    )

    annual_hike_pct = st.number_input(
        "Annual EPF Inflow Hike (%)",
        value=10.0,
        step=0.5
    ) / 100.0

    epf_rate = st.number_input(
        "EPF Interest Rate (%)",
        value=8.25,
        step=0.25
    ) / 100.0

    epf_harvest_pct = st.number_input(
        "EPF Hybrid Prepayment % (%)",
        value=75.0,
        min_value=0.0,
        max_value=100.0,
        step=5.0,
        help="Percentage of available EPF balance used at scheduled hybrid events."
    ) / 100.0

    st.divider()

    st.header("🎁 Sporadic Windfalls")

    wf1_amt = st.number_input(
        "Windfall 1 Amount (₹)",
        value=0,
        step=10000
    )

    wf1_m = st.number_input(
        "Windfall 1 Month",
        value=18,
        step=1
    )

    wf2_amt = st.number_input(
        "Windfall 2 Amount (₹)",
        value=0,
        step=10000
    )

    wf2_m = st.number_input(
        "Windfall 2 Month",
        value=30,
        step=1
    )

    st.divider()

    st.header("📈 MF Portfolio & Tax")

    mf_sip = st.number_input(
        "Monthly MF SIP (₹)",
        value=70000,
        step=5000
    )

    mf_cagr = st.number_input(
        "MF Planning CAGR (%)",
        value=13.0,
        step=0.5
    ) / 100.0

    ltcg_limit = st.number_input(
        "Annual LTCG Exemption (₹)",
        value=125000,
        step=5000
    )

    st.divider()

    st.header("🧪 Scenario Controls")

    scenario_horizon = st.number_input(
        "Simulation Horizon (Months)",
        value=120,
        min_value=48,
        max_value=240,
        step=12
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def financial_year(dt):
    """
    Indian financial year.
    Apr-Mar.
    """
    if dt.month >= 4:
        return f"{dt.year}-{str(dt.year + 1)[-2:]}"
    else:
        return f"{dt.year - 1}-{str(dt.year)[-2:]}"


def month_difference(start_date, end_date):
    return (
        (end_date.year - start_date.year) * 12
        + end_date.month
        - start_date.month
    )


def get_rate_for_month(
    month,
    base_rate,
    change_month=None,
    changed_rate=None
):
    if change_month is not None and month >= change_month:
        return changed_rate
    return base_rate


# ============================================================
# CORE SIMULATION ENGINE
# ============================================================

def run_pfos_simulation(
    loan_p,
    base_loan_rate,
    monthly_emi,
    annual_bonus,
    epf_b,
    epf_base,
    hike_m,
    hike_rate,
    r_epf,
    sip,
    r_mf,
    wf1_a,
    wf1_mo,
    wf2_a,
    wf2_mo,
    base_dt,
    horizon,
    ltcg_exemption,
    epf_harvest_percentage,
    rate_change_m=None,
    rate_after_change=None,
    extra_initial_prepayment=0
):

    loan = float(loan_p)

    epf = float(epf_b)

    loan_r_base = float(base_loan_rate)

    epf_r = float(r_epf) / 12.0
    mf_r = float(r_mf) / 12.0

    # --------------------------------------------------------
    # MF lots
    # Each lot tracks:
    # month
    # cost basis
    # current value
    # --------------------------------------------------------

    mf_lots = []

    # --------------------------------------------------------
    # Annual realised LTCG tracking
    # --------------------------------------------------------

    ltcg_used_by_fy = {}

    # --------------------------------------------------------
    # Initial optional prepayment
    # --------------------------------------------------------

    initial_extra_used = min(
        float(extra_initial_prepayment),
        loan
    )

    loan -= initial_extra_used

    log = []

    # Scheduled hybrid events
    hybrid_event_months = [6, 18, 30, 42]

    for m in range(1, horizon + 1):

        curr_dt = base_dt + relativedelta(months=m)

        # ====================================================
        # RATE ENGINE
        # ====================================================

        current_rate = get_rate_for_month(
            m,
            loan_r_base,
            rate_change_m,
            rate_after_change
        )

        monthly_loan_rate = current_rate / 12.0

        # ====================================================
        # EPF INFLOW ENGINE
        # ====================================================

        if m < hike_m:

            current_epf_inflow = epf_base

        else:

            years_elapsed = (m - hike_m) // 12

            current_epf_inflow = epf_base * (
                (1 + hike_rate) ** (years_elapsed + 1)
            )

        # EPF growth
        epf = epf * (1 + epf_r) + current_epf_inflow

        # ====================================================
        # MF GROWTH
        # ====================================================

        for lot in mf_lots:
            lot["v"] *= (1 + mf_r)

        # SIP continues while model is running
        current_sip = sip

        mf_lots.append({
            "m": m,
            "p": current_sip,
            "v": current_sip
        })

        # ====================================================
        # EMI / LOAN AMORTISATION
        # ====================================================

        interest = 0.0
        principal_from_emi = 0.0

        if loan > 0:

            interest = loan * monthly_loan_rate

            principal_from_emi = max(
                0.0,
                monthly_emi - interest
            )

            # If interest exceeds EMI, don't let loan
            # accidentally become negative.
            if principal_from_emi > 0:

                principal_from_emi = min(
                    principal_from_emi,
                    loan
                )

                loan -= principal_from_emi

        # ====================================================
        # PREPAYMENT EVENT TRACKING
        # ====================================================

        bonus_paid = 0.0
        epf_harvest = 0.0
        mf_harvest = 0.0
        windfall_applied = 0.0
        realised_ltcg = 0.0

        # ====================================================
        # SPORADIC WINDFALL 1
        # ====================================================

        if (
            m == wf1_mo
            and loan > 0
            and wf1_a > 0
        ):

            windfall_applied += min(
                wf1_a,
                loan
            )

            loan -= min(
                wf1_a,
                loan
            )

        # ====================================================
        # SPORADIC WINDFALL 2
        # ====================================================

        if (
            m == wf2_mo
            and loan > 0
            and wf2_a > 0
        ):

            wf2_use = min(
                wf2_a,
                loan
            )

            windfall_applied += wf2_use
            loan -= wf2_use

        # ====================================================
        # HYBRID PREPAYMENT EVENTS
        #
        # March:
        # Bonus → EPF → MF
        #
        # MF is harvested only from eligible lots and
        # respects the annual LTCG exemption.
        # ====================================================

        if (
            m in hybrid_event_months
            and loan > 0
        ):

            # ------------------------------------------------
            # 1. BONUS
            # ------------------------------------------------

            bonus_paid = min(
                annual_bonus,
                loan
            )

            loan -= bonus_paid

            # ------------------------------------------------
            # 2. EPF HYBRID HARVEST
            # ------------------------------------------------

            if loan > 0:

                available_epf = epf * epf_harvest_percentage

                epf_harvest = min(
                    available_epf,
                    loan
                )

                epf -= epf_harvest
                loan -= epf_harvest

            # ------------------------------------------------
            # 3. MF TAX-EFFICIENT HARVEST
            # ------------------------------------------------

            if loan > 0:

                # Original PFOS schedule:
                # M18 and M30 = up to ₹2.5L
                # M42 = whatever remains.
                #
                # M6 does not use MF.
                if m in [18, 30]:

                    target_mf = min(
                        loan,
                        250000.0
                    )

                elif m == 42:

                    target_mf = loan

                else:

                    target_mf = 0.0

                if target_mf > 0:

                    fy = financial_year(curr_dt)

                    already_used = ltcg_used_by_fy.get(
                        fy,
                        0.0
                    )

                    remaining_ltcg = max(
                        0.0,
                        ltcg_exemption - already_used
                    )

                    eligible = []

                    for lot in mf_lots:

                        age_months = m - lot["m"]

                        if (
                            age_months >= 12
                            and lot["v"] > lot["p"]
                        ):

                            eligible.append(lot)

                    # FIFO
                    eligible.sort(
                        key=lambda x: x["m"]
                    )

                    actual_harvest = 0.0

                    for lot in eligible:

                        if actual_harvest >= target_mf:
                            break

                        gain = max(
                            0.0,
                            lot["v"] - lot["p"]
                        )

                        if gain <= 0:
                            continue

                        remaining_needed = (
                            target_mf - actual_harvest
                        )

                        # Fraction of lot needed
                        fraction = min(
                            1.0,
                            remaining_needed / lot["v"]
                        )

                        # Tax constraint
                        if gain * fraction > remaining_ltcg:

                            if remaining_ltcg <= 0:
                                break

                            fraction = (
                                remaining_ltcg / gain
                            )

                        amount = lot["v"] * fraction

                        gain_realised = gain * fraction

                        actual_harvest += amount

                        realised_ltcg += gain_realised

                        remaining_ltcg -= gain_realised

                        # Reduce remaining lot
                        lot["p"] *= (1 - fraction)
                        lot["v"] *= (1 - fraction)

                    mf_harvest = actual_harvest

                    loan -= mf_harvest

                    ltcg_used_by_fy[fy] = (
                        already_used
                        + realised_ltcg
                    )

        # ====================================================
        # CLEAN-UP
        # ====================================================

        loan = max(
            0.0,
            loan
        )

        epf = max(
            0.0,
            epf
        )

        mf_value = sum(
            lot["v"]
            for lot in mf_lots
        )

        total_assets = (
            epf
            + mf_value
        )

        net_worth = (
            total_assets
            - loan
        )

        # ====================================================
        # LOG
        # ====================================================

        log.append({

            "Month": m,

            "Calendar Date":
                curr_dt.strftime("%b %Y"),

            "Loan Rate":
                current_rate * 100,

            "Loan":
                loan,

            "Interest":
                interest,

            "EMI Principal":
                principal_from_emi,

            "EPF":
                epf,

            "EPF Inflow":
                current_epf_inflow,

            "MF":
                mf_value,

            "Net Worth":
                net_worth,

            "Bonus":
                bonus_paid,

            "Windfall":
                windfall_applied,

            "EPF Harvest":
                epf_harvest,

            "MF Harvest":
                mf_harvest,

            "Realized LTCG":
                realised_ltcg,

            "LTCG Used FY":
                ltcg_used_by_fy.get(
                    financial_year(curr_dt),
                    0.0
                ),

            "Initial Extra Prepayment":
                initial_extra_used if m == 1 else 0.0
        })

    return pd.DataFrame(log)


# ============================================================
# BASE SIMULATION
# ============================================================

df_sim = run_pfos_simulation(
    loan_start,
    loan_rate,
    emi,
    bonus,
    epf_start,
    epf_inflow_base,
    first_hike_month,
    annual_hike_pct,
    epf_rate,
    mf_sip,
    mf_cagr,
    wf1_amt,
    wf1_m,
    wf2_amt,
    wf2_m,
    baseline_date,
    scenario_horizon,
    ltcg_limit,
    epf_harvest_pct,
    rate_change_month,
    rate_change_value
)


# ============================================================
# DEBT-FREE DATE
# ============================================================

def get_debt_free_info(df):

    rows = df[df["Loan"] <= 0.01]

    if rows.empty:

        return None, "Beyond model horizon"

    row = rows.iloc[0]

    return (
        int(row["Month"]),
        f"M {int(row['Month'])} ({row['Calendar Date']})"
    )


debt_free_m, debt_free_date_str = get_debt_free_info(
    df_sim
)


# ============================================================
# TARGET DATE MONTH
# ============================================================

target_month = month_difference(
    baseline_date,
    datetime(
        target_date.year,
        target_date.month,
        target_date.day
    )
)

target_month = max(
    1,
    target_month
)


# ============================================================
# TARGET DATE STATUS
# ============================================================

if target_month <= len(df_sim):

    target_row = df_sim.iloc[
        target_month - 1
    ]

    target_balance = target_row["Loan"]

else:

    target_balance = None


# ============================================================
# EXTRA PREPAYMENT REQUIRED
#
# Binary-search the minimum lump sum TODAY needed to
# make the loan reach zero by the target month.
# ============================================================

def calculate_extra_required(
    rate_for_scenario,
    target_m,
    max_search=10000000
):

    if target_m > scenario_horizon:
        return None

    # First check without extra money
    base = run_pfos_simulation(
        loan_start,
        rate_for_scenario,
        emi,
        bonus,
        epf_start,
        epf_inflow_base,
        first_hike_month,
        annual_hike_pct,
        epf_rate,
        mf_sip,
        mf_cagr,
        wf1_amt,
        wf1_m,
        wf2_amt,
        wf2_m,
        baseline_date,
        scenario_horizon,
        ltcg_limit,
        epf_harvest_pct
    )

    if base.iloc[target_m - 1]["Loan"] <= 0.01:
        return 0.0

    low = 0.0
    high = min(
        max_search,
        loan_start
    )

    # If even the entire loan doesn't solve it,
    # return the full loan as a cap.
    test = run_pfos_simulation(
        loan_start,
        rate_for_scenario,
        emi,
        bonus,
        epf_start,
        epf_inflow_base,
        first_hike_month,
        annual_hike_pct,
        epf_rate,
        mf_sip,
        mf_cagr,
        wf1_amt,
        wf1_m,
        wf2_amt,
        wf2_m,
        baseline_date,
        scenario_horizon,
        ltcg_limit,
        epf_harvest_pct,
        extra_initial_prepayment=high
    )

    if test.iloc[target_m - 1]["Loan"] > 0.01:
        return None

    for _ in range(35):

        mid = (low + high) / 2.0

        test = run_pfos_simulation(
            loan_start,
            rate_for_scenario,
            emi,
            bonus,
            epf_start,
            epf_inflow_base,
            first_hike_month,
            annual_hike_pct,
            epf_rate,
            mf_sip,
            mf_cagr,
            wf1_amt,
            wf1_m,
            wf2_amt,
            wf2_m,
            baseline_date,
            scenario_horizon,
            ltcg_limit,
            epf_harvest_pct,
            extra_initial_prepayment=mid
        )

        balance = test.iloc[
            target_m - 1
        ]["Loan"]

        if balance <= 0.01:
            high = mid
        else:
            low = mid

    return high


# ============================================================
# SCENARIO ENGINE
# ============================================================

scenario_rates = [
    loan_rate,
    0.0735,
    0.0760,
    0.0810
]

scenario_rows = []

for rate in scenario_rates:

    scenario_df = run_pfos_simulation(
        loan_start,
        rate,
        emi,
        bonus,
        epf_start,
        epf_inflow_base,
        first_hike_month,
        annual_hike_pct,
        epf_rate,
        mf_sip,
        mf_cagr,
        wf1_amt,
        wf1_m,
        wf2_amt,
        wf2_m,
        baseline_date,
        scenario_horizon,
        ltcg_limit,
        epf_harvest_pct
    )

    scenario_debt_m, scenario_debt_date = (
        get_debt_free_info(
            scenario_df
        )
    )

    extra_required = calculate_extra_required(
        rate,
        target_month
    )

    if target_month <= len(scenario_df):

        balance_at_target = scenario_df.iloc[
            target_month - 1
        ]["Loan"]

    else:

        balance_at_target = np.nan

    scenario_rows.append({

        "Loan Rate":
            f"{rate * 100:.2f}%",

        "Debt-Free":
            scenario_debt_date,

        "Balance at Target":
            balance_at_target,

        "Extra Needed Today":
            extra_required
    })


scenario_df = pd.DataFrame(
    scenario_rows
)


# ============================================================
# DASHBOARD
# ============================================================

st.divider()

st.subheader("🎯 PFOS Control Center")

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "Projected Debt-Free",
        debt_free_date_str
    )

with col2:
    st.metric(
        "Current Loan",
        f"₹ {loan_start:,.0f}"
    )


col3, col4 = st.columns(2)

with col3:
    st.metric(
        "Monthly MF SIP",
        f"₹ {mf_sip:,.0f}"
    )

with col4:
    st.metric(
        "Current Loan Rate",
        f"{loan_rate * 100:.2f}%"
    )


# ============================================================
# TARGET DATE PROTECTION
# ============================================================

st.divider()

st.subheader("🛡️ Aug-2029 Target Protection")

if target_balance is not None:

    if target_balance <= 0.01:

        st.success(
            f"🟢 ON TRACK — loan reaches ₹0 by "
            f"{target_date.strftime('%b %Y')}."
        )

    else:

        st.warning(
            f"🟡 Target gap — approximately
