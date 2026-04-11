# ============================================================
#  INDIA RED FLAG DASHBOARD  —  app.py  (v2)
#
#  SECTION 1 — DATA LAYER
#  SECTION 2 — ANALYSIS LAYER
#             2A: Financial Risk Flags  (RED)
#             2B: Manipulation Warning Signals  (PURPLE)
#  SECTION 3 — UI LAYER
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
    from io import StringIO
    sources = [
        {
            "url": "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://www.nseindia.com/",
            },
        },
        {
            "url": "https://raw.githubusercontent.com/punkzberryz/nse-stock-data/main/data/EQUITY_L.csv",
            "headers": {"User-Agent": "Mozilla/5.0"},
        },
        {
            "url": "https://raw.githubusercontent.com/iamsmkr/til/main/nse/EQUITY_L.csv",
            "headers": {"User-Agent": "Mozilla/5.0"},
        },
    ]
    for src in sources:
        try:
            resp = requests.get(src["url"], headers=src["headers"], timeout=15)
            resp.raise_for_status()
            text = resp.text.strip()
            if len(text) < 500:
                continue
            df = pd.read_csv(StringIO(text))
            df.columns = [c.strip() for c in df.columns]
            if "SYMBOL" not in df.columns:
                continue
            name_col = "NAME OF COMPANY" if "NAME OF COMPANY" in df.columns else None
            if name_col is None:
                continue
            company_dict = {}
            for _, row in df.iterrows():
                sym  = str(row["SYMBOL"]).strip()
                name = str(row[name_col]).strip()
                if sym and name and sym != "nan" and name != "nan":
                    company_dict[f"{name}  ({sym})"] = f"{sym}.NS"
            if len(company_dict) > 500:
                return company_dict
        except Exception:
            continue

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
        ("Bajaj Finserv","BAJAJFINSV"),("M&M","M&M"),("HDFCLIFE","HDFCLIFE"),
        ("SBILIFE","SBILIFE"),("ICICIPRULI","ICICIPRULI"),("Nykaa","NYKAA"),
        ("Delhivery","DELHIVERY"),("PolicyBazaar","POLICYBZR"),
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
        raw_qpnl = t.quarterly_financials  # for Q4 seasonality check

        pnl = {
            "revenue":          _series_cr(_safe_row(raw_pnl, ["Total Revenue","Revenue"])),
            "ebitda":           _series_cr(_safe_row(raw_pnl, ["EBITDA","Normalized EBITDA"])),
            "operating_profit": _series_cr(_safe_row(raw_pnl, ["Operating Income","EBIT"])),
            "net_profit":       _series_cr(_safe_row(raw_pnl, ["Net Income","Net Income Common Stockholders"])),
            "interest_exp":     _series_cr(_safe_row(raw_pnl, ["Interest Expense"])),
            "other_income":     _series_cr(_safe_row(raw_pnl, ["Other Income Expense","Non Operating Income"])),
            "depreciation":     _series_cr(_safe_row(raw_pnl, ["Reconciled Depreciation","Depreciation And Amortization"])),
            "gross_profit":     _series_cr(_safe_row(raw_pnl, ["Gross Profit"])),
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
            "goodwill":       _series_cr(_safe_row(raw_bs, ["Goodwill","Goodwill And Other Intangible Assets"])),
            "payables":       _series_cr(_safe_row(raw_bs, ["Accounts Payable","Payables"])),
            "non_current_assets": _series_cr(_safe_row(raw_bs, ["Net PPE","Total Non Current Assets"])),
            "deferred_tax":   _series_cr(_safe_row(raw_bs, ["Deferred Tax Assets","Deferred Income Tax"])),
        }
        cf = {
            "cfo":   _series_cr(_safe_row(raw_cf, ["Operating Cash Flow","Cash From Operations"])),
            "capex": _series_cr(_safe_row(raw_cf, ["Capital Expenditure"])),
            "fcf":   _series_cr(_safe_row(raw_cf, ["Free Cash Flow"])),
            "investing": _series_cr(_safe_row(raw_cf, ["Investing Cash Flow","Cash From Investing Activities"])),
        }

        # Quarterly revenue for Q4 concentration check
        q4_pct = None
        try:
            if raw_qpnl is not None and not raw_qpnl.empty:
                qrev_row = _safe_row(raw_qpnl, ["Total Revenue","Revenue"])
                if qrev_row is not None and len(qrev_row) >= 4:
                    qrev = qrev_row.sort_index(ascending=False)
                    # Most recent 4 quarters
                    last4 = qrev.iloc[:4]
                    total = last4.sum()
                    # Identify which quarter indices are Q4 (month == 3 for Indian FY ending March)
                    q4_vals = [v for d, v in last4.items()
                               if hasattr(d, 'month') and d.month in [3, 12]]
                    if total and q4_vals:
                        q4_pct = sum(q4_vals) / float(total)
        except Exception:
            pass

        return {
            "ticker":               ticker,
            "name":                 info.get("longName") or info.get("shortName") or ticker,
            "sector":               info.get("sector","Unknown"),
            "industry":             info.get("industry","Unknown"),
            "mcap_cr":              _to_cr(info.get("marketCap")),
            "de_ratio":             round(info.get("debtToEquity",0)/100,2) if info.get("debtToEquity") else None,
            "promoter_holding_pct": round(info.get("heldPercentInsiders",0)*100,1),
            "revenue_growth_pct":   info.get("revenueGrowth"),   # YoY as decimal
            "operating_margins":    info.get("operatingMargins"),
            "q4_revenue_pct":       q4_pct,
            "pnl": pnl, "bs": bs, "cf": cf,
        }
    except Exception:
        return None


# ============================================================
#  SECTION 2 — ANALYSIS LAYER
#
#  Each flag: (severity, title, detail, evidence_list)
#  evidence item: {"panel":"BS"|"PL"|"CF", "label":str,
#                  "series":pd.Series|None, "highlight":"increase"|"decrease"|"neutral"}
#
#  FLAG TYPES: "RISK" or "MANIP"
#  Tuple format: (flag_type, severity, title, detail, evidence_list)
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


# ── 2A: FINANCIAL RISK FLAGS ─────────────────────────────────────

def risk_interest_coverage(data):
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
        flags.append(("RISK","HIGH",f"Dangerously low interest coverage ({icr:.1f}x)",
            f"Operating profit covers interest only {icr:.1f}x. Below 1.5x is danger zone.", ev))
    elif icr < 2.5:
        flags.append(("RISK","MEDIUM",f"Weak interest coverage ({icr:.1f}x)",
            f"Coverage of {icr:.1f}x is below comfortable 3x+ threshold.", ev))
    return flags

def risk_high_leverage(data):
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
        flags.append(("RISK","HIGH",f"Very high Debt/Equity ({de:.1f}x)",
            f"D/E of {de:.1f}x is well above safe levels (<1x for non-financials). "
            "High leverage amplifies losses and raises solvency risk.", ev))
    elif de > 1.0:
        flags.append(("RISK","MEDIUM",f"Elevated Debt/Equity ({de:.1f}x)",
            f"D/E of {de:.1f}x above 1x. Combine with interest coverage for full picture.", ev))
    return flags

def risk_sustained_losses(data):
    flags = []
    pat = data["pnl"].get("net_profit")
    if pat is None: return flags
    s = pat.dropna()
    loss_years = int((s < 0).sum())
    ev = [{"panel":"PL","label":"Net Profit","series":pat,"highlight":"decrease"}]
    if loss_years >= 3:
        flags.append(("RISK","HIGH",f"Loss-making in {loss_years} of {len(s)} years",
            "Sustained losses — check if unit economics are at least improving YoY.", ev))
    elif loss_years >= 1:
        flags.append(("RISK","MEDIUM",f"Net loss in {loss_years} recent year(s)",
            "Check if one-off or structural. Look at EBITDA to separate operating health.", ev))
    return flags

def risk_revenue_decline(data):
    flags = []
    rev = data["pnl"].get("revenue")
    if rev is None: return flags
    rg = _cagr(rev,3)
    ev = [{"panel":"PL","label":"Revenue","series":rev,"highlight":"decrease"}]
    if rg is not None and rg < -0.05:
        flags.append(("RISK","MEDIUM",f"Revenue declining (3Y CAGR: {rg:.1%})",
            f"Revenue falling at {abs(rg):.1%} per year. Determine if cyclical or structural.", ev))
    return flags

def risk_debt_vs_cfo(data):
    flags = []
    debt, cfo = data["bs"].get("total_debt"), data["cf"].get("cfo")
    if debt is None or cfo is None: return flags
    d, c = debt.dropna(), cfo.dropna()
    if len(d) < 3 or len(c) < 3: return flags
    ev = [{"panel":"BS","label":"Total Debt","series":debt,"highlight":"increase"},
          {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"decrease"}]
    if float(d.iloc[-1]) > float(d.iloc[0])*1.35 and float(c.iloc[-1]) < float(c.iloc[0])*0.75:
        flags.append(("RISK","HIGH","Debt up 35%+ while CFO dropped 25%+",
            "Borrowing significantly more while generating less operating cash. "
            "Classic pre-distress signal. Check if debt is funding operations rather than capex.", ev))
    return flags

def risk_low_promoter_holding(data):
    flags = []
    ph = data.get("promoter_holding_pct", 0)
    if ph == 0: return flags
    if ph < 25:
        flags.append(("RISK","LOW",f"Low promoter / insider holding ({ph:.1f}%)",
            f"Promoters hold only {ph:.1f}%. Watch for any further quarterly decline.", []))
    return flags

def risk_inventory_buildup(data):
    flags = []
    inv, rev = data["bs"].get("inventory"), data["pnl"].get("revenue")
    if inv is None or rev is None: return flags
    ig, rg = _cagr(inv,3), _cagr(rev,3)
    if ig is None or rg is None: return flags
    ev = [{"panel":"PL","label":"Revenue","series":rev,"highlight":"neutral"},
          {"panel":"BS","label":"Inventory","series":inv,"highlight":"increase"}]
    if ig - rg > 0.15:
        flags.append(("RISK","MEDIUM",f"Inventory growing faster than revenue (gap: {ig-rg:.0%})",
            f"Inventory 3Y CAGR: {ig:.0%} vs Revenue 3Y CAGR: {rg:.0%}. "
            "May signal demand slowdown or obsolete stock.", ev))
    return flags


# ── 2B: MANIPULATION WARNING SIGNALS ─────────────────────────────

def manip_cfo_vs_ebit(data):
    """Operating CF lower than Operating Income — classic manipulation signal."""
    flags = []
    cfo  = data["cf"].get("cfo")
    ebit = data["pnl"].get("operating_profit")
    if cfo is None or ebit is None: return flags
    avg_cfo, avg_ebit = _avg(cfo, 3), _avg(ebit, 3)
    if avg_cfo is None or avg_ebit is None or avg_ebit == 0: return flags
    r = avg_cfo / avg_ebit
    ev = [{"panel":"PL","label":"Operating Profit","series":ebit,"highlight":"neutral"},
          {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"decrease"}]
    if r < 0.6:
        flags.append(("MANIP","HIGH","CFO significantly below Operating Income",
            f"3-yr avg CFO is only {r:.0%} of EBIT. Real operating businesses should convert "
            "most of their operating income into cash. Large persistent gaps suggest non-cash "
            "income recognition, aggressive accruals, or off-balance-sheet liabilities.", ev))
    elif r < 0.85:
        flags.append(("MANIP","MEDIUM",f"CFO below Operating Income ({r:.0%} ratio)",
            f"CFO covers only {r:.0%} of reported operating profit (3yr avg). "
            "Healthy threshold is ≥85%.", ev))
    return flags

def manip_cfo_vs_net_profit(data):
    """CFO/Net Profit divergence — earnings quality signal."""
    flags = []
    cfo, pat = data["cf"].get("cfo"), data["pnl"].get("net_profit")
    if cfo is None or pat is None: return flags
    avg_cfo, avg_pat = _avg(cfo,3), _avg(pat,3)
    if avg_cfo is None or avg_pat is None or avg_pat == 0: return flags
    r = avg_cfo / avg_pat
    ev = [{"panel":"PL","label":"Net Profit","series":pat,"highlight":"neutral"},
          {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"decrease"}]
    if r < 0.7:
        flags.append(("MANIP","HIGH","Low CFO / Net Profit ratio — earnings quality concern",
            f"3-year avg CFO is only {r:.0%} of reported profit. "
            "Healthy companies generate ≥1x CFO vs profit. "
            "Strong signal of accrual-based earnings inflation.", ev))
    elif r < 0.85:
        flags.append(("MANIP","MEDIUM",f"Below-average CFO / Net Profit ratio ({r:.0%})",
            f"CFO is {r:.0%} of net profit (3yr avg). Below healthy 85%+ threshold.", ev))
    return flags

def manip_negative_cfo_with_profit(data):
    """Negative CFO while reporting profits."""
    flags = []
    cfo, pat = data["cf"].get("cfo"), data["pnl"].get("net_profit")
    if cfo is None or pat is None: return flags
    neg_cfo = int((cfo.dropna() < 0).sum())
    pos_pat = int((pat.dropna() > 0).sum())
    ev = [{"panel":"PL","label":"Net Profit","series":pat,"highlight":"neutral"},
          {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"decrease"}]
    if neg_cfo >= 2 and pos_pat >= 3:
        flags.append(("MANIP","HIGH",f"Negative CFO in {neg_cfo} years despite reported profits",
            f"Reported profits in {pos_pat} years but negative CFO in {neg_cfo} years. "
            "Company is printing paper profits but not generating real cash.", ev))
    return flags

def manip_receivables_vs_revenue(data):
    """Receivables growing faster than revenue."""
    flags = []
    rev, rec = data["pnl"].get("revenue"), data["bs"].get("receivables")
    if rev is None or rec is None: return flags
    rg, recg = _cagr(rev,3), _cagr(rec,3)
    if rg is None or recg is None: return flags
    gap = recg - rg
    ev = [{"panel":"PL","label":"Revenue","series":rev,"highlight":"neutral"},
          {"panel":"BS","label":"Receivables","series":rec,"highlight":"increase"}]
    if gap > 0.15:
        flags.append(("MANIP","HIGH","Receivables growing much faster than revenue",
            f"Revenue 3Y CAGR: {rg:.0%} | Receivables 3Y CAGR: {recg:.0%} — gap of {gap:.0%}. "
            "Classic channel stuffing or aggressive revenue recognition.", ev))
    elif gap > 0.08:
        flags.append(("MANIP","MEDIUM","Receivables growing faster than revenue",
            f"Revenue CAGR: {rg:.0%} | Receivables CAGR: {recg:.0%} — gap of {gap:.0%}. "
            "Monitor for sustained divergence.", ev))
    return flags

def manip_revenue_growth_outlier(data):
    """Revenue growth substantially above sector median (proxy: own historical)."""
    flags = []
    rev = data["pnl"].get("revenue")
    reported_growth = data.get("revenue_growth_pct")
    if rev is None: return flags
    rg = _cagr(rev, 3)
    # Without peer data, flag if reported YoY growth is suspiciously high vs own CAGR
    ev = [{"panel":"PL","label":"Revenue","series":rev,"highlight":"neutral"}]
    if reported_growth is not None and rg is not None:
        if reported_growth > 0.35 and rg < 0.10:
            flags.append(("MANIP","MEDIUM","Revenue growth spike vs historical trend",
                f"Latest reported YoY revenue growth ({reported_growth:.0%}) is far above "
                f"the 3-year CAGR ({rg:.0%}). Sudden acceleration without a clear catalyst "
                "may indicate channel stuffing or one-off revenue pulls.", ev))
    elif reported_growth is not None and reported_growth > 0.40:
        flags.append(("MANIP","LOW","Very high revenue growth — verify quality",
            f"Revenue growth of {reported_growth:.0%} YoY warrants scrutiny. "
            "Cross-check against receivables growth and peer comparisons.", ev))
    return flags

def manip_q4_revenue_concentration(data):
    """High proportion of revenue in final quarter."""
    flags = []
    q4_pct = data.get("q4_revenue_pct")
    if q4_pct is None: return flags
    ev = []
    if q4_pct > 0.40:
        flags.append(("MANIP","HIGH",f"Q4 revenue concentration very high ({q4_pct:.0%} of annual)",
            f"Final quarter accounts for {q4_pct:.0%} of annual revenue. Extreme Q4 loading "
            "is a classic sign of channel stuffing, bill-and-hold transactions, or "
            "premature revenue recognition to meet full-year targets.", ev))
    elif q4_pct > 0.32:
        flags.append(("MANIP","MEDIUM",f"Q4 revenue concentration elevated ({q4_pct:.0%} of annual)",
            f"Q4 contributes {q4_pct:.0%} of annual revenue (>32% threshold). "
            "Verify if industry-normal or driven by quarter-end booking patterns.", ev))
    return flags

def manip_margin_anomaly(data):
    """Unexplained boost to operating margin."""
    flags = []
    rev  = data["pnl"].get("revenue")
    ebit = data["pnl"].get("operating_profit")
    if rev is None or ebit is None: return flags
    rev_s = rev.dropna().sort_index()
    ebit_s = ebit.dropna().sort_index()
    # align
    common = rev_s.index.intersection(ebit_s.index)
    if len(common) < 3: return flags
    margins = (ebit_s[common] / rev_s[common]).dropna()
    if len(margins) < 3: return flags
    latest_margin = float(margins.iloc[-1])
    prior_avg     = float(margins.iloc[:-1].mean())
    jump = latest_margin - prior_avg
    ev = [{"panel":"PL","label":"Operating Profit","series":ebit,"highlight":"neutral"},
          {"panel":"PL","label":"Revenue","series":rev,"highlight":"neutral"}]
    if jump > 0.08 and prior_avg < 0.15:
        flags.append(("MANIP","HIGH",
            f"Unexplained operating margin surge (+{jump:.0%} vs prior avg {prior_avg:.0%})",
            f"Operating margin jumped {jump:.0%} in the latest year to {latest_margin:.0%}, "
            "against a prior average of {prior_avg:.0%}. "
            "Absent an obvious structural change, large margin surges may reflect "
            "expense capitalisation, reduced provisions, or aggressive revenue recognition.", ev))
    elif jump > 0.05:
        flags.append(("MANIP","MEDIUM",
            f"Sharp operating margin improvement (+{jump:.0%})",
            f"Margin expanded {jump:.0%} in one year (to {latest_margin:.0%}). "
            "Verify: is this driven by genuine operating leverage or accounting adjustments?", ev))
    return flags

def manip_working_capital_reversal(data):
    """Payables up + inventory down + receivables down simultaneously — WC manipulation."""
    flags = []
    pay = data["bs"].get("payables")
    inv = data["bs"].get("inventory")
    rec = data["bs"].get("receivables")
    cfo = data["cf"].get("cfo")
    if pay is None or inv is None or cfo is None: return flags
    pay_s = pay.dropna().sort_index()
    inv_s = inv.dropna().sort_index()
    cfo_s = cfo.dropna().sort_index()
    if len(pay_s) < 2 or len(inv_s) < 2 or len(cfo_s) < 2: return flags
    pay_up  = float(pay_s.iloc[-1]) > float(pay_s.iloc[-2]) * 1.10
    inv_dn  = float(inv_s.iloc[-1]) < float(inv_s.iloc[-2]) * 0.95
    cfo_up  = float(cfo_s.iloc[-1]) > float(cfo_s.iloc[-2]) * 1.15
    ev_list = [
        {"panel":"BS","label":"Payables","series":pay,"highlight":"increase"},
        {"panel":"BS","label":"Inventory","series":inv,"highlight":"decrease"},
        {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"neutral"},
    ]
    if rec is not None:
        rec_s = rec.dropna().sort_index()
        rec_dn = len(rec_s) >= 2 and float(rec_s.iloc[-1]) < float(rec_s.iloc[-2]) * 0.95
        ev_list.append({"panel":"BS","label":"Receivables","series":rec,"highlight":"decrease"})
    else:
        rec_dn = False
    if pay_up and (inv_dn or rec_dn) and cfo_up:
        flags.append(("MANIP","HIGH","Working capital manipulation pattern detected",
            "Payables rising 10%+ while inventory/receivables shrink — combined with "
            "a sudden CFO boost. This classic pattern artificially inflates operating "
            "cash flow through working capital timing games rather than real operations.", ev_list))
    return flags

def manip_high_goodwill(data):
    """High goodwill relative to total assets."""
    flags = []
    gw  = data["bs"].get("goodwill")
    ta  = data["bs"].get("total_assets")
    if gw is None or ta is None: return flags
    gw_last = _last(gw)
    ta_last = _last(ta)
    if gw_last is None or ta_last is None or ta_last == 0: return flags
    ratio = gw_last / ta_last
    ev = [{"panel":"BS","label":"Goodwill","series":gw,"highlight":"increase"},
          {"panel":"BS","label":"Total Assets","series":ta,"highlight":"neutral"}]
    if ratio > 0.30:
        flags.append(("MANIP","HIGH",f"Very high goodwill relative to assets ({ratio:.0%})",
            f"Goodwill represents {ratio:.0%} of total assets. "
            "Excessive goodwill signals overpaid acquisitions and inflated asset base. "
            "Watch for impairment risks and whether acquisitions are used to inflate revenue.", ev))
    elif ratio > 0.15:
        flags.append(("MANIP","MEDIUM",f"Elevated goodwill-to-assets ratio ({ratio:.0%})",
            f"Goodwill is {ratio:.0%} of total assets. Verify acquisition history and "
            "whether goodwill is tested annually for impairment.", ev))
    return flags

def manip_deferred_tax_swings(data):
    """Large fluctuations in deferred tax assets/liabilities."""
    flags = []
    dt = data["bs"].get("deferred_tax")
    if dt is None: return flags
    s = dt.dropna().sort_index()
    if len(s) < 3: return flags
    changes = s.diff().dropna().abs()
    avg_ta  = _last(data["bs"].get("total_assets")) or 1
    large_swings = int((changes > avg_ta * 0.03).sum())
    ev = [{"panel":"BS","label":"Deferred Tax","series":dt,"highlight":"neutral"}]
    if large_swings >= 2:
        flags.append(("MANIP","MEDIUM","Large recurring deferred tax fluctuations",
            f"Deferred tax assets/liabilities swung by >3% of total assets in "
            f"{large_swings} years. Large or erratic deferred tax movements can signal "
            "income shifting, aggressive tax provisioning, or changing accounting estimates.", ev))
    return flags

def manip_capex_classification(data):
    """High capex relative to CFO — potential expense capitalisation."""
    flags = []
    cfo   = data["cf"].get("cfo")
    capex = data["cf"].get("capex")
    if cfo is None or capex is None: return flags
    avg_cfo   = _avg(cfo, 3)
    avg_capex = _avg(capex.abs() if hasattr(capex,'abs') else capex, 3)
    if avg_cfo is None or avg_capex is None or avg_cfo <= 0: return flags
    ratio = avg_capex / avg_cfo
    ev = [{"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"neutral"},
          {"panel":"CF","label":"CapEx","series":capex,"highlight":"increase"}]
    if ratio > 1.2:
        flags.append(("MANIP","MEDIUM",
            f"CapEx exceeds CFO ({ratio:.1f}x) — possible expense capitalisation",
            f"3-yr avg CapEx is {ratio:.1f}x operating cash flow. While heavy investment "
            "phases are normal, persistently high CapEx vs CFO may indicate expenses "
            "being capitalised (flowing to investing rather than operating activities).", ev))
    return flags


def run_all_checks(data):
    risk_flags  = []
    manip_flags = []

    risk_fns = [
        risk_interest_coverage,
        risk_high_leverage,
        risk_sustained_losses,
        risk_revenue_decline,
        risk_debt_vs_cfo,
        risk_low_promoter_holding,
        risk_inventory_buildup,
    ]
    manip_fns = [
        manip_cfo_vs_ebit,
        manip_cfo_vs_net_profit,
        manip_negative_cfo_with_profit,
        manip_receivables_vs_revenue,
        manip_revenue_growth_outlier,
        manip_q4_revenue_concentration,
        manip_margin_anomaly,
        manip_working_capital_reversal,
        manip_high_goodwill,
        manip_deferred_tax_swings,
        manip_capex_classification,
    ]

    for fn in risk_fns:
        try: risk_flags.extend(fn(data))
        except Exception: pass
    for fn in manip_fns:
        try: manip_flags.extend(fn(data))
        except Exception: pass

    sev_pts = {"HIGH":2,"MEDIUM":1,"LOW":0}
    risk_score  = min(sum(sev_pts.get(f[1],0) for f in risk_flags),  10)
    manip_score = min(sum(sev_pts.get(f[1],0) for f in manip_flags), 10)
    return risk_flags, manip_flags, risk_score, manip_score


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

/* ── Dual Score Cards ── */
.dual-score-wrap {
    display: flex; gap: 16px; margin-bottom: 1rem;
}
.score-card-risk {
    flex: 1; background: #111827;
    border: 1px solid rgba(239,68,68,0.25);
    border-radius: 14px; padding: 1.2rem 1rem; text-align: center;
    transition: transform 0.2s, border-color 0.2s;
}
.score-card-risk:hover { transform: translateY(-3px); border-color: rgba(239,68,68,0.5); }
.score-card-manip {
    flex: 1; background: #111827;
    border: 1px solid rgba(168,85,247,0.25);
    border-radius: 14px; padding: 1.2rem 1rem; text-align: center;
    transition: transform 0.2s, border-color 0.2s;
}
.score-card-manip:hover { transform: translateY(-3px); border-color: rgba(168,85,247,0.5); }
.score-type-label {
    font-size: 0.58rem; font-family: 'IBM Plex Mono', monospace;
    text-transform: uppercase; letter-spacing: 2px; margin-bottom: 0.3rem;
}
.score-type-label.risk  { color: #ef4444; }
.score-type-label.manip { color: #a855f7; }
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

/* ── Flag bucket headers ── */
.bucket-header {
    display: flex; align-items: center; gap: 10px;
    font-size: 0.72rem; font-family: 'IBM Plex Mono', monospace;
    text-transform: uppercase; letter-spacing: 2px;
    margin: 1.2rem 0 0.7rem;
}
.bucket-header::after { content: ''; flex: 1; height: 1px; background: #1f2937; }
.bucket-header.risk  { color: #ef4444; }
.bucket-header.manip { color: #a855f7; }
.bucket-dot-risk  { display:inline-block; width:8px; height:8px; border-radius:50%; background:#ef4444; }
.bucket-dot-manip { display:inline-block; width:8px; height:8px; border-radius:50%; background:#a855f7; }

/* ── Statement panel table styles ── */
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
.r-val.hl-purple { color: #a855f7; font-weight: 700; }
.chg-tag {
    font-size: 0.58rem; font-family: 'IBM Plex Mono', monospace;
    margin-left: 3px; vertical-align: middle;
}

/* ── Widget overrides ── */
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


def risk_gauge(score, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        title={'text':"Score",'font':{'size':11,'color':'#94a3b8','family':'Sora'}},
        number={'font':{'size':28,'color':color,'family':'Sora'},'suffix':'/10'},
        domain={'x':[0,1],'y':[0,1]},
        gauge={
            'axis':{'range':[0,10],'tickcolor':'#334155','tickfont':{'color':'#475569','size':8}},
            'bar':{'color':color,'thickness':0.28}, 'bgcolor':'#0c0f1a','borderwidth':0,
            'steps':[{'range':[0,3],'color':f'rgba({_hex_to_rgb(color)},0.05)'},
                     {'range':[3,6],'color':f'rgba({_hex_to_rgb(color)},0.09)'},
                     {'range':[6,10],'color':f'rgba({_hex_to_rgb(color)},0.14)'}]
        }
    ))
    fig.update_layout(height=180, margin=dict(t=30,b=5,l=15,r=15),
                      paper_bgcolor='#111827', font=dict(color='#94a3b8'))
    return fig

def _hex_to_rgb(hex_color):
    h = hex_color.lstrip('#')
    return ','.join(str(int(h[i:i+2],16)) for i in (0,2,4))

def _score_color(score):
    return "#ef4444" if score >= 6 else "#f59e0b" if score >= 3 else "#10b981"

def _risk_label(score):
    return "HIGH RISK" if score >= 6 else "WATCH" if score >= 3 else "CLEAN"

def dual_score_card_html(ticker, name, risk_score, manip_score, risk_flags, manip_flags):
    rc = _score_color(risk_score)
    mc = "#a855f7" if manip_score >= 6 else "#c084fc" if manip_score >= 3 else "#86efac"
    mc_actual = "#a855f7"  # always purple family for manip
    manip_label = "HIGH CONCERN" if manip_score >= 6 else "SIGNALS PRESENT" if manip_score >= 3 else "CLEAN"
    sym = ticker.replace('.NS','').replace('.BO','')
    rr,rg,rb = (239,68,68) if risk_score>=6 else (245,158,11) if risk_score>=3 else (16,185,129)
    mr,mg,mb = (168,85,247) if manip_score>=6 else (192,132,252) if manip_score>=3 else (134,239,172)
    return f"""
    <div style="display:flex;gap:12px;margin-bottom:0.8rem;">
      <div class="score-card-risk" style="flex:1;">
        <div class="score-type-label risk">🔴 Financial Risk</div>
        <div class="ticker-label">{sym}</div>
        <div class="company-name">{name[:28]}</div>
        <div class="big-score" style="color:{rc};">{risk_score}<span class="score-denom">/10</span></div>
        <div><span class="risk-pill"
            style="background:rgba({rr},{rg},{rb},0.12);border:1px solid rgba({rr},{rg},{rb},0.35);color:{rc};">
            {_risk_label(risk_score)}</span></div>
        <div class="flag-count">🚩 {len(risk_flags)} flag(s)</div>
      </div>
      <div class="score-card-manip" style="flex:1;">
        <div class="score-type-label manip">🟣 Manipulation Signal</div>
        <div class="ticker-label">{sym}</div>
        <div class="company-name">{name[:28]}</div>
        <div class="big-score" style="color:{mc_actual};">{manip_score}<span class="score-denom">/10</span></div>
        <div><span class="risk-pill"
            style="background:rgba({mr},{mg},{mb},0.12);border:1px solid rgba({mr},{mg},{mb},0.35);color:{mc_actual};">
            {manip_label}</span></div>
        <div class="flag-count">⚠️ {len(manip_flags)} signal(s)</div>
      </div>
    </div>"""


def make_mini_bar(series, title, hl_type):
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


PANEL_ROWS = {
    "BS": [
        ("Total Debt",          "total_debt"),
        ("Shareholders Equity", "equity"),
        ("Receivables",         "receivables"),
        ("Inventory",           "inventory"),
        ("Payables",            "payables"),
        ("Cash & Equivalents",  "cash"),
        ("Current Assets",      "current_assets"),
        ("Current Liabilities", "current_liab"),
        ("Goodwill",            "goodwill"),
        ("Deferred Tax",        "deferred_tax"),
        ("Total Assets",        "total_assets"),
    ],
    "PL": [
        ("Revenue",             "revenue"),
        ("Gross Profit",        "gross_profit"),
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
        ("Investing CF",        "investing"),
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
    src   = data.get(PANEL_SRC[panel_key], {})
    rows  = PANEL_ROWS[panel_key]
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
            if val is None:
                val_str = "—"; val_cls = "r-val"; chg_html = ""
            else:
                val_str = fmt_cr(val)
                if is_hl:
                    val_cls = f"r-val hl-{'red' if hl_type=='increase' else 'amber' if hl_type=='decrease' else 'blue'}"
                elif val < 0:
                    val_cls = "r-val negative"
                else:
                    val_cls = "r-val positive" if val > 0 else "r-val"
                chg_html = ""
                if is_hl and prev_val is not None and prev_val != 0:
                    chg = (val - prev_val) / abs(prev_val)
                    arrow = "▲" if chg > 0 else "▼"
                    bad = (chg > 0 and hl_type=="increase") or (chg < 0 and hl_type=="decrease")
                    chg_color = "#ef4444" if bad else "#34d399"
                    chg_html = (f'<span class="chg-tag" style="color:{chg_color}">'
                                f'{arrow}{abs(chg):.0%}</span>')
            vals_html += f'<span class="{val_cls}">{val_str}{chg_html}</span>'
            prev_val = val
        html += f'<div class="{row_cls}"><span class="{lbl_cls}">{label}</span>{vals_html}</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_flag(flag_tuple, data, unique_key: str, flag_type: str = "RISK"):
    """
    flag_tuple: (flag_type, severity, title, detail, evidence_list)
    flag_type: "RISK" or "MANIP"
    """
    _, sev, title, detail = flag_tuple[0], flag_tuple[1], flag_tuple[2], flag_tuple[3]
    evidence = flag_tuple[4] if len(flag_tuple) > 4 else []

    if flag_type == "MANIP":
        color_map  = {"HIGH":"#a855f7","MEDIUM":"#c084fc","LOW":"#ddd6fe"}
        bg_map     = {"HIGH":"rgba(168,85,247,0.08)","MEDIUM":"rgba(192,132,252,0.07)","LOW":"rgba(221,214,254,0.05)"}
        border_map = {"HIGH":"rgba(168,85,247,0.35)","MEDIUM":"rgba(192,132,252,0.25)","LOW":"rgba(221,214,254,0.2)"}
        icon = "⚠️"
    else:
        color_map  = {"HIGH":"#ef4444","MEDIUM":"#f59e0b","LOW":"#3b82f6"}
        bg_map     = {"HIGH":"rgba(220,38,38,0.08)","MEDIUM":"rgba(217,119,6,0.08)","LOW":"rgba(37,99,235,0.08)"}
        border_map = {"HIGH":"rgba(220,38,38,0.3)","MEDIUM":"rgba(217,119,6,0.3)","LOW":"rgba(37,99,235,0.25)"}
        icon = "🚩"

    c  = color_map.get(sev,"#94a3b8")
    bg = bg_map.get(sev,"transparent")
    bd = border_map.get(sev,"#334155")

    st.markdown(
        f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;'
        f'padding:0.9rem 1rem;margin-bottom:0.5rem;">'
        f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:0.6rem;font-weight:700;'
        f'color:{c};letter-spacing:1px;text-transform:uppercase;">{icon} {sev}</span>'
        f'<div style="font-weight:600;font-size:0.9rem;color:#e2e8f0;margin-top:3px;">{title}</div>'
        f'<div style="font-size:0.78rem;color:#94a3b8;margin-top:4px;line-height:1.55;">{detail}</div>'
        f'</div>', unsafe_allow_html=True)

    if not evidence:
        return

    panels_info = {}
    for ev in evidence:
        p = ev["panel"]
        if p not in panels_info:
            panels_info[p] = {"labels": set(), "type_map": {}}
        panels_info[p]["labels"].add(ev["label"])
        panels_info[p]["type_map"][ev["label"]] = ev["highlight"]

    st.markdown('<div class="evidence-lede">↳ Evidence in Financial Statements</div>',
                unsafe_allow_html=True)
    cols = st.columns(3)
    for i, pk in enumerate(["BS","PL","CF"]):
        with cols[i]:
            info = panels_info.get(pk, {"labels":set(),"type_map":{}})
            render_stmt_panel(pk, data, info["labels"], info["type_map"])

    ev_series = [e for e in evidence if e.get("series") is not None and
                 not e["series"].dropna().empty]
    if ev_series:
        chart_cols = st.columns(min(3, len(ev_series)))
        for i, ev in enumerate(ev_series[:3]):
            fig = make_mini_bar(ev["series"], ev["label"], ev["highlight"])
            if fig:
                chart_key = f"chart_{unique_key}_{i}_{ev['label'].replace(' ','_')}"
                chart_cols[i].plotly_chart(fig, use_container_width=True,
                                           config={"displayModeBar":False},
                                           key=chart_key)
    st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def analyse_ticker(ticker):
    data = get_company_data(ticker)
    if data is None: return None
    risk_flags, manip_flags, risk_score, manip_score = run_all_checks(data)
    return {**data, "risk_flags": risk_flags, "manip_flags": manip_flags,
            "risk_score": risk_score, "manip_score": manip_score}


# ── Bootstrap ─────────────────────────────────────────────────────

with st.spinner("Loading NSE company list…"):
    ALL_COMPANIES = load_nse_company_list()

_fallback_mode = len(ALL_COMPANIES) < 500

st.markdown(f"""
<div class="hero">
  <div class="hero-title">India <span>Red Flag</span> Dashboard</div>
  <div class="hero-sub" style="margin-top:0.7rem;">
    <span class="hero-badge">NSE</span>
    <span class="hero-badge">{len(ALL_COMPANIES):,} companies</span>
    <span class="hero-badge">7 risk checks</span>
    <span class="hero-badge">11 manipulation signals</span>
    &nbsp;·&nbsp; {datetime.now().strftime('%d %b %Y, %I:%M %p')}
  </div>
</div>""", unsafe_allow_html=True)

if _fallback_mode:
    st.warning(
        "⚠️ Could not reach NSE or GitHub mirrors. Showing ~65 major companies. "
        "You can still type any NSE ticker directly in the text box below.",
        icon="⚠️"
    )

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

        results.sort(key=lambda x: x["risk_score"] + x["manip_score"], reverse=True)

        # Summary cards
        st.markdown('<div class="section-heading">Risk Summary</div>', unsafe_allow_html=True)
        for r in results:
            st.markdown(
                dual_score_card_html(r["ticker"], r["name"],
                                     r["risk_score"], r["manip_score"],
                                     r["risk_flags"], r["manip_flags"]),
                unsafe_allow_html=True)
        st.divider()

        for r in results:
            risk_icon  = "🔴" if r["risk_score"]>=6  else "🟡" if r["risk_score"]>=3  else "🟢"
            manip_icon = "🟣" if r["manip_score"]>=6 else "🔵" if r["manip_score"]>=3 else "⚪"
            with st.expander(
                f"{risk_icon}{manip_icon}  {r['name']}  ({r['ticker'].replace('.NS','')})  "
                f"|  Risk: {r['risk_score']}/10  ·  Manip: {r['manip_score']}/10",
                expanded=(r["risk_score"]>=6 or r["manip_score"]>=6)
            ):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Market Cap",       f"₹{r['mcap_cr']:,.0f} Cr" if r["mcap_cr"] else "—")
                    st.metric("Debt / Equity",    f"{r['de_ratio']:.2f}x"    if r["de_ratio"] else "—")
                with c2:
                    st.metric("Promoter Holding", f"{r['promoter_holding_pct']:.1f}%" if r["promoter_holding_pct"] else "—")
                    st.metric("Sector",           r["sector"])
                with c3:
                    st.plotly_chart(
                        risk_gauge(r["risk_score"], _score_color(r["risk_score"])),
                        use_container_width=True, config={"displayModeBar":False},
                        key=f"gauge_risk_search_{r['ticker']}")
                    st.caption("🔴 Financial Risk Score")
                with c4:
                    manip_color = "#a855f7" if r["manip_score"]>=6 else "#c084fc" if r["manip_score"]>=3 else "#86efac"
                    st.plotly_chart(
                        risk_gauge(r["manip_score"], manip_color),
                        use_container_width=True, config={"displayModeBar":False},
                        key=f"gauge_manip_search_{r['ticker']}")
                    st.caption("🟣 Manipulation Signal Score")

                # ── Risk flags section ──
                st.markdown(
                    '<div class="bucket-header risk">'
                    '<span class="bucket-dot-risk"></span>'
                    f'Financial Risk Flags &nbsp;({len(r["risk_flags"])})'
                    '</div>', unsafe_allow_html=True)
                if not r["risk_flags"]:
                    st.success("✅ No financial risk flags triggered.")
                else:
                    for fi, flag in enumerate(r["risk_flags"]):
                        render_flag(flag, r, unique_key=f"search_risk_{r['ticker']}_{fi}",
                                    flag_type="RISK")

                # ── Manipulation signals section ──
                st.markdown(
                    '<div class="bucket-header manip">'
                    '<span class="bucket-dot-manip"></span>'
                    f'Manipulation Warning Signals &nbsp;({len(r["manip_flags"])})'
                    '</div>', unsafe_allow_html=True)
                if not r["manip_flags"]:
                    st.success("✅ No manipulation signals detected.")
                else:
                    for fi, flag in enumerate(r["manip_flags"]):
                        render_flag(flag, r, unique_key=f"search_manip_{r['ticker']}_{fi}",
                                    flag_type="MANIP")

        # Download
        df_report = pd.DataFrame([{
            "Ticker":       r["ticker"].replace(".NS",""),
            "Company":      r["name"],
            "Sector":       r["sector"],
            "Mkt Cap Cr":   r["mcap_cr"],
            "Risk Score":   r["risk_score"],
            "Manip Score":  r["manip_score"],
            "Risk Flags":   " | ".join([f"{f[1]}: {f[2]}" for f in r["risk_flags"]]) or "None",
            "Manip Signals":  " | ".join([f"{f[1]}: {f[2]}" for f in r["manip_flags"]]) or "None",
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

        results.sort(key=lambda x: x["risk_score"] + x["manip_score"], reverse=True)
        st.divider()

        for r in results:
            risk_icon  = "🔴" if r["risk_score"]>=6  else "🟡" if r["risk_score"]>=3  else "🟢"
            manip_icon = "🟣" if r["manip_score"]>=6 else "🔵" if r["manip_score"]>=3 else "⚪"
            with st.expander(
                f"{risk_icon}{manip_icon}  {r['name']}  "
                f"|  Risk: {r['risk_score']}/10  ·  Manip: {r['manip_score']}/10"
            ):
                c1, c2, c3 = st.columns(3)
                c1.metric("Market Cap", f"₹{r['mcap_cr']:,.0f} Cr" if r["mcap_cr"] else "—")
                c2.metric("D/E",        f"{r['de_ratio']:.2f}x"    if r["de_ratio"] else "—")
                c3.metric("Promoter",   f"{r['promoter_holding_pct']:.1f}%")

                st.markdown(
                    '<div class="bucket-header risk">'
                    '<span class="bucket-dot-risk"></span>'
                    f'Financial Risk Flags &nbsp;({len(r["risk_flags"])})'
                    '</div>', unsafe_allow_html=True)
                if not r["risk_flags"]:
                    st.success("✅ No financial risk flags.")
                else:
                    for fi, flag in enumerate(r["risk_flags"]):
                        render_flag(flag, r, unique_key=f"sector_risk_{r['ticker']}_{fi}",
                                    flag_type="RISK")

                st.markdown(
                    '<div class="bucket-header manip">'
                    '<span class="bucket-dot-manip"></span>'
                    f'Manipulation Warning Signals &nbsp;({len(r["manip_flags"])})'
                    '</div>', unsafe_allow_html=True)
                if not r["manip_flags"]:
                    st.success("✅ No manipulation signals.")
                else:
                    for fi, flag in enumerate(r["manip_flags"]):
                        render_flag(flag, r, unique_key=f"sector_manip_{r['ticker']}_{fi}",
                                    flag_type="MANIP")


# ═══════════════════════════════════════════════════════════════════
#  TAB 3 — ABOUT
# ═══════════════════════════════════════════════════════════════════
with tab_about:
    st.markdown("""
    <div style="max-width:720px;color:#94a3b8;line-height:1.8;font-size:0.88rem;">

    <div class="section-heading">Two-Track Scoring System</div>
    <p>This dashboard separates two distinct concerns:</p>
    <ul style="padding-left:1.2rem;">
      <li><strong style="color:#ef4444">🔴 Financial Risk Score (0–10)</strong> — measures balance sheet stress,
          solvency risk, and operational deterioration. High scores indicate a company may struggle
          to meet obligations or sustain operations.</li>
      <li><strong style="color:#a855f7">🟣 Manipulation Signal Score (0–10)</strong> — measures the probability
          of accounting shenanigans, earnings management, or misstatement. High scores indicate
          the reported financials may not reflect economic reality.</li>
    </ul>
    <p>A company can have a low risk score but a high manipulation score (superficially healthy
    numbers hiding underlying problems) — or vice versa.</p>

    <div class="section-heading">🔴 Financial Risk Flags (7 checks)</div>
    <ul style="padding-left:1.2rem;">
      <li>Interest coverage ratio (EBIT / Interest)</li>
      <li>Debt / Equity ratio (for non-financials)</li>
      <li>Sustained net losses over multiple years</li>
      <li>Revenue decline (3Y CAGR negative)</li>
      <li>Debt growth alongside CFO decline</li>
      <li>Inventory build-up vs revenue</li>
      <li>Low promoter / insider holding</li>
    </ul>

    <div class="section-heading">🟣 Manipulation Warning Signals (11 checks)</div>
    <ul style="padding-left:1.2rem;">
      <li>CFO significantly below Operating Income (EBIT)</li>
      <li>CFO / Net Profit divergence (earnings quality)</li>
      <li>Negative CFO despite reported profits</li>
      <li>Receivables growing faster than revenue (channel stuffing)</li>
      <li>Revenue growth spike vs own historical trend</li>
      <li>High Q4 revenue concentration (end-of-year stuffing)</li>
      <li>Unexplained operating margin surge</li>
      <li>Working capital manipulation pattern (payables up, WC down, CFO spike)</li>
      <li>High goodwill relative to total assets</li>
      <li>Large deferred tax fluctuations</li>
      <li>CapEx exceeding CFO (possible expense capitalisation)</li>
    </ul>

    <div class="section-heading">Evidence Highlights</div>
    <ul style="padding-left:1.2rem;margin-top:0.4rem;">
      <li><strong style="color:#ef4444">Red</strong> = value increasing when it shouldn't
          (e.g. debt rising, receivables outpacing sales)</li>
      <li><strong style="color:#f59e0b">Amber</strong> = value decreasing when it shouldn't
          (e.g. CFO falling while profits are reported)</li>
      <li><strong style="color:#60a5fa">Blue</strong> = reference metric for context</li>
    </ul>

    <div class="section-heading">Scoring</div>
    <p>HIGH = 2 pts · MEDIUM = 1 pt · LOW = 0 pts · Each score capped at 10.</p>

    <div class="section-heading">Disclaimer</div>
    <p>Not investment advice. Data sourced from Yahoo Finance — may lag official filings.
    Always cross-check with BSE/NSE filings and consult a SEBI-registered advisor.</p>
    </div>""", unsafe_allow_html=True)
