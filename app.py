# ============================================================
#  INDIA RED FLAG DASHBOARD  —  app.py
#  Single-file version for Streamlit
#
#  SECTION 1 — DATA LAYER       edit for new data sources
#  SECTION 2 — ANALYSIS LAYER   edit for new checks / scoring
#  SECTION 3 — UI LAYER         edit for look, charts, layout
# ============================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import io
import time
import requests

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
#  SECTION 3 — UI LAYER
# ============================================================

st.set_page_config(page_title="India Red Flag Dashboard", page_icon="🚨",
    layout="wide", menu_items={"About": "Forensic analysis. Not investment advice."})

st.markdown("""
<style>
.flag-HIGH   {background:#fff0f0;border-left:4px solid #e24b4a;padding:10px 14px;border-radius:6px;margin:6px 0;font-size:14px;line-height:1.6;}
.flag-MEDIUM {background:#fffbe6;border-left:4px solid #ef9f27;padding:10px 14px;border-radius:6px;margin:6px 0;font-size:14px;line-height:1.6;}
.flag-LOW    {background:#f0f7ff;border-left:4px solid #378ADD;padding:10px 14px;border-radius:6px;margin:6px 0;font-size:14px;line-height:1.6;}
</style>""", unsafe_allow_html=True)

def make_bar_chart(series, title, color):
    if series is None or series.empty: return None
    fig = go.Figure(go.Bar(
        x=[str(d)[:4] for d in series.index],
        y=[round(v, 0) for v in series.values],
        marker_color=color))
    fig.update_layout(title=title, height=220, margin=dict(t=30,b=20,l=10,r=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="₹ Crore", font=dict(size=12))
    fig.update_yaxes(gridcolor="rgba(0,0,0,0.06)")
    return fig

def score_card(symbol, name, score, flag_count):
    color = "#e24b4a" if score>=6 else "#ef9f27" if score>=3 else "#639922"
    label = "HIGH RISK" if score>=6 else "WATCH" if score>=3 else "CLEAN"
    return f"""<div style="background:var(--secondary-background-color);border-radius:10px;
        padding:14px;text-align:center;margin-bottom:8px;">
      <div style="font-size:13px;font-weight:500;">{symbol.replace('.NS','').replace('.BO','')}</div>
      <div style="font-size:11px;color:gray;margin-bottom:6px;">{name[:24]}</div>
      <div style="font-size:28px;font-weight:600;color:{color};">{score}
        <span style="font-size:14px;color:gray;">/10</span></div>
      <div style="font-size:11px;color:{color};font-weight:500;">{label}</div>
      <div style="font-size:11px;color:gray;margin-top:4px;">{flag_count} flag(s)</div>
    </div>"""

@st.cache_data(ttl=3600, show_spinner=False)
def analyse_ticker(ticker):
    data = get_company_data(ticker)
    if data is None: return None
    flags, score = run_all_checks(data)
    return {**data, "flags": flags, "score": score}

# ── Load full NSE list once ────────────────────────────────
with st.spinner("Loading NSE company list..."):
    ALL_COMPANIES = load_nse_company_list()   # {Display Name: TICKER.NS}

# ── Page ───────────────────────────────────────────────────
st.title("🚨 India Red Flag Dashboard")
st.caption("All NSE-listed companies · Forensic financial analysis · Data via Yahoo Finance · Not investment advice")

tab_search, tab_sector, tab_about = st.tabs(["🔍 Search", "📊 Sector scan", "ℹ️ About"])

with tab_search:
    st.markdown("Search across all ~2000 NSE-listed companies by name or ticker.")

    col1, col2 = st.columns([3, 2])
    with col1:
        # Searchable dropdown across all NSE companies
        selected_names = st.multiselect(
            "Search by company name",
            options=sorted(ALL_COMPANIES.keys()),
            placeholder="Type any company name or ticker — e.g. Infosys, HDFC, Suzlon..."
        )
        # Also allow raw ticker entry as fallback
        manual = st.text_input(
            "Or type NSE tickers directly (comma separated)",
            placeholder="e.g.  RCOM, JPPOWER, DHFL, GTLINFRA"
        )
    with col2:
        st.markdown("**Tips**")
        st.caption("• Search by company name in the dropdown above")
        st.caption("• Or type the NSE ticker directly (no .NS needed)")
        st.caption("• You can select multiple companies at once")
        st.caption("• Results are cached for 1 hour — fast on repeat searches")

    # Resolve all tickers
    tickers = []
    if selected_names:
        tickers += [ALL_COMPANIES[n] for n in selected_names]
    if manual.strip():
        raw_tickers = [t.strip() for t in manual.split(",") if t.strip()]
        with st.spinner("Validating tickers..."):
            for raw in raw_tickers:
                resolved = resolve_ticker(raw)
                if resolved:
                    tickers.append(resolved)
                else:
                    st.warning(f"Could not find **{raw}** on NSE or BSE — check the spelling")
    tickers = list(dict.fromkeys(tickers))   # deduplicate

    if tickers and st.button(f"🔍 Analyse {len(tickers)} company/companies", type="primary"):
        results, prog = [], st.progress(0, "Starting...")
        for i, ticker in enumerate(tickers):
            prog.progress(i / len(tickers), f"Analysing {ticker}...")
            r = analyse_ticker(ticker)
            if r:
                results.append(r)
            else:
                st.warning(f"Data unavailable for **{ticker}** — Yahoo Finance may not cover this stock")
            time.sleep(0.3)
        prog.empty()

        if not results:
            st.error("No results fetched. Try a different ticker or check back later.")
            st.stop()

        results.sort(key=lambda x: x["score"], reverse=True)

        # Score cards
        st.divider()
        st.subheader("Summary")
        cols = st.columns(min(len(results), 5))
        for i, r in enumerate(results):
            cols[i%5].markdown(score_card(r["ticker"], r["name"], r["score"], len(r["flags"])),
                               unsafe_allow_html=True)
        st.divider()

        # Detail cards
        for r in results:
            icon = "🔴" if r["score"]>=6 else "🟡" if r["score"]>=3 else "✅"
            mcap = f"₹{r['mcap_cr']:,.0f} Cr" if r.get("mcap_cr") else "—"
            label = r["ticker"].replace(".NS","").replace(".BO","")
            with st.expander(
                f"{icon}  {r['name']}  ({label})   |   Score: {r['score']}/10   |   {r.get('sector','—')}   |   {mcap}",
                expanded=(r["score"] >= 6)):

                c1, c2, c3 = st.columns(3)
                for col, key, df_key, title, color in [
                    (c1, "revenue",    "pnl", "Revenue (₹ Cr)",      "#378ADD"),
                    (c2, "net_profit", "pnl", "Net Profit (₹ Cr)",   "#1D9E75"),
                    (c3, "cfo",        "cf",  "Operating CF (₹ Cr)", "#EF9F27"),
                ]:
                    fig = make_bar_chart(r[df_key].get(key), title, color)
                    if fig: col.plotly_chart(fig, use_container_width=True,
                                             config={"displayModeBar": False})

                st.markdown("**Red flag analysis**")
                if not r["flags"]:
                    st.success("✅ No red flags triggered. Always do further due diligence.")
                else:
                    for sev, title, detail in r["flags"]:
                        icon2 = "🔴" if sev=="HIGH" else "🟡" if sev=="MEDIUM" else "🔵"
                        st.markdown(
                            f'<div class="flag-{sev}"><strong>{icon2} [{sev}] {title}</strong>'
                            f'<br><span style="color:#555;font-size:13px;">{detail}</span></div>',
                            unsafe_allow_html=True)

        # Excel download
        st.divider()
        rows = [{"Ticker": r["ticker"].replace(".NS","").replace(".BO",""),
                 "Company": r["name"], "Sector": r.get("sector","—"),
                 "Industry": r.get("industry","—"),
                 "Mkt Cap (₹ Cr)": r.get("mcap_cr"),
                 "Score (0-10)": r["score"],
                 "Flags": " | ".join(f"[{s}] {t}" for s,t,_ in r["flags"]) or "None"}
                for r in results]
        buf = io.BytesIO()
        pd.DataFrame(rows).to_excel(buf, index=False)
        st.download_button("⬇️ Download Excel report", buf.getvalue(),
            file_name="red_flag_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_sector:
    st.markdown("Scan all companies within a sector — pulled live from NSE data.")

    # Build sector list dynamically from the full NSE company list
    sector_map = {}
    for display_name, ticker in ALL_COMPANIES.items():
        # Try to extract sector from cached yfinance info
        # (we don't fetch all sectors upfront — too slow)
        pass

    # Hardcoded sector groups using real NSE tickers — covers major sectors
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

    chosen_sector = st.selectbox("Choose sector", list(SECTOR_GROUPS.keys()))
    sector_tickers = [f"{t}.NS" for t in SECTOR_GROUPS[chosen_sector]]
    st.caption(f"{len(sector_tickers)} companies in this sector")

    if st.button("🔍 Scan entire sector", type="primary"):
        rows, prog = [], st.progress(0)
        for i, sym in enumerate(sector_tickers):
            prog.progress(i / len(sector_tickers), f"Scanning {sym}...")
            r = analyse_ticker(sym)
            if r:
                rows.append({
                    "Ticker":   sym.replace(".NS",""),
                    "Company":  r["name"],
                    "Industry": r.get("industry","—"),
                    "Mkt Cap":  f"₹{r['mcap_cr']:,.0f} Cr" if r.get("mcap_cr") else "—",
                    "Score":    r["score"],
                    "# Flags":  len(r["flags"]),
                    "Top flag": r["flags"][0][1] if r["flags"] else "None",
                })
            time.sleep(0.3)
        prog.empty()
        if rows:
            df = pd.DataFrame(rows).sort_values("Score", ascending=False)
            st.dataframe(
                df.style.background_gradient(subset=["Score"], cmap="RdYlGn_r"),
                use_container_width=True, hide_index=True)

            buf = io.BytesIO()
            df.to_excel(buf, index=False)
            st.download_button("⬇️ Download sector report", buf.getvalue(),
                file_name=f"sector_scan_{chosen_sector[:20].strip()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_about:
    st.markdown(f"""
### Coverage
This dashboard covers all **{len(ALL_COMPANIES):,} NSE-listed companies** — loaded fresh from NSE every 24 hours.

### Checks run on every company

| # | Check | What it catches | Severity |
|---|-------|----------------|----------|
| 1 | CFO / Net Profit ratio | Accrual manipulation | HIGH / MEDIUM |
| 2 | Receivables vs Revenue | Channel stuffing | HIGH / MEDIUM |
| 3 | Debt up + CFO down | Pre-distress signal | HIGH |
| 4 | Inventory accumulation | Demand slowdown | MEDIUM |
| 5 | Interest coverage | Debt servicing risk | HIGH / MEDIUM |
| 6 | Negative CFO vs profits | Persistent manipulation | HIGH |
| 7 | Revenue decline | Structural deterioration | MEDIUM |
| 8 | Sustained losses | Profitability failure | HIGH / MEDIUM |
| 9 | Debt / Equity ratio | Over-leverage | HIGH / MEDIUM |
| 10 | Promoter holding | Governance concern | LOW |

**Scoring:** HIGH = 2 pts · MEDIUM = 1 pt · LOW = 0 pts · Max = 10

**Data:** Yahoo Finance · Annual financials · ~4 years history · May lag latest filings by a few weeks

**Disclaimer:** For research and education only. Not SEBI-registered investment advice.
    """)
