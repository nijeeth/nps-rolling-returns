"""
NPS Rolling Returns — Streamlit Application
Main UI file for the NPS Rolling Returns analysis tool.
"""

from datetime import date
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import time

from config import (
    APP_TITLE,
    APP_ICON,
    ROLLING_PERIOD_OPTIONS,
    MIN_SIP_AMOUNT,
    MAX_SIP_AMOUNT,
    DEFAULT_SIP_AMOUNT,
    MIN_LUMPSUM_AMOUNT,
    MAX_LUMPSUM_AMOUNT,
    DEFAULT_LUMPSUM_AMOUNT,
    MIN_VALID_PERIODS,
    MAX_COMPARE_FUNDS,
    CREATOR_NAME,
    CREATOR_EMAIL,
    DATA_SOURCE_NAME,
    DATA_SOURCE_URL,
    MSF_WARNING_TEXT,
    SALARY_DATE_MESSAGE,
)
from data_api import (
    fetch_all_schemes,
    fetch_nav,
    build_dropdown_options,
    get_scheme_types_for_tier,
    get_pfms_for_tier_and_type,
    get_scheme_code,
)
from calculations import (
    calculate_all_possible_rolling_sip,
    calculate_all_possible_rolling_lumpsum,
)
from utils import (
    validate_inputs,
    plot_rolling_xirr,
    plot_rolling_xirr_compare,
    build_excel,
    build_excel_compare,
    fmt_inr,
    format_date,
)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="NPS Rolling Returns Calculator",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    [data-testid="stSidebar"] { display: none; }

    .stTabs [data-baseweb="tab-list"] {
        background: #1a1f36 !important;
        border: none !important;
        border-bottom: 3px solid #667eea !important;
        gap: 0 !important;
        justify-content: center !important;
        padding: 0 !important;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        color: #a5b4fc !important;
        font-size: 2.0em !important;
        font-weight: 700 !important;
        padding: 36px 200px !important;
        letter-spacing: 0.04em !important;
        transition: background 0.2s, color 0.2s !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(102,126,234,0.15) !important;
        color: #ffffff !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(102,126,234,0.2) !important;
        color: #ffffff !important;
        border-bottom: 3px solid #a78bfa !important;
    }
    .stTabs [data-baseweb="tab-highlight"] { display: none !important; }
    .stTabs [data-baseweb="tab-border"]    { display: none !important; }

    div[data-testid="stDownloadButton"] > button {
        background: linear-gradient(135deg, #16a34a 0%, #15803d 100%) !important;
        border-color: #15803d !important; color: white !important;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background: linear-gradient(135deg, #15803d 0%, #166534 100%) !important;
    }
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #16a34a 0%, #15803d 100%) !important;
        border-color: #15803d !important;
        color: white !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #15803d 0%, #166534 100%) !important;
    }

    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a { display: none !important; }
    .main .block-container { padding-top: 2rem !important; }
</style>
""", unsafe_allow_html=True)

# Floating go-to-top button
import streamlit.components.v1 as _components
_components.html("""
<style>
  #topbtn {
    position: fixed; bottom: 32px; right: 32px; z-index: 9999;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white; border: none; border-radius: 50%;
    width: 52px; height: 52px; font-size: 1.5em;
    cursor: pointer; box-shadow: 0 4px 16px rgba(102,126,234,0.5);
    display: flex; align-items: center; justify-content: center;
    transition: transform 0.2s, box-shadow 0.2s;
  }
  #topbtn:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(102,126,234,0.7); }
</style>
<button id="topbtn" title="Back to top" onclick="
  var el = window.parent.document.querySelector('section.main') ||
            window.parent.document.querySelector('.block-container') ||
            window.parent.document.documentElement;
  el.scrollTo ? el.scrollTo({top:0,behavior:'smooth'}) : el.scrollTop=0;
">↑</button>
""", height=0)

# ══════════════════════════════════════════════════════════════════════════════
# HERO BANNER
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 40px 2rem 36px 2rem; text-align: center; margin-bottom: 0;'>
    <a href='/' target='_self' style='text-decoration: none;'>
        <h1 style='color: #ffffff; font-size: 2.2em; font-weight: 800;
                   text-transform: uppercase; letter-spacing: 0.06em;
                   margin: 0 0 10px 0; line-height: 1.2; cursor: pointer;'>
            NPS Rolling Returns Calculator
        </h1>
    </a>
    <p style='color: rgba(255,255,255,0.82); font-size: 1.05em;
              font-weight: 400; margin: 0;'>
        Analyze historical rolling returns for National Pension System schemes
    </p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# NAVIGATION TABS
# ══════════════════════════════════════════════════════════════════════════════

tab1, tab2 = st.tabs(["🏠 Home", "ℹ️ How It Works"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: HOW IT WORKS
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    st.markdown("""
## 🧭 How to Use This Calculator

**Step 1 — Select a Scheme**
Use the three linked dropdowns:
- **Tier** — Tier I (long-term, tax-benefit account) or Tier II (flexible, no lock-in)
- **Scheme Type** — E (Equity), C (Corporate Bonds), G (Govt Securities), Central Govt, State Govt, etc.
- **Fund (PFM)** — The Pension Fund Manager, e.g. HDFC, SBI, ICICI

**Step 2 — Choose SIP or Lumpsum**
- **SIP** — Monthly investment, same as an SIP in a mutual fund
- **Lumpsum** — One-time investment held for the chosen period

**Step 3 — Select Rolling Period**
Choose 1, 2, 3, 5, 7, or 10 years.

**Step 4 — Choose Date Range**
Set From and To dates. The tool will calculate returns for every possible start date in this range.

**Step 5 — (Optional) Salary Contribution Date** *(Tier I + SIP only)*
Check this box and select a day (1–28) to see returns only for SIP windows starting on your salary credit date each month.

**Step 6 — (Optional) Compare Mode**
Add up to 3 funds to compare them on the same chart and Excel file.

**Step 7 — Click Calculate**

---

## 📊 Understanding the Results

**Statistics Table** — Min, Max, Mean, Median, 25th/75th percentile, Std Dev of XIRR across all rolling windows.

**Distribution Table** — What % of rolling periods fell into each return range (< 0%, 0–5%, 5–10%, etc.).

**Amount Analysis** — Worst, percentile, and best final corpus across all rolling windows.

**Rolling XIRR Chart** — Each point on the chart is one rolling window. X-axis = start date, Y-axis = XIRR %.

---

## ⚠️ Important Notes

- NPS NAV data is sourced from **npsnav.in** — for personal/educational/non-commercial use only.
- XIRR calculation uses Newton-Raphson iteration, identical to standard financial calculators.
- Past performance does **NOT** guarantee future returns.
- This is NOT financial advice. Consult a qualified advisor before investing.
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: MAIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

with tab1:

    # ── Session state defaults ───────────────────────────────────────────────
    for key, default in {
        'results':        None,
        'compare_funds':  [],     # list of {code, name, label, tier, scheme_type}
        'tier_locked':    False,  # True after first fund added to compare list
        'st_locked':      False,  # scheme_type locked too
    }.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Load scheme list ─────────────────────────────────────────────────────
    with st.spinner("Loading NPS scheme list..."):
        all_schemes, scheme_load_error = fetch_all_schemes()

    if not all_schemes:
        st.error("❌ Could not load the NPS scheme list.")
        st.markdown(
            f"**Reason:** `{scheme_load_error}`\n\n"
            "**What to try:**\n"
            "1. Refresh the page\n"
            "2. Check that [npsnav.in](https://npsnav.in) is accessible from your browser\n"
            "3. If the site is down, try again in a few minutes"
        )
        st.stop()

    dropdown_data = build_dropdown_options(all_schemes)

    # ══════════════════════════════════════════════════════════════════════════
    # SCHEME SELECTION — THREE CASCADING DROPDOWNS
    # ══════════════════════════════════════════════════════════════════════════

    st.markdown("#### Select NPS Scheme")

    col_t, col_st, col_pfm, _ = st.columns([1.2, 1.8, 2.2, 1.5])

    # ── Tier Dropdown ────────────────────────────────────────────────────────
    with col_t:
        st.markdown("**Tier**")
        tier_options = dropdown_data['tiers']
        tier_disabled = st.session_state.tier_locked

        if tier_disabled:
            # Show current value but greyed-out via label note
            locked_tier = st.session_state.compare_funds[0]['tier']
            tier_idx = tier_options.index(locked_tier) if locked_tier in tier_options else 0
            selected_tier = st.selectbox(
                "Tier",
                options=tier_options,
                index=tier_idx,
                disabled=True,
                label_visibility="collapsed",
                key="sel_tier",
                help="Tier is locked because a fund is already in the compare list. "
                     "Click 'Reset Comparison' to change it.",
            )
        else:
            selected_tier = st.selectbox(
                "Tier",
                options=tier_options,
                index=None,
                placeholder="Select Tier...",
                label_visibility="collapsed",
                key="sel_tier",
            )

    # ── Scheme Type Dropdown (depends on Tier) ───────────────────────────────
    with col_st:
        st.markdown("**Scheme Type**")
        scheme_types = get_scheme_types_for_tier(dropdown_data, selected_tier) if selected_tier else []
        st_disabled = st.session_state.st_locked

        if not scheme_types:
            st.selectbox("Scheme Type", options=[], placeholder="Select Tier first...",
                         label_visibility="collapsed", disabled=True, key="sel_scheme_type")
            selected_scheme_type = None
        else:
            if st_disabled:
                locked_st = st.session_state.compare_funds[0]['scheme_type']
                st_idx = scheme_types.index(locked_st) if locked_st in scheme_types else 0
                selected_scheme_type = st.selectbox(
                    "Scheme Type", options=scheme_types, index=st_idx,
                    disabled=True, label_visibility="collapsed",
                    key="sel_scheme_type",
                    help="Scheme Type is locked. Click 'Reset Comparison' to change.",
                )
            else:
                selected_scheme_type = st.selectbox(
                    "Scheme Type", options=scheme_types, index=None,
                    placeholder="Select Scheme Type...",
                    label_visibility="collapsed", key="sel_scheme_type",
                )

    # ── PFM Dropdown (depends on Tier + Scheme Type) ─────────────────────────
    with col_pfm:
        st.markdown("**Fund (PFM)**")
        pfms = (get_pfms_for_tier_and_type(dropdown_data, selected_tier, selected_scheme_type)
                if selected_tier and selected_scheme_type else [])

        if not pfms:
            st.selectbox("Fund (PFM)", options=[],
                         placeholder="Select Scheme Type first...",
                         label_visibility="collapsed", disabled=True, key="sel_pfm")
            selected_pfm = None
        else:
            selected_pfm = st.selectbox(
                "Fund (PFM)", options=pfms, index=None,
                placeholder="Select Fund...",
                label_visibility="collapsed", key="sel_pfm",
            )

    # Resolve scheme code + full name from selection
    selected_code, selected_full_name = (None, None)
    if selected_tier and selected_scheme_type and selected_pfm:
        selected_code, selected_full_name = get_scheme_code(
            dropdown_data, selected_tier, selected_scheme_type, selected_pfm
        )

    # MSF Warning
    if selected_full_name and 'MSF' in selected_full_name.upper():
        st.warning(f"⚠️ {MSF_WARNING_TEXT}")

    # ══════════════════════════════════════════════════════════════════════════
    # COMPARE MODE
    # ══════════════════════════════════════════════════════════════════════════

    st.markdown("#### Compare Mode *(optional — add up to 3 funds)*")

    compare_funds = st.session_state.compare_funds
    at_max = len(compare_funds) >= MAX_COMPARE_FUNDS

    # Add Fund button
    col_add, col_reset, _ = st.columns([1.2, 1.2, 4])
    with col_add:
        add_disabled = at_max or not selected_code
        add_clicked = st.button(
            "➕ Add Fund",
            disabled=add_disabled,
            help="Select a fund above and click here to add it to the comparison list."
                 if not add_disabled else
                 ("Maximum 3 funds reached." if at_max else "Select a fund above first."),
        )
    with col_reset:
        reset_clicked = st.button("🔄 Reset Comparison",
                                  disabled=len(compare_funds) == 0)

    if add_clicked and selected_code:
        # Check not already in list
        existing_codes = [f['code'] for f in compare_funds]
        if selected_code not in existing_codes:
            compare_funds.append({
                'code':        selected_code,
                'name':        selected_full_name,
                'label':       selected_pfm,
                'tier':        selected_tier,
                'scheme_type': selected_scheme_type,
            })
            # Lock tier + scheme_type after first fund added
            st.session_state.tier_locked = True
            st.session_state.st_locked   = True
            st.session_state.compare_funds = compare_funds
            st.rerun()
        else:
            st.info("This fund is already in the compare list.")

    if reset_clicked:
        st.session_state.compare_funds  = []
        st.session_state.tier_locked    = False
        st.session_state.st_locked      = False
        st.session_state.results        = None
        st.rerun()

    # Show current compare list
    if compare_funds:
        for idx, fund in enumerate(compare_funds):
            col_name, col_remove = st.columns([5, 1])
            with col_name:
                color = ['#4f83cc', '#e05c5c', '#4caf7d'][idx]
                st.markdown(
                    f"<div style='padding:6px 12px;background:#f8f9fa;"
                    f"border-left:4px solid {color};border-radius:4px;"
                    f"font-size:0.92em;margin-bottom:4px;'>"
                    f"<b>Fund {idx+1}:</b> {fund['name']}</div>",
                    unsafe_allow_html=True
                )
            with col_remove:
                if st.button("✖", key=f"remove_{idx}",
                             help=f"Remove Fund {idx+1}"):
                    compare_funds.pop(idx)
                    if len(compare_funds) == 0:
                        st.session_state.tier_locked = False
                        st.session_state.st_locked   = False
                    st.session_state.compare_funds = compare_funds
                    st.session_state.results = None
                    st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # MODE — SIP or LUMPSUM
    # ══════════════════════════════════════════════════════════════════════════

    st.markdown("#### Investment Mode")
    col_mode, _ = st.columns([2, 5])
    with col_mode:
        inv_mode = st.radio(
            "Investment Mode",
            options=["SIP (Monthly)", "Lumpsum (One-time)"],
            index=0,
            horizontal=True,
            label_visibility="collapsed",
        )
    is_sip = inv_mode == "SIP (Monthly)"

    # ══════════════════════════════════════════════════════════════════════════
    # ANALYSIS PERIOD + AMOUNT
    # ══════════════════════════════════════════════════════════════════════════

    st.markdown("#### Analysis Period & Amount")
    col_yr, col_from, col_to, col_amt, _ = st.columns([1, 1.3, 1.3, 1.4, 1])

    with col_yr:
        st.markdown("**Rolling Period**")
        years = st.selectbox(
            "Rolling Years", ROLLING_PERIOD_OPTIONS,
            index=0, label_visibility="collapsed", key="years",
        )

    with col_from:
        st.markdown("**From Date**")
        from_date = st.date_input(
            "From Date", value=None, format="DD/MM/YYYY",
            min_value=date(1990, 1, 1), max_value=date(2100, 12, 31),
            label_visibility="collapsed", key="from_date",
        )

    with col_to:
        st.markdown("**To Date**")
        to_date = st.date_input(
            "To Date", value=None, format="DD/MM/YYYY",
            min_value=date(1990, 1, 1), max_value=date(2100, 12, 31),
            label_visibility="collapsed", key="to_date",
        )

    with col_amt:
        if is_sip:
            st.markdown("**Monthly SIP Amount (₹)**")
            if "sip_amount" not in st.session_state:
                st.session_state["sip_amount"] = DEFAULT_SIP_AMOUNT
            else:
                _raw = st.session_state["sip_amount"]
                _rounded = int(round(_raw / 500) * 500)
                _rounded = max(MIN_SIP_AMOUNT, min(MAX_SIP_AMOUNT, _rounded))
                st.session_state["sip_amount"] = _rounded

            inv_amount = st.number_input(
                "Monthly SIP Amount (₹)",
                min_value=MIN_SIP_AMOUNT,
                max_value=MAX_SIP_AMOUNT,
                step=500,
                label_visibility="collapsed",
                key="sip_amount",
            )
        else:
            st.markdown("**Lumpsum Amount (₹)**")
            if "lumpsum_amount" not in st.session_state:
                st.session_state["lumpsum_amount"] = DEFAULT_LUMPSUM_AMOUNT

            inv_amount = st.number_input(
                "Lumpsum Amount (₹)",
                min_value=MIN_LUMPSUM_AMOUNT,
                max_value=MAX_LUMPSUM_AMOUNT,
                step=1000,
                label_visibility="collapsed",
                key="lumpsum_amount",
            )

    # ══════════════════════════════════════════════════════════════════════════
    # SALARY CONTRIBUTION DATE (Tier I + SIP only)
    # ══════════════════════════════════════════════════════════════════════════

    salary_day = None
    if is_sip and selected_tier == 'TIER I':
        st.markdown("#### Salary Contribution Date *(optional)*")
        col_sal_chk, col_sal_day, _ = st.columns([1.5, 1, 5])
        with col_sal_chk:
            use_salary_date = st.checkbox(
                "Use Salary Contribution Date",
                value=False,
                key="use_salary_date",
            )
        with col_sal_day:
            if use_salary_date:
                salary_day = st.selectbox(
                    "Day", options=list(range(1, 29)),
                    index=24,  # default day 25
                    label_visibility="collapsed",
                    key="salary_day",
                )
        if use_salary_date:
            st.info(SALARY_DATE_MESSAGE)

    # ══════════════════════════════════════════════════════════════════════════
    # CALCULATE BUTTON
    # ══════════════════════════════════════════════════════════════════════════

    st.divider()
    col_btn, _ = st.columns([1, 4])
    with col_btn:
        # Determine what we're calculating — single fund or compare list
        is_compare_mode = len(compare_funds) > 1
        btn_label = (
            f"▶ Compare {len(compare_funds)} Funds" if is_compare_mode
            else "▶ Calculate Rolling Returns"
        )
        calculate_btn = st.button(btn_label, type="primary", use_container_width=True)

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # CALCULATION LOGIC
    # ══════════════════════════════════════════════════════════════════════════

    if calculate_btn:
        # Determine which funds to run
        if is_compare_mode:
            funds_to_run = compare_funds
        elif selected_code:
            funds_to_run = [{
                'code':  selected_code,
                'name':  selected_full_name,
                'label': selected_pfm,
            }]
        else:
            funds_to_run = []

        # Basic validation (before any API call)
        basic_errors = validate_inputs(
            scheme_selected=bool(funds_to_run),
            from_date=from_date,
            to_date=to_date,
            years=years,
        )
        if basic_errors:
            for e in basic_errors:
                st.error(e)
        else:
            all_fund_results = []
            calc_ok = True

            for fund in funds_to_run:
                with st.spinner(f"Fetching NAV data for {fund['name']}..."):
                    nav_df = fetch_nav(fund['code'])

                if nav_df.empty:
                    st.error(f"Could not fetch NAV data for {fund['name']}. "
                             "Check your connection and try again.")
                    calc_ok = False
                    break

                nav_errors = validate_inputs(
                    scheme_selected=True,
                    from_date=from_date,
                    to_date=to_date,
                    years=years,
                    nav_df=nav_df,
                )
                if nav_errors:
                    for e in nav_errors:
                        st.error(f"[{fund['label']}] {e}")
                    calc_ok = False
                    break

                start_time = time.time()
                with st.spinner(f"Calculating rolling returns for {fund['label']}..."):
                    if is_sip:
                        result_df = calculate_all_possible_rolling_sip(
                            nav_df_json=nav_df.to_json(date_format='iso'),
                            years=years,
                            range_start=pd.Timestamp(from_date),
                            range_end=pd.Timestamp(to_date),
                            sip_amount=inv_amount,
                            salary_day=salary_day,
                        )
                    else:
                        result_df = calculate_all_possible_rolling_lumpsum(
                            nav_df_json=nav_df.to_json(date_format='iso'),
                            years=years,
                            range_start=pd.Timestamp(from_date),
                            range_end=pd.Timestamp(to_date),
                            lumpsum_amount=inv_amount,
                        )
                elapsed = time.time() - start_time

                if result_df.empty or len(result_df) < MIN_VALID_PERIODS:
                    st.error(
                        f"[{fund['label']}] Not enough data to generate reliable results. "
                        "Please extend your date range."
                    )
                    calc_ok = False
                    break

                # For compare mode: auto-align date ranges to overlap
                all_fund_results.append({
                    'code':    fund['code'],
                    'name':    fund['name'],
                    'label':   fund['label'],
                    'df':      result_df,
                    'elapsed': elapsed,
                    'nav_df':  nav_df,
                })

            if calc_ok and all_fund_results:
                # Date alignment warning for compare mode
                if len(all_fund_results) > 1:
                    min_starts = [r['df']['Start Date'].min() for r in all_fund_results]
                    latest_start = max(min_starts)
                    if len(set(min_starts)) > 1:
                        st.warning(
                            f"⚠️ Funds have different history lengths. "
                            f"Comparison is aligned from **{latest_start}** onwards "
                            f"(the earliest date all selected funds have data)."
                        )
                        # Clip all DFs to the common start date
                        for r in all_fund_results:
                            r['df'] = r['df'][
                                r['df']['Start Date'] >= latest_start
                            ].reset_index(drop=True)

                st.session_state.results = {
                    'fund_results':  all_fund_results,
                    'years':         years,
                    'from_date':     from_date,
                    'to_date':       to_date,
                    'is_sip':        is_sip,
                    'inv_amount':    inv_amount,
                    'is_compare':    is_compare_mode,
                    'salary_day':    salary_day,
                }

    # ══════════════════════════════════════════════════════════════════════════
    # RESULTS RENDERING
    # ══════════════════════════════════════════════════════════════════════════

    if st.session_state.get("results") is not None:
        r             = st.session_state.results
        fund_results  = r['fund_results']
        years_r       = r['years']
        from_date_r   = r['from_date']
        to_date_r     = r['to_date']
        is_sip_r      = r['is_sip']
        inv_amount_r  = r['inv_amount']
        is_compare_r  = r['is_compare']
        salary_day_r  = r['salary_day']
        mode_label    = "SIP" if is_sip_r else "Lumpsum"

        total_elapsed = sum(f['elapsed'] for f in fund_results)
        total_periods = sum(len(f['df']) for f in fund_results)

        st.markdown(
            f"<div style='margin-bottom:10px;'>"
            f"<span style='color:#22c55e;font-size:0.9em;font-weight:600;'>✓ Done in {total_elapsed:.1f}s "
            f"— {total_periods:,} rolling periods calculated&nbsp;&nbsp;"
            f"<span style='color:#ef5350;font-weight:600;'>⚠ Past performance does not "
            f"guarantee future returns.</span></span></div>",
            unsafe_allow_html=True
        )

        # ── Results header banner ──────────────────────────────────────────
        fund_names_display = " vs ".join(f['label'] for f in fund_results)
        st.markdown(
            f"<div style='background:linear-gradient(135deg,#1a237e 0%,#4a148c 100%);"
            f"padding:14px 20px;border-radius:8px;margin:10px 0 16px 0;text-align:center;'>"
            f"<div style='color:#ffffff;font-size:1.05em;font-weight:600;'>📈 Results : "
            f"{years_r}-Year {mode_label} Rolling Return &nbsp;|&nbsp; "
            f"{from_date_r.strftime('%d/%m/%Y')} – {to_date_r.strftime('%d/%m/%Y')}</div>"
            f"<div style='color:#ffffff;font-size:0.95em;font-weight:500;margin-top:5px;'>"
            f"{fund_names_display}</div></div>",
            unsafe_allow_html=True
        )

        # ── Per-fund stats ─────────────────────────────────────────────────
        for fund in fund_results:
            df = fund['df']
            x  = df['XIRR %']
            fv = df['Final Value']

            if len(fund_results) > 1:
                color = ['#4f83cc', '#e05c5c', '#4caf7d'][fund_results.index(fund)]
                st.markdown(
                    f"<div style='border-left:5px solid {color};"
                    f"padding:6px 14px;margin:12px 0 6px 0;"
                    f"background:#f8f9fa;border-radius:4px;"
                    f"font-weight:700;font-size:1em;'>{fund['name']}</div>",
                    unsafe_allow_html=True
                )

            col1, col2 = st.columns(2)

            # Stats table
            with col1:
                stats_rows = [
                    ('Min',       round(x.min(),    2)),
                    ('Max',       round(x.max(),    2)),
                    ('Mean',      round(x.mean(),   2)),
                    ('Median',    round(x.median(), 2)),
                    ('25th %ile', round(float(x.quantile(0.25)), 2)),
                    ('75th %ile', round(float(x.quantile(0.75)), 2)),
                    ('Std Dev',   round(x.std(),    2)),
                ]
                rows1 = ''.join(
                    f"<tr>"
                    f"<td style='padding:7px 12px;color:#1e293b;"
                    f"border-right:1px solid #cbd5e1;border-bottom:1px solid #e2e8f0;"
                    f"background:{'#f8fafc' if j%2==0 else '#f1f5f9'};'>{m}</td>"
                    f"<td style='padding:7px 12px;color:#1e293b;text-align:right;"
                    f"border-bottom:1px solid #e2e8f0;"
                    f"background:{'#f8fafc' if j%2==0 else '#f1f5f9'};"
                    f"font-weight:600;'>{v:.2f}%</td></tr>"
                    for j, (m, v) in enumerate(stats_rows)
                )
                st.markdown(
                    "<div style='border:1px solid #cbd5e1;border-radius:6px;"
                    "overflow:hidden;margin-bottom:8px;'>"
                    "<div style='background:linear-gradient(135deg,#667eea,#764ba2);"
                    "padding:8px 12px;text-align:center;'>"
                    "<b style='color:white;font-size:0.95em;'>Return Statistics (XIRR %)</b></div>"
                    "<table style='width:100%;border-collapse:collapse;'>"
                    "<thead><tr>"
                    "<th style='padding:7px 12px;background:#e8eaf6;color:#3730a3;"
                    "font-weight:700;font-size:0.82em;text-align:left;"
                    "border-right:1px solid #c7d2fe;border-bottom:2px solid #c7d2fe;'>Metric</th>"
                    "<th style='padding:7px 12px;background:#e8eaf6;color:#3730a3;"
                    "font-weight:700;font-size:0.82em;text-align:right;"
                    "border-bottom:2px solid #c7d2fe;'>Value</th>"
                    f"</tr></thead><tbody>{rows1}</tbody></table></div>",
                    unsafe_allow_html=True
                )

            # Distribution table
            with col2:
                bins = [
                    round((x < 0).mean()                        * 100, 2),
                    round(((x >= 0)  & (x < 5)).mean()          * 100, 2),
                    round(((x >= 5)  & (x < 10)).mean()         * 100, 2),
                    round(((x >= 10) & (x < 15)).mean()         * 100, 2),
                    round(((x >= 15) & (x < 20)).mean()         * 100, 2),
                    round((x >= 20).mean()                       * 100, 2),
                ]
                ranges = ['< 0%', '0–5%', '5–10%', '10–15%', '15–20%', '> 20%']
                rows2 = ''.join(
                    f"<tr>"
                    f"<td style='padding:7px 12px;color:#1e293b;"
                    f"border-right:1px solid #cbd5e1;border-bottom:1px solid #e2e8f0;"
                    f"background:{'#f8fafc' if j%2==0 else '#f1f5f9'};'>{rng}</td>"
                    f"<td style='padding:7px 12px;color:#1e293b;text-align:right;"
                    f"border-bottom:1px solid #e2e8f0;"
                    f"background:{'#f8fafc' if j%2==0 else '#f1f5f9'};"
                    f"font-weight:600;'>{p:.2f}%</td></tr>"
                    for j, (rng, p) in enumerate(zip(ranges, bins))
                )
                st.markdown(
                    "<div style='border:1px solid #cbd5e1;border-radius:6px;"
                    "overflow:hidden;margin-bottom:8px;'>"
                    "<div style='background:linear-gradient(135deg,#667eea,#764ba2);"
                    "padding:8px 12px;text-align:center;'>"
                    "<b style='color:white;font-size:0.95em;'>Return Distribution</b></div>"
                    "<table style='width:100%;border-collapse:collapse;'>"
                    "<thead><tr>"
                    "<th style='padding:7px 12px;background:#e8eaf6;color:#3730a3;"
                    "font-weight:700;font-size:0.82em;text-align:left;"
                    "border-right:1px solid #c7d2fe;border-bottom:2px solid #c7d2fe;'>Range</th>"
                    "<th style='padding:7px 12px;background:#e8eaf6;color:#3730a3;"
                    "font-weight:700;font-size:0.82em;text-align:right;"
                    "border-bottom:2px solid #c7d2fe;'>% of Times</th>"
                    f"</tr></thead><tbody>{rows2}</tbody></table></div>",
                    unsafe_allow_html=True
                )

            # Amount analysis table
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        padding: 10px; border-radius: 5px; text-align: center;
                        margin-top: 10px; margin-bottom: 0px;'>
                <b style='color: white; font-size: 16px;'>
                    💰 {years_r}-Year {mode_label} Amount Analysis —
                    {'₹'+f'{inv_amount_r:,}'+'/month' if is_sip_r else '₹'+f'{inv_amount_r:,}'+' lumpsum'}
                </b>
            </div>
            """, unsafe_allow_html=True)

            if is_sip_r:
                invested = inv_amount_r * years_r * 12
            else:
                invested = inv_amount_r

            labels = ['Invested', 'Worst', '10th %ile', '25th %ile',
                      'Mean', 'Median', '75th %ile', '90th %ile', 'Best']
            values = [
                fmt_inr(invested),
                fmt_inr(float(fv.min())),
                fmt_inr(float(fv.quantile(0.10))),
                fmt_inr(float(fv.quantile(0.25))),
                fmt_inr(float(fv.mean())),
                fmt_inr(float(fv.median())),
                fmt_inr(float(fv.quantile(0.75))),
                fmt_inr(float(fv.quantile(0.90))),
                fmt_inr(float(fv.max())),
            ]
            header_cells = "".join(
                f"<th style='padding:8px 14px;background:#e8eaf6;color:#3730a3;"
                f"font-size:0.82em;font-weight:600;text-align:center;"
                f"border-right:1px solid #c7d2fe;white-space:nowrap;'>{lbl}</th>"
                for lbl in labels
            )
            value_cells = "".join(
                f"<td style='padding:10px 14px;"
                f"color:{'#dc2626' if idx==1 else ('#16a34a' if idx==8 else '#1e293b')};"
                f"font-size:0.9em;font-weight:{'700' if idx in (1,8) else '400'};"
                f"text-align:center;border-right:1px solid #cbd5e1;white-space:nowrap;"
                f"background:{'#fef2f2' if idx==1 else ('#f0fdf4' if idx==8 else ('#f8fafc' if idx%2==0 else '#f1f5f9'))};'>{val}</td>"
                for idx, (lbl, val) in enumerate(zip(labels, values))
            )
            st.markdown(
                f"<div style='overflow-x:auto;margin-bottom:20px;'>"
                f"<table style='width:100%;border-collapse:collapse;"
                f"border:1px solid #cbd5e1;overflow:hidden;'>"
                f"<thead><tr>{header_cells}</tr></thead>"
                f"<tbody><tr>{value_cells}</tr></tbody>"
                f"</table></div>",
                unsafe_allow_html=True
            )

        # ── Chart ──────────────────────────────────────────────────────────
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 10px; border-radius: 5px; text-align: center;
                    margin-top: 20px; margin-bottom: 10px;'>
            <b style='color: white; font-size: 16px;'>📊 Rolling XIRR Chart</b>
        </div>
        """, unsafe_allow_html=True)

        if len(fund_results) == 1:
            fig = plot_rolling_xirr(fund_results[0]['df'],
                                    fund_results[0]['name'], years_r)
        else:
            fig = plot_rolling_xirr_compare(fund_results, years_r)

        st.pyplot(fig)
        plt.close(fig)

        st.markdown("<div style='margin-top: 56px;'></div>", unsafe_allow_html=True)

        # ── Excel Download ─────────────────────────────────────────────────
        if len(fund_results) == 1:
            fund = fund_results[0]
            df_export = fund['df'].copy()
            for col in ['Start Date', 'End Date', 'Redemption Date']:
                if col in df_export.columns:
                    df_export[col] = pd.to_datetime(df_export[col]).dt.strftime('%d/%m/%Y')

            if is_sip_r:
                months_xl   = years_r * 12
                invested_xl = inv_amount_r * months_xl
                df_export['Invested Amount (₹)'] = invested_xl
                df_export['Final Value (₹)']      = fund['df']['Final Value'].apply(lambda v: round(v, 0))

            excel_buf = build_excel(
                df_export, fund['name'], years_r,
                from_date_r, to_date_r, is_sip_r, inv_amount_r
            )
            safe_name = fund['name'].replace(' ', '_').replace('/', '-')[:50]
            st.download_button(
                label="⬇  Download complete rolling period data as Excel",
                data=excel_buf,
                file_name=f"nps_rolling_{safe_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary",
            )
        else:
            excel_buf = build_excel_compare(
                fund_results, years_r, from_date_r, to_date_r,
                is_sip_r, inv_amount_r
            )
            st.download_button(
                label="⬇  Download comparison Excel (Summary + per-fund sheets)",
                data=excel_buf,
                file_name=f"nps_compare_{years_r}yr.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary",
            )

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER DISCLAIMERS
# ══════════════════════════════════════════════════════════════════════════════

st.divider()
st.markdown(f"""
<div style='background:#fffdf0; border:1px solid #e8d870; border-radius:8px;
            padding:16px 20px; font-size:0.83em; line-height:1.8; color:#1a1a1a;'>

  <span style='color:#1e40af; font-weight:600;'>💡 Note:</span>
  Switch to the "How It Works" tab above for detailed instructions and examples.
  <br><br>

  <span style='color:#1e40af; font-weight:600;'>Special Thanks:</span>
  <a href="{DATA_SOURCE_URL}" target="_blank"
     style="color:#1a56db; text-decoration:none; font-weight:600;">{DATA_SOURCE_NAME}</a>
  for providing NPS NAV data through their freely accessible API.
  This tool is for <b>personal/educational/non-commercial use only</b> in accordance
  with their terms of service.
  <br><br>

  <span style='color:#b91c1c; font-weight:700;'>⚠ Disclaimer:</span>
  This dashboard is a personal project created with AI assistance.
  It may contain inaccuracies or errors. All outputs should be interpreted with caution
  and are not guaranteed to be accurate or suitable for investment decision-making.
  For suggestions/feedback:
  <a href="mailto:{CREATOR_EMAIL}"
     style="color:#1a56db; text-decoration:none;">{CREATOR_EMAIL}</a>
  <br><br>

  <span style='color:#b91c1c; font-weight:700;'>⚠ Disclaimer:</span>
  This tool is built solely for educational/exploratory purposes.
  Results may contain unintended errors. This is <b>NOT financial advice.</b>
  NPS investments are subject to market risks, and past performance does not guarantee
  future returns. The creator is <b>NOT a SEBI-registered investment advisor.</b>
  Please consult a qualified financial advisor before investing.

</div>
""", unsafe_allow_html=True)
