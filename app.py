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
#  SECTION 3 — UI LAYER (Redesigned: sharp fintech aesthetic)
# ============================================================

st.set_page_config(
    page_title="India Red Flag Dashboard",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "Forensic analysis tool for NSE-listed companies. Not investment advice."}
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Sora:wght@300;400;600;700;800&display=swap');

/* ── BASE ─────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp {
    background-color: #0c0f1a !important;
    color: #e8eaf0 !important;
    font-family: 'Sora', sans-serif !important;
}

/* kill all default streamlit white backgrounds */
section[data-testid="stSidebar"],
.block-container {
    background: transparent !important;
    padding-top: 1rem !important;
}

/* ── HERO ─────────────────────────────────────────── */
.hero {
    background: linear-gradient(135deg, #0d1b3e 0%, #0c0f1a 60%);
    border: 1px solid #1e2d54;
    border-radius: 16px;
    padding: 2rem 2.4rem;
    margin-bottom: 1.8rem;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 220px; height: 220px;
    background: radial-gradient(circle, rgba(239,68,68,0.18) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-title {
    font-size: 1.75rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #ffffff;
}
.hero-title span { color: #ef4444; }
.hero-sub {
    font-size: 0.78rem;
    color: #94a3b8;
    margin-top: 0.35rem;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: 0.5px;
}
.hero-badge {
    display: inline-block;
    background: rgba(239,68,68,0.12);
    border: 1px solid rgba(239,68,68,0.3);
    color: #fca5a5;
    font-size: 0.65rem;
    font-family: 'IBM Plex Mono', monospace;
    padding: 3px 10px;
    border-radius: 4px;
    margin-right: 8px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── SEARCH PANEL ─────────────────────────────────── */
.search-panel {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 14px;
    padding: 1.6rem 1.8rem;
    margin-bottom: 1.4rem;
}
.panel-label {
    font-size: 0.7rem;
    font-family: 'IBM Plex Mono', monospace;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 0.6rem;
}

/* ── STREAMLIT WIDGET OVERRIDES ───────────────────── */
/* Multiselect */
div[data-baseweb="select"] > div,
div[data-baseweb="select"] > div:focus-within {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
}
div[data-baseweb="select"] span { color: #e2e8f0 !important; }
div[data-baseweb="select"] svg { fill: #64748b !important; }

/* Text input */
.stTextInput input {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.85rem !important;
    padding: 0.55rem 0.9rem !important;
}
.stTextInput input::placeholder { color: #475569 !important; }
.stTextInput input:focus { border-color: #3b82f6 !important; box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important; }

/* Labels */
label[data-testid="stWidgetLabel"] > div > p,
.stTextInput label { color: #94a3b8 !important; font-size: 0.75rem !important; }

/* Buttons */
.stButton > button {
    background: #1d4ed8 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Sora', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    padding: 0.55rem 1.4rem !important;
    transition: background 0.2s, transform 0.15s !important;
    letter-spacing: 0.2px !important;
}
.stButton > button:hover {
    background: #2563eb !important;
    transform: translateY(-1px) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* Download button */
.stDownloadButton > button {
    background: #064e3b !important;
    color: #6ee7b7 !important;
    border: 1px solid #065f46 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
.stDownloadButton > button:hover { background: #065f46 !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #111827 !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 2px !important;
    border: 1px solid #1f2937 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #64748b !important;
    border-radius: 7px !important;
    font-family: 'Sora', sans-serif !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    padding: 0.45rem 1rem !important;
    transition: all 0.2s !important;
}
.stTabs [aria-selected="true"] {
    background: #1e3a8a !important;
    color: #ffffff !important;
    font-weight: 600 !important;
}

/* Expanders */
details {
    background: #111827 !important;
    border: 1px solid #1f2937 !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    margin-bottom: 0.75rem !important;
}
details summary {
    background: #111827 !important;
    color: #e2e8f0 !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.9rem 1.2rem !important;
    cursor: pointer !important;
}
details summary:hover { background: #1e293b !important; }
details[open] summary { border-bottom: 1px solid #1f2937 !important; }
details > div { background: #111827 !important; padding: 1rem 1.2rem !important; }

/* Metrics */
[data-testid="stMetric"] {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 10px !important;
    padding: 0.75rem 1rem !important;
}
[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-size: 0.72rem !important; }
[data-testid="stMetricValue"] { color: #f1f5f9 !important; font-size: 1.3rem !important; font-weight: 700 !important; }

/* Selectbox */
div[data-baseweb="select"] [role="listbox"] {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
}
div[data-baseweb="select"] [role="option"] { color: #e2e8f0 !important; }
div[data-baseweb="select"] [role="option"]:hover { background: #334155 !important; }

/* Progress bar */
.stProgress > div > div > div { background: #3b82f6 !important; }

/* Spinner text */
.stSpinner > div { color: #94a3b8 !important; }

/* Success / error / warning alerts */
.stSuccess { background: #052e16 !important; color: #86efac !important; border: 1px solid #166534 !important; border-radius: 8px !important; }
.stError   { background: #1c0a0a !important; color: #fca5a5 !important; border: 1px solid #7f1d1d !important; border-radius: 8px !important; }
.stWarning { background: #1c1208 !important; color: #fde68a !important; border: 1px solid #78350f !important; border-radius: 8px !important; }

/* Divider */
hr { border-color: #1f2937 !important; }

/* Dataframe */
[data-testid="stDataFrame"] { border: 1px solid #1f2937 !important; border-radius: 10px !important; overflow: hidden !important; }

/* Caption / small text */
.stCaption, small { color: #64748b !important; font-size: 0.72rem !important; }

/* ── SCORE CARD ───────────────────────────────────── */
.score-card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 14px;
    padding: 1.2rem 0.8rem;
    text-align: center;
    transition: transform 0.2s, border-color 0.2s;
    position: relative;
    overflow: hidden;
}
.score-card:hover {
    transform: translateY(-3px);
    border-color: #334155;
}
.score-card .ticker-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.65rem;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.score-card .company-name {
    font-size: 0.82rem;
    font-weight: 600;
    color: #cbd5e1;
    margin: 0.4rem 0;
    line-height: 1.3;
}
.score-card .big-score {
    font-size: 2.5rem;
    font-weight: 800;
    line-height: 1;
    margin: 0.3rem 0;
}
.score-card .score-denom {
    font-size: 0.9rem;
    color: #475569;
    font-weight: 400;
}
.score-card .risk-pill {
    display: inline-block;
    font-size: 0.62rem;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
    letter-spacing: 1.2px;
    padding: 3px 12px;
    border-radius: 20px;
    text-transform: uppercase;
    margin-top: 0.3rem;
}
.score-card .flag-count {
    font-size: 0.68rem;
    color: #475569;
    margin-top: 0.5rem;
}

/* ── FLAGS ────────────────────────────────────────── */
.flag-wrap { display: flex; flex-direction: column; gap: 0.6rem; margin-top: 0.5rem; }
.flag-item {
    border-radius: 10px;
    padding: 0.85rem 1rem;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0 0.85rem;
    align-items: start;
}
.flag-HIGH {
    background: rgba(220,38,38,0.1);
    border: 1px solid rgba(220,38,38,0.3);
}
.flag-MEDIUM {
    background: rgba(217,119,6,0.1);
    border: 1px solid rgba(217,119,6,0.3);
}
.flag-LOW {
    background: rgba(37,99,235,0.1);
    border: 1px solid rgba(37,99,235,0.25);
}
.flag-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-top: 5px;
    flex-shrink: 0;
}
.flag-HIGH .flag-dot  { background: #ef4444; box-shadow: 0 0 6px rgba(239,68,68,0.5); }
.flag-MEDIUM .flag-dot { background: #f59e0b; box-shadow: 0 0 6px rgba(245,158,11,0.5); }
.flag-LOW .flag-dot   { background: #3b82f6; box-shadow: 0 0 6px rgba(59,130,246,0.5); }
.flag-sev {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.6rem;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 3px;
    display: block;
}
.flag-HIGH  .flag-sev { color: #f87171; }
.flag-MEDIUM .flag-sev { color: #fbbf24; }
.flag-LOW   .flag-sev { color: #60a5fa; }
.flag-title { font-weight: 600; font-size: 0.88rem; color: #e2e8f0; }
.flag-detail { font-size: 0.78rem; color: #94a3b8; margin-top: 3px; line-height: 1.5; }

/* ── SECTION HEADINGS ─────────────────────────────── */
.section-heading {
    font-size: 0.7rem;
    font-family: 'IBM Plex Mono', monospace;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin: 1.2rem 0 0.7rem;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-heading::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #1f2937;
}

/* ── CLEAN BADGE ──────────────────────────────────── */
.clean-badge {
    background: rgba(16,185,129,0.1);
    border: 1px solid rgba(16,185,129,0.25);
    border-radius: 8px;
    padding: 0.7rem 1rem;
    color: #6ee7b7;
    font-size: 0.83rem;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# ── helpers ──────────────────────────────────────────────────────────

def make_bar_chart(series, title, color):
    if series is None or series.empty:
        return None
    years  = [str(d)[:4] for d in series.index]
    values = [round(v, 0) for v in series.values]
    fig = go.Figure(go.Bar(
        x=years, y=values,
        marker_color=color,
        marker_line_width=0,
        text=values,
        textposition='outside',
        textfont=dict(color='#94a3b8', size=9, family='IBM Plex Mono')
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=12, color='#cbd5e1', family='Sora'), x=0.5),
        height=240,
        margin=dict(t=40, b=20, l=30, r=10),
        paper_bgcolor='#111827',
        plot_bgcolor='#111827',
        yaxis_title="₹ Cr",
        font=dict(color='#94a3b8', family='Sora'),
        xaxis=dict(tickangle=0, tickfont=dict(color='#64748b', size=9), gridcolor='#1f2937', showgrid=False),
        yaxis=dict(gridcolor='#1f2937', zerolinecolor='#334155', tickfont=dict(color='#64748b', size=9)),
    )
    return fig


def risk_gauge(score):
    color = "#ef4444" if score >= 6 else "#f59e0b" if score >= 3 else "#10b981"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={'text': "Risk Score", 'font': {'size': 11, 'color': '#94a3b8', 'family': 'Sora'}},
        number={'font': {'size': 28, 'color': color, 'family': 'Sora'}, 'suffix': '/10'},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [0, 10], 'tickcolor': '#334155', 'tickfont': {'color': '#475569', 'size': 8}},
            'bar': {'color': color, 'thickness': 0.28},
            'bgcolor': '#0c0f1a',
            'borderwidth': 0,
            'steps': [
                {'range': [0, 3],  'color': 'rgba(16,185,129,0.08)'},
                {'range': [3, 6],  'color': 'rgba(245,158,11,0.08)'},
                {'range': [6, 10], 'color': 'rgba(239,68,68,0.08)'},
            ]
        }
    ))
    fig.update_layout(
        height=195,
        margin=dict(t=30, b=5, l=15, r=15),
        paper_bgcolor='#111827',
        font=dict(color='#94a3b8')
    )
    return fig


def score_card_html(symbol, name, score, flag_count):
    risk_label = "HIGH RISK" if score >= 6 else "WATCH" if score >= 3 else "CLEAN"
    score_color = "#ef4444" if score >= 6 else "#f59e0b" if score >= 3 else "#10b981"
    pill_bg = (
        "rgba(239,68,68,0.12)" if score >= 6 else
        "rgba(245,158,11,0.12)" if score >= 3 else
        "rgba(16,185,129,0.12)"
    )
    pill_border = (
        "rgba(239,68,68,0.35)" if score >= 6 else
        "rgba(245,158,11,0.35)" if score >= 3 else
        "rgba(16,185,129,0.35)"
    )
    return f"""
    <div class="score-card">
        <div class="ticker-label">{symbol.replace('.NS','').replace('.BO','')}</div>
        <div class="company-name">{name[:30]}</div>
        <div class="big-score" style="color:{score_color};">{score}<span class="score-denom">/10</span></div>
        <div>
            <span class="risk-pill" style="background:{pill_bg}; border:1px solid {pill_border}; color:{score_color};">{risk_label}</span>
        </div>
        <div class="flag-count">🚩 {flag_count} flag(s)</div>
    </div>
    """


def flag_html(sev, title, detail):
    return f"""
    <div class="flag-item flag-{sev}">
        <div class="flag-dot"></div>
        <div>
            <span class="flag-sev">{sev}</span>
            <div class="flag-title">{title}</div>
            <div class="flag-detail">{detail}</div>
        </div>
    </div>
    """


@st.cache_data(ttl=3600, show_spinner=False)
def analyse_ticker(ticker):
    data = get_company_data(ticker)
    if data is None: return None
    flags, score = run_all_checks(data)
    return {**data, "flags": flags, "score": score}


# ── Bootstrap ──────────────────────────────────────────────────────

with st.spinner("Loading NSE company list…"):
    ALL_COMPANIES = load_nse_company_list()

# ── Hero ───────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
    <div class="hero-title">🚨 India <span>Red Flag</span> Dashboard</div>
    <div class="hero-sub" style="margin-top:0.7rem;">
        <span class="hero-badge">NSE</span>
        <span class="hero-badge">{len(ALL_COMPANIES):,} companies</span>
        <span class="hero-badge">10 forensic checks</span>
        &nbsp;·&nbsp; {datetime.now().strftime('%d %b %Y, %I:%M %p')}
    </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────
tab_search, tab_sector, tab_about = st.tabs(["🔍  Search & Analyse", "📊  Sector Scanner", "ℹ️  About"])


# ═══════════════════════════════════════════════════════════════════
#  TAB 1 — SEARCH & ANALYSE
# ═══════════════════════════════════════════════════════════════════
with tab_search:

    st.markdown('<div class="search-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">Search companies</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        selected_names = st.multiselect(
            "Company name",
            options=sorted(ALL_COMPANIES.keys()),
            placeholder="Type to search by name…",
        )
        manual = st.text_input(
            "NSE tickers (comma-separated)",
            placeholder="e.g. RELIANCE, TCS, ZOMATO"
        )
    with col2:
        st.caption("💡 Select multiple to compare")
        st.caption("📌 Enter tickers without .NS")

    st.markdown('</div>', unsafe_allow_html=True)

    # Resolve tickers
    tickers = []
    if selected_names:
        tickers += [ALL_COMPANIES[n] for n in selected_names]
    if manual.strip():
        for raw in [t.strip().upper() for t in manual.split(",") if t.strip()]:
            resolved = resolve_ticker(raw)
            if resolved:
                tickers.append(resolved)
            else:
                st.warning(f"⚠️ Invalid or unresolvable ticker: **{raw}**")
    tickers = list(dict.fromkeys(tickers))

    if tickers and st.button(f"Analyse {len(tickers)} company/companies →", type="primary"):
        results = []
        prog = st.progress(0)
        for i, t in enumerate(tickers):
            prog.progress((i + 1) / len(tickers), f"Fetching {t}…")
            r = analyse_ticker(t)
            if r:
                results.append(r)
            else:
                st.error(f"No data available for **{t}** — check the ticker.")
            time.sleep(0.3)
        prog.empty()

        if not results:
            st.error("No results returned. Try different tickers.")
            st.stop()

        results.sort(key=lambda x: x["score"], reverse=True)

        # ── Risk summary cards ──────────────────────────────────
        st.markdown('<div class="section-heading">Risk Summary</div>', unsafe_allow_html=True)
        cols = st.columns(min(5, len(results)))
        for idx, r in enumerate(results):
            cols[idx % 5].markdown(
                score_card_html(r["ticker"], r["name"], r["score"], len(r["flags"])),
                unsafe_allow_html=True
            )

        st.divider()

        # ── Per-company detail ──────────────────────────────────
        for r in results:
            icon = "🔴" if r["score"] >= 6 else "🟡" if r["score"] >= 3 else "🟢"
            with st.expander(
                f"{icon}  {r['name']}  ({r['ticker'].replace('.NS','')})   |   Score: {r['score']} / 10",
                expanded=(r["score"] >= 6)
            ):
                # Metrics row
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Market Cap", f"₹{r['mcap_cr']:,.0f} Cr" if r["mcap_cr"] else "—")
                    st.metric("Debt / Equity", f"{r['de_ratio']:.2f}x" if r["de_ratio"] else "—")
                with c2:
                    st.metric("Promoter Holding", f"{r['promoter_holding_pct']:.1f}%" if r["promoter_holding_pct"] else "—")
                    st.metric("Sector", r["sector"])
                with c3:
                    st.plotly_chart(risk_gauge(r["score"]), use_container_width=True,
                                    config={"displayModeBar": False})

                # Charts
                st.markdown('<div class="section-heading">Financial Trends (₹ Crore)</div>', unsafe_allow_html=True)
                col_ch1, col_ch2, col_ch3 = st.columns(3)
                charts = [
                    (r["pnl"].get("revenue"),    "Revenue",              "#3b82f6"),
                    (r["pnl"].get("net_profit"),  "Net Profit",           "#10b981"),
                    (r["cf"].get("cfo"),           "Operating Cash Flow",  "#f59e0b"),
                ]
                for i, (series, title, color) in enumerate(charts):
                    fig = make_bar_chart(series, title, color)
                    if fig:
                        [col_ch1, col_ch2, col_ch3][i].plotly_chart(
                            fig, use_container_width=True, config={"displayModeBar": False})
                    else:
                        [col_ch1, col_ch2, col_ch3][i].caption("No data available")

                # Flags
                st.markdown('<div class="section-heading">Red Flags</div>', unsafe_allow_html=True)
                if not r["flags"]:
                    st.markdown('<div class="clean-badge">✅ No red flags triggered for this company.</div>',
                                unsafe_allow_html=True)
                else:
                    flag_blocks = "\n".join(flag_html(sev, title, detail) for sev, title, detail in r["flags"])
                    st.markdown(f'<div class="flag-wrap">{flag_blocks}</div>', unsafe_allow_html=True)

        # Excel download
        df_report = pd.DataFrame([{
            "Ticker":   r["ticker"].replace(".NS", ""),
            "Company":  r["name"],
            "Sector":   r["sector"],
            "Mkt Cap Cr": r["mcap_cr"],
            "Score":    r["score"],
            "Flags":    " | ".join([f"{s}: {t}" for s, t, _ in r["flags"]]) or "None"
        } for r in results])
        buffer = io.BytesIO()
        df_report.to_excel(buffer, index=False)
        st.download_button("📥 Download Excel Report", buffer.getvalue(), file_name="red_flags.xlsx")


# ═══════════════════════════════════════════════════════════════════
#  TAB 2 — SECTOR SCANNER
# ═══════════════════════════════════════════════════════════════════
with tab_sector:
    st.markdown('<div class="section-heading">Sector-wise Health Scan</div>', unsafe_allow_html=True)

    SECTOR_GROUPS = {
        "🏦 Banks": ["HDFCBANK","ICICIBANK","AXISBANK","YESBANK","KOTAKBANK","SBIN","INDUSINDBK","FEDERALBNK","BANDHANBNK","IDFCFIRSTB"],
        "💻 IT":    ["TCS","INFY","WIPRO","HCLTECH"],
    }

    chosen = st.selectbox("Select sector", list(SECTOR_GROUPS.keys()))

    if st.button("Scan Sector →", type="primary"):
        sector_tickers = [f"{t}.NS" for t in SECTOR_GROUPS[chosen]]
        results = []
        prog = st.progress(0)
        for i, sym in enumerate(sector_tickers):
            prog.progress((i + 1) / len(sector_tickers), f"Scanning {sym}…")
            r = analyse_ticker(sym)
            if r:
                results.append(r)
            time.sleep(0.2)
        prog.empty()

        if not results:
            st.warning("No data returned. Try again later.")
            st.stop()

        results.sort(key=lambda x: x["score"], reverse=True)
        st.divider()

        for r in results:
            icon = "🔴" if r["score"] >= 6 else "🟡" if r["score"] >= 3 else "🟢"
            with st.expander(f"{icon}  {r['name']}   |   Score: {r['score']} / 10"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Market Cap", f"₹{r['mcap_cr']:,.0f} Cr" if r["mcap_cr"] else "—")
                c2.metric("D/E", f"{r['de_ratio']:.2f}x" if r["de_ratio"] else "—")
                c3.metric("Promoter", f"{r['promoter_holding_pct']:.1f}%")

                st.markdown('<div class="section-heading">Red Flags</div>', unsafe_allow_html=True)
                if not r["flags"]:
                    st.markdown('<div class="clean-badge">✅ No major red flags detected.</div>',
                                unsafe_allow_html=True)
                else:
                    flag_blocks = "\n".join(flag_html(sev, title, detail) for sev, title, detail in r["flags"])
                    st.markdown(f'<div class="flag-wrap">{flag_blocks}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
#  TAB 3 — ABOUT
# ═══════════════════════════════════════════════════════════════════
with tab_about:
    st.markdown("""
    <div style="max-width: 640px; color: #94a3b8; line-height: 1.8; font-size: 0.88rem;">

    <div class="section-heading">Methodology</div>

    <p>This tool runs <strong style="color:#e2e8f0;">10 forensic checks</strong> on publicly available annual financials sourced from Yahoo Finance:</p>

    <ul style="padding-left: 1.2rem;">
        <li>CFO vs Net Profit ratio</li>
        <li>Receivables growth vs Revenue growth</li>
        <li>Debt growth vs CFO decline</li>
        <li>Inventory build-up vs Revenue</li>
        <li>Interest coverage ratio</li>
        <li>Negative CFO alongside reported profits</li>
        <li>Revenue decline (3Y CAGR)</li>
        <li>Sustained net losses</li>
        <li>Debt / Equity ratio</li>
        <li>Promoter / insider holding %</li>
    </ul>

    <div class="section-heading" style="margin-top: 1.4rem;">Scoring</div>
    <p>HIGH flag = 2 pts &nbsp;·&nbsp; MEDIUM flag = 1 pt &nbsp;·&nbsp; LOW flag = 0 pts &nbsp;·&nbsp; Max score capped at 10.</p>

    <div class="section-heading" style="margin-top: 1.4rem;">Disclaimer</div>
    <p>This is <strong style="color:#f87171;">not investment advice.</strong> Data may lag by one quarter or more. Always do your own research and consult a SEBI-registered advisor before making investment decisions.</p>

    </div>
    """, unsafe_allow_html=True)
