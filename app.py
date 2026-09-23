import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Page Configuration for Mobile-First View
st.set_page_config(
    page_title="Hybrid PFOS Mobile",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- MOBILE-FIRST CSS STYLING ---
st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 12px 15px;
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        margin-bottom: 10px;
    }
    div[data-testid="stMetric"] label {
        font-size: 13px !important;
        color: #6c757d !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 20px !important;
        font-weight: 700 !important;
        color: #1b365d !important;
    }
    h1 {
        font-size: 24px !important;
        font-weight: 800 !important;
        color: #1b365d;
        margin-bottom: 0.5rem;
    }
    h2, h3 {
        font-size: 18px !important;
        color: #1b365d;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Hybrid PFOS Mobile")
st.markdown("*Your mobile command center for dynamic mortgage elimination & wealth acceleration.*")

# --- SIDEBAR: MASTER INPUTS & MODULAR SCENARIOS ---
with st.sidebar:
    st.header("⚙️ Master Inputs")
    baseline_date = datetime(2026, 9, 30)
    
    loan_start = st.number_input("Starting HDFC Principal (₹)", value=3457730, step=10000)
    loan_rate = st.number_input("Home Loan Interest Rate (%)", value=7.10, step=0.05) / 100.0  
    emi = st.number_input("Monthly EMI (₹)", value=31354, step=500)
    bonus = st.number_input("Annual March Bonus (₹)", value=200000, step=10000)

    st.divider()
    st.header("📈 Annual Career Hikes & EPF")
    epf_start = st.number_input("EPF Opening Balance (₹)", value=471347, step=5000)  
    epf_inflow_base = st.number_input("Initial EPF Monthly Inflow (₹)", value=17232, step=500)
    first_hike_month = st.number_input("First Hike Month Number", value=12, step=1, help="Month when your first annual hike applies")
    annual_hike_pct = st.number_input("Annual EPF Hike Rate (%)", value=10.0, step=0.5, help="Percentage increase applied every 12 months from first hike") / 100.0
    epf_rate = st.number_input("EPF Interest Rate (%)", value=8.25, step=0.25) / 100.0

    st.divider()
    st.header("🎁 Sporadic Windfalls")
    st.markdown("Direct loan paydowns from family/support:")
    wf1_amt = st.number_input("Windfall 1 Amount (₹)", value=0, step=10000)
    wf1_m = st.number_input("Windfall 1 Month Number", value=18, step=1)
    
    wf2_amt = st.number_input("Windfall 2 Amount (₹)", value=0, step=10000)
    wf2_m = st.number_input("Windfall 2 Month Number", value=30, step=1)

    st.divider()
    st.header("📊 Portfolio & Tax")
    mf_sip_pre = st.number_input("Monthly MF SIP (₹)", value=70000, step=5000)
    mf_cagr = st.number_input("MF Planning CAGR (%)", value=13.0, step=0.5) / 100.0
    ltcg_limit = st.number_input("Annual LTCG Exemption (₹)", value=125000, step=5000)

# --- ADVANCED MODULAR SIMULATION ENGINE ---
def run_modular_simulation(loan_p, r_loan, monthly_emi, annual_bonus, epf_b, epf_base, hike_m, hike_rate, r_epf, sip_pre, r_mf, wf1_a, wf1_mo, wf2_a, wf2_mo, base_dt):
    months = 120
    loan_r = r_loan / 12.0
    epf_r = r_epf / 12.0
    mf_r = r_mf / 12.0
    
    mf_lots = []
    epf = epf_b
    loan = loan_p
    log = []
    
    for m in range(1, months + 1):
        curr_dt = base_dt + relativedelta(months=m)
        
        # Calculate dynamic EPF inflow with compound annual hikes
        if m < hike_m:
            current_epf_inflow = epf_base
        else:
            # Number of annual hike cycles completed
            years_elapsed = (m - hike_m) // 12
            current_epf_inflow = epf_base * ((1 + hike_rate) ** (years_elapsed + 1))
        
        epf = epf * (1 + epf_r) + current_epf_inflow
        for lot in mf_lots:
            lot['v'] *= (1 + mf_r)
            
        current_sip = sip_pre if loan > 0 else (sip_pre + monthly_emi)
        mf_lots.append({'m': m, 'p': current_sip, 'v': current_sip})
        
        intr = 0.0
        if loan > 0:
            intr = loan * loan_r
            prnc = monthly_emi - intr
            loan = max(0.0, loan - prnc)
            
        bonus_paid = 0.0
        epf_h = 0.0
        mf_h = 0.0
        windfall_applied = 0.0
        realized_gain_period = 0.0
        
        # Check sporadic windfalls in this month
        if m == wf1_mo and loan > 0 and wf1_a > 0:
            windfall_applied += min(wf1_a, loan)
            loan -= windfall_applied
        if m == wf2_mo and loan > 0 and wf2_a > 0:
            wf2_applied = min(wf2_a, loan)
            windfall_applied += wf2_applied
            loan -= wf2_applied
            
        # March Prepayment Events (Months 6, 18, 30, 42)
        if m in [6, 18, 30, 42] and loan > 0:
            bonus_paid = min(annual_bonus, loan)
            loan -= bonus_paid
            
            if loan > 0:
                epf_h = min(epf * 0.75, loan)
                epf -= epf_h
                loan -= epf_h
                
            if loan > 0 and m in [18, 30, 42]:
                target_mf = min(loan, 250000.0 if m != 42 else loan)
                eligible = [lot for lot in mf_lots if (m - lot['m']) >= 12 and lot['v'] > lot['p']]
                eligible.sort(key=lambda x: x['m'])
                
                realized = 0.0
                actual_h = 0.0
                for lot in eligible:
                    gain = lot['v'] - lot['p']
                    if gain <= 0: continue
                    val_needed = target_mf - actual_h
                    frac = 1.0 if lot['v'] <= val_needed else val_needed / lot['v']
                    if realized + (gain * frac) > ltcg_limit:
                        frac = (ltcg_limit - realized) / gain
                    realized += gain * frac
                    amt = lot['v'] * frac
                    actual_h += amt
                    lot['p'] *= (1 - frac)
                    lot['v'] *= (1 - frac)
                    if actual_h >= target_mf or realized >= ltcg_limit:
                        break
                loan -= actual_h
                mf_h = actual_h
                realized_gain_period = realized
                
        loan = max(0.0, loan)
        mf_val = sum(l['v'] for l in mf_lots)
        
        log.append({
            'Month': m,
            'Calendar Date': curr_dt.strftime('%b %Y'),
            'Loan': loan,
            'EPF': epf,
            'MF': mf_val,
            'Net Worth': mf_val + epf - loan,
            'EPF_Harvest': epf_h,
            'MF_Harvest': mf_h,
            'Bonus': bonus_paid,
            'Windfall': windfall_applied,
            'Realized_LTCG': realized_gain_period
        })
        
    return pd.DataFrame(log)

df_sim = run_modular_simulation(
    loan_start, loan_rate, emi, bonus, epf_start, 
    epf_inflow_base, first_hike_month, annual_hike_pct, epf_rate, 
    mf_sip_pre, mf_cagr, wf1_amt, wf1_m, wf2_amt, wf2_m, baseline_date
)

# --- FULLY DYNAMIC DEBT-FREE CALCULATIONS ---
debt_free_rows = df_sim[df_sim['Loan'] == 0]
if not debt_free_rows.empty:
    debt_free_row = debt_free_rows.iloc[0]
    debt_free_m = int(debt_free_row['Month'])
    debt_free_date_str = f"M {debt_free_m} ({debt_free_row['Calendar Date']})"
else:
    debt_free_date_str = "Beyond 10 Yrs"

# --- MOBILE DASHBOARD METRICS ---
col1, col2 = st.columns(2)
with col1:
    st.metric("Debt-Free Target", debt_free_date_str)
with col2:
    st.metric("Opening EPF", f"₹ {epf_start:,.0f}")

col3, col4 = st.columns(2)
with col3:
    st.metric("Portfolio (Yr 5)", f"₹ {df_sim.iloc[59]['MF']:,.0f}")
with col4:
    st.metric("Net Worth (Yr 10)", f"₹ {df_sim.iloc[119]['Net Worth']:,.0f}")

st.divider()

# --- MOBILE CHART VIEW ---
st.subheader("📊 Asset vs. Debt Burn")
chart_data = df_sim.set_index('Month')[['Loan', 'MF', 'EPF']]
st.line_chart(chart_data, height=220)

# --- DYNAMIC SCHEDULE & EVENT TABLE ---
st.subheader("🗓️ Execution Schedule & Calendar")
event_rows = df_sim[(df_sim['Month'].isin([6, 18, 30, 42])) | (df_sim['Windfall'] > 0)][['Calendar Date', 'Month', 'Loan', 'Bonus', 'Windfall', 'EPF_Harvest', 'MF_Harvest']]
event_rows.columns = ['Date', 'M', 'Loan Left', 'Bonus', 'Windfall', 'EPF Harvest', 'MF Sale']
st.dataframe(event_rows.style.format("{:,.0f}", subset=['Loan Left', 'Bonus', 'Windfall', 'EPF Harvest', 'MF Sale']), use_container_width=True)

st.success("✅ Upgraded with compound annual career hikes and modular sporadic windfalls.")


