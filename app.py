# ============================================================
#  INDIA RED FLAG DASHBOARD  —  app.py
#  Single-file version for easy Streamlit deployment
#
#  STRUCTURE:
#  SECTION 1 — DATA LAYER       (line ~30)   edit for new data sources
#  SECTION 2 — ANALYSIS LAYER   (line ~130)  edit for new checks / scoring
#  SECTION 3 — UI LAYER         (line ~340)  edit for look, charts, layout
# ============================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import io
import time

# ============================================================
#  SECTION 1 — DATA LAYER
#  Fetches and cleans financial data from Yahoo Finance.
#  All money values returned in ₹ Crore.
#  To add a new data source or new field — edit only this section.
# ============================================================

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
            "cash":           _series_cr(_safe_row(raw_bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])),
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
            "pnl": pnl,
            "bs":  bs,
            "cf":  cf,
        }
    except Exception:
        return None

def nse_to_yahoo(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
        return ticker + ".NS"
    return ticker

# ============================================================
#  SECTION 2 — ANALYSIS LAYER
#  Pure financial logic. No fetching. No UI.
#  Each check is a separate function — easy to add / remove.
#  To add a new check: write check_xyz(data) and add to run_all_checks().
#
#  FLAG FORMAT: (severity, short_title, plain_english_explanation)
#  SEVERITY:    "HIGH" = 2pts  |  "MEDIUM" = 1pt  |  "LOW" = 0pts
# ============================================================

def _cagr(series, years=3):
    if series is None:
        return None
    s = series.dropna()
    if len(s) < 2:
        return None
    y = min(years, len(s) - 1)
    a, b = float(s.iloc[0]), float(s.iloc[-1])
    if a <= 0 or b <= 0 or y == 0:
        return None
    return (b / a) ** (1 / y) - 1

def _last(series):
    if series is None or series.empty:
        return None
    s = series.dropna()
    return float(s.iloc[-1]) if not s.empty else None

def _avg(series, n=3):
    if series is None or series.empty:
        return None
    s = series.dropna().iloc[-n:]
    return float(s.mean()) if not s.empty else None

# ── Individual checks ──────────────────────────────────────

def check_cfo_vs_profit(data):
    flags = []
    cfo, pat = data["cf"].get("cfo"), data["pnl"].get("net_profit")
    if cfo is None or pat is None:
        return flags
    avg_cfo, avg_pat = _avg(cfo, 3), _avg(pat, 3)
    if avg_cfo is None or avg_pat is None or avg_pat == 0:
        return flags
    r = avg_cfo / avg_pat
    if r < 0.7:
        flags.append(("HIGH", "Low CFO / Net Profit ratio",
            f"3-year avg operating cash flow is only {r:.0%} of reported profit. "
            "Healthy companies generate ≥1x CFO vs profit. "
            "Strong signal of accrual-based earnings inflation — profit not converting to real cash."))
    elif r < 0.85:
        flags.append(("MEDIUM", f"Below-average CFO / Net Profit ({r:.0%})",
            f"CFO is {r:.0%} of net profit (3yr avg). Below the healthy threshold of 85%+. "
            "Watch this trend — if it keeps falling, it becomes a high-severity flag."))
    return flags

def check_receivables_vs_revenue(data):
    flags = []
    rev, rec = data["pnl"].get("revenue"), data["bs"].get("receivables")
    if rev is None or rec is None:
        return flags
    rg, recg = _cagr(rev, 3), _cagr(rec, 3)
    if rg is None or recg is None:
        return flags
    gap = recg - rg
    if gap > 0.15:
        flags.append(("HIGH", "Receivables growing much faster than revenue",
            f"Revenue 3Y CAGR: {rg:.0%} | Receivables 3Y CAGR: {recg:.0%} — gap of {gap:.0%}. "
            "Classic channel stuffing or aggressive revenue recognition signal. "
            "Check debtor days trend and whether customers are actually paying."))
    elif gap > 0.10:
        flags.append(("MEDIUM", "Receivables growing faster than revenue",
            f"Revenue CAGR: {rg:.0%} | Receivables CAGR: {recg:.0%} — gap of {gap:.0%}. "
            "Worth monitoring. Receivables should not consistently outgrow sales."))
    return flags

def check_debt_vs_cfo(data):
    flags = []
    debt, cfo = data["bs"].get("total_debt"), data["cf"].get("cfo")
    if debt is None or cfo is None:
        return flags
    d, c = debt.dropna(), cfo.dropna()
    if len(d) < 3 or len(c) < 3:
        return flags
    if float(d.iloc[-1]) > float(d.iloc[0]) * 1.35 and float(c.iloc[-1]) < float(c.iloc[0]) * 0.75:
        flags.append(("HIGH", "Debt up 35%+ while operating cash flow dropped 25%+",
            "Company is borrowing significantly more while generating less operating cash. "
            "Classic pre-distress signal (IL&FS, DHFL pattern). "
            "Check if debt is funding operations rather than growth capex — that is unsustainable."))
    return flags

def check_inventory_buildup(data):
    flags = []
    inv, rev = data["bs"].get("inventory"), data["pnl"].get("revenue")
    if inv is None or rev is None:
        return flags
    ig, rg = _cagr(inv, 3), _cagr(rev, 3)
    if ig is None or rg is None:
        return flags
    gap = ig - rg
    if gap > 0.15:
        flags.append(("MEDIUM", f"Inventory growing faster than revenue (gap: {gap:.0%})",
            f"Inventory 3Y CAGR: {ig:.0%} vs Revenue 3Y CAGR: {rg:.0%}. "
            "Excess inventory may signal demand slowdown, obsolete stock, or inflated assets. "
            "Check inventory days trend over the last 4 quarters."))
    return flags

def check_interest_coverage(data):
    flags = []
    ebit   = data["pnl"].get("operating_profit")
    intexp = data["pnl"].get("interest_exp")
    if ebit is None or intexp is None:
        return flags
    e = _last(ebit)
    i = abs(_last(intexp)) if _last(intexp) else None
    if e is None or i is None or i == 0:
        return flags
    icr = e / i
    if icr < 1.5:
        flags.append(("HIGH", f"Dangerously low interest coverage ({icr:.1f}x)",
            f"Operating profit covers interest only {icr:.1f}x. "
            "Below 1.5x is the danger zone — one bad quarter could trigger a default. "
            "Lenders typically require 2x+ as a loan covenant."))
    elif icr < 2.5:
        flags.append(("MEDIUM", f"Weak interest coverage ({icr:.1f}x)",
            f"Interest coverage of {icr:.1f}x is below the comfortable threshold of 3x+. "
            "Monitor closely, especially in a rising interest rate environment."))
    return flags

def check_negative_cfo_vs_profit(data):
    flags = []
    cfo, pat = data["cf"].get("cfo"), data["pnl"].get("net_profit")
    if cfo is None or pat is None:
        return flags
    neg_cfo = int((cfo.dropna() < 0).sum())
    pos_pat = int((pat.dropna() > 0).sum())
    if neg_cfo >= 2 and pos_pat >= 3:
        flags.append(("HIGH", f"Negative operating cash flow in {neg_cfo} years despite profits",
            f"Reported profits in {pos_pat} years but negative operating cash flow in {neg_cfo} years. "
            "One of the strongest red flags in forensic accounting. "
            "The company is printing paper profits but not generating real cash."))
    return flags

def check_revenue_decline(data):
    flags = []
    rev = data["pnl"].get("revenue")
    if rev is None:
        return flags
    rg = _cagr(rev, 3)
    if rg is not None and rg < -0.05:
        flags.append(("MEDIUM", f"Revenue declining (3Y CAGR: {rg:.1%})",
            f"Revenue has been falling at {abs(rg):.1%} per year for 3 years. "
            "Determine if cyclical (commodity, seasonal) or structural "
            "(losing market share, product obsolescence, pricing pressure)."))
    return flags

def check_sustained_losses(data):
    flags = []
    pat = data["pnl"].get("net_profit")
    if pat is None:
        return flags
    s = pat.dropna()
    loss_years  = int((s < 0).sum())
    total_years = len(s)
    if loss_years >= 3:
        flags.append(("HIGH", f"Loss-making in {loss_years} of {total_years} years",
            "Sustained losses indicate inability to reach profitability. "
            "For new-age companies, check if EBITDA margins and unit economics "
            "are improving YoY even if net profit is negative."))
    elif loss_years >= 1:
        flags.append(("MEDIUM", f"Net loss in {loss_years} recent year(s)",
            "Check if this is a one-off (write-off, deferred tax) or structural. "
            "Look at EBITDA trends to separate operating health from accounting charges."))
    return flags

def check_high_leverage(data):
    flags = []
    de     = data.get("de_ratio")
    sector = data.get("sector", "")
    if "financial" in sector.lower() or "bank" in sector.lower():
        return flags
    if de is None:
        return flags
    if de > 2.0:
        flags.append(("HIGH", f"Very high Debt/Equity ratio ({de:.1f}x)",
            f"D/E of {de:.1f}x is well above safe levels (typically <1x for non-financial companies). "
            "High leverage amplifies losses and raises solvency risk, "
            "especially if operating cash flows are also declining."))
    elif de > 1.0:
        flags.append(("MEDIUM", f"Elevated Debt/Equity ratio ({de:.1f}x)",
            f"D/E of {de:.1f}x is above 1x. Not alarming on its own — "
            "combine with interest coverage and CFO trend for the full picture."))
    return flags

def check_low_promoter_holding(data):
    flags = []
    ph     = data.get("promoter_holding_pct", 0)
    sector = data.get("sector", "")
    if ph == 0 or "financial" in sector.lower():
        return flags
    if ph < 25:
        flags.append(("LOW", f"Low promoter / insider holding ({ph:.1f}%)",
            f"Promoters hold only {ph:.1f}%. While not definitive, "
            "low promoter holding reduces alignment of interests. "
            "Watch for any further quarterly decline in promoter holding."))
    return flags

# ── Master function — add new checks here ──────────────────

def run_all_checks(data):
    """
    Runs every check and returns (flags_list, score).
    To add a new check: write the function above, then add it to this list.
    """
    all_flags = []
    for check_fn in [
        check_cfo_vs_profit,
        check_receivables_vs_revenue,
        check_debt_vs_cfo,
        check_inventory_buildup,
        check_interest_coverage,
        check_negative_cfo_vs_profit,
        check_revenue_decline,
        check_sustained_losses,
        check_high_leverage,
        check_low_promoter_holding,
    ]:
        try:
            all_flags.extend(check_fn(data))
        except Exception:
            pass
    score = sum({"HIGH": 2, "MEDIUM": 1, "LOW": 0}.get(s, 0) for s, _, _ in all_flags)
    return all_flags, min(score, 10)

# ============================================================
#  SECTION 3 — UI LAYER
#  Everything the user sees. Charts, layout, colours, downloads.
#  To change the look and feel — edit only this section.
#  Do NOT put data fetching or analysis logic here.
# ============================================================

POPULAR = {
    "Reliance Industries": "RELIANCE.NS",  "TCS": "TCS.NS",
    "Infosys": "INFY.NS",                  "HDFC Bank": "HDFCBANK.NS",
    "ICICI Bank": "ICICIBANK.NS",          "Wipro": "WIPRO.NS",
    "Adani Enterprises": "ADANIENT.NS",    "Yes Bank": "YESBANK.NS",
    "Zomato": "ZOMATO.NS",                 "Paytm": "PAYTM.NS",
    "Nykaa": "NYKAA.NS",                   "Bajaj Finance": "BAJFINANCE.NS",
    "Axis Bank": "AXISBANK.NS",            "ITC": "ITC.NS",
    "L&T": "LT.NS",                        "Sun Pharma": "SUNPHARMA.NS",
    "Tata Motors": "TATAMOTORS.NS",        "Coal India": "COALINDIA.NS",
    "ONGC": "ONGC.NS",                     "Maruti": "MARUTI.NS",
}

SECTORS = {
    "🏦 Banks & NBFCs":         ["HDFCBANK.NS","ICICIBANK.NS","AXISBANK.NS","YESBANK.NS","KOTAKBANK.NS","BAJFINANCE.NS","SBIN.NS"],
    "💻 IT":                    ["TCS.NS","INFY.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS"],
    "⚡ Adani Group":           ["ADANIENT.NS","ADANIPORTS.NS","ADANIPOWER.NS","ADANIGREEN.NS"],
    "🚀 New-age / loss-making": ["ZOMATO.NS","PAYTM.NS","NYKAA.NS","DELHIVERY.NS"],
    "🏭 Auto & Manufacturing":  ["TATAMOTORS.NS","MARUTI.NS","HEROMOTOCO.NS","BAJAJ-AUTO.NS"],
    "💊 Pharma":                ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS"],
}

st.set_page_config(page_title="India Red Flag Dashboard", page_icon="🚨", layout="wide",
    menu_items={"About": "Forensic financial analysis. Not investment advice."})

st.markdown("""
<style>
.flag-HIGH   { background:#fff0f0; border-left:4px solid #e24b4a; padding:10px 14px; border-radius:6px; margin:6px 0; font-size:14px; line-height:1.6; }
.flag-MEDIUM { background:#fffbe6; border-left:4px solid #ef9f27; padding:10px 14px; border-radius:6px; margin:6px 0; font-size:14px; line-height:1.6; }
.flag-LOW    { background:#f0f7ff; border-left:4px solid #378ADD; padding:10px 14px; border-radius:6px; margin:6px 0; font-size:14px; line-height:1.6; }
</style>""", unsafe_allow_html=True)

def make_bar_chart(series, title, color):
    if series is None or series.empty:
        return None
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
    color = "#e24b4a" if score >= 6 else "#ef9f27" if score >= 3 else "#639922"
    label = "HIGH RISK" if score >= 6 else "WATCH" if score >= 3 else "CLEAN"
    return f"""<div style="background:var(--secondary-background-color);border-radius:10px;
        padding:14px;text-align:center;margin-bottom:8px;">
      <div style="font-size:13px;font-weight:500;">{symbol.replace('.NS','')}</div>
      <div style="font-size:11px;color:gray;margin-bottom:6px;">{name[:24]}</div>
      <div style="font-size:28px;font-weight:600;color:{color};">{score}
        <span style="font-size:14px;color:gray;">/10</span></div>
      <div style="font-size:11px;color:{color};font-weight:500;">{label}</div>
      <div style="font-size:11px;color:gray;margin-top:4px;">{flag_count} flag(s)</div>
    </div>"""

@st.cache_data(ttl=3600, show_spinner=False)
def analyse_ticker(ticker):
    data = get_company_data(ticker)
    if data is None:
        return None
    flags, score = run_all_checks(data)
    return {**data, "flags": flags, "score": score}

# ── Page ──────────────────────────────────────────────────────────────────────
st.title("🚨 India Red Flag Dashboard")
st.caption("Forensic financial analysis of BSE/NSE companies · Data via Yahoo Finance · Not investment advice")

tab_search, tab_sector, tab_about = st.tabs(["🔍 Search", "📊 Sector scan", "ℹ️ About"])

with tab_search:
    col1, col2 = st.columns([3, 2])
    with col1:
        selected = st.multiselect("Search by company name", list(POPULAR.keys()), placeholder="Type a company name...")
        manual   = st.text_input("Or enter NSE tickers (comma separated)", placeholder="e.g.  RCOM, DHFL, SUZLON")
    with col2:
        preset = st.selectbox("Or pick a preset sector", ["-- choose --"] + list(SECTORS.keys()))

    tickers = []
    if selected:
        tickers += [POPULAR[n] for n in selected]
    if manual.strip():
        tickers += [nse_to_yahoo(t) for t in manual.split(",") if t.strip()]
    if preset != "-- choose --" and not selected and not manual.strip():
        tickers = SECTORS[preset]
    tickers = list(dict.fromkeys(tickers))

    if tickers and st.button(f"🔍 Analyse {len(tickers)} company/companies", type="primary"):
        results, prog = [], st.progress(0, "Starting...")
        for i, ticker in enumerate(tickers):
            prog.progress(i / len(tickers), f"Analysing {ticker}...")
            r = analyse_ticker(ticker)
            if r:
                results.append(r)
            else:
                st.warning(f"Could not fetch **{ticker}** — check the ticker symbol")
            time.sleep(0.3)
        prog.empty()

        if not results:
            st.error("No results. Check your ticker symbols.")
            st.stop()

        results.sort(key=lambda x: x["score"], reverse=True)

        st.divider()
        st.subheader("Summary")
        cols = st.columns(min(len(results), 5))
        for i, r in enumerate(results):
            cols[i % 5].markdown(score_card(r["ticker"], r["name"], r["score"], len(r["flags"])), unsafe_allow_html=True)

        st.divider()
        for r in results:
            icon = "🔴" if r["score"] >= 6 else "🟡" if r["score"] >= 3 else "✅"
            mcap = f"₹{r['mcap_cr']:,.0f} Cr" if r.get("mcap_cr") else "—"
            with st.expander(f"{icon}  {r['name']}  ({r['ticker'].replace('.NS','')})   |   Score: {r['score']}/10   |   {r.get('sector','—')}   |   {mcap}", expanded=(r["score"] >= 6)):
                c1, c2, c3 = st.columns(3)
                for col, key, df_key, title, color in [
                    (c1, "revenue",    "pnl", "Revenue (₹ Cr)",      "#378ADD"),
                    (c2, "net_profit", "pnl", "Net Profit (₹ Cr)",   "#1D9E75"),
                    (c3, "cfo",        "cf",  "Operating CF (₹ Cr)", "#EF9F27"),
                ]:
                    fig = make_bar_chart(r[df_key].get(key), title, color)
                    if fig:
                        col.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

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

        st.divider()
        rows = [{"Ticker": r["ticker"].replace(".NS",""), "Company": r["name"],
                 "Sector": r.get("sector","—"), "Mkt Cap (₹ Cr)": r.get("mcap_cr"),
                 "Score (0-10)": r["score"],
                 "Flags": " | ".join(f"[{s}] {t}" for s,t,_ in r["flags"]) or "None"}
                for r in results]
        buf = io.BytesIO()
        pd.DataFrame(rows).to_excel(buf, index=False)
        st.download_button("⬇️ Download Excel report", buf.getvalue(),
            file_name="red_flag_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_sector:
    chosen = st.selectbox("Choose sector to scan", list(SECTORS.keys()))
    if st.button("🔍 Scan entire sector", type="primary"):
        rows, prog = [], st.progress(0)
        for i, sym in enumerate(SECTORS[chosen]):
            prog.progress(i / len(SECTORS[chosen]), f"Scanning {sym}...")
            r = analyse_ticker(sym)
            if r:
                rows.append({"Ticker": sym.replace(".NS",""), "Company": r["name"],
                             "Score": r["score"], "Flags": len(r["flags"]),
                             "Top flag": r["flags"][0][1] if r["flags"] else "None"})
            time.sleep(0.3)
        prog.empty()
        if rows:
            st.dataframe(pd.DataFrame(rows).sort_values("Score", ascending=False)
                .style.background_gradient(subset=["Score"], cmap="RdYlGn_r"),
                use_container_width=True, hide_index=True)

with tab_about:
    st.markdown("""
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

**Scoring:** HIGH = 2 pts · MEDIUM = 1 pt · LOW = 0 pts · Max score = 10

**Data:** Yahoo Finance via `yfinance` · Annual financials · ~4 years of history

**Disclaimer:** For research and education only. Not SEBI-registered investment advice.
    """)
