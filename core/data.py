# ============================================================
#  core/data.py
#
#  SINGLE SOURCE OF TRUTH for:
#    - Loading the NSE company universe (EQUITY_L.csv + fallbacks)
#    - Fetching per-company fundamentals via yfinance
#
#  Extracted from app.py during Sprint 1 de-duplication.
#  Previously, deep_research_tab.py maintained its own copies of
#  these functions (prefixed _dr_). Both app.py and
#  deep_research_tab.py (and any future workspace) should import
#  from here instead of re-implementing this layer.
# ============================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
from io import StringIO
import os


# ── NSE company universe ─────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def load_nse_company_list():
    """Returns {display_name: ticker} for the full NSE universe,
    with graceful fallback to a curated list of ~65 major companies
    if EQUITY_L.csv can't be found locally or fetched remotely."""

    def _parse_csv_text(text):
        df = pd.read_csv(StringIO(text))
        df.columns = [c.strip() for c in df.columns]
        if "SYMBOL" not in df.columns:
            return None
        name_col = "NAME OF COMPANY" if "NAME OF COMPANY" in df.columns else None
        if name_col is None:
            return None
        company_dict = {}
        for _, row in df.iterrows():
            sym = str(row["SYMBOL"]).strip()
            name = str(row[name_col]).strip()
            if sym and name and sym != "nan" and name != "nan":
                company_dict[f"{name}  ({sym})"] = f"{sym}.NS"
        return company_dict if len(company_dict) > 500 else None

    local_paths = ["EQUITY_L.csv", "./EQUITY_L.csv", "data/EQUITY_L.csv"]
    for path in local_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read().strip()
                result = _parse_csv_text(text)
                if result:
                    return result
            except Exception:
                continue

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

    tickers = [
        ("Reliance Industries", "RELIANCE"), ("TCS", "TCS"), ("Infosys", "INFY"),
        ("HDFC Bank", "HDFCBANK"), ("ICICI Bank", "ICICIBANK"), ("Wipro", "WIPRO"),
        ("Adani Enterprises", "ADANIENT"), ("Yes Bank", "YESBANK"), ("Zomato", "ZOMATO"),
        ("Paytm", "PAYTM"), ("Bajaj Finance", "BAJFINANCE"), ("ITC", "ITC"),
        ("L&T", "LT"), ("Sun Pharma", "SUNPHARMA"), ("Tata Motors", "TATAMOTORS"),
        ("ONGC", "ONGC"), ("Coal India", "COALINDIA"), ("SBI", "SBIN"),
        ("Axis Bank", "AXISBANK"), ("Maruti Suzuki", "MARUTI"),
        ("HCL Tech", "HCLTECH"), ("Tech Mahindra", "TECHM"),
        ("NTPC", "NTPC"), ("Power Grid", "POWERGRID"), ("Tata Steel", "TATASTEEL"),
        ("JSW Steel", "JSWSTEEL"), ("Hindalco", "HINDALCO"), ("Vedanta", "VEDL"),
        ("NMDC", "NMDC"), ("Dr Reddy's", "DRREDDY"), ("Cipla", "CIPLA"),
        ("Divis Labs", "DIVISLAB"), ("Lupin", "LUPIN"), ("Aurobindo Pharma", "AUROPHARMA"),
        ("Hindustan Unilever", "HINDUNILVR"), ("Nestle India", "NESTLEIND"),
        ("Britannia", "BRITANNIA"), ("Dabur", "DABUR"), ("Marico", "MARICO"),
        ("DLF", "DLF"), ("Godrej Properties", "GODREJPROP"), ("Prestige Estates", "PRESTIGE"),
        ("Tata Power", "TATAPOWER"), ("Adani Ports", "ADANIPORTS"),
        ("Bajaj Auto", "BAJAJ-AUTO"), ("Eicher Motors", "EICHERMOT"),
        ("Hero MotoCorp", "HEROMOTOCO"), ("Ashok Leyland", "ASHOKLEY"),
        ("TVS Motor", "TVSMOTOR"), ("Muthoot Finance", "MUTHOOTFIN"),
        ("Cholamandalam Finance", "CHOLAFIN"), ("Shriram Finance", "SHRIRAMFIN"),
        ("Federal Bank", "FEDERALBNK"), ("Bandhan Bank", "BANDHANBNK"),
        ("Kotak Mahindra Bank", "KOTAKBANK"), ("IndusInd Bank", "INDUSINDBK"),
        ("Tata Communications", "TATACOMM"), ("Adani Green", "ADANIGREEN"),
        ("JSW Energy", "JSWENERGY"), ("Torrent Power", "TORNTPOWER"),
        ("Bajaj Finserv", "BAJAJFINSV"), ("M&M", "M&M"), ("HDFCLIFE", "HDFCLIFE"),
        ("SBILIFE", "SBILIFE"), ("ICICIPRULI", "ICICIPRULI"), ("Nykaa", "NYKAA"),
        ("Delhivery", "DELHIVERY"), ("PolicyBazaar", "POLICYBZR"),
    ]
    return {f"{name}  ({sym})": f"{sym}.NS" for name, sym in tickers}


def resolve_ticker(raw: str) -> str:
    """Given a raw user-typed symbol, figures out whether it trades
    on NSE (.NS) or BSE (.BO) by probing yfinance."""
    raw = raw.strip().upper().replace(".NS", "").replace(".BO", "")
    for suffix in [".NS", ".BO"]:
        symbol = raw + suffix
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            if not hist.empty:
                return symbol
        except Exception:
            continue
    return None


# ── Small numeric helpers used while shaping fundamentals ────

def _safe_row(df, names):
    if df is None or df.empty:
        return None
    for name in names:
        if name in df.index:
            row = pd.to_numeric(df.loc[name], errors="coerce").dropna()
            if not row.empty:
                new_idx = [str(idx)[:4] for idx in row.index]
                row.index = new_idx
                row = row[~row.index.duplicated(keep="last")]
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


# ── Fundamentals fetch (yfinance) ─────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def get_company_data(ticker: str):
    """Fetches and normalises fundamentals for a single ticker.
    Returns a dict with pnl/bs/cf sub-dicts of per-year Series (in Cr),
    plus scalar fields (mcap_cr, de_ratio, promoter_holding_pct, etc.),
    or None if data could not be retrieved after retries."""
    for attempt in range(3):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if hist.empty:
                if attempt < 2:
                    time.sleep(2)
                    continue
                return None

            try:
                info = t.info or {}
            except Exception:
                info = {}

            fallback_name = ticker.replace(".NS", "").replace(".BO", "")
            name = info.get("longName") or info.get("shortName") or fallback_name

            raw_pnl = t.financials
            raw_bs = t.balance_sheet
            raw_cf = t.cashflow
            raw_qpnl = t.quarterly_financials

            if (raw_pnl is None or raw_pnl.empty) and \
               (raw_bs is None or raw_bs.empty) and \
               (raw_cf is None or raw_cf.empty):
                if attempt < 2:
                    time.sleep(2)
                    continue
                return None

            pnl = {
                "revenue":          _series_cr(_safe_row(raw_pnl, ["Total Revenue", "Revenue"])),
                "ebitda":           _series_cr(_safe_row(raw_pnl, ["EBITDA", "Normalized EBITDA"])),
                "operating_profit": _series_cr(_safe_row(raw_pnl, ["Operating Income", "EBIT"])),
                "net_profit":       _series_cr(_safe_row(raw_pnl, ["Net Income", "Net Income Common Stockholders"])),
                "interest_exp":     _series_cr(_safe_row(raw_pnl, ["Interest Expense"])),
                "other_income":     _series_cr(_safe_row(raw_pnl, ["Other Income Expense", "Non Operating Income"])),
                "depreciation":     _series_cr(_safe_row(raw_pnl, ["Reconciled Depreciation", "Depreciation And Amortization"])),
                "gross_profit":     _series_cr(_safe_row(raw_pnl, ["Gross Profit"])),
            }
            bs = {
                "total_debt":         _series_cr(_safe_row(raw_bs, ["Total Debt", "Long Term Debt"])),
                "equity":             _series_cr(_safe_row(raw_bs, ["Stockholders Equity", "Common Stock Equity"])),
                "receivables":        _series_cr(_safe_row(raw_bs, ["Accounts Receivable", "Net Receivables"])),
                "inventory":          _series_cr(_safe_row(raw_bs, ["Inventory"])),
                "total_assets":       _series_cr(_safe_row(raw_bs, ["Total Assets"])),
                "current_assets":     _series_cr(_safe_row(raw_bs, ["Current Assets"])),
                "current_liab":       _series_cr(_safe_row(raw_bs, ["Current Liabilities"])),
                "cash":               _series_cr(_safe_row(raw_bs, ["Cash And Cash Equivalents",
                                                 "Cash Cash Equivalents And Short Term Investments"])),
                "goodwill":           _series_cr(_safe_row(raw_bs, ["Goodwill", "Goodwill And Other Intangible Assets"])),
                "payables":           _series_cr(_safe_row(raw_bs, ["Accounts Payable", "Payables"])),
                "non_current_assets": _series_cr(_safe_row(raw_bs, ["Net PPE", "Total Non Current Assets"])),
                "deferred_tax":       _series_cr(_safe_row(raw_bs, ["Deferred Tax Assets", "Deferred Income Tax"])),
            }
            cf = {
                "cfo":       _series_cr(_safe_row(raw_cf, ["Operating Cash Flow", "Cash From Operations"])),
                "capex":     _series_cr(_safe_row(raw_cf, ["Capital Expenditure"])),
                "fcf":       _series_cr(_safe_row(raw_cf, ["Free Cash Flow"])),
                "investing": _series_cr(_safe_row(raw_cf, ["Investing Cash Flow", "Cash From Investing Activities"])),
            }

            q4_pct = None
            try:
                if raw_qpnl is not None and not raw_qpnl.empty:
                    qrev_row = _safe_row(raw_qpnl, ["Total Revenue", "Revenue"])
                    if qrev_row is not None and len(qrev_row) >= 4:
                        qrev = qrev_row.sort_index(ascending=False)
                        last4 = qrev.iloc[:4]
                        total = last4.sum()
                        q4_vals = [v for d, v in last4.items()
                                   if hasattr(d, 'month') and d.month in [3, 12]]
                        if total and q4_vals:
                            q4_pct = sum(q4_vals) / float(total)
            except Exception:
                pass

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

        except Exception:
            if attempt < 2:
                time.sleep(2)
                continue
            return None

    return None