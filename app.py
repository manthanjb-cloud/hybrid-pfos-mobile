import streamlit as st
import pandas as pd
import numpy as np

# Page Configuration for Mobile-First View
st.set_page_config(
    page_title="Hybrid PFOS Mobile",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed"  # Collapsed by default so mobile users see dashboard first
)

# --- MOBILE-FIRST CSS STYLING ---
st.markdown("""
<style>
    /* Remove default Streamlit top padding & margins for mobile */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* Style metric cards for a native look */
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
    
    /* Headings */
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
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #f1f3f5;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Hybrid PFOS Mobile")
st.markdown("*Your mobile command center for the 42-month mortgage elimination strategy.*")

# --- SIDEBAR: MASTER INPUTS & MODULARITY ---
with st.sidebar:
    st.header("⚙️ Master Inputs")
    st.markdown("Modify inputs for career or rate changes.")

    loan_start = st.number_input("Starting HDFC Principal (₹)", value=3457730, step=10000)
    loan_rate = st.number_input("Home Loan Interest Rate (%)", value=7.10, step=0.05) / 100.0  
    emi = st.number_input("Monthly EMI (₹)", value=31354, step=500)
    bonus = st.number_input("Annual March Bonus (₹)", value=200000, step=10000)

    epf_start = st.number_input("EPF Opening Balance (₹)", value=471347, step=5000)  
    epf_inflow = st.number_input("EPF Monthly Inflow (₹) [MODURAL]", value=17232, step=500)
    epf_rate = st.number_input("EPF Interest Rate (%)", value=8.25, step=0.25) / 100.0

    mf_sip_pre = st.number_input("Monthly MF SIP (₹)", value=70000, step=5000)
    mf_cagr = st.number_input("MF Planning CAGR (%)", value=13.0, step=0.5) / 100.0
    ltcg_limit = st.number_input("Annual LTCG Exemption (₹)", value=125000, step=5000)

# --- RECONCILED SIMULATION ENGINE ---
def run_reconciled_simulation(loan_p, r_loan, monthly_emi, annual_bonus, epf_b, epf_monthly, r_epf, sip_pre, r_mf):
    months = 120
    loan_r = r_loan / 12.0
    epf_r = r_epf / 12.0
    mf_r = r_mf / 12.0
    
    mf_lots = []
    epf = epf_b
    loan = loan_p
    
    log = []
    
    for m in range(1, months + 1):
        epf = epf * (1 + epf_r) + epf_monthly
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
        realized_gain_period = 0.0
        
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
            'Loan': loan,
            'EPF': epf,
            'MF': mf_val,
            'Net Worth': mf_val + epf - loan,
            'EPF_Harvest': epf_h,
            'MF_Harvest': mf_h,
            'Bonus': bonus_paid,
            'Realized_LTCG': realized_gain_period
        })
        
    return pd.DataFrame(log)

df_sim = run_reconciled_simulation(loan_start, loan_rate, emi, bonus, epf_start, epf_inflow, epf_rate, mf_sip_pre, mf_cagr)

# --- MOBILE DASHBOARD METRICS (2x2 Grid) ---
debt_free_row = df_sim[df_sim['Loan'] == 0]
debt_free_month = int(debt_free_row['Month'].min()) if not debt_free_row.empty else 42

col1, col2 = st.columns(2)
with col1:
    st.metric("Debt-Free Date", f"M {debt_free_month} (Mar '30)")
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

# --- MARCH EXECUTION SCHEDULE ---
st.subheader("🗓️ March Execution Windows")
event_rows = df_sim[df_sim['Month'].isin([6, 18, 30, 42])][['Month', 'Loan', 'Bonus', 'EPF_Harvest', 'MF_Harvest']]
event_rows.columns = ['M', 'Loan Left', 'Bonus', 'EPF Harvest', 'MF Sale']

# Display as clean mobile cards or scrollable table
st.dataframe(event_rows.style.format("{:,.0f}"), use_container_width=True)

st.caption("📱 Tip: Open this app in your mobile browser and select **'Add to Home Screen'** to use it like a native app.")
