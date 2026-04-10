import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

st.set_page_config(page_title="India Red Flag Dashboard", page_icon="🚨", layout="wide")

# ── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.flag-high   { background:#fff0f0; border-left:4px solid #e24b4a; padding:8px 12px; border-radius:4px; margin:4px 0; font-size:14px; }
.flag-medium { background:#fffbe6; border-left:4px solid #ef9f27; padding:8px 12px; border-radius:4px; margin:4px 0; font-size:14px; }
.score-bad   { color:#e24b4a; font-size:32px; font-weight:600; }
.score-ok    { color:#ef9f27; font-size:32px; font-weight:600; }
.score-good  { color:#639922; font-size:32px; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── Screener fetcher ──────────────────────────────────────────────────────────
HEADERS = {"User-Agent": "Mozilla/5.0"}

@st.cache_data(ttl=3600)   # cache results for 1 hour so repeat searches are instant
def get_screener_data(ticker):
    ticker = ticker.upper().strip()
    for suffix in ["/consolidated/", "/"]:
        url = f"https://www.screener.in/company/{ticker}{suffix}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            break
    else:
        return None

    soup = BeautifulSoup(r.text, "lxml")

    def parse_table(section_id):
        sec = soup.find("section", {"id": section_id})
        if not sec:
            return pd.DataFrame()
        tbl = sec.find("table")
        if not tbl:
            return pd.DataFrame()
        rows, headers = [], []
        for i, row in enumerate(tbl.find_all("tr")):
            cols = [c.get_text(strip=True).replace(",", "") for c in row.find_all(["th", "td"])]
            if i == 0:
                headers = cols
            else:
                rows.append(cols)
        if not headers or not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=headers).set_index(headers[0])
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    # Company name
    name_tag = soup.find("h1")
    name = name_tag.get_text(strip=True) if name_tag else ticker

    return {
        "ticker": ticker,
        "name": name,
        "pnl": parse_table("profit-loss"),
        "balance_sheet": parse_table("balance-sheet"),
        "cashflow": parse_table("cash-flow"),
    }

# ── Red flag engine ───────────────────────────────────────────────────────────
def _row(df, names):
    if df is None or df.empty:
        return None
    for n in names:
        if n in df.index:
            s = pd.to_numeric(df.loc[n], errors="coerce").dropna()
            if not s.empty:
                return s
    return None

def _cagr(s, y):
    s = s.dropna()
    if len(s) < y + 1:
        return 0.0
    a, b = s.iloc[-(y + 1)], s.iloc[-1]
    if a <= 0 or b <= 0:
        return 0.0
    return (b / a) ** (1 / y) - 1

def run_red_flags(data):
    pnl, bs, cf = data["pnl"], data["balance_sheet"], data["cashflow"]
    flags = []

    # 1. CFO vs PAT
    try:
        pat = _row(pnl, ["Net Profit", "Profit after tax"])
        cfo = _row(cf,  ["Cash from Operating Activity", "Operating Cash Flow"])
        if pat is not None and cfo is not None:
            r = cfo.iloc[-3:].mean() / pat.iloc[-3:].mean()
            if r < 0.7:
                flags.append(("HIGH", "Low CFO/PAT ratio",
                    f"3-year average CFO is only {r:.0%} of reported profit. "
                    f"Healthy companies typically show CFO ≥ PAT. Suggests possible accrual manipulation."))
    except: pass

    # 2. Receivables vs Revenue
    try:
        rev = _row(pnl, ["Revenue", "Sales", "Net Sales", "Revenue from Operations"])
        rec = _row(bs,  ["Debtors", "Trade Receivables", "Receivables"])
        if rev is not None and rec is not None:
            rg, recg = _cagr(rev, 3), _cagr(rec, 3)
            if recg > rg + 0.10:
                flags.append(("HIGH", "Receivables growing faster than revenue",
                    f"Revenue 3Y CAGR: {rg:.0%} | Receivables 3Y CAGR: {recg:.0%}. "
                    f"Gap of {recg-rg:.0%} — watch for channel stuffing or bad debt risk."))
    except: pass

    # 3. Debt rising + CFO falling
    try:
        debt = _row(bs, ["Borrowings", "Total Debt", "Long Term Borrowings"])
        cfo  = _row(cf, ["Cash from Operating Activity", "Operating Cash Flow"])
        if debt is not None and cfo is not None and len(debt) > 3:
            if debt.iloc[-1] > debt.iloc[-4] * 1.3 and cfo.iloc[-1] < cfo.iloc[-4] * 0.8:
                flags.append(("HIGH", "Debt up 30%+ while CFO dropped 20%+",
                    "Company is borrowing significantly more while generating less operating cash. "
                    "Classic liquidity stress signal — check if debt is being used to fund operations."))
    except: pass

    # 4. Inventory build-up
    try:
        inv = _row(bs,  ["Inventories", "Inventory"])
        rev = _row(pnl, ["Revenue", "Sales", "Net Sales"])
        if inv is not None and rev is not None:
            ig, rg = _cagr(inv, 3), _cagr(rev, 3)
            if ig > rg + 0.15:
                flags.append(("MEDIUM", "Inventory accumulating faster than revenue",
                    f"Inventory CAGR {ig:.0%} vs Revenue CAGR {rg:.0%}. "
                    f"Could indicate demand slowdown, obsolescence risk, or inventory inflation."))
    except: pass

    # 5. Other income > 20% of PBT
    try:
        oi  = _row(pnl, ["Other Income"])
        pbt = _row(pnl, ["Profit before tax", "PBT"])
        if oi is not None and pbt is not None and pbt.iloc[-1] != 0:
            r = oi.iloc[-1] / pbt.iloc[-1]
            if r > 0.20:
                flags.append(("MEDIUM", f"Other income = {r:.0%} of PBT",
                    "High reliance on non-operating income (interest, forex gains, asset sales). "
                    "Core business profitability is weaker than headline numbers suggest."))
    except: pass

    # 6. Negative CFO despite profits
    try:
        cfo = _row(cf,  ["Cash from Operating Activity", "Operating Cash Flow"])
        pat = _row(pnl, ["Net Profit", "Profit after tax"])
        if cfo is not None and pat is not None:
            neg = int((cfo.iloc[-5:] < 0).sum())
            pos = int((pat.iloc[-5:] > 0).sum())
            if neg >= 2 and pos >= 4:
                flags.append(("HIGH", f"Negative CFO in {neg} of last 5 years",
                    f"Reported profits in {pos}/5 years but negative operating cash flow in {neg}/5 years. "
                    "Strong sign of earnings manipulation or poor working capital management."))
    except: pass

    # 7. Degrowth in revenue (3Y)
    try:
        rev = _row(pnl, ["Revenue", "Sales", "Net Sales", "Revenue from Operations"])
        if rev is not None:
            rg = _cagr(rev, 3)
            if rg < 0:
                flags.append(("MEDIUM", f"Revenue declining (3Y CAGR: {rg:.0%})",
                    "Company has been shrinking. Check if it's a cyclical dip or structural decline."))
    except: pass

    # 8. Interest coverage
    try:
        ebit   = _row(pnl, ["Operating Profit", "EBIT", "EBITDA"])
        intexp = _row(pnl, ["Interest", "Finance Costs", "Finance Cost"])
        if ebit is not None and intexp is not None and intexp.iloc[-1] != 0:
            icr = ebit.iloc[-1] / intexp.iloc[-1]
            if icr < 2.0:
                flags.append(("HIGH", f"Weak interest coverage ({icr:.1f}x)",
                    f"Operating profit covers interest only {icr:.1f}x. "
                    "Below 2x is concerning — debt servicing stress risk."))
    except: pass

    score = sum(2 if sev == "HIGH" else 1 for sev, _, _ in flags)
    return flags, min(score, 10)

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🚨 India Listed Companies — Red Flag Dashboard")
st.caption("Data sourced from Screener.in · For research purposes only · Not investment advice")

st.divider()

# Popular preset lists
PRESETS = {
    "Nifty 10 blue chips": ["RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK","HINDUNILVR","ITC","LT","AXISBANK","KOTAKBANK"],
    "High-risk watchlist":  ["YESBANK","RCOM","DHFL","SUZLON","JPPOWER","JPASSOCIAT","PCJL","VAKRANGEE"],
    "New age / loss-making": ["ZOMATO","PAYTM","NYKAA","CARTRADE","MAPMYINDIA"],
}

col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("Search companies")
    ticker_input = st.text_input(
        "Enter NSE ticker(s), comma separated",
        placeholder="e.g.  RELIANCE, TCS, ADANIENT, YESBANK",
    )
with col2:
    st.subheader("Or pick a preset")
    preset = st.selectbox("Quick lists", ["-- choose --"] + list(PRESETS.keys()))

# Resolve tickers
tickers = []
if ticker_input.strip():
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
elif preset != "-- choose --":
    tickers = PRESETS[preset]

if tickers:
    if st.button(f"🔍 Analyse {len(tickers)} company/companies", type="primary"):
        st.divider()
        all_results = []

        progress = st.progress(0, text="Starting...")
        for i, ticker in enumerate(tickers):
            progress.progress((i) / len(tickers), text=f"Fetching {ticker}...")
            data = get_screener_data(ticker)
            if data is None:
                st.warning(f"Could not fetch data for **{ticker}** — check if the ticker is correct on Screener.in")
                continue
            flags, score = run_red_flags(data)
            all_results.append({"ticker": ticker, "name": data["name"], "score": score, "flags": flags, "data": data})
            time.sleep(1.5)

        progress.progress(1.0, text="Done!")
        time.sleep(0.5)
        progress.empty()

        if not all_results:
            st.error("No results. Check your ticker symbols.")
            st.stop()

        # Sort by score descending
        all_results.sort(key=lambda x: x["score"], reverse=True)

        # Summary row
        st.subheader("Summary")
        cols = st.columns(len(all_results))
        for col, r in zip(cols, all_results):
            with col:
                s = r["score"]
                css = "score-bad" if s >= 6 else "score-ok" if s >= 3 else "score-good"
                st.markdown(f"**{r['ticker']}**")
                st.markdown(f"<span class='{css}'>{s}/10</span>", unsafe_allow_html=True)
                st.caption(f"{len(r['flags'])} flag(s)")

        st.divider()

        # Detail cards
        for r in all_results:
            with st.expander(f"{'🔴' if r['score']>=6 else '🟡' if r['score']>=3 else '✅'}  {r['ticker']} — {r['name']}   |   Score: {r['score']}/10", expanded=(r['score']>=3)):
                if not r["flags"]:
                    st.success("No red flags detected in the checks run.")
                else:
                    for sev, title, detail in r["flags"]:
                        css = "flag-high" if sev == "HIGH" else "flag-medium"
                        icon = "🔴" if sev == "HIGH" else "🟡"
                        st.markdown(f'<div class="{css}"><strong>{icon} {title}</strong><br><span style="color:#555;font-size:13px;">{detail}</span></div>', unsafe_allow_html=True)

                # Mini financials snapshot
                st.markdown("**Key financials snapshot**")
                pnl = r["data"]["pnl"]
                cf  = r["data"]["cashflow"]
                snap_rows = {}
                for label, names, df in [
                    ("Revenue (₹ Cr)", ["Revenue","Sales","Net Sales","Revenue from Operations"], pnl),
                    ("Net Profit (₹ Cr)", ["Net Profit","Profit after tax"], pnl),
                    ("CFO (₹ Cr)", ["Cash from Operating Activity","Operating Cash Flow"], cf),
                ]:
                    row = _row(df, names)
                    if row is not None:
                        snap_rows[label] = row.tail(5)

                if snap_rows:
                    snap_df = pd.DataFrame(snap_rows).T
                    st.dataframe(snap_df.style.format("{:,.0f}"), use_container_width=True)

        # Excel download
        st.divider()
        st.subheader("Download report")
        rows = []
        for r in all_results:
            rows.append({
                "Ticker": r["ticker"],
                "Company": r["name"],
                "Red Flag Score (0-10)": r["score"],
                "Flag Count": len(r["flags"]),
                "Flags": " | ".join(f"[{s}] {t}" for s, t, _ in r["flags"]) or "None",
            })
        df_out = pd.DataFrame(rows)
        st.dataframe(df_out, use_container_width=True)

        import io
        buf = io.BytesIO()
        df_out.to_excel(buf, index=False)
        st.download_button("⬇️ Download Excel report", buf.getvalue(),
                           file_name="red_flag_report.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
