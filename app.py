# ============================================================
#  INDIA RED FLAG DASHBOARD  —  app.py
#
#  SECTION 1 — DATA LAYER
#  SECTION 2 — ANALYSIS LAYER  (flags now carry "evidence" metadata)
#  SECTION 3 — UI LAYER        (3-panel BS/PL/CF per flag)
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
#  SECTION 1 — DATA LAYER
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
        tickers = [
            ("Reliance Industries","RELIANCE"),("TCS","TCS"),("Infosys","INFY"),
            ("HDFC Bank","HDFCBANK"),("ICICI Bank","ICICIBANK"),("Wipro","WIPRO"),
            ("Adani Enterprises","ADANIENT"),("Yes Bank","YESBANK"),("Zomato","ZOMATO"),
            ("Paytm","PAYTM"),("Bajaj Finance","BAJFINANCE"),("ITC","ITC"),
            ("L&T","LT"),("Sun Pharma","SUNPHARMA"),("Tata Motors","TATAMOTORS"),
            ("ONGC","ONGC"),("Coal India","COALINDIA"),("SBI","SBIN"),
            ("Axis Bank","AXISBANK"),("Maruti Suzuki","MARUTI"),
            ("HCL Tech","HCLTECH"),("Tech Mahindra","TECHM"),
            ("NTPC","NTPC"),("Power Grid","POWERGRID"),("Tata Steel","TATASTEEL"),
            ("JSW Steel","JSWSTEEL"),("Hindalco","HINDALCO"),("Vedanta","VEDL"),
            ("NMDC","NMDC"),("Dr Reddy's","DRREDDY"),("Cipla","CIPLA"),
            ("Divis Labs","DIVISLAB"),("Lupin","LUPIN"),("Aurobindo Pharma","AUROPHARMA"),
            ("Hindustan Unilever","HINDUNILVR"),("Nestle India","NESTLEIND"),
            ("Britannia","BRITANNIA"),("Dabur","DABUR"),("Marico","MARICO"),
            ("DLF","DLF"),("Godrej Properties","GODREJPROP"),("Prestige Estates","PRESTIGE"),
            ("Tata Power","TATAPOWER"),("Adani Ports","ADANIPORTS"),
            ("Bajaj Auto","BAJAJ-AUTO"),("Eicher Motors","EICHERMOT"),
            ("Hero MotoCorp","HEROMOTOCO"),("Ashok Leyland","ASHOKLEY"),
            ("TVS Motor","TVSMOTOR"),("Muthoot Finance","MUTHOOTFIN"),
            ("Cholamandalam Finance","CHOLAFIN"),("Shriram Finance","SHRIRAMFIN"),
            ("Federal Bank","FEDERALBNK"),("Bandhan Bank","BANDHANBNK"),
            ("Kotak Mahindra Bank","KOTAKBANK"),("IndusInd Bank","INDUSINDBK"),
            ("Tata Communications","TATACOMM"),("Adani Green","ADANIGREEN"),
            ("JSW Energy","JSWENERGY"),("Torrent Power","TORNTPOWER"),
        ]
        return {f"{name}  ({sym})": f"{sym}.NS" for name, sym in tickers}


def resolve_ticker(raw: str) -> str:
    raw = raw.strip().upper().replace(".NS","").replace(".BO","")
    for suffix in [".NS", ".BO"]:
        symbol = raw + suffix
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            if not hist.empty:
                return symbol
        except Exception:
            continue
    return None


def _safe_row(df, names):
    if df is None or df.empty: return None
    for name in names:
        if name in df.index:
            row = pd.to_numeric(df.loc[name], errors="coerce").dropna()
            if not row.empty:
                return row.sort_index()
    return None

def _to_cr(val):
    if val is None or (isinstance(val, float) and pd.isna(val)): return None
    return round(float(val) / 1e7, 2)

def _series_cr(series):
    if series is None: return None
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
            "revenue":          _series_cr(_safe_row(raw_pnl, ["Total Revenue","Revenue"])),
            "ebitda":           _series_cr(_safe_row(raw_pnl, ["EBITDA","Normalized EBITDA"])),
            "operating_profit": _series_cr(_safe_row(raw_pnl, ["Operating Income","EBIT"])),
            "net_profit":       _series_cr(_safe_row(raw_pnl, ["Net Income","Net Income Common Stockholders"])),
            "interest_exp":     _series_cr(_safe_row(raw_pnl, ["Interest Expense"])),
            "other_income":     _series_cr(_safe_row(raw_pnl, ["Other Income Expense","Non Operating Income"])),
            "depreciation":     _series_cr(_safe_row(raw_pnl, ["Reconciled Depreciation","Depreciation And Amortization"])),
        }
        bs = {
            "total_debt":     _series_cr(_safe_row(raw_bs, ["Total Debt","Long Term Debt"])),
            "equity":         _series_cr(_safe_row(raw_bs, ["Stockholders Equity","Common Stock Equity"])),
            "receivables":    _series_cr(_safe_row(raw_bs, ["Accounts Receivable","Net Receivables"])),
            "inventory":      _series_cr(_safe_row(raw_bs, ["Inventory"])),
            "total_assets":   _series_cr(_safe_row(raw_bs, ["Total Assets"])),
            "current_assets": _series_cr(_safe_row(raw_bs, ["Current Assets"])),
            "current_liab":   _series_cr(_safe_row(raw_bs, ["Current Liabilities"])),
            "cash":           _series_cr(_safe_row(raw_bs, ["Cash And Cash Equivalents",
                                         "Cash Cash Equivalents And Short Term Investments"])),
        }
        cf = {
            "cfo":   _series_cr(_safe_row(raw_cf, ["Operating Cash Flow","Cash From Operations"])),
            "capex": _series_cr(_safe_row(raw_cf, ["Capital Expenditure"])),
            "fcf":   _series_cr(_safe_row(raw_cf, ["Free Cash Flow"])),
        }
        return {
            "ticker":               ticker,
            "name":                 info.get("longName") or info.get("shortName") or ticker,
            "sector":               info.get("sector","Unknown"),
            "industry":             info.get("industry","Unknown"),
            "mcap_cr":              _to_cr(info.get("marketCap")),
            "de_ratio":             round(info.get("debtToEquity",0)/100,2) if info.get("debtToEquity") else None,
            "promoter_holding_pct": round(info.get("heldPercentInsiders",0)*100,1),
            "pnl": pnl, "bs": bs, "cf": cf,
        }
    except Exception:
        return None


# ============================================================
#  SECTION 2 — ANALYSIS LAYER
#  Each flag tuple: (severity, title, detail, evidence_list)
#  evidence item: {"panel":"BS"|"PL"|"CF", "label":str,
#                  "series":pd.Series|None, "highlight":"increase"|"decrease"|"neutral"}
# ============================================================

def _cagr(series, years=3):
    if series is None: return None
    s = series.dropna()
    if len(s) < 2: return None
    y = min(years, len(s)-1)
    a, b = float(s.iloc[0]), float(s.iloc[-1])
    if a <= 0 or b <= 0 or y == 0: return None
    return (b/a)**(1/y) - 1

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
    avg_cfo, avg_pat = _avg(cfo,3), _avg(pat,3)
    if avg_cfo is None or avg_pat is None or avg_pat == 0: return flags
    r = avg_cfo / avg_pat
    ev = [{"panel":"PL","label":"Net Profit","series":pat,"highlight":"neutral"},
          {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"decrease"}]
    if r < 0.7:
        flags.append(("HIGH","Low CFO / Net Profit ratio",
            f"3-year avg CFO is only {r:.0%} of reported profit. "
            "Healthy companies generate ≥1x CFO vs profit. "
            "Strong signal of accrual-based earnings inflation.", ev))
    elif r < 0.85:
        flags.append(("MEDIUM",f"Below-average CFO / Net Profit ({r:.0%})",
            f"CFO is {r:.0%} of net profit (3yr avg). Below healthy 85%+ threshold.", ev))
    return flags

def check_receivables_vs_revenue(data):
    flags = []
    rev, rec = data["pnl"].get("revenue"), data["bs"].get("receivables")
    if rev is None or rec is None: return flags
    rg, recg = _cagr(rev,3), _cagr(rec,3)
    if rg is None or recg is None: return flags
    gap = recg - rg
    ev = [{"panel":"PL","label":"Revenue","series":rev,"highlight":"neutral"},
          {"panel":"BS","label":"Receivables","series":rec,"highlight":"increase"}]
    if gap > 0.15:
        flags.append(("HIGH","Receivables growing much faster than revenue",
            f"Revenue 3Y CAGR: {rg:.0%} | Receivables 3Y CAGR: {recg:.0%} — gap of {gap:.0%}. "
            "Classic channel stuffing or aggressive revenue recognition.", ev))
    elif gap > 0.10:
        flags.append(("MEDIUM","Receivables growing faster than revenue",
            f"Revenue CAGR: {rg:.0%} | Receivables CAGR: {recg:.0%} — gap of {gap:.0%}.", ev))
    return flags

def check_debt_vs_cfo(data):
    flags = []
    debt, cfo = data["bs"].get("total_debt"), data["cf"].get("cfo")
    if debt is None or cfo is None: return flags
    d, c = debt.dropna(), cfo.dropna()
    if len(d) < 3 or len(c) < 3: return flags
    ev = [{"panel":"BS","label":"Total Debt","series":debt,"highlight":"increase"},
          {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"decrease"}]
    if float(d.iloc[-1]) > float(d.iloc[0])*1.35 and float(c.iloc[-1]) < float(c.iloc[0])*0.75:
        flags.append(("HIGH","Debt up 35%+ while CFO dropped 25%+",
            "Borrowing significantly more while generating less operating cash. "
            "Classic pre-distress signal. Check if debt is funding operations rather than capex.", ev))
    return flags

def check_inventory_buildup(data):
    flags = []
    inv, rev = data["bs"].get("inventory"), data["pnl"].get("revenue")
    if inv is None or rev is None: return flags
    ig, rg = _cagr(inv,3), _cagr(rev,3)
    if ig is None or rg is None: return flags
    ev = [{"panel":"PL","label":"Revenue","series":rev,"highlight":"neutral"},
          {"panel":"BS","label":"Inventory","series":inv,"highlight":"increase"}]
    if ig - rg > 0.15:
        flags.append(("MEDIUM",f"Inventory growing faster than revenue (gap: {ig-rg:.0%})",
            f"Inventory 3Y CAGR: {ig:.0%} vs Revenue 3Y CAGR: {rg:.0%}. "
            "May signal demand slowdown or obsolete stock.", ev))
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
    ev = [{"panel":"PL","label":"Operating Profit","series":ebit,"highlight":"neutral"},
          {"panel":"PL","label":"Interest Expense","series":intexp,"highlight":"increase"}]
    if icr < 1.5:
        flags.append(("HIGH",f"Dangerously low interest coverage ({icr:.1f}x)",
            f"Operating profit covers interest only {icr:.1f}x. Below 1.5x is danger zone.", ev))
    elif icr < 2.5:
        flags.append(("MEDIUM",f"Weak interest coverage ({icr:.1f}x)",
            f"Coverage of {icr:.1f}x is below comfortable 3x+ threshold.", ev))
    return flags

def check_negative_cfo_vs_profit(data):
    flags = []
    cfo, pat = data["cf"].get("cfo"), data["pnl"].get("net_profit")
    if cfo is None or pat is None: return flags
    neg_cfo = int((cfo.dropna() < 0).sum())
    pos_pat = int((pat.dropna() > 0).sum())
    ev = [{"panel":"PL","label":"Net Profit","series":pat,"highlight":"neutral"},
          {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"decrease"}]
    if neg_cfo >= 2 and pos_pat >= 3:
        flags.append(("HIGH",f"Negative CFO in {neg_cfo} years despite profits",
            f"Reported profits in {pos_pat} years but negative CFO in {neg_cfo} years. "
            "Company is printing paper profits but not generating real cash.", ev))
    return flags

def check_revenue_decline(data):
    flags = []
    rev = data["pnl"].get("revenue")
    if rev is None: return flags
    rg = _cagr(rev,3)
    ev = [{"panel":"PL","label":"Revenue","series":rev,"highlight":"decrease"}]
    if rg is not None and rg < -0.05:
        flags.append(("MEDIUM",f"Revenue declining (3Y CAGR: {rg:.1%})",
            f"Revenue falling at {abs(rg):.1%} per year. Determine if cyclical or structural.", ev))
    return flags

def check_sustained_losses(data):
    flags = []
    pat = data["pnl"].get("net_profit")
    if pat is None: return flags
    s = pat.dropna()
    loss_years = int((s < 0).sum())
    ev = [{"panel":"PL","label":"Net Profit","series":pat,"highlight":"decrease"}]
    if loss_years >= 3:
        flags.append(("HIGH",f"Loss-making in {loss_years} of {len(s)} years",
            "Sustained losses — check if unit economics are at least improving YoY.", ev))
    elif loss_years >= 1:
        flags.append(("MEDIUM",f"Net loss in {loss_years} recent year(s)",
            "Check if one-off or structural. Look at EBITDA to separate operating health.", ev))
    return flags

def check_high_leverage(data):
    flags = []
    de     = data.get("de_ratio")
    sector = data.get("sector","")
    if "financial" in sector.lower() or "bank" in sector.lower(): return flags
    if de is None: return flags
    debt   = data["bs"].get("total_debt")
    equity = data["bs"].get("equity")
    ev = [{"panel":"BS","label":"Total Debt","series":debt,"highlight":"increase"},
          {"panel":"BS","label":"Shareholders Equity","series":equity,"highlight":"decrease"}]
    if de > 2.0:
        flags.append(("HIGH",f"Very high Debt/Equity ({de:.1f}x)",
            f"D/E of {de:.1f}x is well above safe levels (<1x for non-financials). "
            "High leverage amplifies losses and raises solvency risk.", ev))
    elif de > 1.0:
        flags.append(("MEDIUM",f"Elevated Debt/Equity ({de:.1f}x)",
            f"D/E of {de:.1f}x above 1x. Combine with interest coverage for full picture.", ev))
    return flags

def check_low_promoter_holding(data):
    flags = []
    ph = data.get("promoter_holding_pct",0)
    if ph == 0: return flags
    if ph < 25:
        flags.append(("LOW",f"Low promoter / insider holding ({ph:.1f}%)",
            f"Promoters hold only {ph:.1f}%. Watch for any further quarterly decline.", []))
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
    score = sum({"HIGH":2,"MEDIUM":1,"LOW":0}.get(s,0) for s,_,*_ in all_flags)
    return all_flags, min(score,10)


# ============================================================
#  SECTION 3 — UI LAYER
# ============================================================

st.set_page_config(
    page_title="India Red Flag Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About":"Forensic analysis tool for NSE-listed companies. Not investment advice."}
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Sora:wght@300;400;600;700;800&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, .stApp {
    background-color: #0c0f1a !important;
    color: #e8eaf0 !important;
    font-family: 'Sora', sans-serif !important;
}
section[data-testid="stSidebar"], .block-container {
    background: transparent !important; padding-top: 1rem !important;
}
.hero {
    background: linear-gradient(135deg, #0d1b3e 0%, #0c0f1a 60%);
    border: 1px solid #1e2d54; border-radius: 16px;
    padding: 2rem 2.4rem; margin-bottom: 1.8rem;
    position: relative; overflow: hidden;
}
.hero::before {
    content: ''; position: absolute; top: -60px; right: -60px;
    width: 220px; height: 220px;
    background: radial-gradient(circle, rgba(239,68,68,0.15) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-title { font-size: 1.75rem; font-weight: 800; letter-spacing: -0.5px; color: #ffffff; }
.hero-title span { color: #ef4444; }
.hero-sub { font-size: 0.78rem; color: #94a3b8; margin-top: 0.35rem; font-family: 'IBM Plex Mono', monospace; }
.hero-badge {
    display: inline-block; background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.3);
    color: #fca5a5; font-size: 0.65rem; font-family: 'IBM Plex Mono', monospace;
    padding: 3px 10px; border-radius: 4px; margin-right: 8px;
    text-transform: uppercase; letter-spacing: 1px;
}
.search-panel {
    background: #111827; border: 1px solid #1f2937;
    border-radius: 14px; padding: 1.6rem 1.8rem; margin-bottom: 1.4rem;
}
.panel-label {
    font-size: 0.7rem; font-family: 'IBM Plex Mono', monospace;
    color: #64748b; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 0.6rem;
}
/* --- Statement panel table styles --- */
.stmt-panel {
    background: #111827; border: 1px solid #1f2937;
    border-radius: 10px; overflow: hidden; margin-bottom: 0;
}
.stmt-panel-header {
    background: #1a2744; padding: 0.5rem 0.8rem;
    font-size: 0.68rem; font-family: 'IBM Plex Mono', monospace;
    color: #94a3b8; text-transform: uppercase; letter-spacing: 1.5px;
    border-bottom: 1px solid #1f2937;
}
.stmt-header-row {
    display: flex; padding: 0.3rem 0.8rem;
    border-bottom: 1px solid #1a2233;
    font-size: 0.62rem; font-family: 'IBM Plex Mono', monospace; color: #3d5068;
    background: #0f1624;
}
.stmt-header-row .h-label { flex: 1.6; }
.stmt-header-row .h-val   { flex: 1; text-align: right; }
.stmt-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.38rem 0.8rem; border-bottom: 1px solid #0d1422; font-size: 0.76rem;
}
.stmt-row:last-child { border-bottom: none; }
.stmt-row.hl-increase { background: rgba(239,68,68,0.09); border-left: 3px solid #ef4444; }
.stmt-row.hl-decrease { background: rgba(245,158,11,0.09); border-left: 3px solid #f59e0b; }
.stmt-row.hl-neutral  { background: rgba(59,130,246,0.09); border-left: 3px solid #3b82f6; }
.r-label { flex: 1.6; color: #64748b; font-size: 0.74rem; }
.r-label.hl { color: #e2e8f0; font-weight: 600; }
.r-val { flex: 1; text-align: right; font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; color: #4b5563; }
.r-val.positive  { color: #34d399; }
.r-val.negative  { color: #f87171; }
.r-val.hl-red    { color: #ef4444; font-weight: 700; }
.r-val.hl-amber  { color: #f59e0b; font-weight: 700; }
.r-val.hl-blue   { color: #60a5fa; font-weight: 700; }
.chg-tag {
    font-size: 0.58rem; font-family: 'IBM Plex Mono', monospace;
    margin-left: 3px; vertical-align: middle;
}
/* --- Widget overrides --- */
div[data-baseweb="select"] > div {
    background: #1e293b !important; border: 1px solid #334155 !important;
    border-radius: 8px !important; color: #e2e8f0 !important;
}
div[data-baseweb="select"] span { color: #e2e8f0 !important; }
div[data-baseweb="select"] svg { fill: #64748b !important; }
.stTextInput input {
    background: #1e293b !important; border: 1px solid #334155 !important;
    border-radius: 8px !important; color: #e2e8f0 !important;
    font-family: 'IBM Plex Mono', monospace !important; font-size: 0.85rem !important;
}
.stTextInput input::placeholder { color: #475569 !important; }
.stTextInput input:focus { border-color: #3b82f6 !important; box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important; }
label[data-testid="stWidgetLabel"] > div > p, .stTextInput label { color: #94a3b8 !important; font-size: 0.75rem !important; }
.stButton > button {
    background: #1d4ed8 !important; color: #ffffff !important;
    border: none !important; border-radius: 8px !important;
    font-family: 'Sora', sans-serif !important; font-weight: 600 !important;
    font-size: 0.85rem !important; padding: 0.55rem 1.4rem !important;
    transition: background 0.2s, transform 0.15s !important;
}
.stButton > button:hover { background: #2563eb !important; transform: translateY(-1px) !important; }
.stDownloadButton > button {
    background: #064e3b !important; color: #6ee7b7 !important;
    border: 1px solid #065f46 !important; border-radius: 8px !important; font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-list"] {
    background: #111827 !important; border-radius: 10px !important;
    padding: 4px !important; gap: 2px !important; border: 1px solid #1f2937 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important; color: #64748b !important;
    border-radius: 7px !important; font-family: 'Sora', sans-serif !important;
    font-size: 0.82rem !important; font-weight: 500 !important;
    padding: 0.45rem 1rem !important; transition: all 0.2s !important;
}
.stTabs [aria-selected="true"] { background: #1e3a8a !important; color: #ffffff !important; font-weight: 600 !important; }
details {
    background: #111827 !important; border: 1px solid #1f2937 !important;
    border-radius: 12px !important; overflow: hidden !important; margin-bottom: 0.75rem !important;
}
details summary {
    background: #111827 !important; color: #e2e8f0 !important;
    font-weight: 600 !important; font-size: 0.9rem !important;
    padding: 0.9rem 1.2rem !important; cursor: pointer !important;
}
details summary:hover { background: #1e293b !important; }
details[open] summary { border-bottom: 1px solid #1f2937 !important; }
details > div { background: #111827 !important; padding: 1rem 1.2rem !important; }
[data-testid="stMetric"] {
    background: #1e293b !important; border: 1px solid #334155 !important;
    border-radius: 10px !important; padding: 0.75rem 1rem !important;
}
[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-size: 0.72rem !important; }
[data-testid="stMetricValue"] { color: #f1f5f9 !important; font-size: 1.3rem !important; font-weight: 700 !important; }
.stProgress > div > div > div { background: #3b82f6 !important; }
hr { border-color: #1f2937 !important; }
.stCaption, small { color: #64748b !important; font-size: 0.72rem !important; }
.score-card {
    background: #111827; border: 1px solid #1f2937; border-radius: 14px;
    padding: 1.2rem 0.8rem; text-align: center;
    transition: transform 0.2s, border-color 0.2s;
}
.score-card:hover { transform: translateY(-3px); border-color: #334155; }
.ticker-label { font-family: 'IBM Plex Mono', monospace; font-size: 0.65rem; color: #475569; text-transform: uppercase; letter-spacing: 1px; }
.company-name { font-size: 0.82rem; font-weight: 600; color: #cbd5e1; margin: 0.4rem 0; line-height: 1.3; }
.big-score { font-size: 2.5rem; font-weight: 800; line-height: 1; margin: 0.3rem 0; }
.score-denom { font-size: 0.9rem; color: #475569; font-weight: 400; }
.risk-pill {
    display: inline-block; font-size: 0.62rem; font-family: 'IBM Plex Mono', monospace;
    font-weight: 600; letter-spacing: 1.2px; padding: 3px 12px; border-radius: 20px;
    text-transform: uppercase; margin-top: 0.3rem;
}
.flag-count { font-size: 0.68rem; color: #475569; margin-top: 0.5rem; }
.section-heading {
    font-size: 0.7rem; font-family: 'IBM Plex Mono', monospace; color: #475569;
    text-transform: uppercase; letter-spacing: 2px;
    margin: 1.2rem 0 0.7rem; display: flex; align-items: center; gap: 8px;
}
.section-heading::after { content: ''; flex: 1; height: 1px; background: #1f2937; }
.evidence-lede {
    font-size: 0.66rem; font-family: 'IBM Plex Mono', monospace;
    color: #3d5068; text-transform: uppercase; letter-spacing: 1.5px;
    margin: 0.6rem 0 0.4rem 0.1rem;
}
</style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────

def fmt_cr(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    v = float(v)
    if abs(v) >= 100000: return f"₹{v/100000:.1f}L Cr"
    if abs(v) >= 1000:   return f"₹{v/1000:.1f}K Cr"
    return f"₹{v:,.0f} Cr"


def risk_gauge(score):
    color = "#ef4444" if score >= 6 else "#f59e0b" if score >= 3 else "#10b981"
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        title={'text':"Risk Score",'font':{'size':11,'color':'#94a3b8','family':'Sora'}},
        number={'font':{'size':28,'color':color,'family':'Sora'},'suffix':'/10'},
        domain={'x':[0,1],'y':[0,1]},
        gauge={
            'axis':{'range':[0,10],'tickcolor':'#334155','tickfont':{'color':'#475569','size':8}},
            'bar':{'color':color,'thickness':0.28}, 'bgcolor':'#0c0f1a','borderwidth':0,
            'steps':[{'range':[0,3],'color':'rgba(16,185,129,0.08)'},
                     {'range':[3,6],'color':'rgba(245,158,11,0.08)'},
                     {'range':[6,10],'color':'rgba(239,68,68,0.08)'}]
        }
    ))
    fig.update_layout(height=195, margin=dict(t=30,b=5,l=15,r=15),
                      paper_bgcolor='#111827', font=dict(color='#94a3b8'))
    return fig


def score_card_html(symbol, name, score, flag_count):
    risk_label = "HIGH RISK" if score >= 6 else "WATCH" if score >= 3 else "CLEAN"
    sc = "#ef4444" if score >= 6 else "#f59e0b" if score >= 3 else "#10b981"
    r,g,b = (239,68,68) if score>=6 else (245,158,11) if score>=3 else (16,185,129)
    return f"""<div class="score-card">
        <div class="ticker-label">{symbol.replace('.NS','').replace('.BO','')}</div>
        <div class="company-name">{name[:30]}</div>
        <div class="big-score" style="color:{sc};">{score}<span class="score-denom">/10</span></div>
        <div><span class="risk-pill"
            style="background:rgba({r},{g},{b},0.12);border:1px solid rgba({r},{g},{b},0.35);color:{sc};">
            {risk_label}</span></div>
        <div class="flag-count">🚩 {flag_count} flag(s)</div>
    </div>"""


def make_mini_bar(series, title, hl_type):
    """Small bar chart — last bar gets accent colour."""
    if series is None or series.dropna().empty: return None
    s = series.dropna().sort_index()
    years  = [str(d)[:4] for d in s.index]
    values = list(s.values)
    acc = "#ef4444" if hl_type=="increase" else "#f59e0b" if hl_type=="decrease" else "#3b82f6"
    base_rgb = (239,68,68) if hl_type=="increase" else (245,158,11) if hl_type=="decrease" else (59,130,246)
    colors = [f"rgba({base_rgb[0]},{base_rgb[1]},{base_rgb[2]},0.35)"] * len(values)
    colors[-1] = acc
    fig = go.Figure(go.Bar(
        x=years, y=values, marker_color=colors, marker_line_width=0,
        text=[fmt_cr(v) for v in values], textposition='outside',
        textfont=dict(color='#94a3b8', size=8, family='IBM Plex Mono')
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=10, color='#cbd5e1', family='Sora'), x=0.5),
        height=200, margin=dict(t=32, b=8, l=8, r=8),
        paper_bgcolor='#111827', plot_bgcolor='#111827',
        font=dict(color='#94a3b8', family='Sora'),
        xaxis=dict(tickangle=0, tickfont=dict(color='#64748b', size=8), showgrid=False),
        yaxis=dict(gridcolor='#1a2233', zerolinecolor='#334155',
                   tickfont=dict(color='#64748b', size=8), showticklabels=False),
        showlegend=False,
    )
    return fig


# ── Financial statement panel definitions ────────────────────────

PANEL_ROWS = {
    "BS": [
        ("Total Debt",          "total_debt"),
        ("Shareholders Equity", "equity"),
        ("Receivables",         "receivables"),
        ("Inventory",           "inventory"),
        ("Cash & Equivalents",  "cash"),
        ("Current Assets",      "current_assets"),
        ("Current Liabilities", "current_liab"),
        ("Total Assets",        "total_assets"),
    ],
    "PL": [
        ("Revenue",             "revenue"),
        ("EBITDA",              "ebitda"),
        ("Operating Profit",    "operating_profit"),
        ("Interest Expense",    "interest_exp"),
        ("Depreciation",        "depreciation"),
        ("Net Profit",          "net_profit"),
    ],
    "CF": [
        ("Operating CF (CFO)",  "cfo"),
        ("CapEx",               "capex"),
        ("Free Cash Flow",      "fcf"),
    ],
}
PANEL_SRC   = {"BS":"bs","PL":"pnl","CF":"cf"}
PANEL_ICON  = {"BS":"🏦","PL":"📊","CF":"💰"}
PANEL_TITLE = {"BS":"Balance Sheet","PL":"P & L","CF":"Cash Flow"}


def _get_val(data, panel_key, row_key, year_str):
    src = data.get(PANEL_SRC[panel_key], {})
    s   = src.get(row_key)
    if s is None: return None
    s2  = s.dropna()
    for idx in s2.index:
        if str(idx)[:4] == year_str:
            return float(s2[idx])
    return None


def render_stmt_panel(panel_key, data, hl_labels, hl_type_map, n_years=3):
    """
    Render a mini financial statement table.
    hl_labels  : set of label strings to highlight
    hl_type_map: label -> 'increase'|'decrease'|'neutral'
    """
    src   = data.get(PANEL_SRC[panel_key], {})
    rows  = PANEL_ROWS[panel_key]

    # collect years
    all_years = set()
    for _, key in rows:
        s = src.get(key)
        if s is not None:
            for idx in s.dropna().index:
                all_years.add(str(idx)[:4])
    years = sorted(all_years)[-n_years:]
    if not years:
        st.markdown(f'<div class="stmt-panel"><div class="stmt-panel-header">'
                    f'{PANEL_ICON[panel_key]} {PANEL_TITLE[panel_key]}</div>'
                    f'<div class="stmt-row"><span class="r-label" style="color:#3d5068">No data</span></div></div>',
                    unsafe_allow_html=True)
        return

    year_headers = "".join(f'<span class="h-val">{y}</span>' for y in years)
    html = (f'<div class="stmt-panel">'
            f'<div class="stmt-panel-header">{PANEL_ICON[panel_key]} {PANEL_TITLE[panel_key]}</div>'
            f'<div class="stmt-header-row"><span class="h-label">Particulars</span>{year_headers}</div>')

    for label, key in rows:
        is_hl   = label in hl_labels
        hl_type = hl_type_map.get(label, "neutral") if is_hl else None
        row_cls = f"stmt-row hl-{hl_type}" if is_hl else "stmt-row"
        lbl_cls = "r-label hl" if is_hl else "r-label"

        vals_html = ""
        prev_val  = None
        for y in years:
            val = _get_val(data, panel_key, key, y)
            # value colour
            if val is None:
                val_str = "—"
                val_cls = "r-val"
                chg_html = ""
            else:
                val_str = fmt_cr(val)
                if is_hl:
                    val_cls = f"r-val hl-{'red' if hl_type=='increase' else 'amber' if hl_type=='decrease' else 'blue'}"
                elif val < 0:
                    val_cls = "r-val negative"
                else:
                    val_cls = "r-val positive" if val > 0 else "r-val"
                # change tag vs previous year
                chg_html = ""
                if is_hl and prev_val is not None and prev_val != 0:
                    chg = (val - prev_val) / abs(prev_val)
                    arrow = "▲" if chg > 0 else "▼"
                    # for increase-flag: up is bad (red), for decrease-flag: down is bad (red)
                    bad = (chg > 0 and hl_type=="increase") or (chg < 0 and hl_type=="decrease")
                    chg_color = "#ef4444" if bad else "#34d399"
                    chg_html = (f'<span class="chg-tag" style="color:{chg_color}">'
                                f'{arrow}{abs(chg):.0%}</span>')

            vals_html += f'<span class="{val_cls}">{val_str}{chg_html}</span>'
            prev_val = val

        html += f'<div class="{row_cls}"><span class="{lbl_cls}">{label}</span>{vals_html}</div>'

    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_flag_with_evidence(flag_tuple, data):
    sev, title, detail = flag_tuple[0], flag_tuple[1], flag_tuple[2]
    evidence = flag_tuple[3] if len(flag_tuple) > 3 else []

    color_map  = {"HIGH":"#ef4444","MEDIUM":"#f59e0b","LOW":"#3b82f6"}
    bg_map     = {"HIGH":"rgba(220,38,38,0.08)","MEDIUM":"rgba(217,119,6,0.08)","LOW":"rgba(37,99,235,0.08)"}
    border_map = {"HIGH":"rgba(220,38,38,0.3)","MEDIUM":"rgba(217,119,6,0.3)","LOW":"rgba(37,99,235,0.25)"}

    c  = color_map.get(sev,"#94a3b8")
    bg = bg_map.get(sev,"transparent")
    bd = border_map.get(sev,"#334155")

    st.markdown(
        f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;'
        f'padding:0.9rem 1rem;margin-bottom:0.5rem;">'
        f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:0.6rem;font-weight:700;'
        f'color:{c};letter-spacing:1px;text-transform:uppercase;">{sev}</span>'
        f'<div style="font-weight:600;font-size:0.9rem;color:#e2e8f0;margin-top:3px;">{title}</div>'
        f'<div style="font-size:0.78rem;color:#94a3b8;margin-top:4px;line-height:1.55;">{detail}</div>'
        f'</div>', unsafe_allow_html=True)

    if not evidence:
        return

    # Organise which panels need highlighting
    panels_info = {}
    for ev in evidence:
        p = ev["panel"]
        if p not in panels_info:
            panels_info[p] = {"labels": set(), "type_map": {}}
        panels_info[p]["labels"].add(ev["label"])
        panels_info[p]["type_map"][ev["label"]] = ev["highlight"]

    st.markdown('<div class="evidence-lede">↳ Evidence in Financial Statements</div>',
                unsafe_allow_html=True)

    # Always show all 3 panels side by side
    cols = st.columns(3)
    for i, pk in enumerate(["BS","PL","CF"]):
        with cols[i]:
            info = panels_info.get(pk, {"labels":set(),"type_map":{}})
            render_stmt_panel(pk, data, info["labels"], info["type_map"])

    # Mini bar charts for each highlighted series
    ev_series = [e for e in evidence if e.get("series") is not None and
                 not e["series"].dropna().empty]
    if ev_series:
        chart_cols = st.columns(min(3, len(ev_series)))
        for i, ev in enumerate(ev_series[:3]):
            fig = make_mini_bar(ev["series"], ev["label"], ev["highlight"])
            if fig:
                chart_cols[i].plotly_chart(fig, use_container_width=True,
                                           config={"displayModeBar":False})

    st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def analyse_ticker(ticker):
    data = get_company_data(ticker)
    if data is None: return None
    flags, score = run_all_checks(data)
    return {**data, "flags": flags, "score": score}


# ── Bootstrap ─────────────────────────────────────────────────────

with st.spinner("Loading NSE company list…"):
    ALL_COMPANIES = load_nse_company_list()

st.markdown(f"""
<div class="hero">
  <div class="hero-title">India <span>Red Flag</span> Dashboard</div>
  <div class="hero-sub" style="margin-top:0.7rem;">
    <span class="hero-badge">NSE</span>
    <span class="hero-badge">{len(ALL_COMPANIES):,} companies</span>
    <span class="hero-badge">10 forensic checks</span>
    &nbsp;·&nbsp; {datetime.now().strftime('%d %b %Y, %I:%M %p')}
  </div>
</div>""", unsafe_allow_html=True)

tab_search, tab_sector, tab_about = st.tabs(
    ["🔍  Search & Analyse", "📊  Sector Scanner", "ℹ️  About"])


# ═══════════════════════════════════════════════════════════════════
#  TAB 1 — SEARCH & ANALYSE
# ═══════════════════════════════════════════════════════════════════
with tab_search:
    st.markdown('<div class="search-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">Search companies</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([3,1])
    with col1:
        selected_names = st.multiselect(
            "Company name",
            options=sorted(ALL_COMPANIES.keys()),
            placeholder="Type to search by name…",
        )
        manual = st.text_input(
            "Or enter NSE tickers (comma-separated)",
            placeholder="e.g. TATACOMM, ZOMATO, PAYTM"
        )
    with col2:
        st.caption("💡 Select multiple to compare")
        st.caption("📌 No .NS needed")
    st.markdown('</div>', unsafe_allow_html=True)

    tickers = []
    if selected_names:
        tickers += [ALL_COMPANIES[n] for n in selected_names]
    if manual.strip():
        for raw in [t.strip().upper() for t in manual.split(",") if t.strip()]:
            resolved = resolve_ticker(raw)
            if resolved:
                tickers.append(resolved)
            else:
                st.warning(f"⚠️ Could not resolve ticker: **{raw}** — try the dropdown instead.")
    tickers = list(dict.fromkeys(tickers))

    if tickers and st.button(f"Analyse {len(tickers)} company/companies →", type="primary"):
        results = []
        prog = st.progress(0)
        for i, t in enumerate(tickers):
            prog.progress((i+1)/len(tickers), f"Fetching {t}…")
            r = analyse_ticker(t)
            if r:
                results.append(r)
            else:
                st.error(f"No data for **{t}**")
            time.sleep(0.3)
        prog.empty()

        if not results:
            st.error("No results returned. Try different tickers.")
            st.stop()

        results.sort(key=lambda x: x["score"], reverse=True)

        st.markdown('<div class="section-heading">Risk Summary</div>', unsafe_allow_html=True)
        cols = st.columns(min(5, len(results)))
        for idx, r in enumerate(results):
            cols[idx % 5].markdown(
                score_card_html(r["ticker"],r["name"],r["score"],len(r["flags"])),
                unsafe_allow_html=True)
        st.divider()

        for r in results:
            icon = "🔴" if r["score"]>=6 else "🟡" if r["score"]>=3 else "🟢"
            with st.expander(
                f"{icon}  {r['name']}  ({r['ticker'].replace('.NS','')})   |   Score: {r['score']} / 10",
                expanded=(r["score"]>=6)
            ):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Market Cap",    f"₹{r['mcap_cr']:,.0f} Cr" if r["mcap_cr"] else "—")
                    st.metric("Debt / Equity", f"{r['de_ratio']:.2f}x"    if r["de_ratio"] else "—")
                with c2:
                    st.metric("Promoter Holding", f"{r['promoter_holding_pct']:.1f}%" if r["promoter_holding_pct"] else "—")
                    st.metric("Sector", r["sector"])
                with c3:
                    st.plotly_chart(risk_gauge(r["score"]), use_container_width=True,
                                    config={"displayModeBar":False})

                st.markdown('<div class="section-heading">Red Flags with Financial Evidence</div>',
                            unsafe_allow_html=True)
                if not r["flags"]:
                    st.success("✅ No red flags triggered for this company.")
                else:
                    for flag in r["flags"]:
                        render_flag_with_evidence(flag, r)

        df_report = pd.DataFrame([{
            "Ticker":     r["ticker"].replace(".NS",""),
            "Company":    r["name"],
            "Sector":     r["sector"],
            "Mkt Cap Cr": r["mcap_cr"],
            "Score":      r["score"],
            "Flags":      " | ".join([f"{f[0]}: {f[1]}" for f in r["flags"]]) or "None"
        } for r in results])
        buf = io.BytesIO()
        df_report.to_excel(buf, index=False)
        st.download_button("📥 Download Excel Report", buf.getvalue(), file_name="red_flags.xlsx")


# ═══════════════════════════════════════════════════════════════════
#  TAB 2 — SECTOR SCANNER
# ═══════════════════════════════════════════════════════════════════
with tab_sector:
    st.markdown('<div class="section-heading">Sector-wise Health Scan</div>', unsafe_allow_html=True)

    SECTOR_GROUPS = {
        "🏦 Banks":          ["HDFCBANK","ICICIBANK","AXISBANK","YESBANK","KOTAKBANK",
                              "SBIN","INDUSINDBK","FEDERALBNK","BANDHANBNK","IDFCFIRSTB"],
        "💻 IT":             ["TCS","INFY","WIPRO","HCLTECH","TECHM",
                              "LTIM","MPHASIS","PERSISTENT","COFORGE","OFSS"],
        "⚡ Power & Energy": ["NTPC","POWERGRID","ADANIPOWER","TATAPOWER","CESC",
                              "TORNTPOWER","NHPC","SJVN","JSWENERGY","RPOWER"],
        "🏗️ Infrastructure": ["LT","ADANIPORTS","GMRINFRA","IRB","ASHOKA",
                              "KNR","NBCC","RVNL","IRCON","PNC"],
        "🚗 Auto":           ["MARUTI","TATAMOTORS","M&M","BAJAJ-AUTO","EICHERMOT",
                              "HEROMOTOCO","ASHOKLEY","TVSMOTOR","MOTHERSON","BOSCHLTD"],
        "💊 Pharma":         ["SUNPHARMA","DRREDDY","CIPLA","DIVISLAB","AUROPHARMA",
                              "LUPIN","TORNTPHARM","ALKEM","IPCALAB","GLENMARK"],
        "💰 NBFCs":          ["BAJFINANCE","BAJAJFINSV","CHOLAFIN","MUTHOOTFIN","MANAPPURAM",
                              "LTFH","SHRIRAMFIN","ABCAPITAL","IIFL","POONAWALLA"],
        "🛒 FMCG":           ["HINDUNILVR","ITC","NESTLEIND","BRITANNIA","DABUR",
                              "MARICO","COLPAL","GODREJCP","EMAMILTD","TATACONSUM"],
        "🏠 Real Estate":    ["DLF","GODREJPROP","OBEROIRLTY","PRESTIGE","PHOENIXLTD",
                              "BRIGADE","SOBHA","MAHLIFE","LODHA","SUNTECK"],
        "🔩 Metals":         ["TATASTEEL","JSWSTEEL","HINDALCO","SAIL","VEDL",
                              "NMDC","JINDALSTEL","APLAPOLLO","RATNAMANI","HINDCOPPER"],
    }

    chosen = st.selectbox("Select sector", list(SECTOR_GROUPS.keys()))
    if st.button("Scan Sector →", type="primary"):
        sector_tickers = [f"{t}.NS" for t in SECTOR_GROUPS[chosen]]
        results = []
        prog = st.progress(0)
        for i, sym in enumerate(sector_tickers):
            prog.progress((i+1)/len(sector_tickers), f"Scanning {sym}…")
            r = analyse_ticker(sym)
            if r: results.append(r)
            time.sleep(0.2)
        prog.empty()

        if not results:
            st.warning("No data returned.")
            st.stop()

        results.sort(key=lambda x: x["score"], reverse=True)
        st.divider()

        for r in results:
            icon = "🔴" if r["score"]>=6 else "🟡" if r["score"]>=3 else "🟢"
            with st.expander(f"{icon}  {r['name']}   |   Score: {r['score']} / 10"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Market Cap", f"₹{r['mcap_cr']:,.0f} Cr" if r["mcap_cr"] else "—")
                c2.metric("D/E", f"{r['de_ratio']:.2f}x" if r["de_ratio"] else "—")
                c3.metric("Promoter", f"{r['promoter_holding_pct']:.1f}%")
                st.markdown('<div class="section-heading">Red Flags with Financial Evidence</div>',
                            unsafe_allow_html=True)
                if not r["flags"]:
                    st.success("✅ No major red flags detected.")
                else:
                    for flag in r["flags"]:
                        render_flag_with_evidence(flag, r)


# ═══════════════════════════════════════════════════════════════════
#  TAB 3 — ABOUT
# ═══════════════════════════════════════════════════════════════════
with tab_about:
    st.markdown("""
    <div style="max-width:660px;color:#94a3b8;line-height:1.8;font-size:0.88rem;">
    <div class="section-heading">How evidence panels work</div>
    <p>Every red flag is backed by specific rows in the company's financial statements.
    When a flag is triggered, the app automatically shows all three statements —
    <strong style="color:#e2e8f0">Balance Sheet · P&amp;L · Cash Flow</strong> — and highlights
    the exact rows involved:</p>
    <ul style="padding-left:1.2rem;margin-top:0.4rem;">
      <li><strong style="color:#ef4444">Red highlight</strong> = value increasing when it shouldn't
          (e.g. debt rising, receivables growing faster than sales)</li>
      <li><strong style="color:#f59e0b">Amber highlight</strong> = value decreasing when it shouldn't
          (e.g. CFO falling while profits are reported)</li>
      <li><strong style="color:#60a5fa">Blue highlight</strong> = reference metric for context</li>
    </ul>
    <p>% change arrows between years show the direction and magnitude of the move.</p>
    <div class="section-heading">10 Forensic Checks</div>
    <ul style="padding-left:1.2rem;">
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
    <div class="section-heading">Scoring</div>
    <p>HIGH = 2 pts · MEDIUM = 1 pt · LOW = 0 pts · Max capped at 10.</p>
    <div class="section-heading">Disclaimer</div>
    <p>Not investment advice. Data from Yahoo Finance — may lag. Always consult a SEBI-registered advisor.</p>
    </div>""", unsafe_allow_html=True)
