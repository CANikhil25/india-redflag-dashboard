# ============================================================
#  INDIA RED FLAG DASHBOARD  —  app.py
#  Fixed UI: high contrast, readable text, functional layout
#
#  SECTION 1 — DATA LAYER       edit for new data sources
#  SECTION 2 — ANALYSIS LAYER   edit for new checks / scoring
#  SECTION 3 — UI LAYER         clean, accessible, no contrast issues
# ============================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import io
import time
import requests
from datetime import datetime

# ============================================================
#  SECTION 1 — DATA LAYER (unchanged, robust)
# ============================================================

@st.cache_data(ttl=86400, show_spinner=False)
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
#  SECTION 2 — ANALYSIS LAYER (unchanged)
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
#  SECTION 3 — UI LAYER (FIXED: high contrast, readable)
# ============================================================

st.set_page_config(
    page_title="India Red Flag Dashboard",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "Forensic analysis tool for NSE-listed companies. Not investment advice."}
)

# --- Simple, robust CSS for readability (no transparency, dark text on light) ---
st.markdown("""
<style>
    /* Ensure body background is light but text is dark */
    .stApp {
        background-color: #f8f9fa;
    }
    /* Card style with solid background and shadow */
    .card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        margin-bottom: 1rem;
        border: 1px solid #e0e0e0;
    }
    /* Flag containers – solid background, dark text, colored borders */
    .flag-HIGH {
        background-color: #fee9e6;
        border-left: 6px solid #c0392b;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 12px 0;
        color: #2c3e50;
        font-size: 0.9rem;
    }
    .flag-MEDIUM {
        background-color: #fff3e0;
        border-left: 6px solid #e67e22;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 12px 0;
        color: #2c3e50;
    }
    .flag-LOW {
        background-color: #e8f0fe;
        border-left: 6px solid #2980b9;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 12px 0;
        color: #2c3e50;
    }
    /* Score card */
    .score-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 1rem;
        text-align: center;
        border: 1px solid #dee2e6;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    /* Buttons */
    .stButton > button {
        background-color: #1f618d;
        color: white;
        border-radius: 30px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        border: none;
        transition: 0.2s;
    }
    .stButton > button:hover {
        background-color: #154360;
        color: white;
    }
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] button {
        background-color: #e9ecef;
        border-radius: 30px;
        margin-right: 8px;
        font-weight: 500;
        color: #1a1a1a;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        background-color: #1f618d;
        color: white;
    }
    /* Metric text */
    [data-testid="stMetricValue"] {
        color: #1a1a1a;
        font-weight: 600;
    }
    /* Headers */
    h1, h2, h3, h4 {
        color: #1e3a5f;
    }
    /* Expander headers */
    .streamlit-expanderHeader {
        font-weight: 600;
        background-color: #f1f3f5;
        border-radius: 8px;
    }
    /* Dataframe */
    .dataframe {
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

def make_bar_chart(series, title, color):
    if series is None or series.empty:
        return None
    years = [str(d)[:4] for d in series.index]
    values = [round(v, 0) for v in series.values]
    fig = go.Figure(go.Bar(
        x=years, y=values,
        marker_color=color,
        text=values, textposition='outside',
        textfont=dict(color='black', size=10)
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color='black'), x=0.5),
        height=260,
        margin=dict(t=40, b=30, l=40, r=20),
        paper_bgcolor='white',
        plot_bgcolor='white',
        yaxis_title="₹ Crore",
        font=dict(color='black'),
        xaxis=dict(tickangle=0, tickfont=dict(color='black')),
        yaxis=dict(gridcolor='#e0e0e0', zerolinecolor='#cccccc')
    )
    return fig

def risk_gauge(score):
    color = "#c0392b" if score >= 6 else "#e67e22" if score >= 3 else "#27ae60"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={'text': "Risk Score", 'font': {'size': 14, 'color': 'black'}},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [0, 10], 'tickcolor': 'black'},
            'bar': {'color': color, 'thickness': 0.3},
            'bgcolor': 'white',
            'borderwidth': 0,
            'steps': [
                {'range': [0, 3], 'color': '#e8f5e9'},
                {'range': [3, 6], 'color': '#fff3e0'},
                {'range': [6, 10], 'color': '#ffebee'}
            ]
        }
    ))
    fig.update_layout(height=200, margin=dict(t=30, b=10), paper_bgcolor='white')
    return fig

def score_card_modern(symbol, name, score, flag_count):
    risk_label = "HIGH RISK" if score >= 6 else "WATCH" if score >= 3 else "CLEAN"
    color = "#c0392b" if score >= 6 else "#e67e22" if score >= 3 else "#27ae60"
    return f"""
    <div class="score-card">
        <div style="font-size:0.7rem; color:#6c757d;">{symbol.replace('.NS','').replace('.BO','')}</div>
        <div style="font-size:0.85rem; font-weight:500; margin:6px 0;">{name[:28]}</div>
        <div style="font-size:2.2rem; font-weight:700; color:{color};">{score}<span style="font-size:0.9rem; color:#6c757d;">/10</span></div>
        <div style="font-size:0.7rem; font-weight:600; color:{color}; background:#f8f9fa; display:inline-block; padding:2px 12px; border-radius:20px;">{risk_label}</div>
        <div style="font-size:0.7rem; color:#6c757d; margin-top:6px;">🚩 {flag_count} flag(s)</div>
    </div>
    """

@st.cache_data(ttl=3600, show_spinner=False)
def analyse_ticker(ticker):
    data = get_company_data(ticker)
    if data is None: return None
    flags, score = run_all_checks(data)
    return {**data, "flags": flags, "score": score}

# Load NSE list
with st.spinner("Loading NSE company list..."):
    ALL_COMPANIES = load_nse_company_list()

# Header
st.title("🚨 India Red Flag Dashboard")
st.caption(f"**{len(ALL_COMPANIES):,} NSE-listed companies** · Forensic financial screening · Data via Yahoo Finance · {datetime.now().strftime('%d %b %Y, %I:%M %p')}")

tab_search, tab_sector, tab_about = st.tabs(["🔍 Search & Analyse", "📊 Sector Scanner", "ℹ️ About"])

# ======================= TAB 1 =======================
with tab_search:
    st.markdown("### Search by company name or NSE ticker")
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_names = st.multiselect(
            "Company name (searchable)",
            options=sorted(ALL_COMPANIES.keys()),
            placeholder="Type to search...",
            label_visibility="collapsed"
        )
        manual = st.text_input("Or type NSE tickers (comma separated)", placeholder="e.g. RELIANCE, TCS, ZOMATO")
    with col2:
        st.caption("💡 Select multiple to compare")
        st.caption("📌 Ticker: RELIANCE (no .NS)")

    tickers = []
    if selected_names:
        tickers += [ALL_COMPANIES[n] for n in selected_names]
    if manual.strip():
        for raw in [t.strip().upper() for t in manual.split(",") if t.strip()]:
            resolved = resolve_ticker(raw)
            if resolved:
                tickers.append(resolved)
            else:
                st.warning(f"Invalid ticker: {raw}")
    tickers = list(dict.fromkeys(tickers))

    if tickers and st.button(f"Analyse {len(tickers)} company/companies", type="primary"):
        results = []
        prog = st.progress(0)
        for i, t in enumerate(tickers):
            prog.progress((i+1)/len(tickers), f"Fetching {t}...")
            r = analyse_ticker(t)
            if r:
                results.append(r)
            else:
                st.error(f"No data for {t}")
            time.sleep(0.3)
        prog.empty()

        if not results:
            st.error("No results. Try different tickers.")
            st.stop()

        results.sort(key=lambda x: x["score"], reverse=True)

        st.divider()
        st.subheader("Risk Summary")
        cols = st.columns(min(5, len(results)))
        for idx, r in enumerate(results):
            cols[idx % 5].markdown(score_card_modern(r["ticker"], r["name"], r["score"], len(r["flags"])), unsafe_allow_html=True)

        st.divider()
        for r in results:
            with st.expander(f"{'🔴' if r['score']>=6 else '🟡' if r['score']>=3 else '✅'} {r['name']} ({r['ticker'].replace('.NS','')}) | Score: {r['score']}/10", expanded=(r['score']>=6)):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Market Cap", f"₹{r['mcap_cr']:,.0f} Cr" if r['mcap_cr'] else "—")
                    st.metric("Debt/Equity", f"{r['de_ratio']:.2f}" if r['de_ratio'] else "—")
                with c2:
                    st.metric("Promoter Holding", f"{r['promoter_holding_pct']:.1f}%" if r['promoter_holding_pct'] else "—")
                    st.metric("Sector", r['sector'])
                with c3:
                    st.plotly_chart(risk_gauge(r['score']), use_container_width=True, config={"displayModeBar": False})

                st.markdown("#### Financial Trends (₹ Crore)")
                col_ch1, col_ch2, col_ch3 = st.columns(3)
                charts = [
                    (r["pnl"].get("revenue"), "Revenue", "#1f618d"),
                    (r["pnl"].get("net_profit"), "Net Profit", "#27ae60"),
                    (r["cf"].get("cfo"), "Operating Cash Flow", "#e67e22")
                ]
                for i, (series, title, color) in enumerate(charts):
                    fig = make_bar_chart(series, title, color)
                    if fig:
                        [col_ch1, col_ch2, col_ch3][i].plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                    else:
                        [col_ch1, col_ch2, col_ch3][i].info("No data")

                st.markdown("#### 🚩 Red Flags")
                if not r["flags"]:
                    st.success("✅ No red flags triggered.")
                else:
                    for sev, title, detail in r["flags"]:
                        st.markdown(f'<div class="flag-{sev}"><strong>[{sev}] {title}</strong><br>{detail}</div>', unsafe_allow_html=True)

        # Excel download
        df_report = pd.DataFrame([{
            "Ticker": r["ticker"].replace(".NS",""),
            "Company": r["name"],
            "Sector": r["sector"],
            "Mkt Cap Cr": r["mcap_cr"],
            "Score": r["score"],
            "Flags": " | ".join([f"{s}: {t}" for s,t,_ in r["flags"]]) or "None"
        } for r in results])
        buffer = io.BytesIO()
        df_report.to_excel(buffer, index=False)
        st.download_button("📥 Download Excel Report", buffer.getvalue(), file_name="red_flags.xlsx")

# ======================= TAB 2 =======================
with tab_sector:
    st.markdown("### Sector-wise health scan")
    SECTOR_GROUPS = {
        "🏦 Banks": ["HDFCBANK","ICICIBANK","AXISBANK","YESBANK","KOTAKBANK","SBIN","INDUSINDBK","FEDERALBNK","BANDHANBNK","IDFCFIRSTB"],
        "💻 IT Services": ["TCS","INFY","WIPRO","HCLTECH","TECHM","MPHASIS","LTIM","PERSISTENT","COFORGE"],
        "💊 Pharma": ["SUNPHARMA","DRREDDY","CIPLA","DIVISLAB","AUROPHARMA","TORNTPHARM","ALKEM"],
        "⚡ Adani Group": ["ADANIENT","ADANIPORTS","ADANIPOWER","ADANIGREEN","ADANITRANS","ADANIGAS"],
        "🏭 Auto": ["TATAMOTORS","MARUTI","HEROMOTOCO","BAJAJ-AUTO","EICHERMOT","MAHINDRA"],
        "🛢️ Oil & Gas": ["RELIANCE","ONGC","BPCL","IOC","HINDPETRO","GAIL"],
        "⚠️ High-risk": ["YESBANK","RCOM","SUZLON","JPPOWER","GTLINFRA"],
    }
    chosen = st.selectbox("Select sector", list(SECTOR_GROUPS.keys()))
    if st.button("Scan Sector", type="primary"):
        sector_tickers = [f"{t}.NS" for t in SECTOR_GROUPS[chosen]]
        rows, prog = [], st.progress(0)
        for i, sym in enumerate(sector_tickers):
            prog.progress((i+1)/len(sector_tickers), f"Scanning {sym}...")
            r = analyse_ticker(sym)
            if r:
                rows.append({"Ticker": sym.replace(".NS",""), "Company": r["name"], "Score": r["score"], "#Flags": len(r["flags"])})
            time.sleep(0.2)
        prog.empty()
        if rows:
            df = pd.DataFrame(rows).sort_values("Score", ascending=False)
            st.dataframe(df, use_container_width=True)
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False)
            st.download_button("Download Sector Report", buffer.getvalue(), file_name=f"sector_{chosen}.xlsx")
        else:
            st.warning("No data")

# ======================= TAB 3 =======================
with tab_about:
    st.markdown("""
    ## Methodology
    - **10 forensic checks** (CFO/Profit, Receivables growth, Debt vs CFO, Inventory, Interest coverage, Negative CFO with profit, Revenue decline, Sustained losses, Debt/Equity, Promoter holding)
    - **Scoring:** HIGH=2, MEDIUM=1, LOW=0 → max 10
    - **Data:** Yahoo Finance annual financials (lag may exist)
    - **Disclaimer:** Not investment advice. For research only.
    """)
