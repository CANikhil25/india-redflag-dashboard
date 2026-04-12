# ============================================================
#  INDIA RED FLAG DASHBOARD  —  app.py  (v3 — Enhanced UI)
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
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import time
import requests
from deep_research_tab import render_deep_research_selector
from datetime import datetime

# ============================================================
#  SECTION 1 — DATA LAYER
# ============================================================

@st.cache_data(ttl=86400, show_spinner=False)
def load_nse_company_list():
    from io import StringIO
    import os

    def _parse_csv_text(text):
        """Parse raw CSV text into {display_name: ticker} dict."""
        df = pd.read_csv(StringIO(text))
        df.columns = [c.strip() for c in df.columns]
        if "SYMBOL" not in df.columns:
            return None
        name_col = "NAME OF COMPANY" if "NAME OF COMPANY" in df.columns else None
        if name_col is None:
            return None
        company_dict = {}
        for _, row in df.iterrows():
            sym  = str(row["SYMBOL"]).strip()
            name = str(row[name_col]).strip()
            if sym and name and sym != "nan" and name != "nan":
                company_dict[f"{name}  ({sym})"] = f"{sym}.NS"
        return company_dict if len(company_dict) > 500 else None

    # ── PRIORITY 1: Local CSV file (most reliable) ──────────────────
    # Place EQUITY_L.csv in the same folder as app.py
    local_paths = [
        "EQUITY_L.csv",          # same folder as app.py
        "./EQUITY_L.csv",        # explicit current directory
        "data/EQUITY_L.csv",     # if you put it in a data/ subfolder
    ]
    for path in local_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read().strip()
                result = _parse_csv_text(text)
                if result:
                    return result   # ✅ loaded from local file
            except Exception:
                continue

    # ── PRIORITY 2: Network sources (tried in order) ─────────────────
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
        {
            "url": "https://raw.githubusercontent.com/harshildarji/NSE-Stocks/master/EQUITY_L.csv",
            "headers": {"User-Agent": "Mozilla/5.0"},
        },
        {
            "url": "https://www1.nseindia.com/content/equities/EQUITY_L.csv",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/119.0.0.0 Safari/537.36",
                "Referer": "https://www1.nseindia.com/",
            },
        },
    ]

    for src in sources:
        try:
            resp = requests.get(src["url"], headers=src["headers"], timeout=15)
            resp.raise_for_status()
            text = resp.text.strip()
            if len(text) < 500:
                continue
            result = _parse_csv_text(text)
            if result:
                return result
        except Exception:
            continue

    # ── PRIORITY 3: Hardcoded fallback (~65 major companies) ─────────
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
    """Return a Series keyed by 4-digit year strings (ascending), or None."""
    if df is None or df.empty: return None
    for name in names:
        if name in df.index:
            row = pd.to_numeric(df.loc[name], errors="coerce").dropna()
            if not row.empty:
                # Normalise index to plain 4-digit year strings
                new_idx = [str(idx)[:4] for idx in row.index]
                row.index = new_idx
                # Drop duplicate years, keep last (most recent filing)
                row = row[~row.index.duplicated(keep="last")]
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
    for attempt in range(3):
        try:
            t = yf.Ticker(ticker)
            # history() is far more reliable than .info for Indian tickers
            hist = t.history(period="5d")
            if hist.empty:
                if attempt < 2:
                    time.sleep(2)
                    continue
                return None

            # Try fetching info — but don't rely on it for validation
            try:
                info = t.info or {}
            except Exception:
                info = {}

            # Build a fallback name from the ticker if info is empty
            fallback_name = ticker.replace(".NS","").replace(".BO","")
            name = info.get("longName") or info.get("shortName") or fallback_name

            raw_pnl  = t.financials
            raw_bs   = t.balance_sheet
            raw_cf   = t.cashflow
            raw_qpnl = t.quarterly_financials

            # If all financial statements are empty, it's not useful
            if (raw_pnl is None or raw_pnl.empty) and \
               (raw_bs  is None or raw_bs.empty)  and \
               (raw_cf  is None or raw_cf.empty):
                if attempt < 2:
                    time.sleep(2)
                    continue
                return None

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
                "total_debt":         _series_cr(_safe_row(raw_bs, ["Total Debt","Long Term Debt"])),
                "equity":             _series_cr(_safe_row(raw_bs, ["Stockholders Equity","Common Stock Equity"])),
                "receivables":        _series_cr(_safe_row(raw_bs, ["Accounts Receivable","Net Receivables"])),
                "inventory":          _series_cr(_safe_row(raw_bs, ["Inventory"])),
                "total_assets":       _series_cr(_safe_row(raw_bs, ["Total Assets"])),
                "current_assets":     _series_cr(_safe_row(raw_bs, ["Current Assets"])),
                "current_liab":       _series_cr(_safe_row(raw_bs, ["Current Liabilities"])),
                "cash":               _series_cr(_safe_row(raw_bs, ["Cash And Cash Equivalents",
                                                 "Cash Cash Equivalents And Short Term Investments"])),
                "goodwill":           _series_cr(_safe_row(raw_bs, ["Goodwill","Goodwill And Other Intangible Assets"])),
                "payables":           _series_cr(_safe_row(raw_bs, ["Accounts Payable","Payables"])),
                "non_current_assets": _series_cr(_safe_row(raw_bs, ["Net PPE","Total Non Current Assets"])),
                "deferred_tax":       _series_cr(_safe_row(raw_bs, ["Deferred Tax Assets","Deferred Income Tax"])),
            }
            cf = {
                "cfo":       _series_cr(_safe_row(raw_cf, ["Operating Cash Flow","Cash From Operations"])),
                "capex":     _series_cr(_safe_row(raw_cf, ["Capital Expenditure"])),
                "fcf":       _series_cr(_safe_row(raw_cf, ["Free Cash Flow"])),
                "investing": _series_cr(_safe_row(raw_cf, ["Investing Cash Flow","Cash From Investing Activities"])),
            }

            q4_pct = None
            try:
                if raw_qpnl is not None and not raw_qpnl.empty:
                    qrev_row = _safe_row(raw_qpnl, ["Total Revenue","Revenue"])
                    if qrev_row is not None and len(qrev_row) >= 4:
                        qrev  = qrev_row.sort_index(ascending=False)
                        last4 = qrev.iloc[:4]
                        total = last4.sum()
                        q4_vals = [v for d, v in last4.items()
                                   if hasattr(d, 'month') and d.month in [3, 12]]
                        if total and q4_vals:
                            q4_pct = sum(q4_vals) / float(total)
            except Exception:
                pass

            # Safe info field extraction with fallbacks
            def _safe_info(key, default=None):
                try:
                    return info.get(key, default)
                except Exception:
                    return default

            de_raw = _safe_info("debtToEquity")
            de_ratio = round(float(de_raw) / 100, 2) if de_raw else None

            insider_raw = _safe_info("heldPercentInsiders", 0)
            try:
                promoter_pct = round(float(insider_raw) * 100, 1)
            except Exception:
                promoter_pct = 0.0

            return {
                "ticker":               ticker,
                "name":                 name,
                "sector":               _safe_info("sector", "Unknown"),
                "industry":             _safe_info("industry", "Unknown"),
                "mcap_cr":              _to_cr(_safe_info("marketCap")),
                "de_ratio":             de_ratio,
                "promoter_holding_pct": promoter_pct,
                "revenue_growth_pct":   _safe_info("revenueGrowth"),
                "operating_margins":    _safe_info("operatingMargins"),
                "q4_revenue_pct":       q4_pct,
                "pnl": pnl, "bs": bs, "cf": cf,
            }

        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            return None

    return None
# ============================================================
#  SECTION 2 — ANALYSIS LAYER
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
            f"D/E of {de:.1f}x is well above safe levels (<1x for non-financials).", ev))
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
            "Borrowing significantly more while generating less operating cash.", ev))
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
            f"Inventory 3Y CAGR: {ig:.0%} vs Revenue 3Y CAGR: {rg:.0%}.", ev))
    return flags


# ── 2B: MANIPULATION WARNING SIGNALS ─────────────────────────────

def manip_cfo_vs_ebit(data):
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
            f"3-yr avg CFO is only {r:.0%} of EBIT. Large persistent gaps suggest non-cash income recognition.", ev))
    elif r < 0.85:
        flags.append(("MANIP","MEDIUM",f"CFO below Operating Income ({r:.0%} ratio)",
            f"CFO covers only {r:.0%} of reported operating profit (3yr avg).", ev))
    return flags

def manip_cfo_vs_net_profit(data):
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
            f"3-year avg CFO is only {r:.0%} of reported profit. Strong signal of accrual-based earnings inflation.", ev))
    elif r < 0.85:
        flags.append(("MANIP","MEDIUM",f"Below-average CFO / Net Profit ratio ({r:.0%})",
            f"CFO is {r:.0%} of net profit (3yr avg). Below healthy 85%+ threshold.", ev))
    return flags

def manip_negative_cfo_with_profit(data):
    flags = []
    cfo, pat = data["cf"].get("cfo"), data["pnl"].get("net_profit")
    if cfo is None or pat is None: return flags
    neg_cfo = int((cfo.dropna() < 0).sum())
    pos_pat = int((pat.dropna() > 0).sum())
    ev = [{"panel":"PL","label":"Net Profit","series":pat,"highlight":"neutral"},
          {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"decrease"}]
    if neg_cfo >= 2 and pos_pat >= 3:
        flags.append(("MANIP","HIGH",f"Negative CFO in {neg_cfo} years despite reported profits",
            f"Reported profits in {pos_pat} years but negative CFO in {neg_cfo} years.", ev))
    return flags

def manip_receivables_vs_revenue(data):
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
            f"Revenue 3Y CAGR: {rg:.0%} | Receivables 3Y CAGR: {recg:.0%} — gap of {gap:.0%}.", ev))
    elif gap > 0.08:
        flags.append(("MANIP","MEDIUM","Receivables growing faster than revenue",
            f"Revenue CAGR: {rg:.0%} | Receivables CAGR: {recg:.0%} — gap of {gap:.0%}.", ev))
    return flags

def manip_revenue_growth_outlier(data):
    flags = []
    rev = data["pnl"].get("revenue")
    reported_growth = data.get("revenue_growth_pct")
    if rev is None: return flags
    rg = _cagr(rev, 3)
    ev = [{"panel":"PL","label":"Revenue","series":rev,"highlight":"neutral"}]
    if reported_growth is not None and rg is not None:
        if reported_growth > 0.35 and rg < 0.10:
            flags.append(("MANIP","MEDIUM","Revenue growth spike vs historical trend",
                f"Latest YoY growth ({reported_growth:.0%}) far above 3-year CAGR ({rg:.0%}).", ev))
    elif reported_growth is not None and reported_growth > 0.40:
        flags.append(("MANIP","LOW","Very high revenue growth — verify quality",
            f"Revenue growth of {reported_growth:.0%} YoY warrants scrutiny.", ev))
    return flags

def manip_q4_revenue_concentration(data):
    flags = []
    q4_pct = data.get("q4_revenue_pct")
    if q4_pct is None: return flags
    ev = []
    if q4_pct > 0.40:
        flags.append(("MANIP","HIGH",f"Q4 revenue concentration very high ({q4_pct:.0%} of annual)",
            f"Final quarter accounts for {q4_pct:.0%} of annual revenue. Classic sign of channel stuffing.", ev))
    elif q4_pct > 0.32:
        flags.append(("MANIP","MEDIUM",f"Q4 revenue concentration elevated ({q4_pct:.0%} of annual)",
            f"Q4 contributes {q4_pct:.0%} of annual revenue (>32% threshold).", ev))
    return flags

def manip_margin_anomaly(data):
    flags = []
    rev  = data["pnl"].get("revenue")
    ebit = data["pnl"].get("operating_profit")
    if rev is None or ebit is None: return flags
    rev_s = rev.dropna().sort_index()
    ebit_s = ebit.dropna().sort_index()
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
            f"Operating margin jumped {jump:.0%} in the latest year to {latest_margin:.0%}.", ev))
    elif jump > 0.05:
        flags.append(("MANIP","MEDIUM",
            f"Sharp operating margin improvement (+{jump:.0%})",
            f"Margin expanded {jump:.0%} in one year (to {latest_margin:.0%}).", ev))
    return flags

def manip_working_capital_reversal(data):
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
            "Payables rising 10%+ while inventory/receivables shrink — combined with a sudden CFO boost.", ev_list))
    return flags

def manip_high_goodwill(data):
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
            f"Goodwill represents {ratio:.0%} of total assets. Risk of impairment and inflated asset base.", ev))
    elif ratio > 0.15:
        flags.append(("MANIP","MEDIUM",f"Elevated goodwill-to-assets ratio ({ratio:.0%})",
            f"Goodwill is {ratio:.0%} of total assets.", ev))
    return flags

def manip_deferred_tax_swings(data):
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
            f"Deferred tax swung by >3% of total assets in {large_swings} years.", ev))
    return flags

def manip_capex_classification(data):
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
            f"3-yr avg CapEx is {ratio:.1f}x operating cash flow.", ev))
    return flags


def run_all_checks(data):
    risk_flags  = []
    manip_flags = []

    risk_fns = [
        risk_interest_coverage, risk_high_leverage, risk_sustained_losses,
        risk_revenue_decline, risk_debt_vs_cfo, risk_low_promoter_holding, risk_inventory_buildup,
    ]
    manip_fns = [
        manip_cfo_vs_ebit, manip_cfo_vs_net_profit, manip_negative_cfo_with_profit,
        manip_receivables_vs_revenue, manip_revenue_growth_outlier, manip_q4_revenue_concentration,
        manip_margin_anomaly, manip_working_capital_reversal, manip_high_goodwill,
        manip_deferred_tax_swings, manip_capex_classification,
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


"""
UI PATCH — paste this into app.py, replacing SECTION 3 (UI LAYER) onwards.
All data/analysis logic (Sections 1 & 2) is unchanged.
"""

# ============================================================
#  SECTION 3 — UI LAYER  (New Landing + Navigation)
#  Paste this into app.py replacing Section 3 onwards
# ============================================================

st.set_page_config(
    page_title="Financial Shenanigans",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "Forensic analysis tool for NSE-listed companies. Not investment advice."}
)

if "all_results_store" not in st.session_state:
    st.session_state["all_results_store"] = []
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "landing"

# ── GLOBAL STYLES ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&family=JetBrains+Mono:wght@400;500;600&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp {
    background: #04060c !important;
    color: #c8cdd8 !important;
    font-family: 'DM Sans', sans-serif !important;
}

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1c2640; border-radius: 2px; }

.block-container {
    background: transparent !important;
    padding: 1rem 2rem 2rem !important;
    max-width: 1400px !important;
}

/* ── HIDE DEFAULT STREAMLIT CHROME ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── LANDING HERO ── */
.hero-eyebrow {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 2rem;
}
.hero-eyebrow-line {
    width: 36px;
    height: 1px;
    background: #dc2626;
}
.hero-eyebrow-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #dc2626;
    letter-spacing: 4px;
    text-transform: uppercase;
}
.hero-title {
    font-family: 'DM Serif Display', serif;
    font-size: 5.5rem;
    line-height: 1.0;
    color: #f0f2f8;
    letter-spacing: -2px;
    margin-bottom: 1.8rem;
}
.hero-title .accent { color: #ef4444; font-style: italic; }
.hero-title .dim { color: #1e2a40; }
.hero-subtitle {
    font-size: 1.2rem;
    color: #4b5e7a;
    max-width: 560px;
    line-height: 1.8;
    font-weight: 300;
    margin-bottom: 3rem;
}

/* ── STAT STRIP ── */
.stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    border: 1px solid #0d1726;
    border-radius: 16px;
    overflow: hidden;
    margin-bottom: 3rem;
}
.stat-cell {
    padding: 1.8rem 2rem;
    border-right: 1px solid #0d1726;
    background: #060a14;
}
.stat-cell:last-child { border-right: none; }
.stat-num {
    font-family: 'DM Serif Display', serif;
    font-size: 2.8rem;
    color: #f0f2f8;
    letter-spacing: -1px;
    line-height: 1;
    margin-bottom: 0.4rem;
}
.stat-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #2d3a55;
    text-transform: uppercase;
    letter-spacing: 2px;
}

/* ── TICKER STRIP ── */
.ticker-outer {
    border-top: 1px solid #0d1726;
    border-bottom: 1px solid #0d1726;
    background: #04060c;
    overflow: hidden;
    padding: 0.8rem 0;
    margin: 2rem 0;
}
.ticker-track {
    display: flex;
    gap: 2.5rem;
    animation: tickerScroll 35s linear infinite;
    white-space: nowrap;
    width: max-content;
}
@keyframes tickerScroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
.ticker-item {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #1e2a40;
    text-transform: uppercase;
    letter-spacing: 2px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
}
.ticker-dot {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: #dc2626;
    flex-shrink: 0;
}

/* ── ABOUT SECTION ── */
.about-section {
    border-top: 1px solid #0d1726;
    padding: 3rem 0 2rem;
    margin-top: 2rem;
}
.about-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 3rem;
}
.about-col-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #1e2a40;
    text-transform: uppercase;
    letter-spacing: 2.5px;
    margin-bottom: 0.9rem;
    padding-bottom: 0.7rem;
    border-bottom: 1px solid #0a1020;
}
.about-col-body {
    font-size: 0.88rem;
    color: #2d3a55;
    line-height: 1.85;
    font-weight: 300;
}

/* ── NAV PAGE TOP BAR ── */
.nav-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 0 2rem;
    border-bottom: 1px solid #0d1726;
    margin-bottom: 3rem;
}
.nav-logo {
    font-family: 'DM Serif Display', serif;
    font-size: 1.3rem;
    color: #f0f2f8;
}
.nav-logo span { color: #ef4444; font-style: italic; }

.nav-section-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #1e2a40;
    text-transform: uppercase;
    letter-spacing: 3px;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 10px;
}
.nav-section-label::before {
    content: '';
    width: 22px;
    height: 1px;
    background: #1e2a40;
}
.nav-heading {
    font-family: 'DM Serif Display', serif;
    font-size: 3.2rem;
    color: #f0f2f8;
    letter-spacing: -1px;
    line-height: 1.1;
    margin-bottom: 1rem;
}
.nav-heading span { color: #ef4444; font-style: italic; }
.nav-subtext {
    font-size: 1rem;
    color: #2d3a55;
    font-weight: 300;
    max-width: 480px;
    line-height: 1.75;
    margin-bottom: 3rem;
}

/* ── FEATURE CARDS ── */
.feat-card {
    border: 1px solid #0d1726;
    border-radius: 20px;
    padding: 2.2rem 2rem 2.5rem;
    background: #060a14;
    position: relative;
    overflow: hidden;
    height: 100%;
    min-height: 380px;
    transition: border-color 0.25s, transform 0.25s;
    cursor: default;
}
.feat-card:hover {
    border-color: #1c2640;
    transform: translateY(-3px);
}
.feat-card-top-line {
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
}
.feat-card-top-line.red    { background: linear-gradient(90deg, transparent, rgba(220,38,38,0.5), transparent); }
.feat-card-top-line.purple { background: linear-gradient(90deg, transparent, rgba(139,92,246,0.5), transparent); }
.feat-card-top-line.blue   { background: linear-gradient(90deg, transparent, rgba(59,130,246,0.5), transparent); }

.feat-num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem;
    color: #1c2640;
    letter-spacing: 2px;
    margin-bottom: 1.8rem;
}
.feat-icon {
    width: 46px;
    height: 46px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 1.6rem;
    font-size: 1.3rem;
}
.feat-icon.red    { background: rgba(220,38,38,0.12); }
.feat-icon.purple { background: rgba(139,92,246,0.12); }
.feat-icon.blue   { background: rgba(59,130,246,0.12); }

.feat-title {
    font-family: 'DM Serif Display', serif;
    font-size: 1.7rem;
    color: #e5e7eb;
    letter-spacing: -0.5px;
    line-height: 1.2;
    margin-bottom: 0.9rem;
}
.feat-desc {
    font-size: 0.88rem;
    color: #2d3a55;
    line-height: 1.8;
    font-weight: 300;
    margin-bottom: 1.8rem;
}
.feat-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 1.8rem;
}
.feat-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.56rem;
    color: #1c2640;
    border: 1px solid #0d1726;
    padding: 4px 10px;
    border-radius: 5px;
    letter-spacing: 0.5px;
}

/* ── WORK PAGES HEADER ── */
.work-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 0 1.5rem;
    border-bottom: 1px solid #0d1726;
    margin-bottom: 1.5rem;
}
.work-logo {
    font-family: 'DM Serif Display', serif;
    font-size: 1.2rem;
    color: #f0f2f8;
}
.work-logo span { color: #ef4444; font-style: italic; }
.work-page-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #2d3a55;
    text-transform: uppercase;
    letter-spacing: 2px;
}

/* ── STREAMLIT BUTTON OVERRIDES ── */
.stButton > button {
    background: transparent !important;
    color: #9ca3af !important;
    border: 1px solid #1c2640 !important;
    border-radius: 12px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 1rem !important;
    padding: 0.75rem 2rem !important;
    width: 100% !important;
    transition: all 0.2s !important;
    letter-spacing: 0.1px !important;
}
.stButton > button:hover {
    background: #0d1726 !important;
    border-color: #dc2626 !important;
    color: #f0f2f8 !important;
}

/* Primary CTA — red filled */
div[data-testid="stButton"]:has(button[kind="primary"]) button,
.stButton > button[kind="primary"] {
    background: #dc2626 !important;
    border-color: #dc2626 !important;
    color: #ffffff !important;
    font-size: 1.05rem !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover {
    background: #ef4444 !important;
    border-color: #ef4444 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 24px rgba(220,38,38,0.35) !important;
}

/* ── EXISTING TOOL WIDGET OVERRIDES ── */
div[data-baseweb="select"] > div {
    background: #0d1120 !important;
    border: 1px solid #1f2d47 !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
}
div[data-baseweb="select"] span { color: #e2e8f0 !important; }
div[data-baseweb="select"] svg  { fill: #4b5563 !important; }
div[data-baseweb="select"]:hover > div { border-color: #2d4070 !important; }

.stTextInput input {
    background: #111827 !important;
    border: 1px solid #1f2d47 !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
    padding: 0.55rem 0.9rem !important;
}
.stTextInput input::placeholder { color: #374151 !important; }
.stTextInput input:focus { border-color: #dc2626 !important; box-shadow: 0 0 0 3px rgba(220,38,38,0.12) !important; }
label[data-testid="stWidgetLabel"] > div > p { color: #6b7280 !important; font-size: 0.75rem !important; }

.stTabs [data-baseweb="tab-list"] {
    background: #0d1120 !important;
    border-radius: 12px !important;
    padding: 5px !important;
    gap: 3px !important;
    border: 1px solid #1a2540 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #4b5563 !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    padding: 0.45rem 1.1rem !important;
}
.stTabs [aria-selected="true"] {
    background: #162048 !important;
    color: #93c5fd !important;
    font-weight: 600 !important;
}

details {
    background: #0d1120 !important;
    border: 1px solid #1a2540 !important;
    border-radius: 14px !important;
    overflow: hidden !important;
    margin-bottom: 0.85rem !important;
}
details summary {
    background: #0d1120 !important;
    color: #c9d1e6 !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    padding: 1rem 1.4rem !important;
    cursor: pointer !important;
    list-style: none !important;
}
details summary::-webkit-details-marker { display: none; }
details[open] summary { border-bottom: 1px solid #1a2540 !important; }
details > div { background: #0d1120 !important; padding: 1.2rem 1.4rem !important; }

[data-testid="stMetric"] {
    background: #0d1120 !important;
    border: 1px solid #1a2540 !important;
    border-radius: 12px !important;
    padding: 0.85rem 1.1rem !important;
}
[data-testid="stMetricLabel"] { color: #6b7280 !important; font-size: 0.72rem !important; }
[data-testid="stMetricValue"] { color: #e5e7eb !important; font-size: 1.3rem !important; font-weight: 700 !important; }

.stDownloadButton > button {
    background: #052e16 !important;
    color: #4ade80 !important;
    border: 1px solid #14532d !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}

hr { border-color: #111827 !important; }
.stCaption, small { color: #4b5563 !important; font-size: 0.72rem !important; }

/* ── FLAG / SCORE CARDS (carry over) ── */
.dual-score-wrap{display:flex;gap:14px;margin-bottom:1.2rem;}
.score-card{flex:1;background:#0d1120;border-radius:16px;padding:1.4rem 1.2rem;text-align:center;position:relative;overflow:hidden;transition:transform 0.2s;}
.score-card:hover{transform:translateY(-3px);}
.score-card.risk{border:1px solid rgba(220,38,38,0.2);}
.score-card.manip{border:1px solid rgba(139,92,246,0.2);}
.score-card.risk::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,transparent,rgba(220,38,38,0.6),transparent);}
.score-card.manip::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,transparent,rgba(139,92,246,0.6),transparent);}
.score-type{font-family:'JetBrains Mono',monospace;font-size:0.6rem;text-transform:uppercase;letter-spacing:2.5px;margin-bottom:0.4rem;}
.score-type.risk{color:#ef4444;}.score-type.manip{color:#a78bfa;}
.score-company{font-size:0.78rem;font-weight:500;color:#9ca3af;margin:0.2rem 0 0.5rem;line-height:1.3;}
.score-ticker{font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:#374151;}
.score-number{font-size:3rem;font-weight:700;line-height:1;margin:0.3rem 0;letter-spacing:-2px;}
.score-denom{font-size:1rem;color:#374151;font-weight:400;letter-spacing:0;}
.score-verdict{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:0.6rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;padding:4px 14px;border-radius:20px;margin-top:0.4rem;}
.score-flags{font-size:0.67rem;color:#374151;margin-top:0.6rem;}
.bucket-header{display:flex;align-items:center;gap:10px;font-family:'JetBrains Mono',monospace;font-size:0.67rem;text-transform:uppercase;letter-spacing:2.5px;margin:1.4rem 0 0.8rem;padding-bottom:0.6rem;border-bottom:1px solid #111827;}
.bucket-header.risk{color:#ef4444;}.bucket-header.manip{color:#a78bfa;}
.b-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}
.b-dot.risk{background:#ef4444;box-shadow:0 0 8px rgba(239,68,68,0.5);}
.b-dot.manip{background:#a78bfa;box-shadow:0 0 8px rgba(167,139,250,0.5);}
.flag-card{border-radius:12px;padding:1rem 1.15rem;margin-bottom:0.6rem;}
.flag-sev{font-family:'JetBrains Mono',monospace;font-size:0.6rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;}
.flag-title{font-size:0.95rem;font-weight:600;color:#e5e7eb;margin-top:4px;line-height:1.4;}
.flag-detail{font-size:0.82rem;color:#6b7280;margin-top:5px;line-height:1.6;}
.stmt-wrap{background:#0d1120;border:1px solid #151e33;border-radius:10px;overflow:hidden;margin-bottom:0;}
.stmt-header{background:#101726;padding:0.5rem 0.9rem;font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:#6b7280;text-transform:uppercase;letter-spacing:2px;border-bottom:1px solid #151e33;}
.stmt-col-row{display:flex;padding:0.28rem 0.9rem;border-bottom:1px solid #0d1726;font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:#2d3a55;background:#090e1a;}
.h-lbl{flex:1.6;}.h-v{flex:1;text-align:right;}
.stmt-row{display:flex;align-items:center;padding:0.35rem 0.9rem;border-bottom:1px solid #0a1020;font-size:0.75rem;transition:background 0.15s;}
.stmt-row:last-child{border-bottom:none;}
.stmt-row:hover{background:rgba(255,255,255,0.015);}
.stmt-row.hl-increase{background:rgba(220,38,38,0.07);border-left:2px solid rgba(220,38,38,0.5);}
.stmt-row.hl-decrease{background:rgba(245,158,11,0.07);border-left:2px solid rgba(245,158,11,0.5);}
.stmt-row.hl-neutral{background:rgba(59,130,246,0.06);border-left:2px solid rgba(59,130,246,0.4);}
.r-lbl{flex:1.6;color:#4b5563;font-size:0.75rem;}.r-lbl.hl{color:#d1d5db;font-weight:600;}
.r-v{flex:1;text-align:right;font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#374151;}
.r-v.pos{color:#34d399;}.r-v.neg{color:#f87171;}.r-v.hl-r{color:#ef4444;font-weight:600;}.r-v.hl-a{color:#f59e0b;font-weight:600;}.r-v.hl-b{color:#60a5fa;font-weight:600;}
.chg{font-family:'JetBrains Mono',monospace;font-size:0.58rem;margin-left:3px;}
.ev-lede{font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:#2d3a55;text-transform:uppercase;letter-spacing:2px;margin:0.7rem 0 0.4rem 0.1rem;}
.sec-head{display:flex;align-items:center;gap:10px;font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#374151;text-transform:uppercase;letter-spacing:2.5px;margin:1.4rem 0 0.8rem;}
.sec-head::after{content:'';flex:1;height:1px;background:#111827;}
</style>
""", unsafe_allow_html=True)


# ── HELPERS ───────────────────────────────────────────────────

def fmt_cr(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    v = float(v)
    if abs(v) >= 100000: return f"₹{v/100000:.1f}L Cr"
    if abs(v) >= 1000:   return f"₹{v/1000:.1f}K Cr"
    return f"₹{v:,.0f} Cr"

def _score_color(s): return "#ef4444" if s >= 6 else "#f59e0b" if s >= 3 else "#22c55e"
def _manip_color(s): return "#a78bfa" if s >= 6 else "#c4b5fd" if s >= 3 else "#6ee7b7"
def _risk_label(s):  return "HIGH RISK" if s >= 6 else "WATCH" if s >= 3 else "CLEAN"
def _manip_label(s): return "HIGH CONCERN" if s >= 6 else "SIGNALS" if s >= 3 else "CLEAN"

def risk_gauge(score, color, title_text):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        title={'text': title_text, 'font': {'size': 11, 'color': '#6b7280', 'family': 'DM Sans'}},
        number={'font': {'size': 32, 'color': color, 'family': 'DM Sans'}, 'suffix': '/10'},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [0, 10], 'tickwidth': 1, 'tickcolor': '#1f2d47', 'tickfont': {'color': '#374151', 'size': 8}},
            'bar': {'color': color, 'thickness': 0.22}, 'bgcolor': '#080b14', 'borderwidth': 0,
            'steps': [{'range': [0,3], 'color': 'rgba(34,197,94,0.06)'},
                      {'range': [3,6], 'color': 'rgba(245,158,11,0.06)'},
                      {'range': [6,10], 'color': 'rgba(239,68,68,0.08)'}],
            'threshold': {'line': {'color': color, 'width': 2}, 'thickness': 0.78, 'value': score}
        }
    ))
    fig.update_layout(height=190, margin=dict(t=38, b=8, l=20, r=20),
                      paper_bgcolor='#0d1120', plot_bgcolor='#0d1120',
                      font=dict(color='#6b7280', family='DM Sans'))
    return fig

def make_trend_bar(series, title, hl_type, show_trendline=True):
    if series is None or series.dropna().empty: return None
    s = series.dropna().sort_index()
    years = [str(d)[:4] for d in s.index]
    values = list(s.values)
    if len(values) < 2: return None
    if hl_type == "increase":   base, last, tl = "rgba(220,38,38,0.25)", "#ef4444", "rgba(239,68,68,0.6)"
    elif hl_type == "decrease": base, last, tl = "rgba(245,158,11,0.25)", "#f59e0b", "rgba(245,158,11,0.6)"
    else:                       base, last, tl = "rgba(59,130,246,0.25)", "#3b82f6", "rgba(59,130,246,0.6)"
    bar_colors = [base] * (len(values)-1) + [last]
    yoy = [""]
    for i in range(1, len(values)):
        p = values[i-1]
        if p and p != 0:
            pct = (values[i]-p)/abs(p)*100
            yoy.append(f"{'+'if pct>0 else''}{pct:.0f}%")
        else: yoy.append("")
    hover = [f"<b>{y}</b><br>₹{v:,.1f} Cr<br>{yoy[i] or '—'}" for i,(y,v) in enumerate(zip(years,values))]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=years, y=values, marker=dict(color=bar_colors, line=dict(width=0)),
                         hovertemplate="%{customdata}<extra></extra>", customdata=hover, showlegend=False))
    if show_trendline and len(values) >= 3:
        xi = np.arange(len(values), dtype=float); ya = np.array(values, dtype=float)
        v = ~np.isnan(ya)
        if v.sum() >= 2:
            m, b = np.polyfit(xi[v], ya[v], 1)
            fig.add_trace(go.Scatter(x=years, y=[m*x+b for x in xi],
                                     mode='lines', line=dict(color=tl, width=2, dash='dot'), showlegend=False))
    ann = []
    for i,(y,val,txt) in enumerate(zip(years,values,yoy)):
        if txt:
            pv = float(txt.replace("+","").replace("%",""))
            c = "#34d399" if pv >= 0 else "#f87171"
            ann.append(dict(x=y,y=val,text=f"<span style='color:{c}'>{txt}</span>",
                            showarrow=False,yanchor="bottom",yshift=5,
                            font=dict(size=8,color=c,family="JetBrains Mono")))
    fig.update_layout(title=dict(text=f"<b>{title}</b>",font=dict(size=11,color='#9ca3af',family='DM Sans'),x=0.5),
                      height=210, margin=dict(t=38,b=12,l=10,r=10),
                      paper_bgcolor='#0d1120', plot_bgcolor='#0d1120',
                      font=dict(color='#6b7280',family='DM Sans'), annotations=ann,
                      xaxis=dict(type='category',tickfont=dict(color='#4b5563',size=9,family='JetBrains Mono'),showgrid=False),
                      yaxis=dict(gridcolor='rgba(26,37,64,0.5)',gridwidth=0.5,zerolinecolor='rgba(26,37,64,0.8)',
                                 tickfont=dict(color='#374151',size=8),showticklabels=False),
                      bargap=0.35, showlegend=False, hovermode='x unified')
    return fig

def make_dual_trend_chart(s1, l1, s2, l2, title):
    if s1 is None or s2 is None: return None
    a = s1.dropna().sort_index(); b = s2.dropna().sort_index()
    if a.empty or b.empty: return None
    y1 = [str(d)[:4] for d in a.index]; y2 = [str(d)[:4] for d in b.index]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=y1,y=list(a.values),mode='lines+markers',name=l1,
                             line=dict(color='#3b82f6',width=2),marker=dict(size=6,color='#3b82f6'),
                             hovertemplate=f"<b>{l1}</b><br>₹%{{y:,.1f}} Cr<extra></extra>"))
    fig.add_trace(go.Scatter(x=y2,y=list(b.values),mode='lines+markers',name=l2,
                             line=dict(color='#ef4444',width=2),marker=dict(size=6,color='#ef4444',symbol='diamond'),
                             hovertemplate=f"<b>{l2}</b><br>₹%{{y:,.1f}} Cr<extra></extra>"))
    for (ys,vs,col) in [(y1,list(a.values),'rgba(59,130,246,0.4)'),(y2,list(b.values),'rgba(239,68,68,0.4)')]:
        xi=np.arange(len(vs),dtype=float); ya=np.array(vs,dtype=float)
        if len(ya)>=3:
            m,c=np.polyfit(xi,ya,1)
            fig.add_trace(go.Scatter(x=ys,y=[m*x+c for x in xi],mode='lines',
                                     line=dict(color=col,width=1.5,dash='dot'),showlegend=False,hoverinfo='skip'))
    fig.update_layout(title=dict(text=f"<b>{title}</b>",font=dict(size=11,color='#9ca3af',family='DM Sans'),x=0.5),
                      height=230, margin=dict(t=38,b=12,l=10,r=10),
                      paper_bgcolor='#0d1120', plot_bgcolor='#0d1120',
                      font=dict(color='#6b7280',family='DM Sans'),
                      legend=dict(font=dict(color='#9ca3af',size=9,family='JetBrains Mono'),
                                  bgcolor='rgba(13,17,32,0.8)',bordercolor='#1a2540',borderwidth=1,
                                  orientation='h',yanchor='bottom',y=1.02,xanchor='center',x=0.5),
                      xaxis=dict(type='category',tickfont=dict(color='#4b5563',size=9,family='JetBrains Mono'),showgrid=False),
                      yaxis=dict(gridcolor='rgba(26,37,64,0.5)',gridwidth=0.5,zerolinecolor='rgba(26,37,64,0.8)',
                                 tickfont=dict(color='#374151',size=8),showticklabels=False),
                      hovermode='x unified')
    return fig

PANEL_ROWS = {
    "BS": [("Total Debt","total_debt"),("Shareholders Equity","equity"),("Receivables","receivables"),
           ("Inventory","inventory"),("Payables","payables"),("Cash & Equivalents","cash"),
           ("Current Assets","current_assets"),("Current Liabilities","current_liab"),
           ("Goodwill","goodwill"),("Deferred Tax","deferred_tax"),("Total Assets","total_assets")],
    "PL": [("Revenue","revenue"),("Gross Profit","gross_profit"),("EBITDA","ebitda"),
           ("Operating Profit","operating_profit"),("Interest Expense","interest_exp"),
           ("Depreciation","depreciation"),("Net Profit","net_profit")],
    "CF": [("Operating CF (CFO)","cfo"),("CapEx","capex"),("Free Cash Flow","fcf"),("Investing CF","investing")],
}
PANEL_SRC={"BS":"bs","PL":"pnl","CF":"cf"}
PANEL_ICON={"BS":"🏦","PL":"📊","CF":"💰"}
PANEL_TITLE={"BS":"Balance Sheet","PL":"P & L","CF":"Cash Flow"}

def _get_val(data, pk, rk, yr):
    s = data.get(PANEL_SRC[pk],{}).get(rk)
    if s is None: return None
    s2 = s.dropna()
    if yr in s2.index: return float(s2[yr])
    for idx in s2.index:
        if str(idx)[:4] == yr: return float(s2[idx])
    return None

def render_stmt_panel(pk, data, hl_labels, hl_type_map, n_years=3):
    src = data.get(PANEL_SRC[pk],{})
    all_years = set()
    for _,key in PANEL_ROWS[pk]:
        s = src.get(key)
        if s is not None:
            for idx in s.dropna().index: all_years.add(str(idx)[:4])
    years = sorted(all_years)[-n_years:]
    if not years:
        st.markdown(f'<div class="stmt-wrap"><div class="stmt-header">{PANEL_ICON[pk]} {PANEL_TITLE[pk]}</div>'
                    f'<div class="stmt-row"><span class="r-lbl" style="color:#2d3a55">No data</span></div></div>',
                    unsafe_allow_html=True)
        return
    yh = "".join(f'<span class="h-v">{y}</span>' for y in years)
    html = (f'<div class="stmt-wrap"><div class="stmt-header">{PANEL_ICON[pk]} {PANEL_TITLE[pk]}</div>'
            f'<div class="stmt-col-row"><span class="h-lbl">Metric</span>{yh}</div>')
    for label,key in PANEL_ROWS[pk]:
        is_hl = label in hl_labels
        hl_type = hl_type_map.get(label,"neutral") if is_hl else None
        row_cls = f"stmt-row hl-{hl_type}" if is_hl else "stmt-row"
        lbl_cls = "r-lbl hl" if is_hl else "r-lbl"
        vals_html = ""; prev_val = None
        for y in years:
            val = _get_val(data, pk, key, y)
            if val is None: val_str="—"; val_cls="r-v"; chg_html=""
            else:
                val_str = fmt_cr(val)
                if is_hl:
                    val_cls = f"r-v hl-{'r' if hl_type=='increase' else 'a' if hl_type=='decrease' else 'b'}"
                elif val < 0: val_cls = "r-v neg"
                else: val_cls = "r-v pos" if val > 0 else "r-v"
                chg_html = ""
                if is_hl and prev_val is not None and prev_val != 0:
                    chg = (val-prev_val)/abs(prev_val)
                    arrow = "▲" if chg > 0 else "▼"
                    bad = (chg>0 and hl_type=="increase") or (chg<0 and hl_type=="decrease")
                    chg_color = "#ef4444" if bad else "#34d399"
                    chg_html = f'<span class="chg" style="color:{chg_color}">{arrow}{abs(chg):.0%}</span>'
            vals_html += f'<span class="{val_cls}">{val_str}{chg_html}</span>'
            prev_val = val
        html += f'<div class="{row_cls}"><span class="{lbl_cls}">{label}</span>{vals_html}</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def dual_score_card_html(ticker, name, risk_score, manip_score, risk_flags, manip_flags):
    rc = _score_color(risk_score); mc = _manip_color(manip_score)
    sym = ticker.replace('.NS','').replace('.BO','')
    def pb(color,a=0.12):
        h=color.lstrip('#'); r,g,b=int(h[0:2],16),int(h[2:4],16),int(h[4:6],16); return f"rgba({r},{g},{b},{a})"
    def pbd(color,a=0.3):
        h=color.lstrip('#'); r,g,b=int(h[0:2],16),int(h[2:4],16),int(h[4:6],16); return f"rgba({r},{g},{b},{a})"
    return f"""<div class="dual-score-wrap">
      <div class="score-card risk">
        <div class="score-type risk">🔴 Financial Risk</div>
        <div class="score-ticker">{sym}</div>
        <div class="score-company">{name[:30]}</div>
        <div class="score-number" style="color:{rc};">{risk_score}<span class="score-denom">/10</span></div>
        <div><span class="score-verdict" style="background:{pb(rc)};border:1px solid {pbd(rc)};color:{rc};">{_risk_label(risk_score)}</span></div>
        <div class="score-flags">🚩 {len(risk_flags)} flag(s)</div>
      </div>
      <div class="score-card manip">
        <div class="score-type manip">🟣 Manip. Signal</div>
        <div class="score-ticker">{sym}</div>
        <div class="score-company">{name[:30]}</div>
        <div class="score-number" style="color:{mc};">{manip_score}<span class="score-denom">/10</span></div>
        <div><span class="score-verdict" style="background:{pb(mc)};border:1px solid {pbd(mc)};color:{mc};">{_manip_label(manip_score)}</span></div>
        <div class="score-flags">⚠️ {len(manip_flags)} signal(s)</div>
      </div>
    </div>"""

def render_flag(flag_tuple, data, unique_key, flag_type="RISK"):
    _, sev, title, detail = flag_tuple[0], flag_tuple[1], flag_tuple[2], flag_tuple[3]
    evidence = flag_tuple[4] if len(flag_tuple) > 4 else []
    if flag_type == "MANIP":
        cm={"HIGH":"#a78bfa","MEDIUM":"#c4b5fd","LOW":"#ddd6fe"}
        bm={"HIGH":"rgba(139,92,246,0.07)","MEDIUM":"rgba(167,139,250,0.06)","LOW":"rgba(221,214,254,0.04)"}
        bd={"HIGH":"rgba(139,92,246,0.3)","MEDIUM":"rgba(167,139,250,0.2)","LOW":"rgba(221,214,254,0.15)"}
        icon="⚠️"
    else:
        cm={"HIGH":"#ef4444","MEDIUM":"#f59e0b","LOW":"#3b82f6"}
        bm={"HIGH":"rgba(220,38,38,0.07)","MEDIUM":"rgba(245,158,11,0.07)","LOW":"rgba(59,130,246,0.06)"}
        bd={"HIGH":"rgba(220,38,38,0.28)","MEDIUM":"rgba(245,158,11,0.28)","LOW":"rgba(59,130,246,0.22)"}
        icon="🚩"
    c=cm.get(sev,"#6b7280"); bg=bm.get(sev,"transparent"); border=bd.get(sev,"#1a2540")
    st.markdown(f'<div class="flag-card" style="background:{bg};border:1px solid {border};">'
                f'<div class="flag-sev" style="color:{c};">{icon} {sev}</div>'
                f'<div class="flag-title">{title}</div>'
                f'<div class="flag-detail">{detail}</div></div>', unsafe_allow_html=True)
    if not evidence: return
    panels_info = {}
    for ev in evidence:
        p=ev["panel"]
        if p not in panels_info: panels_info[p]={"labels":set(),"type_map":{}}
        panels_info[p]["labels"].add(ev["label"]); panels_info[p]["type_map"][ev["label"]]=ev["highlight"]
    st.markdown('<div class="ev-lede">↳ Evidence in financial statements</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for i,pk in enumerate(["BS","PL","CF"]):
        with cols[i]:
            info=panels_info.get(pk,{"labels":set(),"type_map":{}})
            render_stmt_panel(pk,data,info["labels"],info["type_map"])
    ews=[e for e in evidence if e.get("series") is not None and not e["series"].dropna().empty]
    if len(ews)>=2:
        e1,e2=ews[0],ews[1]
        df=make_dual_trend_chart(e1["series"],e1["label"],e2["series"],e2["label"],f"{e1['label']} vs {e2['label']}")
        rem=ews[2:]
    else:
        df=None; rem=ews
    if df:
        cc=st.columns([2,1] if rem else [1])
        cc[0].plotly_chart(df,use_container_width=True,config={"displayModeBar":False},key=f"dual_{unique_key}")
        for i,ev in enumerate(rem[:1]):
            fig=make_trend_bar(ev["series"],ev["label"],ev["highlight"])
            if fig: cc[1].plotly_chart(fig,use_container_width=True,config={"displayModeBar":False},key=f"bar_{unique_key}_{i}")
    else:
        cc=st.columns(min(3,len(ews))) if ews else []
        for i,ev in enumerate(ews[:3]):
            fig=make_trend_bar(ev["series"],ev["label"],ev["highlight"])
            if fig: cc[i].plotly_chart(fig,use_container_width=True,config={"displayModeBar":False},key=f"bar_{unique_key}_{i}")
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

@st.cache_data(ttl=3600, show_spinner=False)
def analyse_ticker(ticker):
    data = get_company_data(ticker)
    if data is None: return None
    rf, mf, rs, ms = run_all_checks(data)
    return {**data, "risk_flags":rf, "manip_flags":mf, "risk_score":rs, "manip_score":ms}


# ═══════════════════════════════════════════════════════════════
#  BOOTSTRAP
# ═══════════════════════════════════════════════════════════════
with st.spinner("Loading NSE company list…"):
    ALL_COMPANIES = load_nse_company_list()
_fallback_mode = len(ALL_COMPANIES) < 500


# ═══════════════════════════════════════════════════════════════
#  REUSABLE ABOUT SECTION
# ═══════════════════════════════════════════════════════════════
def render_about():
    st.markdown("""
    <div class="about-section">
      <div class="about-grid">
        <div>
          <div class="about-col-title">What this does</div>
          <div class="about-col-body">
            Applies 7 financial risk checks and 11 manipulation signal
            detectors to any NSE-listed company. Combines classical forensic
            models — Beneish M-Score, Altman Z-Score — with AI-powered
            governance and concall intelligence.
          </div>
        </div>
        <div>
          <div class="about-col-title">Scoring system</div>
          <div class="about-col-body">
            HIGH flags = 2 pts &nbsp;·&nbsp; MEDIUM = 1 pt &nbsp;·&nbsp; LOW = 0 pts.
            Financial Risk and Manipulation Signal scores each capped at 10.
            Red bars = rising when it shouldn't. Amber = falling when it shouldn't.
          </div>
        </div>
        <div>
          <div class="about-col-title">Disclaimer</div>
          <div class="about-col-body">
            Not investment advice. Data sourced from Yahoo Finance — may lag
            official BSE/NSE filings. Always cross-check with a SEBI-registered
            advisor before acting on any output from this tool.
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  PAGE 1 — LANDING
# ═══════════════════════════════════════════════════════════════
if st.session_state["current_page"] == "landing":

    # Eyebrow
    st.markdown("""
    <div class="hero-eyebrow">
      <div class="hero-eyebrow-line"></div>
      <div class="hero-eyebrow-text">India Equity Forensics</div>
    </div>
    """, unsafe_allow_html=True)

    # Big title
    st.markdown("""
    <div class="hero-title">
      Financial<br>
      <span class="accent">Shenanigans</span><br>
      <span class="dim">/ Detector</span>
    </div>
    """, unsafe_allow_html=True)

    # Subtitle
    st.markdown("""
    <div class="hero-subtitle">
      Institutional-grade red flag analysis for NSE-listed companies.
      Uncover earnings manipulation, balance sheet stress, and governance
      risks before they become headlines.
    </div>
    """, unsafe_allow_html=True)

    # CTA
    col_btn, _, _ = st.columns([1.2, 1, 1])
    with col_btn:
        if st.button("Start Analysing  →", type="primary", use_container_width=True, key="landing_cta"):
            st.session_state["current_page"] = "nav"
            st.rerun()

    st.markdown("<div style='height:2.5rem;'></div>", unsafe_allow_html=True)

    # Stats strip
    n_co = len(ALL_COMPANIES)
    st.markdown(f"""
    <div class="stat-grid">
      <div class="stat-cell">
        <div class="stat-num">{n_co:,}</div>
        <div class="stat-label">NSE Companies</div>
      </div>
      <div class="stat-cell">
        <div class="stat-num">18</div>
        <div class="stat-label">Forensic Checks</div>
      </div>
      <div class="stat-cell">
        <div class="stat-num">2</div>
        <div class="stat-label">Academic Models</div>
      </div>
      <div class="stat-cell">
        <div class="stat-num">Live</div>
        <div class="stat-label">NSE Data Feed</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Ticker strip — built purely in Python to avoid JS brace issues
    items = ["Forensic Finance", "NSE Listed", "7 Risk Checks", "11 Manipulation Signals",
             "Beneish M-Score", "Altman Z-Score", "Sector Scan", "Deep Research",
             "Governance Intel", "Concall Analysis", "Earnings Quality", "Balance Sheet",
             "Cash Flow Checks", "Promoter Pledging", "Working Capital"]
    repeated = items * 6
    ticker_items_html = "".join(
        f'<span class="ticker-item"><span class="ticker-dot"></span>{t}</span>'
        for t in repeated
    )
    st.markdown(f"""
    <div class="ticker-outer">
      <div class="ticker-track">{ticker_items_html}</div>
    </div>
    """, unsafe_allow_html=True)

    render_about()


# ═══════════════════════════════════════════════════════════════
#  PAGE 2 — NAVIGATION  (three equal cards)
# ═══════════════════════════════════════════════════════════════
elif st.session_state["current_page"] == "nav":

    # Top bar with logo + back
    col_logo, col_back = st.columns([5, 1])
    with col_logo:
        st.markdown('<div class="nav-topbar"><div class="nav-logo">Financial <span>Shenanigans</span></div></div>',
                    unsafe_allow_html=True)
    with col_back:
        st.markdown("<div style='padding-top:0.8rem;'>", unsafe_allow_html=True)
        if st.button("← Home", key="nav_back", use_container_width=True):
            st.session_state["current_page"] = "landing"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # Heading
    st.markdown("""
    <div class="nav-section-label">Choose your tool</div>
    <div class="nav-heading">Where do you want<br>to <span>dig</span> today?</div>
    <p class="nav-subtext">
      Three forensic lenses — each revealing a different layer of risk
      hiding inside a company's financials.
    </p>
    """, unsafe_allow_html=True)

    # ── THREE EQUAL CARDS ──────────────────────────────────────
    c1, c2, c3 = st.columns(3, gap="medium")

    with c1:
        st.markdown("""
        <div class="feat-card">
          <div class="feat-card-top-line red"></div>
          <div class="feat-num">01</div>
          <div class="feat-icon red">🔍</div>
          <div class="feat-title">Research &amp;<br>Analysis</div>
          <div class="feat-desc">
            Search any NSE company and run the full 18-point forensic check.
            Compare multiple companies side-by-side with dual risk scores.
          </div>
          <div class="feat-tags">
            <span class="feat-tag">7 Risk Checks</span>
            <span class="feat-tag">11 Manip Signals</span>
            <span class="feat-tag">Dual Score</span>
            <span class="feat-tag">Excel Export</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Open Research & Analysis  →", key="card_search",
                     use_container_width=True, type="primary"):
            st.session_state["current_page"] = "search"
            st.rerun()

    with c2:
        st.markdown("""
        <div class="feat-card">
          <div class="feat-card-top-line purple"></div>
          <div class="feat-num">02</div>
          <div class="feat-icon purple">📊</div>
          <div class="feat-title">Sector<br>Scanner</div>
          <div class="feat-desc">
            Scan an entire sector at once. Ranks every company by combined
            risk score so you know exactly where to look first.
          </div>
          <div class="feat-tags">
            <span class="feat-tag">10 Sectors</span>
            <span class="feat-tag">Heatmap View</span>
            <span class="feat-tag">Batch Analysis</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Open Sector Scanner  →", key="card_sector",
                     use_container_width=True, type="primary"):
            st.session_state["current_page"] = "sector"
            st.rerun()

    with c3:
        st.markdown("""
        <div class="feat-card">
          <div class="feat-card-top-line blue"></div>
          <div class="feat-num">03</div>
          <div class="feat-icon blue">🔬</div>
          <div class="feat-title">Deep<br>Research</div>
          <div class="feat-desc">
            AI-powered deep dive with Beneish M-Score, Altman Z-Score,
            live governance scan, and concall management credibility tracker.
          </div>
          <div class="feat-tags">
            <span class="feat-tag">Beneish M-Score</span>
            <span class="feat-tag">Altman Z-Score</span>
            <span class="feat-tag">Governance AI</span>
            <span class="feat-tag">Concall Intel</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Open Deep Research  →", key="card_deep",
                     use_container_width=True, type="primary"):
            st.session_state["current_page"] = "deep"
            st.rerun()

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    render_about()


# ═══════════════════════════════════════════════════════════════
#  SHARED WORK-PAGE HEADER
# ═══════════════════════════════════════════════════════════════
def _work_header(subtitle, back_key):
    col_logo, col_label, col_back = st.columns([3, 3, 1])
    with col_logo:
        st.markdown(f'<div class="work-topbar"><div class="work-logo">Financial <span>Shenanigans</span></div></div>',
                    unsafe_allow_html=True)
    with col_label:
        st.markdown(f'<div style="padding-top:1rem;"><span class="work-page-label">{subtitle}</span></div>',
                    unsafe_allow_html=True)
    with col_back:
        st.markdown("<div style='padding-top:0.6rem;'>", unsafe_allow_html=True)
        if st.button("← Back", key=back_key, use_container_width=True):
            st.session_state["current_page"] = "nav"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  PAGE 3a — SEARCH & ANALYSE
# ═══════════════════════════════════════════════════════════════
elif st.session_state["current_page"] == "search":

    _work_header("Research & Analysis", "search_back")

    if _fallback_mode:
        st.warning("⚠️ Could not reach NSE. Showing ~65 major companies. You can type any NSE ticker directly.", icon="⚠️")

    col1, col2 = st.columns([3, 1])
    with col1:
        selected_names = st.multiselect("Company name", options=sorted(ALL_COMPANIES.keys()),
                                         placeholder="Type to search by name…")
        manual = st.text_input("Or enter NSE tickers (comma-separated)",
                               placeholder="e.g. TATACOMM, ZOMATO, PAYTM")
    with col2:
        st.caption("💡 Select multiple to compare")
        st.caption("📌 No .NS suffix needed")

    tickers = []
    if selected_names:
        tickers += [ALL_COMPANIES[n] for n in selected_names]
    if manual.strip():
        for raw in [t.strip().upper() for t in manual.split(",") if t.strip()]:
            resolved = resolve_ticker(raw)
            if resolved: tickers.append(resolved)
            else: st.error(f"❌ Could not fetch data for **{raw}**. Yahoo Finance may be rate-limiting. Try again in 30 seconds.")

    if tickers and st.button(f"Analyse {len(tickers)} company/companies →", type="primary"):
        results = []; prog = st.progress(0)
        for i, t in enumerate(tickers):
            prog.progress((i+1)/len(tickers), f"Fetching {t}…")
            r = analyse_ticker(t)
            if r: results.append(r)
            else: st.error(f"No data for **{t}**")
            time.sleep(0.3)
        prog.empty()
        if not results: st.error("No results returned."); st.stop()
        results.sort(key=lambda x: x["risk_score"]+x["manip_score"], reverse=True)
        st.session_state["all_results_store"] = results

        st.markdown('<div class="sec-head">Risk Summary</div>', unsafe_allow_html=True)
        for r in results:
            st.markdown(dual_score_card_html(r["ticker"],r["name"],r["risk_score"],
                                             r["manip_score"],r["risk_flags"],r["manip_flags"]),
                        unsafe_allow_html=True)
        st.divider()

        for r in results:
            ri = "🔴" if r["risk_score"]>=6 else "🟡" if r["risk_score"]>=3 else "🟢"
            mi = "🟣" if r["manip_score"]>=6 else "🔵" if r["manip_score"]>=3 else "⚪"
            with st.expander(f"{ri}{mi}  {r['name']}  ({r['ticker'].replace('.NS','')})  "
                             f"|  Risk: {r['risk_score']}/10  ·  Manip: {r['manip_score']}/10",
                             expanded=(r["risk_score"]>=6 or r["manip_score"]>=6)):
                c1,c2,c3,c4 = st.columns(4)
                with c1:
                    st.metric("Market Cap", f"₹{r['mcap_cr']:,.0f} Cr" if r["mcap_cr"] else "—")
                    st.metric("Debt / Equity", f"{r['de_ratio']:.2f}x" if r["de_ratio"] else "—")
                with c2:
                    st.metric("Promoter Holding", f"{r['promoter_holding_pct']:.1f}%" if r["promoter_holding_pct"] else "—")
                    st.metric("Sector", r["sector"])
                with c3:
                    st.plotly_chart(risk_gauge(r["risk_score"],_score_color(r["risk_score"]),"Financial Risk"),
                                    use_container_width=True, config={"displayModeBar":False},
                                    key=f"gauge_risk_{r['ticker']}")
                    st.caption("🔴 Financial Risk Score")
                with c4:
                    st.plotly_chart(risk_gauge(r["manip_score"],_manip_color(r["manip_score"]),"Manipulation Signal"),
                                    use_container_width=True, config={"displayModeBar":False},
                                    key=f"gauge_manip_{r['ticker']}")
                    st.caption("🟣 Manipulation Signal Score")

                st.markdown(f'<div class="bucket-header risk"><span class="b-dot risk"></span>'
                            f'Financial Risk Flags &nbsp;({len(r["risk_flags"])})</div>', unsafe_allow_html=True)
                if not r["risk_flags"]: st.success("✅ No financial risk flags triggered.")
                else:
                    for fi,flag in enumerate(r["risk_flags"]):
                        render_flag(flag, r, unique_key=f"s_risk_{r['ticker']}_{fi}", flag_type="RISK")

                st.markdown(f'<div class="bucket-header manip"><span class="b-dot manip"></span>'
                            f'Manipulation Warning Signals &nbsp;({len(r["manip_flags"])})</div>', unsafe_allow_html=True)
                if not r["manip_flags"]: st.success("✅ No manipulation signals detected.")
                else:
                    for fi,flag in enumerate(r["manip_flags"]):
                        render_flag(flag, r, unique_key=f"s_manip_{r['ticker']}_{fi}", flag_type="MANIP")

        df_report = pd.DataFrame([{
            "Ticker": r["ticker"].replace(".NS",""), "Company": r["name"], "Sector": r["sector"],
            "Mkt Cap Cr": r["mcap_cr"], "Risk Score": r["risk_score"], "Manip Score": r["manip_score"],
            "Risk Flags": " | ".join([f"{f[1]}: {f[2]}" for f in r["risk_flags"]]) or "None",
            "Manip Signals": " | ".join([f"{f[1]}: {f[2]}" for f in r["manip_flags"]]) or "None",
        } for r in results])
        buf = io.BytesIO(); df_report.to_excel(buf, index=False)
        st.download_button("📥 Download Excel Report", buf.getvalue(), file_name="red_flags.xlsx")

    render_about()


# ═══════════════════════════════════════════════════════════════
#  PAGE 3b — SECTOR SCANNER
# ═══════════════════════════════════════════════════════════════
elif st.session_state["current_page"] == "sector":

    _work_header("Sector Scanner", "sector_back")

    SECTOR_GROUPS = {
        "🏦 Banks":          ["HDFCBANK","ICICIBANK","AXISBANK","YESBANK","KOTAKBANK","SBIN","INDUSINDBK","FEDERALBNK","BANDHANBNK","IDFCFIRSTB"],
        "💻 IT":             ["TCS","INFY","WIPRO","HCLTECH","TECHM","LTIM","MPHASIS","PERSISTENT","COFORGE","OFSS"],
        "⚡ Power & Energy": ["NTPC","POWERGRID","ADANIPOWER","TATAPOWER","CESC","TORNTPOWER","NHPC","SJVN","JSWENERGY","RPOWER"],
        "🏗️ Infrastructure": ["LT","ADANIPORTS","GMRINFRA","IRB","ASHOKA","KNR","NBCC","RVNL","IRCON","PNC"],
        "🚗 Auto":           ["MARUTI","TATAMOTORS","M&M","BAJAJ-AUTO","EICHERMOT","HEROMOTOCO","ASHOKLEY","TVSMOTOR","MOTHERSON","BOSCHLTD"],
        "💊 Pharma":         ["SUNPHARMA","DRREDDY","CIPLA","DIVISLAB","AUROPHARMA","LUPIN","TORNTPHARM","ALKEM","IPCALAB","GLENMARK"],
        "💰 NBFCs":          ["BAJFINANCE","BAJAJFINSV","CHOLAFIN","MUTHOOTFIN","MANAPPURAM","LTFH","SHRIRAMFIN","ABCAPITAL","IIFL","POONAWALLA"],
        "🛒 FMCG":           ["HINDUNILVR","ITC","NESTLEIND","BRITANNIA","DABUR","MARICO","COLPAL","GODREJCP","EMAMILTD","TATACONSUM"],
        "🏠 Real Estate":    ["DLF","GODREJPROP","OBEROIRLTY","PRESTIGE","PHOENIXLTD","BRIGADE","SOBHA","MAHLIFE","LODHA","SUNTECK"],
        "🔩 Metals":         ["TATASTEEL","JSWSTEEL","HINDALCO","SAIL","VEDL","NMDC","JINDALSTEL","APLAPOLLO","RATNAMANI","HINDCOPPER"],
    }

    chosen = st.selectbox("Select sector", list(SECTOR_GROUPS.keys()))
    if st.button("Scan Sector →", type="primary"):
        sector_tickers = [f"{t}.NS" for t in SECTOR_GROUPS[chosen]]
        results = []; prog = st.progress(0)
        for i,sym in enumerate(sector_tickers):
            prog.progress((i+1)/len(sector_tickers), f"Scanning {sym}…")
            r = analyse_ticker(sym)
            if r: results.append(r)
            time.sleep(0.2)
        prog.empty()
        if not results: st.warning("No data returned."); st.stop()
        results.sort(key=lambda x: x["risk_score"]+x["manip_score"], reverse=True)
        st.session_state["all_results_store"] = results

        st.markdown('<div class="sec-head">Sector Overview</div>', unsafe_allow_html=True)
        overview_data = []
        for r in results:
            re = "🔴" if r["risk_score"]>=6 else "🟡" if r["risk_score"]>=3 else "🟢"
            me = "🟣" if r["manip_score"]>=6 else "🔵" if r["manip_score"]>=3 else "⚪"
            overview_data.append({"Company":r["name"][:22],"Risk":f"{re} {r['risk_score']}/10",
                                   "Manip.":f"{me} {r['manip_score']}/10","Mkt Cap":fmt_cr(r["mcap_cr"]),
                                   "D/E":f"{r['de_ratio']:.2f}x" if r["de_ratio"] else "—",
                                   "Promoter %":f"{r['promoter_holding_pct']:.1f}%" if r["promoter_holding_pct"] else "—"})
        st.dataframe(pd.DataFrame(overview_data), use_container_width=True, hide_index=True)
        st.divider()

        for r in results:
            ri="🔴" if r["risk_score"]>=6 else "🟡" if r["risk_score"]>=3 else "🟢"
            mi="🟣" if r["manip_score"]>=6 else "🔵" if r["manip_score"]>=3 else "⚪"
            with st.expander(f"{ri}{mi}  {r['name']}  |  Risk: {r['risk_score']}/10  ·  Manip: {r['manip_score']}/10"):
                c1,c2,c3 = st.columns(3)
                c1.metric("Market Cap", f"₹{r['mcap_cr']:,.0f} Cr" if r["mcap_cr"] else "—")
                c2.metric("D/E", f"{r['de_ratio']:.2f}x" if r["de_ratio"] else "—")
                c3.metric("Promoter", f"{r['promoter_holding_pct']:.1f}%")
                st.markdown(f'<div class="bucket-header risk"><span class="b-dot risk"></span>'
                            f'Financial Risk Flags &nbsp;({len(r["risk_flags"])})</div>', unsafe_allow_html=True)
                if not r["risk_flags"]: st.success("✅ No financial risk flags.")
                else:
                    for fi,flag in enumerate(r["risk_flags"]):
                        render_flag(flag,r,unique_key=f"sec_risk_{r['ticker']}_{fi}",flag_type="RISK")
                st.markdown(f'<div class="bucket-header manip"><span class="b-dot manip"></span>'
                            f'Manipulation Warning Signals &nbsp;({len(r["manip_flags"])})</div>', unsafe_allow_html=True)
                if not r["manip_flags"]: st.success("✅ No manipulation signals.")
                else:
                    for fi,flag in enumerate(r["manip_flags"]):
                        render_flag(flag,r,unique_key=f"sec_manip_{r['ticker']}_{fi}",flag_type="MANIP")

    render_about()


# ═══════════════════════════════════════════════════════════════
#  PAGE 3c — DEEP RESEARCH
# ═══════════════════════════════════════════════════════════════
elif st.session_state["current_page"] == "deep":

    _work_header("Deep Research", "deep_back")
    render_deep_research_selector(st.session_state.get("all_results_store", []))
    render_about()
