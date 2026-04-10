# ============================================================
#  INDIA RED FLAG DASHBOARD  —  app.py
#  Enhanced UI version – modern, clean, professional
#
#  SECTION 1 — DATA LAYER       edit for new data sources
#  SECTION 2 — ANALYSIS LAYER   edit for new checks / scoring
#  SECTION 3 — UI LAYER         modern dashboard, charts, cards
# ============================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import io
import time
import requests
from datetime import datetime

# ============================================================
#  SECTION 1 — DATA LAYER
# ============================================================

# Full NSE-listed company list — loaded once from NSE's public endpoint
@st.cache_data(ttl=86400, show_spinner=False)   # refresh once a day
def load_nse_company_list():
    """
    Fetches the full list of NSE-listed companies directly from NSE's website.
    Returns a dict of {Company Name: NSE_TICKER.NS}
    Falls back to a small hardcoded list if NSE is unreachable.
    """
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))
        # NSE CSV columns: SYMBOL, NAME OF COMPANY, ...
        symbol_col = "SYMBOL"
        name_col   = " NAME OF COMPANY" if " NAME OF COMPANY" in df.columns else "NAME OF COMPANY"
        company_dict = {}
        for _, row in df.iterrows():
            sym  = str(row[symbol_col]).strip()
            name = str(row[name_col]).strip()
            if sym and name:
                company_dict[f"{name}  ({sym})"] = f"{sym}.NS"
        return company_dict
    except Exception:
        # Fallback hardcoded list if NSE endpoint fails
        return {
            "Reliance Industries (RELIANCE)": "RELIANCE.NS",
            "TCS (TCS)": "TCS.NS",
            "Infosys (INFY)": "INFY.NS",
            "HDFC Bank (HDFCBANK)": "HDFCBANK.NS",
            "ICICI Bank (ICICIBANK)": "ICICIBANK.NS",
            "Wipro (WIPRO)": "WIPRO.NS",
            "Adani Enterprises (ADANIENT)": "ADANIENT.NS",
            "Yes Bank (YESBANK)": "YESBANK.NS",
            "Zomato (ZOMATO)": "ZOMATO.NS",
            "Paytm (PAYTM)": "PAYTM.NS",
            "Bajaj Finance (BAJFINANCE)": "BAJFINANCE.NS",
            "ITC (ITC)": "ITC.NS",
            "L&T (LT)": "LT.NS",
            "Sun Pharma (SUNPHARMA)": "SUNPHARMA.NS",
            "Tata Motors (TATAMOTORS)": "TATAMOTORS.NS",
            "ONGC (ONGC)": "ONGC.NS",
            "Coal India (COALINDIA)": "COALINDIA.NS",
            "SBIN (SBIN)": "SBIN.NS",
            "Axis Bank (AXISBANK)": "AXISBANK.NS",
            "Maruti Suzuki (MARUTI)": "MARUTI.NS",
        }


def resolve_ticker(raw: str) -> str:
    """
    Tries to resolve a user-typed ticker to a valid Yahoo Finance symbol.
    Tries NSE (.NS) first, then BSE (.BO).
    Returns the working symbol or None.
    """
    raw = raw.strip().upper().replace(".NS", "").replace(".BO", "")
    for suffix in [".NS", ".BO"]:
        symbol = raw + suffix
        try:
            info = yf.Ticker(symbol).info
            if info.get("longName") or info.get("shortName"):
                return symbol
        except Exception:
            continue
    return None


def _safe_row(df, names):
    if df is None or df.empty:
        return None
    for name in names:
        if name in df.index:
            row = pd.to_numeric(df.loc[name], errors="coerce").dropna()
            if not row.empty:
                return row.sort_index()
    return None

def _to_cr(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return round(float(val) / 1e7, 2)

def _series_cr(series):
    if series is None:
        return None
    return series.apply(lambda x: round(x / 1e7, 2) if pd.notna(x) else None)

@st.cache_data(ttl=3600, show_spinner=False)
def get_company_data(ticker: str):
    """
    Fetches and returns clean financial data for one company.
    ticker: Yahoo Finance format e.g. RELIANCE.NS
    Returns dict or None if fetch fails.
    """
    try:
        t    = yf.Ticker(ticker)
        info = t.info or {}
        if not info.get("longName") and not info.get("shortName"):
            return None

        raw_pnl = t.financials
        raw_bs  = t.balance_sheet
        raw_cf  = t.cashflow

        pnl = {
            "revenue":          _series_cr(_safe_row(raw_pnl, ["Total Revenue", "Revenue"])),
            "ebitda":           _series_cr(_safe_row(raw_pnl, ["EBITDA", "Normalized EBITDA"])),
            "operating_profit": _series_cr(_safe_row(raw_pnl, ["Operating Income", "EBIT"])),
            "net_profit":       _series_cr(_safe_row(raw_pnl, ["Net Income", "Net Income Common Stockholders"])),
            "interest_exp":     _series_cr(_safe_row(raw_pnl, ["Interest Expense"])),
            "other_income":     _series_cr(_safe_row(raw_pnl, ["Other Income Expense", "Non Operating Income"])),
            "depreciation":     _series_cr(_safe_row(raw_pnl, ["Reconciled Depreciation", "Depreciation And Amortization"])),
        }
        bs = {
            "total_debt":     _series_cr(_safe_row(raw_bs, ["Total Debt", "Long Term Debt"])),
            "equity":         _series_cr(_safe_row(raw_bs, ["Stockholders Equity", "Common Stock Equity"])),
            "receivables":    _series_cr(_safe_row(raw_bs, ["Accounts Receivable", "Net Receivables"])),
            "inventory":      _series_cr(_safe_row(raw_bs, ["Inventory"])),
            "total_assets":   _series_cr(_safe_row(raw_bs, ["Total Assets"])),
            "current_assets": _series_cr(_safe_row(raw_bs, ["Current Assets"])),
            "current_liab":   _series_cr(_safe_row(raw_bs, ["Current Liabilities"])),
            "cash":           _series_cr(_safe_row(raw_bs, ["Cash And Cash Equivalents",
                                         "Cash Cash Equivalents And Short Term Investments"])),
        }
        cf = {
            "cfo":   _series_cr(_safe_row(raw_cf, ["Operating Cash Flow", "Cash From Operations"])),
            "capex": _series_cr(_safe_row(raw_cf, ["Capital Expenditure"])),
            "fcf":   _series_cr(_safe_row(raw_cf, ["Free Cash Flow"])),
        }
        return {
            "ticker":               ticker,
            "name":                 info.get("longName") or info.get("shortName") or ticker,
            "sector":               info.get("sector", "Unknown"),
            "industry":             info.get("industry", "Unknown"),
            "mcap_cr":              _to_cr(info.get("marketCap")),
            "de_ratio":             round(info.get("debtToEquity", 0) / 100, 2) if info.get("debtToEquity") else None,
            "promoter_holding_pct": round(info.get("heldPercentInsiders", 0) * 100, 1),
            "pnl": pnl, "bs": bs, "cf": cf,
        }
    except Exception:
        return None


# ============================================================
#  SECTION 2 — ANALYSIS LAYER
#  Add new checks here. Register them in run_all_checks().
#  FLAG FORMAT: (severity, short_title, explanation)
#  SEVERITY: "HIGH"=2pts | "MEDIUM"=1pt | "LOW"=0pts
# ============================================================

def _cagr(series, years=3):
    if series is None: return None
    s = series.dropna()
    if len(s) < 2: return None
    y = min(years, len(s) - 1)
    a, b = float(s.iloc[0]), float(s.iloc[-1])
    if a <= 0 or b <= 0 or y == 0: return None
    return (b / a) ** (1 / y) - 1

def _last(series):
    if series is None or series.empty: return None
    s = series.dropna()
    return float(s.iloc[-1]) if not s.empty else None

def _avg(series, n=3):
    if series is None or series.empty: return None
    s = series.dropna().iloc[-n:]
    return float(s.mean()) if not s.empty else None

def check_cfo_vs_profit(data):
    flags = []
    cfo, pat = data["cf"].get("cfo"), data["pnl"].get("net_profit")
    if cfo is None or pat is None: return flags
    avg_cfo, avg_pat = _avg(cfo, 3), _avg(pat, 3)
    if avg_cfo is None or avg_pat is None or avg_pat == 0: return flags
    r = avg_cfo / avg_pat
    if r < 0.7:
        flags.append(("HIGH", "Low CFO / Net Profit ratio",
            f"3-year avg operating cash flow is only {r:.0%} of reported profit. "
            "Healthy companies generate ≥1x CFO vs profit. "
            "Strong signal of accrual-based earnings inflation — profit not converting to real cash."))
    elif r < 0.85:
        flags.append(("MEDIUM", f"Below-average CFO / Net Profit ({r:.0%})",
            f"CFO is {r:.0%} of net profit (3yr avg). Below healthy threshold of 85%+. "
            "Watch this trend — if it keeps falling, it becomes a high-severity flag."))
    return flags

def check_receivables_vs_revenue(data):
    flags = []
    rev, rec = data["pnl"].get("revenue"), data["bs"].get("receivables")
    if rev is None or rec is None: return flags
    rg, recg = _cagr(rev, 3), _cagr(rec, 3)
    if rg is None or recg is None: return flags
    gap = recg - rg
    if gap > 0.15:
        flags.append(("HIGH", "Receivables growing much faster than revenue",
            f"Revenue 3Y CAGR: {rg:.0%} | Receivables 3Y CAGR: {recg:.0%} — gap of {gap:.0%}. "
            "Classic channel stuffing or aggressive revenue recognition. "
            "Check debtor days trend and whether customers are actually paying."))
    elif gap > 0.10:
        flags.append(("MEDIUM", "Receivables growing faster than revenue",
            f"Revenue CAGR: {rg:.0%} | Receivables CAGR: {recg:.0%} — gap of {gap:.0%}. "
            "Worth monitoring. Receivables should not consistently outgrow sales."))
    return flags

def check_debt_vs_cfo(data):
    flags = []
    debt, cfo = data["bs"].get("total_debt"), data["cf"].get("cfo")
    if debt is None or cfo is None: return flags
    d, c = debt.dropna(), cfo.dropna()
    if len(d) < 3 or len(c) < 3: return flags
    if float(d.iloc[-1]) > float(d.iloc[0]) * 1.35 and float(c.iloc[-1]) < float(c.iloc[0]) * 0.75:
        flags.append(("HIGH", "Debt up 35%+ while operating cash flow dropped 25%+",
            "Borrowing significantly more while generating less operating cash. "
            "Classic pre-distress signal. "
            "Check if debt is funding operations rather than growth capex — unsustainable."))
    return flags

def check_inventory_buildup(data):
    flags = []
    inv, rev = data["bs"].get("inventory"), data["pnl"].get("revenue")
    if inv is None or rev is None: return flags
    ig, rg = _cagr(inv, 3), _cagr(rev, 3)
    if ig is None or rg is None: return flags
    if ig - rg > 0.15:
        flags.append(("MEDIUM", f"Inventory growing faster than revenue (gap: {ig-rg:.0%})",
            f"Inventory 3Y CAGR: {ig:.0%} vs Revenue 3Y CAGR: {rg:.0%}. "
            "May signal demand slowdown, obsolete stock, or inflated assets."))
    return flags

def check_interest_coverage(data):
    flags = []
    ebit   = data["pnl"].get("operating_profit")
    intexp = data["pnl"].get("interest_exp")
    if ebit is None or intexp is None: return flags
    e = _last(ebit)
    i = abs(_last(intexp)) if _last(intexp) else None
    if e is None or i is None or i == 0: return flags
    icr = e / i
    if icr < 1.5:
        flags.append(("HIGH", f"Dangerously low interest coverage ({icr:.1f}x)",
            f"Operating profit covers interest only {icr:.1f}x. "
            "Below 1.5x is danger zone — one bad quarter could trigger default."))
    elif icr < 2.5:
        flags.append(("MEDIUM", f"Weak interest coverage ({icr:.1f}x)",
            f"Coverage of {icr:.1f}x is below the comfortable 3x+ threshold. "
            "Monitor closely in a rising rate environment."))
    return flags

def check_negative_cfo_vs_profit(data):
    flags = []
    cfo, pat = data["cf"].get("cfo"), data["pnl"].get("net_profit")
    if cfo is None or pat is None: return flags
    neg_cfo = int((cfo.dropna() < 0).sum())
    pos_pat = int((pat.dropna() > 0).sum())
    if neg_cfo >= 2 and pos_pat >= 3:
        flags.append(("HIGH", f"Negative operating cash flow in {neg_cfo} years despite profits",
            f"Reported profits in {pos_pat} years but negative CFO in {neg_cfo} years. "
            "One of the strongest forensic accounting red flags. "
            "Company is printing paper profits but not generating real cash."))
    return flags

def check_revenue_decline(data):
    flags = []
    rev = data["pnl"].get("revenue")
    if rev is None: return flags
    rg = _cagr(rev, 3)
    if rg is not None and rg < -0.05:
        flags.append(("MEDIUM", f"Revenue declining (3Y CAGR: {rg:.1%})",
            f"Revenue falling at {abs(rg):.1%} per year. "
            "Determine if cyclical or structural deterioration."))
    return flags

def check_sustained_losses(data):
    flags = []
    pat = data["pnl"].get("net_profit")
    if pat is None: return flags
    s = pat.dropna()
    loss_years = int((s < 0).sum())
    if loss_years >= 3:
        flags.append(("HIGH", f"Loss-making in {loss_years} of {len(s)} years",
            "Sustained losses — check if unit economics are at least improving YoY."))
    elif loss_years >= 1:
        flags.append(("MEDIUM", f"Net loss in {loss_years} recent year(s)",
            "Check if one-off or structural. Look at EBITDA to separate "
            "operating health from accounting charges."))
    return flags

def check_high_leverage(data):
    flags = []
    de     = data.get("de_ratio")
    sector = data.get("sector", "")
    if "financial" in sector.lower() or "bank" in sector.lower(): return flags
    if de is None: return flags
    if de > 2.0:
        flags.append(("HIGH", f"Very high Debt/Equity ({de:.1f}x)",
            f"D/E of {de:.1f}x is well above safe levels (<1x for non-financial companies). "
            "High leverage amplifies losses and raises solvency risk."))
    elif de > 1.0:
        flags.append(("MEDIUM", f"Elevated Debt/Equity ({de:.1f}x)",
            f"D/E of {de:.1f}x above 1x. Combine with interest coverage and CFO trend for full picture."))
    return flags

def check_low_promoter_holding(data):
    flags = []
    ph     = data.get("promoter_holding_pct", 0)
    if ph == 0: return flags
    if ph < 25:
        flags.append(("LOW", f"Low promoter / insider holding ({ph:.1f}%)",
            f"Promoters hold only {ph:.1f}%. Watch for any further quarterly decline."))
    return flags

def run_all_checks(data):
    all_flags = []
    for fn in [
        check_cfo_vs_profit, check_receivables_vs_revenue, check_debt_vs_cfo,
        check_inventory_buildup, check_interest_coverage, check_negative_cfo_vs_profit,
        check_revenue_decline, check_sustained_losses, check_high_leverage,
        check_low_promoter_holding,
    ]:
        try: all_flags.extend(fn(data))
        except Exception: pass
    score = sum({"HIGH":2,"MEDIUM":1,"LOW":0}.get(s,0) for s,_,_ in all_flags)
    return all_flags, min(score, 10)


# ============================================================
#  SECTION 3 — UI LAYER (ENHANCED MODERN DASHBOARD)
# ============================================================

st.set_page_config(
    page_title="India Red Flag Dashboard",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "About": "Forensic analysis tool for NSE-listed companies. Not investment advice."
    }
)

# --- Custom CSS for modern look ---
st.markdown("""
<style>
    /* Main background and font */
    .stApp {
        background: linear-gradient(135deg, #f5f7fc 0%, #eef2f7 100%);
    }
    /* Card style */
    .card {
        background: white;
        border-radius: 20px;
        padding: 1.2rem;
        box-shadow: 0 8px 20px rgba(0,0,0,0.03), 0 2px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        margin-bottom: 1rem;
        border: 1px solid rgba(0,0,0,0.05);
    }
    .card:hover {
        transform: translateY(-2px);
        box-shadow: 0 16px 28px rgba(0,0,0,0.08);
    }
    /* Flag styles - refined */
    .flag-HIGH {
        background: #fff2f0;
        border-left: 5px solid #d32f2f;
        padding: 12px 18px;
        border-radius: 12px;
        margin: 12px 0;
        font-size: 0.95rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .flag-MEDIUM {
        background: #fff9e6;
        border-left: 5px solid #f57c00;
        padding: 12px 18px;
        border-radius: 12px;
        margin: 12px 0;
    }
    .flag-LOW {
        background: #eef3fc;
        border-left: 5px solid #1976d2;
        padding: 12px 18px;
        border-radius: 12px;
        margin: 12px 0;
    }
    /* Score card styling */
    .score-card {
        background: white;
        border-radius: 24px;
        padding: 1rem;
        text-align: center;
        transition: all 0.2s;
        border: 1px solid rgba(0,0,0,0.05);
        backdrop-filter: blur(2px);
    }
    /* Custom buttons */
    .stButton > button {
        border-radius: 40px;
        padding: 0.5rem 1.8rem;
        font-weight: 600;
        transition: all 0.2s;
        background: linear-gradient(95deg, #1e3c72, #2a5298);
        color: white;
        border: none;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        background: linear-gradient(95deg, #2a5298, #1e3c72);
        box-shadow: 0 8px 18px rgba(0,0,0,0.1);
    }
    /* Metric cards */
    .metric-badge {
        background: rgba(255,255,255,0.8);
        border-radius: 16px;
        padding: 0.4rem 1rem;
        text-align: center;
        backdrop-filter: blur(4px);
    }
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 40px;
        padding: 6px 20px;
        background-color: rgba(255,255,255,0.5);
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e3c72;
        color: white;
    }
    /* Headers */
    h1, h2, h3 {
        font-weight: 600;
        letter-spacing: -0.3px;
    }
    hr {
        margin: 1rem 0;
        background: linear-gradient(90deg, transparent, #ccc, transparent);
    }
    /* Dataframe */
    .dataframe {
        border-radius: 16px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

def make_bar_chart(series, title, color):
    if series is None or series.empty:
        return None
    # Clean year labels
    years = [str(d)[:4] for d in series.index]
    values = [round(v, 0) for v in series.values]
    fig = go.Figure(go.Bar(
        x=years,
        y=values,
        marker_color=color,
        marker_line_width=0,
        opacity=0.85,
        text=values,
        textposition='outside',
        textfont=dict(size=10)
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, weight='bold'), x=0.5),
        height=260,
        margin=dict(t=40, b=30, l=40, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="₹ Crore",
        font=dict(size=11),
        xaxis=dict(tickangle=0, tickfont=dict(size=10)),
        yaxis=dict(gridcolor="rgba(0,0,0,0.05)", zerolinecolor="rgba(0,0,0,0.1)")
    )
    fig.update_traces(texttemplate='%{text:.0f}', textposition='outside')
    return fig

def risk_gauge(score):
    """Plotly gauge chart for risk score."""
    color = "#d32f2f" if score >= 6 else "#f57c00" if score >= 3 else "#2e7d32"
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = score,
        title = {'text': "Risk Score", 'font': {'size': 16}},
        domain = {'x': [0, 1], 'y': [0, 1]},
        gauge = {
            'axis': {'range': [0, 10], 'tickwidth': 1, 'tickcolor': "darkgray"},
            'bar': {'color': color, 'thickness': 0.3},
            'bgcolor': "white",
            'borderwidth': 0,
            'steps': [
                {'range': [0, 3], 'color': '#e8f5e9'},
                {'range': [3, 6], 'color': '#fff3e0'},
                {'range': [6, 10], 'color': '#ffebee'}
            ],
            'threshold': {
                'line': {'color': "black", 'width': 2},
                'thickness': 0.75,
                'value': score
            }
        }
    ))
    fig.update_layout(height=220, margin=dict(t=30, b=10, l=30, r=30), paper_bgcolor="rgba(0,0,0,0)")
    return fig

def score_card_modern(symbol, name, score, flag_count):
    """Enhanced score card with risk level and gauge."""
    risk_label = "HIGH RISK" if score >= 6 else "WATCH" if score >= 3 else "CLEAN"
    color = "#d32f2f" if score >= 6 else "#f57c00" if score >= 3 else "#2e7d32"
    bg_gradient = "linear-gradient(135deg, #ffffff, #fafafa)"
    return f"""
    <div class="score-card" style="background: {bg_gradient}; border-top: 4px solid {color};">
        <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; color: #666;">{symbol.replace('.NS','').replace('.BO','')}</div>
        <div style="font-size: 0.8rem; font-weight: 500; margin: 4px 0; color: #222;">{name[:28]}</div>
        <div style="font-size: 2.4rem; font-weight: 700; color: {color};">{score}<span style="font-size: 1rem; color: #aaa;">/10</span></div>
        <div style="font-size: 0.7rem; font-weight: 600; color: {color}; background: rgba(0,0,0,0.03); display: inline-block; padding: 2px 10px; border-radius: 30px;">{risk_label}</div>
        <div style="font-size: 0.7rem; color: #777; margin-top: 6px;">⚑ {flag_count} flag(s)</div>
    </div>
    """

@st.cache_data(ttl=3600, show_spinner=False)
def analyse_ticker(ticker):
    data = get_company_data(ticker)
    if data is None: return None
    flags, score = run_all_checks(data)
    return {**data, "flags": flags, "score": score}

# Load NSE company list
with st.spinner("📡 Fetching latest NSE company list..."):
    ALL_COMPANIES = load_nse_company_list()

# ─── HEADER SECTION ────────────────────────────────────────
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.markdown("## 🚨")
with col_title:
    st.markdown("# India Red Flag Dashboard")
    st.caption(f"**{len(ALL_COMPANIES):,} NSE-listed companies** · Forensic financial health screening · Data via Yahoo Finance · Last updated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}")

# Tabs
tab_search, tab_sector, tab_about = st.tabs(["🔍  Company Search & Analysis", "📊  Sector Scanner", "ℹ️  About & Methodology"])

# ======================= TAB 1: SEARCH =======================
with tab_search:
    st.markdown("### Search across all NSE companies")
    st.caption("Select one or more companies from the dropdown, or type NSE tickers directly.")
    
    col1, col2 = st.columns([2.5, 1.5])
    with col1:
        selected_names = st.multiselect(
            "🔎 Company name (searchable)",
            options=sorted(ALL_COMPANIES.keys()),
            placeholder="e.g. Infosys, HDFC Bank, Reliance...",
            label_visibility="collapsed"
        )
        manual = st.text_input(
            "✏️ Or type NSE tickers (comma separated)",
            placeholder="RCOM, JPPOWER, DHFL, GTLINFRA",
            label_visibility="collapsed"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)  # spacing
        st.info("💡 **Tip**: Select multiple companies to compare them side by side.")
    
    # Resolve tickers
    tickers = []
    if selected_names:
        tickers += [ALL_COMPANIES[n] for n in selected_names]
    if manual.strip():
        raw_tickers = [t.strip().upper() for t in manual.split(",") if t.strip()]
        with st.spinner("Validating tickers..."):
            for raw in raw_tickers:
                resolved = resolve_ticker(raw)
                if resolved:
                    tickers.append(resolved)
                else:
                    st.warning(f"⚠️ Could not find **{raw}** on NSE/BSE")
    tickers = list(dict.fromkeys(tickers))
    
    if tickers and st.button(f"🔍 Analyse {len(tickers)} company/companies", type="primary", use_container_width=False):
        results, progress_bar = [], st.progress(0, text="Fetching financials...")
        for i, ticker in enumerate(tickers):
            progress_bar.progress(i / len(tickers), f"Analysing {ticker}...")
            r = analyse_ticker(ticker)
            if r:
                results.append(r)
            else:
                st.warning(f"❌ Data unavailable for {ticker} — may not be covered by Yahoo Finance")
            time.sleep(0.25)
        progress_bar.empty()
        
        if not results:
            st.error("No data fetched. Try different tickers or check later.")
            st.stop()
        
        # Sort by risk score (highest first)
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Summary score cards row
        st.divider()
        st.subheader("📋 Risk Summary")
        cols = st.columns(min(len(results), 5))
        for idx, r in enumerate(results):
            cols[idx % 5].markdown(score_card_modern(r["ticker"], r["name"], r["score"], len(r["flags"])), unsafe_allow_html=True)
        
        st.divider()
        
        # Detailed expanders for each company
        for r in results:
            with st.expander(f"{'🔴' if r['score']>=6 else '🟡' if r['score']>=3 else '✅'}  {r['name']}  ({r['ticker'].replace('.NS','')})  |  Score: {r['score']}/10  |  {r.get('sector','—')}  |  ₹{r['mcap_cr']:,.0f} Cr" if r.get('mcap_cr') else f"{r['name']}  ({r['ticker'].replace('.NS','')})", expanded=(r['score']>=6)):
                
                # Top row: key metrics + gauge
                col_a, col_b, col_c = st.columns([1, 1.2, 1.8])
                with col_a:
                    st.metric("Market Cap", f"₹{r['mcap_cr']:,.0f} Cr" if r['mcap_cr'] else "—")
                    st.metric("Debt/Equity", f"{r['de_ratio']:.2f}x" if r['de_ratio'] else "—")
                with col_b:
                    st.metric("Promoter Holding", f"{r['promoter_holding_pct']:.1f}%" if r['promoter_holding_pct'] else "—")
                    st.metric("Sector", r['sector'][:20] if r['sector'] else "—")
                with col_c:
                    st.plotly_chart(risk_gauge(r['score']), use_container_width=True, config={"displayModeBar": False})
                
                # Financial charts: Revenue, Profit, CFO
                st.markdown("#### 📊 Financial Trends (₹ Crore)")
                chart_cols = st.columns(3)
                for idx, (key, df_key, title, color) in enumerate([
                    ("revenue", "pnl", "Revenue", "#2c6e9e"),
                    ("net_profit", "pnl", "Net Profit", "#1b8c5e"),
                    ("cfo", "cf", "Operating Cash Flow", "#e67e22")
                ]):
                    fig = make_bar_chart(r[df_key].get(key), title, color)
                    if fig:
                        chart_cols[idx].plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                    else:
                        chart_cols[idx].info("No data available")
                
                # Red flags analysis
                st.markdown("#### 🚩 Red Flag Analysis")
                if not r["flags"]:
                    st.success("✅ No red flags triggered based on forensic checks. Always conduct your own due diligence.")
                else:
                    for sev, title, detail in r["flags"]:
                        icon = "🔴" if sev=="HIGH" else "🟡" if sev=="MEDIUM" else "🔵"
                        st.markdown(
                            f'<div class="flag-{sev}"><strong>{icon} [{sev}] {title}</strong><br><span style="color:#444; font-size:0.85rem;">{detail}</span></div>',
                            unsafe_allow_html=True
                        )
        
        # Download Excel report
        st.divider()
        rows = [{
            "Ticker": r["ticker"].replace(".NS","").replace(".BO",""),
            "Company": r["name"],
            "Sector": r.get("sector","—"),
            "Industry": r.get("industry","—"),
            "Mkt Cap (₹ Cr)": r.get("mcap_cr"),
            "Score (0-10)": r["score"],
            "Flags": " | ".join(f"[{s}] {t}" for s,t,_ in r["flags"]) or "None"
        } for r in results]
        df_download = pd.DataFrame(rows)
        excel_buffer = io.BytesIO()
        df_download.to_excel(excel_buffer, index=False)
        st.download_button(
            label="📥 Download Excel Report",
            data=excel_buffer.getvalue(),
            file_name=f"red_flag_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=False
        )

# ======================= TAB 2: SECTOR SCAN =======================
with tab_sector:
    st.markdown("### 📊 Sector-wide health scan")
    st.caption("Pre-defined sector baskets covering major NSE segments. Click 'Scan' to run forensic checks on all companies in that sector.")
    
    # Sector groups (unchanged)
    SECTOR_GROUPS = {
        "🏦 Banks":                ["HDFCBANK","ICICIBANK","AXISBANK","YESBANK","KOTAKBANK","SBIN","INDUSINDBK","FEDERALBNK","BANDHANBNK","IDFCFIRSTB"],
        "🏦 NBFCs":                ["BAJFINANCE","BAJAJFINSV","CHOLAFIN","MUTHOOTFIN","MANAPPURAM","LICHSGFIN","PNBHOUSING","CANFINHOME"],
        "💻 IT Services":          ["TCS","INFY","WIPRO","HCLTECH","TECHM","MPHASIS","LTIM","PERSISTENT","COFORGE","KPITTECH"],
        "💊 Pharma":               ["SUNPHARMA","DRREDDY","CIPLA","DIVISLAB","AUROPHARMA","TORNTPHARM","ALKEM","IPCALAB","GLENMARK","NATCOPHARM"],
        "⚡ Adani Group":          ["ADANIENT","ADANIPORTS","ADANIPOWER","ADANIGREEN","ADANITRANS","ADANIGAS","ADANIENSOL","AWL"],
        "🏭 Auto":                 ["TATAMOTORS","MARUTI","HEROMOTOCO","BAJAJ-AUTO","EICHERMOT","MAHINDRA","TVSMOTORS","ASHOKLEY"],
        "🏗️ Infrastructure":       ["LT","ULTRACEMCO","GRASIM","AMBUJACEM","ACC","SHREECEM","JKCEMENT","RAMCOCEM"],
        "🛢️ Oil & Gas":            ["RELIANCE","ONGC","BPCL","IOC","HINDPETRO","GAIL","OIL","MGL"],
        "🛒 FMCG":                 ["HINDUNILVR","ITC","NESTLEIND","BRITANNIA","DABUR","MARICO","GODREJCP","COLPAL","EMAMILTD"],
        "🔌 Power":                ["NTPC","POWERGRID","TATAPOWER","CESC","TORNTPOWER","JSWENERGY","NHPC","SJVN"],
        "🏠 Real Estate":          ["DLF","GODREJPROP","OBEROIRLTY","PHOENIXLTD","PRESTIGE","BRIGADE","SOBHA","MAHLIFE"],
        "🚀 New-age / Startups":   ["ZOMATO","PAYTM","NYKAA","DELHIVERY","CARTRADE","EASEMYTRIP","POLICYBZR","MAPMYINDIA"],
        "📡 Telecom":              ["BHARTIARTL","IDEA","TATACOMM","INDUSTOWER","HFCL"],
        "🔩 Metals & Mining":      ["TATASTEEL","JSWSTEEL","HINDALCO","VEDL","SAIL","NMDC","NATIONALUM","HINDCOPPER"],
        "⚠️ High-risk / Stressed": ["YESBANK","RCOM","SUZLON","JPPOWER","JPASSOCIAT","GTLINFRA","DEWAN","ALOKTEXT"],
    }
    
    chosen_sector = st.selectbox("Select sector to analyse", list(SECTOR_GROUPS.keys()))
    sector_tickers = [f"{t}.NS" for t in SECTOR_GROUPS[chosen_sector]]
    st.caption(f"📌 {len(sector_tickers)} companies in this sector")
    
    if st.button(f"🔍 Scan {chosen_sector}", type="primary"):
        rows, prog = [], st.progress(0, text="Scanning sector...")
        for i, sym in enumerate(sector_tickers):
            prog.progress(i / len(sector_tickers), f"Processing {sym}...")
            r = analyse_ticker(sym)
            if r:
                rows.append({
                    "Ticker":   sym.replace(".NS",""),
                    "Company":  r["name"],
                    "Industry": r.get("industry","—"),
                    "Mkt Cap (₹ Cr)": r.get("mcap_cr"),
                    "Score":    r["score"],
                    "# Flags":  len(r["flags"]),
                    "Top Flag": r["flags"][0][1] if r["flags"] else "None",
                })
            time.sleep(0.2)
        prog.empty()
        
        if rows:
            df = pd.DataFrame(rows).sort_values("Score", ascending=False)
            # Color gradient on Score
            styled_df = df.style.background_gradient(subset=["Score"], cmap="RdYlGn_r", vmin=0, vmax=10)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            # Download sector report
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False)
            st.download_button(
                label="📥 Download sector report (Excel)",
                data=buffer.getvalue(),
                file_name=f"sector_{chosen_sector.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("No data retrieved for this sector.")

# ======================= TAB 3: ABOUT =======================
with tab_about:
    st.markdown("""
    ## 🧠 Methodology & Red Flag Checks
    
    This dashboard performs **forensic accounting analysis** on NSE-listed companies using annual financial data from Yahoo Finance.  
    Each company is scored out of **10** based on 10 quantitative checks – the higher the score, the more red flags.
    
    ### Checks performed
    
    | # | Check | What it detects | Severity |
    |---|-------|----------------|----------|
    | 1 | CFO / Net Profit ratio | Earnings manipulation, poor cash conversion | HIGH/MEDIUM |
    | 2 | Receivables vs Revenue growth | Channel stuffing, aggressive revenue | HIGH/MEDIUM |
    | 3 | Debt up + CFO down | Pre-distress signal | HIGH |
    | 4 | Inventory buildup | Demand slowdown, obsolete stock | MEDIUM |
    | 5 | Interest coverage ratio | Debt servicing risk | HIGH/MEDIUM |
    | 6 | Negative CFO despite profits | Persistent accounting manipulation | HIGH |
    | 7 | Revenue decline | Structural deterioration | MEDIUM |
    | 8 | Sustained losses | Profitability failure | HIGH/MEDIUM |
    | 9 | Debt/Equity ratio | Over-leverage | HIGH/MEDIUM |
    | 10 | Low promoter holding | Governance concern | LOW |
    
    **Scoring:** HIGH = 2 points, MEDIUM = 1 point, LOW = 0 points → max 10.
    
    ### Data source & limitations
    - **Data:** Yahoo Finance (annual reports). May lag latest filings by several weeks.
    - **Coverage:** All NSE-listed companies with financials available on Yahoo Finance.
    - **Not investment advice:** These are quantitative forensic flags, not buy/sell recommendations.
    
    ### Version & Credits
    Built with Streamlit, yfinance, Plotly.  
    Updated daily with NSE company list.
    """)
