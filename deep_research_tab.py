# ============================================================
#  DEEP RESEARCH TAB  —  deep_research_tab.py
#
#  Integrates with the India Red Flag Dashboard (app.py)
#
#  AI STACK (fully free):
#    - DuckDuckGo  → web search (no key needed)
#    - Groq        → primary LLM  (console.groq.com — free)
#    - Gemini      → fallback LLM (aistudio.google.com — free)
#
#  SECTION A — FORENSIC MODELS  (Beneish M-Score, Altman Z-Score)
#  SECTION B — AI CALLER        (Groq + Gemini + DuckDuckGo)
#  SECTION C — GOVERNANCE SCAN
#  SECTION D — CONCALL INTELLIGENCE
#  SECTION E — FINAL VERDICT ENGINE
#  SECTION F — UI RENDERER
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import json
import os
import time
from datetime import datetime

# ──────────────────────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────────────────────

def _last(series):
    if series is None or series.empty:
        return None
    s = series.dropna()
    return float(s.iloc[-1]) if not s.empty else None

def _prev(series):
    if series is None or series.empty:
        return None
    s = series.dropna()
    return float(s.iloc[-2]) if len(s) >= 2 else None

def _avg(series, n=3):
    if series is None or series.empty:
        return None
    s = series.dropna().iloc[-n:]
    return float(s.mean()) if not s.empty else None

def fmt_cr(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    v = float(v)
    if abs(v) >= 100000:
        return f"₹{v/100000:.1f}L Cr"
    if abs(v) >= 1000:
        return f"₹{v/1000:.1f}K Cr"
    return f"₹{v:,.1f} Cr"

def _safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


# ══════════════════════════════════════════════════════════════
#  SECTION A — FORENSIC MODELS
# ══════════════════════════════════════════════════════════════

def compute_beneish_mscore(data):
    """
    Beneish M-Score (8-factor model).
    Components:
      DSRI  = Days Sales Receivable Index
      GMI   = Gross Margin Index
      AQI   = Asset Quality Index
      SGI   = Sales Growth Index
      DEPI  = Depreciation Index
      SGAI  = SG&A Index (proxied via interest/revenue)
      LVGI  = Leverage Index
      TATA  = Total Accruals to Total Assets
    """
    pnl = data.get("pnl", {})
    bs  = data.get("bs",  {})
    cf  = data.get("cf",  {})

    rev  = pnl.get("revenue")
    gp   = pnl.get("gross_profit")
    dep  = pnl.get("depreciation")
    pat  = pnl.get("net_profit")
    rec  = bs.get("receivables")
    ta   = bs.get("total_assets")
    nca  = bs.get("non_current_assets")
    debt = bs.get("total_debt")
    cfo  = cf.get("cfo")

    components = {}
    missing = []

    # DSRI
    rec_t = _last(rec); rec_p = _prev(rec)
    rev_t = _last(rev); rev_p = _prev(rev)
    if all(v not in (None, 0) for v in [rec_t, rec_p, rev_t, rev_p]):
        dsri = (rec_t / rev_t) / (rec_p / rev_p)
    else:
        dsri = 1.0; missing.append("DSRI")
    components["DSRI"] = {"value": round(dsri, 3), "weight": 0.920,
                           "label": "Days Sales Receivable Index", "flag": dsri > 1.465,
                           "note": "Receivables growing faster than revenue → potential channel stuffing"}

    # GMI
    gp_t = _last(gp); gp_p = _prev(gp)
    if all(v not in (None, 0) for v in [gp_t, gp_p, rev_t, rev_p]):
        gmi = _safe_div(gp_p / rev_p, gp_t / rev_t) or 1.0
    else:
        gmi = 1.0; missing.append("GMI")
    components["GMI"] = {"value": round(gmi, 3), "weight": 0.528,
                          "label": "Gross Margin Index", "flag": gmi > 1.193,
                          "note": "Margins deteriorating — incentive to manipulate earnings"}

    # AQI
    ca_t  = _last(bs.get("current_assets")); ca_p  = _prev(bs.get("current_assets"))
    nca_t = _last(nca);                       nca_p = _prev(nca)
    ta_t  = _last(ta);                        ta_p  = _prev(ta)
    if all(v not in (None, 0) for v in [ca_t, nca_t, ta_t, ca_p, nca_p, ta_p]):
        aqi = _safe_div(1 - (ca_t + nca_t) / ta_t, 1 - (ca_p + nca_p) / ta_p) or 1.0
    else:
        aqi = 1.0; missing.append("AQI")
    components["AQI"] = {"value": round(aqi, 3), "weight": 0.404,
                          "label": "Asset Quality Index", "flag": aqi > 1.254,
                          "note": "Non-current / intangible assets increasing → possible capitalisation"}

    # SGI
    sgi = _safe_div(rev_t, rev_p) or 1.0
    if rev_t is None or rev_p is None: missing.append("SGI")
    components["SGI"] = {"value": round(sgi, 3), "weight": 0.892,
                          "label": "Sales Growth Index", "flag": sgi > 1.607,
                          "note": "High growth companies face pressure to sustain it through manipulation"}

    # DEPI
    dep_t = _last(dep); dep_p = _prev(dep)
    ppe_t = _last(nca);  ppe_p = _prev(nca)
    if all(v not in (None, 0) for v in [dep_t, dep_p, ppe_t, ppe_p]):
        depi = _safe_div(dep_p / (dep_p + ppe_p), dep_t / (dep_t + ppe_t)) or 1.0
    else:
        depi = 1.0; missing.append("DEPI")
    components["DEPI"] = {"value": round(depi, 3), "weight": 0.115,
                           "label": "Depreciation Index", "flag": depi > 1.077,
                           "note": "Slowing depreciation rate → assets being sweated or life extended"}

    # SGAI (proxy: interest/revenue)
    int_t = abs(_last(pnl.get("interest_exp")) or 0)
    int_p = abs(_prev(pnl.get("interest_exp")) or 0)
    if all(v not in (None, 0) for v in [int_t, int_p, rev_t, rev_p]):
        sgai = _safe_div(int_t / rev_t, int_p / rev_p) or 1.0
    else:
        sgai = 1.0; missing.append("SGAI")
    components["SGAI"] = {"value": round(sgai, 3), "weight": 0.415,
                           "label": "Expense Index (Interest/Revenue proxy)", "flag": sgai > 1.041,
                           "note": "Disproportionate expense growth vs revenue"}

    # LVGI
    cl_t  = _last(bs.get("current_liab")); cl_p = _prev(bs.get("current_liab"))
    dbt_t = _last(debt);                   dbt_p = _prev(debt)
    if all(v not in (None, 0) for v in [cl_t, cl_p, dbt_t, dbt_p, ta_t, ta_p]):
        lvgi = _safe_div((dbt_t + cl_t) / ta_t, (dbt_p + cl_p) / ta_p) or 1.0
    else:
        lvgi = 1.0; missing.append("LVGI")
    components["LVGI"] = {"value": round(lvgi, 3), "weight": 0.172,
                           "label": "Leverage Index", "flag": lvgi > 1.111,
                           "note": "Increasing leverage → debt covenant pressure to inflate profits"}

    # TATA
    pat_t = _last(pat); cfo_t = _last(cfo)
    if all(v is not None for v in [pat_t, cfo_t, ta_t]) and ta_t != 0:
        tata = (pat_t - cfo_t) / ta_t
    else:
        tata = 0.0; missing.append("TATA")
    components["TATA"] = {"value": round(tata, 4), "weight": 4.679,
                           "label": "Total Accruals to Total Assets", "flag": tata > 0.031,
                           "note": "High accruals = earnings not backed by cash → manipulation signal"}

    m_score = round(
        -4.840 + 0.920*dsri + 0.528*gmi + 0.404*aqi + 0.892*sgi
        + 0.115*depi + 0.415*sgai + 0.172*lvgi + 4.679*tata, 3
    )

    if m_score > -1.78:
        interpretation, verdict_color, verdict_icon, risk_level = "Likely manipulator",    "#ef4444", "🔴", "HIGH"
    elif m_score > -2.22:
        interpretation, verdict_color, verdict_icon, risk_level = "Grey zone — monitor",   "#f59e0b", "🟡", "MEDIUM"
    else:
        interpretation, verdict_color, verdict_icon, risk_level = "Unlikely manipulator",  "#22c55e", "🟢", "LOW"

    return {
        "score": m_score, "interpretation": interpretation,
        "verdict_color": verdict_color, "verdict_icon": verdict_icon,
        "risk_level": risk_level, "components": components,
        "red_flags": [k for k, v in components.items() if v["flag"]],
        "missing": missing, "threshold": -1.78,
    }


def compute_altman_zscore(data, sector=""):
    """Altman Z-Score: Z = 1.2X1 + 1.4X2 + 3.3X3 + 0.6X4 + 1.0X5"""
    pnl  = data.get("pnl", {})
    bs   = data.get("bs",  {})
    mcap = data.get("mcap_cr")

    ca   = _last(bs.get("current_assets"))
    cl   = _last(bs.get("current_liab"))
    ta   = _last(bs.get("total_assets"))
    debt = _last(bs.get("total_debt"))
    ebit = _last(pnl.get("operating_profit"))
    rev  = _last(pnl.get("revenue"))

    components = {}
    missing    = []

    x1 = (ca - cl) / ta if ca and cl and ta else (missing.append("X1") or 0.0)
    components["X1"] = {"value": round(x1, 4), "weight": 1.2,
                         "label": "Working Capital / Total Assets",
                         "note": "Liquidity — negative means current debts exceed current assets"}

    pat_s = pnl.get("net_profit")
    if pat_s is not None and ta:
        x2 = float(pat_s.dropna().sum()) / ta
    else:
        x2 = 0.0; missing.append("X2")
    components["X2"] = {"value": round(x2, 4), "weight": 1.4,
                         "label": "Retained Earnings (proxy) / Total Assets",
                         "note": "Cumulative profitability"}

    x3 = ebit / ta if ebit and ta else (missing.append("X3") or 0.0)
    components["X3"] = {"value": round(x3, 4), "weight": 3.3,
                         "label": "EBIT / Total Assets", "note": "Core earnings power"}

    if mcap and debt and cl:
        x4 = _safe_div(mcap, (debt or 0) + (cl or 0)) or 0.0
    else:
        x4 = 1.0; missing.append("X4")
    components["X4"] = {"value": round(x4, 4), "weight": 0.6,
                         "label": "Market Cap / Total Liabilities",
                         "note": "Market confidence vs debt burden"}

    x5 = rev / ta if rev and ta else (missing.append("X5") or 0.0)
    components["X5"] = {"value": round(x5, 4), "weight": 1.0,
                         "label": "Revenue / Total Assets", "note": "Asset efficiency"}

    z_score = round(1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5, 3)
    is_financial = any(k in sector.lower() for k in ["bank", "financial", "nbfc", "insurance"])

    if is_financial:
        interpretation, verdict_color, verdict_icon, risk_level = \
            "Z-Score less reliable for financial sector", "#6b7280", "⚪", "N/A"
    elif z_score < 1.81:
        interpretation, verdict_color, verdict_icon, risk_level = \
            "Distress zone — high bankruptcy risk", "#ef4444", "🔴", "HIGH"
    elif z_score < 2.99:
        interpretation, verdict_color, verdict_icon, risk_level = \
            "Grey zone — financial stress possible", "#f59e0b", "🟡", "MEDIUM"
    else:
        interpretation, verdict_color, verdict_icon, risk_level = \
            "Safe zone — financially healthy", "#22c55e", "🟢", "LOW"

    return {
        "score": z_score, "interpretation": interpretation,
        "verdict_color": verdict_color, "verdict_icon": verdict_icon,
        "risk_level": risk_level, "components": components,
        "missing": missing, "is_financial": is_financial,
        "zones": {"distress": 1.81, "grey": 2.99},
    }


# ══════════════════════════════════════════════════════════════
#  SECTION B — FREE AI STACK
#  DuckDuckGo (search) + Groq (primary) + Gemini (fallback)
# ══════════════════════════════════════════════════════════════

def _get_groq_key():
    try:
        return st.secrets["GROQ_API_KEY"]
    except Exception:
        return os.environ.get("GROQ_API_KEY")

def _get_gemini_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY")


def web_search_ddg(query, max_results=6):
    """
    Free web search via DuckDuckGo.
    Tries duckduckgo_search library first, falls back to HTML scrape.
    No API key required.
    Install: pip install duckduckgo-search
    """
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [
                {"title": r.get("title",""), "body": r.get("body",""), "url": r.get("href","")}
                for r in results
            ]
    except ImportError:
        return _ddg_html_fallback(query, max_results)
    except Exception:
        return _ddg_html_fallback(query, max_results)


def _ddg_html_fallback(query, max_results=5):
    """Fallback: scrape DuckDuckGo HTML — no library needed."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=headers,
            timeout=10
        )
        if not resp.ok:
            return []
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for r in soup.select(".result__body")[:max_results]:
            title   = r.select_one(".result__title")
            snippet = r.select_one(".result__snippet")
            url     = r.select_one(".result__url")
            results.append({
                "title": title.get_text(strip=True)   if title   else "",
                "body":  snippet.get_text(strip=True) if snippet else "",
                "url":   url.get_text(strip=True)     if url     else "",
            })
        return results
    except Exception:
        return []


def call_groq(prompt, system_prompt, max_tokens=2500):
    """Call Groq API — free, uses llama-3.3-70b-versatile."""
    api_key = _get_groq_key()
    if not api_key:
        return None, "GROQ_API_KEY not set"
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.1,
            },
            timeout=60,
        )
        if not resp.ok:
            return None, f"Groq HTTP {resp.status_code}: {resp.text[:250]}"
        return resp.json()["choices"][0]["message"]["content"], None
    except requests.exceptions.Timeout:
        return None, "Groq timed out"
    except Exception as e:
        return None, f"Groq error: {str(e)[:150]}"


def call_gemini(prompt, system_prompt, max_tokens=2500):
    """Call Gemini API — free, uses gemini-1.5-flash."""
    api_key = _get_gemini_key()
    if not api_key:
        return None, "GEMINI_API_KEY not set"
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
            json={
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.1},
            },
            timeout=60,
        )
        if not resp.ok:
            return None, f"Gemini HTTP {resp.status_code}: {resp.text[:250]}"
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"], None
    except requests.exceptions.Timeout:
        return None, "Gemini timed out"
    except Exception as e:
        return None, f"Gemini error: {str(e)[:150]}"


def call_ai(prompt, system_prompt, max_tokens=2500):
    """
    Primary AI caller. Tries Groq first (faster), auto-falls back to Gemini.
    Returns response string or ⚠️-prefixed error.
    """
    content, err = call_groq(prompt, system_prompt, max_tokens)
    if content:
        return content

    st.caption(f"ℹ️ Groq unavailable ({err}), switching to Gemini…")
    content, err = call_gemini(prompt, system_prompt, max_tokens)
    if content:
        return content

    return f"⚠️ Both Groq and Gemini failed. Last error: {err}"


def build_search_context(search_queries, max_results_per_query=4):
    """
    Runs multiple DuckDuckGo searches and compiles results into a
    text block injected into the AI prompt as context.
    """
    parts = []
    for query in search_queries:
        results = web_search_ddg(query, max_results=max_results_per_query)
        if results:
            parts.append(f'\n📌 Search: "{query}"')
            for r in results:
                parts.append(
                    f"  • {r['title']}\n"
                    f"    {r['body'][:250]}\n"
                    f"    URL: {r['url']}"
                )
    return "\n".join(parts) if parts else "No search results returned."


def _parse_json_response(raw, context=""):
    """Safely extract a JSON object from an AI response string."""
    if not raw or str(raw).startswith("⚠️"):
        return None, raw
    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(clean[start:end]), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error ({context}): {str(e)[:150]}\nRaw snippet: {raw[:300]}"
    return None, f"No JSON object found ({context})"


# ══════════════════════════════════════════════════════════════
#  SECTION C — GOVERNANCE SCAN
# ══════════════════════════════════════════════════════════════

def _governance_fallback(raw=""):
    return {
        "governance_score": 5, "overall_risk": "UNKNOWN",
        "auditor_issues": [], "sebi_actions": [], "board_changes": [],
        "credit_events": [], "regulatory_actions": [], "other_flags": [],
        "positive_signals": [],
        "summary": raw[:400] if raw and not str(raw).startswith("⚠️") else "Could not retrieve governance data.",
        "sources_checked": [],
    }


def _build_governance_queries(company_name, nse_sym, sector, risk_flags, manip_flags):
    """
    Derives search queries dynamically from detected financial flags.
    No hardcoded company-specific templates — all driven by what anomalies were found.
    """
    queries = [
        f"{company_name} SEBI notice investigation penalty 2024 2025",
        f"{company_name} auditor resignation qualification 2024 2025",
        f"{company_name} director CEO CFO resignation exit 2024 2025",
        f"{nse_sym} NSE BSE corporate announcement board 2024 2025",
    ]

    # Sector-specific regulator queries
    sector_l = sector.lower()
    if any(k in sector_l for k in ["bank", "nbfc", "financial", "lending"]):
        queries += [
            f"{company_name} RBI penalty directive NPA default 2024 2025",
            f"{company_name} credit rating downgrade ICRA CRISIL CARE 2024",
        ]
    elif "insurance" in sector_l:
        queries.append(f"{company_name} IRDAI penalty action 2024 2025")
    elif any(k in sector_l for k in ["telecom", "tele"]):
        queries.append(f"{company_name} TRAI DOT penalty 2024 2025")
    elif any(k in sector_l for k in ["pharma", "drug"]):
        queries.append(f"{company_name} FDA warning letter import alert 2024 2025")
    else:
        queries.append(f"{company_name} credit rating downgrade NCLT IBC 2024 2025")

    # Flag-driven queries — each financial anomaly maps to a real-world search
    all_flags = list(risk_flags or []) + list(manip_flags or [])
    for f in all_flags:
        detail = (f[2] if len(f) > 2 else str(f)).lower()
        if any(k in detail for k in ["receivable", "channel", "revenue recognition"]):
            queries.append(f"{company_name} revenue recognition fraud channel stuffing 2024")
        if any(k in detail for k in ["debt", "leverage", "interest"]):
            queries.append(f"{company_name} loan default debt restructuring NPA 2024 2025")
        if any(k in detail for k in ["cash", "cfo", "accrual"]):
            queries.append(f"{company_name} cash flow audit qualification 2024 2025")
        if any(k in detail for k in ["promoter", "pledge"]):
            queries.append(f"{company_name} promoter pledge margin call stake sale 2024")
        if any(k in detail for k in ["margin", "profit"]):
            queries.append(f"{company_name} margin pressure regulatory price control 2024")

    # Deduplicate preserving order, cap at 8
    seen, unique = set(), []
    for q in queries:
        if q not in seen:
            seen.add(q); unique.append(q)
    return unique[:8]


def governance_scan(company_name, ticker, sector, risk_flags=None, manip_flags=None):
    """
    Governance scan: DuckDuckGo search → Groq/Gemini analysis.
    Search queries are derived from detected financial flags, not hardcoded.
    """
    nse_sym = ticker.replace(".NS", "").replace(".BO", "")
    queries = _build_governance_queries(company_name, nse_sym, sector, risk_flags or [], manip_flags or [])

    with st.status("🔍 Running governance searches…", expanded=False) as status:
        search_context = build_search_context(queries, max_results_per_query=4)
        status.update(label=f"✅ Completed {len(queries)} searches", state="complete")

    flag_lines = [
        f"  [{f[1] if len(f)>1 else 'MEDIUM'}] {f[2] if len(f)>2 else str(f)}"
        for f in list(risk_flags or []) + list(manip_flags or [])
    ]
    flag_section = "\n".join(flag_lines) if flag_lines else "  None detected"

    system = """You are a forensic equity research analyst for Indian listed companies.
Analyze the web search results and extract governance risk signals.
Respond ONLY in valid JSON — no markdown, no text outside the JSON object.
Return exactly:
{
  "governance_score": <1-10, 10=highest risk>,
  "overall_risk": "<LOW|MEDIUM|HIGH>",
  "auditor_issues":     [{"date":"...","detail":"...","severity":"<LOW|MEDIUM|HIGH>"}],
  "sebi_actions":       [{"date":"...","detail":"...","severity":"<LOW|MEDIUM|HIGH>"}],
  "board_changes":      [{"date":"...","detail":"...","severity":"<LOW|MEDIUM|HIGH>"}],
  "credit_events":      [{"date":"...","detail":"...","severity":"<LOW|MEDIUM|HIGH>"}],
  "regulatory_actions": [{"date":"...","detail":"...","severity":"<LOW|MEDIUM|HIGH>"}],
  "other_flags":        [{"date":"...","detail":"...","severity":"<LOW|MEDIUM|HIGH>"}],
  "positive_signals":   ["..."],
  "summary": "<2-3 sentence governance summary>",
  "sources_checked": ["..."]
}
Only include findings supported by the search results. Return [] for empty categories."""

    prompt = f"""Company: {company_name} (NSE: {nse_sym}, Sector: {sector})

FINANCIAL RED FLAGS ALREADY DETECTED:
{flag_section}

WEB SEARCH RESULTS:
{search_context}

Instructions:
1. Extract all governance risk events from the search results above
2. For each financial flag, look for real-world events in the results that could explain it
3. Note positive governance signals if present
4. Score overall governance risk 1-10 (10 = very high risk)
5. Only report what is supported by the search results — do not hallucinate

Return ONLY valid JSON."""

    raw = call_ai(prompt, system, max_tokens=2000)

    if str(raw).startswith("⚠️"):
        st.error(f"🚨 Governance scan failed: {raw}")
        return _governance_fallback(raw)

    result, err = _parse_json_response(raw, "governance_scan")
    if err:
        st.warning(f"⚠️ Governance parse issue: {err}")
        return _governance_fallback(raw)

    return result


# ══════════════════════════════════════════════════════════════
#  SECTION D — CONCALL INTELLIGENCE
# ══════════════════════════════════════════════════════════════

def _concall_fallback(raw=""):
    return {
        "quarters_found": 0, "quarters_data": [], "flag_tracking": [],
        "overall_credibility": "UNKNOWN", "credibility_score": 5,
        "key_concerns": [], "positive_signals": [],
        "summary": raw[:400] if raw and not str(raw).startswith("⚠️") else "Could not retrieve concall data.",
    }


def _build_concall_queries(company_name, nse_sym):
    """
    Queries targeting sources that ARE publicly indexed:
    news articles, analyst summaries, business press coverage of earnings calls.
    Raw transcripts are mostly paywalled so we target secondary coverage instead.
    """
    return [
        f"{company_name} earnings call management commentary Q4 FY25",
        f"{company_name} concall highlights management Q3 FY25",
        f"{company_name} quarterly results management guidance 2025",
        f"{company_name} investor call analyst meet commentary 2024 2025",
        f"{nse_sym} concall transcript screener 2024 2025",
        f"{company_name} management guidance revenue outlook FY26",
        f'"{company_name}" "management said" OR "management stated" earnings 2024 2025',
    ]


def concall_intelligence(company_name, ticker, risk_flags, manip_flags):
    """
    Concall intelligence: DuckDuckGo search → Groq/Gemini analysis.
    Searches news and analyst coverage (publicly indexed) rather than
    paywalled raw transcript PDFs.
    """
    nse_sym = ticker.replace(".NS", "").replace(".BO", "")
    queries = _build_concall_queries(company_name, nse_sym)

    with st.status("📞 Searching earnings call coverage…", expanded=False) as status:
        search_context = build_search_context(queries, max_results_per_query=4)
        status.update(label=f"✅ Completed {len(queries)} searches", state="complete")

    flag_lines = [
        f"  [{f[1] if len(f)>1 else 'MEDIUM'}] {f[2] if len(f)>2 else str(f)}"
        for f in list(risk_flags or []) + list(manip_flags or [])[:8]
    ]
    flag_section = "\n".join(flag_lines) if flag_lines else "  No specific flags — do general credibility review"

    system = """You are a forensic equity analyst reviewing management credibility via earnings calls.
Analyze the web search results to extract management commentary and assess credibility.
Respond ONLY in valid JSON — no markdown, no text outside the JSON.

Signs of LOW credibility to flag:
- Explanations for red flags keep changing quarter to quarter
- Vague language with no resolution timeline
- Guided high repeatedly but delivered low
- Avoided specific analyst questions on concerns"""

    prompt = f"""Company: {company_name} (NSE: {nse_sym})

FINANCIAL RED FLAGS TO TRACK — find what management said about each:
{flag_section}

WEB SEARCH RESULTS (earnings call coverage, analyst notes, news articles):
{search_context}

From the search results extract:
1. Per-quarter management commentary (last 4 quarters if available)
2. What management said specifically about each red flag
3. Whether management tone or explanations changed across quarters
4. Any guidance given and whether it was met
5. Overall credibility assessment

Return this exact JSON:
{{
  "quarters_found": <0-4>,
  "quarters_data": [
    {{
      "quarter": "Q4 FY25",
      "date": "May 2025",
      "source": "<publication name or URL>",
      "key_themes": ["theme1","theme2","theme3"],
      "commentary_on_flags": {{"<flag short name>": "<what management said>"}},
      "management_tone": "<Confident|Cautious|Evasive|Optimistic|Defensive>",
      "credibility_score": <1-10>,
      "notable_quotes": ["<quote under 15 words>"],
      "guidance_given": "<guidance for next period>",
      "red_flags_in_call": ["<anything concerning said or conspicuously avoided>"]
    }}
  ],
  "flag_tracking": [
    {{
      "flag": "<flag title from the list above>",
      "trend": "<Resolved|Improving|Persistent|Worsening|Not Addressed>",
      "trend_color": "<green|yellow|orange|red>",
      "q_by_q": {{"Q1":"...","Q2":"...","Q3":"...","Q4":"..."}},
      "management_credible": <true|false>,
      "insight": "<2 sentence analyst insight on how management handled this>"
    }}
  ],
  "overall_credibility": "<LOW|MEDIUM|HIGH>",
  "credibility_score": <1-10>,
  "key_concerns": ["..."],
  "positive_signals": ["..."],
  "summary": "<3-4 sentence overall assessment>"
}}

Only report what is supported by search results. Do not fabricate quotes or events.
If no data found for a quarter, omit it from quarters_data.
Return ONLY valid JSON."""

    raw = call_ai(prompt, system, max_tokens=3000)

    if str(raw).startswith("⚠️"):
        st.error(f"🚨 Concall intelligence failed: {raw}")
        return _concall_fallback(raw)

    result, err = _parse_json_response(raw, "concall_intelligence")
    if err:
        st.warning(f"⚠️ Concall parse issue: {err}")
        return _concall_fallback(raw)

    return result


# ══════════════════════════════════════════════════════════════
#  SECTION E — FINAL VERDICT ENGINE
# ══════════════════════════════════════════════════════════════

def compute_final_verdict(risk_score, manip_score, m_score_result, z_score_result,
                           governance_result, concall_result):
    reasons, positives, score_components = [], [], []

    # Financial risk
    if risk_score >= 6:
        reasons.append(f"High financial risk score ({risk_score}/10)")
        score_components.append(("Financial Risk", risk_score, 10, "#ef4444"))
    elif risk_score >= 3:
        reasons.append(f"Moderate financial risk ({risk_score}/10)")
        score_components.append(("Financial Risk", risk_score, 10, "#f59e0b"))
    else:
        positives.append(f"Clean financial risk profile ({risk_score}/10)")
        score_components.append(("Financial Risk", risk_score, 10, "#22c55e"))

    # Manipulation
    if manip_score >= 6:
        reasons.append(f"High manipulation signal score ({manip_score}/10)")
        score_components.append(("Manipulation Signal", manip_score, 10, "#a78bfa"))
    elif manip_score >= 3:
        reasons.append(f"Some manipulation signals ({manip_score}/10)")
        score_components.append(("Manipulation Signal", manip_score, 10, "#c4b5fd"))
    else:
        positives.append(f"No significant manipulation signals ({manip_score}/10)")
        score_components.append(("Manipulation Signal", manip_score, 10, "#6ee7b7"))

    # Beneish
    m_risk = m_score_result.get("risk_level", "LOW")
    m_val  = m_score_result.get("score", -3.0)
    m_red  = len(m_score_result.get("red_flags", []))
    if m_risk == "HIGH":
        reasons.append(f"Beneish M-Score ({m_val}) in manipulation zone — {m_red} components flagged")
        score_components.append(("Beneish M-Score", min(8, m_red * 2), 10, "#ef4444"))
    elif m_risk == "MEDIUM":
        reasons.append(f"Beneish M-Score ({m_val}) in grey zone")
        score_components.append(("Beneish M-Score", 5, 10, "#f59e0b"))
    else:
        positives.append(f"Beneish M-Score ({m_val}) — no manipulation signal")
        score_components.append(("Beneish M-Score", 2, 10, "#22c55e"))

    # Altman
    z_risk = z_score_result.get("risk_level", "LOW")
    z_val  = z_score_result.get("score", 3.0)
    if z_risk == "HIGH":
        reasons.append(f"Altman Z-Score ({z_val}) in distress zone")
        score_components.append(("Altman Z-Score", 8, 10, "#ef4444"))
    elif z_risk == "MEDIUM":
        reasons.append(f"Altman Z-Score ({z_val}) in grey zone")
        score_components.append(("Altman Z-Score", 5, 10, "#f59e0b"))
    elif z_risk == "N/A":
        score_components.append(("Altman Z-Score", 0, 10, "#6b7280"))
    else:
        positives.append(f"Altman Z-Score ({z_val}) — safe zone")
        score_components.append(("Altman Z-Score", 2, 10, "#22c55e"))

    # Governance
    gov_risk  = governance_result.get("overall_risk", "UNKNOWN")
    gov_score = governance_result.get("governance_score", 5)
    if gov_risk == "HIGH":
        reasons.append(f"High governance risk ({gov_score}/10)")
        score_components.append(("Governance", gov_score, 10, "#ef4444"))
    elif gov_risk == "MEDIUM":
        reasons.append(f"Moderate governance concerns ({gov_score}/10)")
        score_components.append(("Governance", gov_score, 10, "#f59e0b"))
    elif gov_risk == "LOW":
        positives.append("Clean governance profile")
        score_components.append(("Governance", gov_score, 10, "#22c55e"))
    else:
        score_components.append(("Governance", 5, 10, "#6b7280"))

    # Concall credibility
    cc_cred  = concall_result.get("overall_credibility", "UNKNOWN")
    cc_score = concall_result.get("credibility_score", 5)
    if cc_cred == "LOW":
        reasons.append(f"Low management credibility ({cc_score}/10)")
        score_components.append(("Mgmt Credibility", 10 - cc_score, 10, "#ef4444"))
    elif cc_cred == "MEDIUM":
        score_components.append(("Mgmt Credibility", 10 - cc_score, 10, "#f59e0b"))
    elif cc_cred == "HIGH":
        positives.append("High management credibility in earnings calls")
        score_components.append(("Mgmt Credibility", 10 - cc_score, 10, "#22c55e"))
    else:
        score_components.append(("Mgmt Credibility", 5, 10, "#6b7280"))

    weights = {
        "Financial Risk": 0.25, "Manipulation Signal": 0.20,
        "Beneish M-Score": 0.20, "Altman Z-Score": 0.15,
        "Governance": 0.10, "Mgmt Credibility": 0.10,
    }
    composite = round(sum(
        (val / mx) * weights.get(label, 0.10) * 10
        for label, val, mx, _ in score_components if mx > 0
    ), 1)

    red_count = sum(1 for r in reasons if any(w in r for w in ["High", "distress", "manipulation zone"]))

    if composite >= 6.5 or red_count >= 3:
        verdict, vc, vbg, vbd, vi = "AVOID", "#ef4444", "rgba(220,38,38,0.08)", "rgba(220,38,38,0.3)", "🔴"
        vd = "Multiple high-severity signals across financial, forensic, and governance dimensions."
    elif composite >= 4.0 or red_count >= 1:
        verdict, vc, vbg, vbd, vi = "WATCH", "#f59e0b", "rgba(245,158,11,0.08)", "rgba(245,158,11,0.3)", "🟡"
        vd = "Some concerns detected. Not safe to invest without deeper due diligence."
    else:
        verdict, vc, vbg, vbd, vi = "INVEST", "#22c55e", "rgba(34,197,94,0.08)", "rgba(34,197,94,0.3)", "🟢"
        vd = "No major red flags. Financials appear trustworthy. Proceed with normal valuation analysis."

    return {
        "verdict": verdict, "verdict_color": vc, "verdict_bg": vbg,
        "verdict_border": vbd, "verdict_icon": vi, "verdict_desc": vd,
        "composite_score": composite, "reasons": reasons,
        "positives": positives, "score_components": score_components,
    }


# ══════════════════════════════════════════════════════════════
#  SECTION F — UI RENDERER
# ══════════════════════════════════════════════════════════════

DEEP_RESEARCH_CSS = """
<style>
.dr-snapshot {
    background: linear-gradient(135deg,#060a14 0%,#090c18 100%);
    border:1px solid #1a2540;border-radius:18px;padding:2rem 2.4rem;
    margin-bottom:1.4rem;position:relative;overflow:hidden;
}
.dr-snapshot::before {
    content:'';position:absolute;top:-60px;right:-60px;width:220px;height:220px;
    background:radial-gradient(circle,rgba(139,92,246,0.1) 0%,transparent 65%);
    border-radius:50%;pointer-events:none;
}
.dr-badge {
    display:inline-flex;align-items:center;gap:5px;
    background:rgba(139,92,246,0.1);border:1px solid rgba(139,92,246,0.25);
    color:#a78bfa;font-family:'JetBrains Mono',monospace;font-size:0.58rem;
    letter-spacing:2px;text-transform:uppercase;padding:4px 12px;border-radius:20px;margin-bottom:0.7rem;
}
.dr-company-name{font-size:1.6rem;font-weight:700;color:#f0f2f8;letter-spacing:-0.5px;margin-bottom:0.2rem;}
.dr-company-meta{font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#4b5563;margin-bottom:1.2rem;}
.dr-score-row{display:flex;gap:12px;flex-wrap:wrap;}
.dr-score-pill{
    display:inline-flex;align-items:center;gap:7px;background:rgba(255,255,255,0.04);
    border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px 14px;
    font-family:'JetBrains Mono',monospace;
}
.dr-score-pill .label{font-size:0.6rem;color:#4b5563;text-transform:uppercase;letter-spacing:1.5px;}
.dr-score-pill .val{font-size:1rem;font-weight:700;letter-spacing:-0.5px;}
.dr-section{background:#0d1120;border:1px solid #1a2540;border-radius:16px;padding:1.5rem 1.8rem;margin-bottom:1.2rem;}
.dr-section-title{
    display:flex;align-items:center;gap:10px;font-family:'JetBrains Mono',monospace;
    font-size:0.63rem;text-transform:uppercase;letter-spacing:2.5px;
    margin-bottom:1.2rem;padding-bottom:0.7rem;border-bottom:1px solid #111827;
}
.forensic-card{flex:1;background:#090e1a;border-radius:14px;padding:1.2rem;text-align:center;position:relative;overflow:hidden;}
.forensic-score{font-size:2.6rem;font-weight:700;line-height:1;letter-spacing:-1.5px;margin:0.4rem 0;}
.forensic-label{font-family:'JetBrains Mono',monospace;font-size:0.58rem;text-transform:uppercase;letter-spacing:2px;color:#4b5563;margin-bottom:0.3rem;}
.forensic-verdict{font-family:'JetBrains Mono',monospace;font-size:0.6rem;font-weight:600;letter-spacing:1.2px;text-transform:uppercase;padding:3px 12px;border-radius:20px;display:inline-block;margin-top:0.4rem;}
.comp-table{width:100%;border-collapse:collapse;margin-top:0.8rem;}
.comp-table th{font-family:'JetBrains Mono',monospace;font-size:0.56rem;color:#2d3a55;text-transform:uppercase;letter-spacing:2px;padding:6px 8px;border-bottom:1px solid #0d1726;text-align:left;}
.comp-table td{font-size:0.72rem;padding:7px 8px;border-bottom:1px solid #0a1020;color:#6b7280;vertical-align:middle;}
.comp-table tr:last-child td{border-bottom:none;}
.comp-table tr:hover td{background:rgba(255,255,255,0.015);}
.comp-flag{color:#ef4444;font-weight:700;} .comp-ok{color:#34d399;}
.comp-mono{font-family:'JetBrains Mono',monospace;font-size:0.68rem;color:#e5e7eb;}
.gov-item{background:#090e1a;border-radius:10px;padding:0.85rem 1rem;margin-bottom:0.5rem;border-left:3px solid transparent;}
.gov-item.HIGH{border-left-color:#ef4444;background:rgba(220,38,38,0.05);}
.gov-item.MEDIUM{border-left-color:#f59e0b;background:rgba(245,158,11,0.05);}
.gov-item.LOW{border-left-color:#3b82f6;background:rgba(59,130,246,0.05);}
.gov-date{font-family:'JetBrains Mono',monospace;font-size:0.58rem;color:#374151;margin-bottom:3px;}
.gov-detail{font-size:0.78rem;color:#9ca3af;line-height:1.5;}
.gov-sev{font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;float:right;padding:2px 8px;border-radius:4px;}
.gov-sev.HIGH{color:#ef4444;background:rgba(220,38,38,0.1);}
.gov-sev.MEDIUM{color:#f59e0b;background:rgba(245,158,11,0.1);}
.gov-sev.LOW{color:#60a5fa;background:rgba(59,130,246,0.1);}
.quarter-card{background:#090e1a;border:1px solid #151e33;border-radius:12px;padding:1rem 1.1rem;margin-bottom:0.7rem;}
.quarter-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:0.7rem;}
.quarter-label{font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#6b7280;font-weight:600;}
.quarter-tone{font-family:'JetBrains Mono',monospace;font-size:0.55rem;padding:3px 10px;border-radius:6px;text-transform:uppercase;letter-spacing:1px;}
.tone-Confident{color:#34d399;background:rgba(52,211,153,0.1);}
.tone-Cautious{color:#f59e0b;background:rgba(245,158,11,0.1);}
.tone-Evasive{color:#ef4444;background:rgba(220,38,38,0.1);}
.tone-Defensive{color:#f87171;background:rgba(248,113,113,0.1);}
.tone-Optimistic{color:#60a5fa;background:rgba(96,165,250,0.1);}
.quarter-theme{font-size:0.72rem;color:#6b7280;line-height:1.6;}
.quarter-source{font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:#374151;margin-top:5px;}
.flag-track{background:#090e1a;border-radius:12px;padding:1rem 1.1rem;margin-bottom:0.6rem;border:1px solid #151e33;}
.flag-track-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.6rem;}
.flag-track-name{font-size:0.82rem;font-weight:600;color:#e5e7eb;}
.flag-track-status{font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;letter-spacing:1.5px;padding:3px 10px;border-radius:6px;white-space:nowrap;}
.status-Resolved{color:#34d399;background:rgba(52,211,153,0.1);}
.status-Improving{color:#60a5fa;background:rgba(96,165,250,0.1);}
.status-Persistent{color:#f59e0b;background:rgba(245,158,11,0.1);}
.status-Worsening{color:#ef4444;background:rgba(220,38,38,0.1);}
.status-Not-Addressed{color:#9ca3af;background:rgba(156,163,175,0.1);}
.flag-q-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:0.6rem 0;}
.flag-q-cell{background:rgba(255,255,255,0.03);border-radius:6px;padding:6px 8px;}
.flag-q-label{font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:#374151;margin-bottom:2px;}
.flag-q-text{font-size:0.66rem;color:#9ca3af;line-height:1.4;}
.flag-insight{font-size:0.72rem;color:#6b7280;font-style:italic;margin-top:0.5rem;line-height:1.5;}
.verdict-card{border-radius:18px;padding:2rem 2.4rem;margin-bottom:1.4rem;text-align:center;}
.verdict-word{font-size:3.5rem;font-weight:700;letter-spacing:-2px;line-height:1;margin:0.5rem 0;}
.verdict-desc{font-size:0.85rem;color:#6b7280;max-width:480px;margin:0.5rem auto;}
.verdict-composite{font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:#374151;margin-top:0.7rem;}
.reason-list{list-style:none;padding:0;margin:0.8rem 0;}
.reason-list li{font-size:0.78rem;color:#9ca3af;padding:5px 0 5px 1.2rem;position:relative;line-height:1.5;}
.reason-list li::before{content:'→';position:absolute;left:0;}
.reason-list li.neg::before{color:#ef4444;} .reason-list li.pos::before{color:#34d399;}
.score-bar-row{display:flex;align-items:center;gap:10px;margin-bottom:0.55rem;}
.score-bar-label{font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:#4b5563;width:140px;flex-shrink:0;text-transform:uppercase;}
.score-bar-track{flex:1;background:rgba(255,255,255,0.04);border-radius:4px;height:6px;overflow:hidden;}
.score-bar-fill{height:100%;border-radius:4px;}
.score-bar-val{font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:#374151;width:36px;text-align:right;}
.positive-chip{
    display:inline-flex;align-items:center;gap:4px;background:rgba(34,197,94,0.07);
    border:1px solid rgba(34,197,94,0.2);color:#4ade80;font-size:0.7rem;
    padding:4px 12px;border-radius:20px;margin:3px 4px 3px 0;
}
.dr-empty{text-align:center;padding:2rem;color:#374151;font-size:0.78rem;}
.ai-stack-badge{
    display:inline-flex;align-items:center;gap:6px;background:rgba(34,197,94,0.07);
    border:1px solid rgba(34,197,94,0.2);color:#4ade80;font-family:'JetBrains Mono',monospace;
    font-size:0.55rem;letter-spacing:1px;padding:3px 10px;border-radius:6px;margin-bottom:1rem;
}
</style>
"""


def _gauge_chart(score, color, title, min_val, max_val, threshold=None, threshold_label=""):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        title={'text': title, 'font': {'size': 10, 'color': '#6b7280', 'family': 'Space Grotesk'}},
        number={'font': {'size': 28, 'color': color, 'family': 'JetBrains Mono'}, 'valueformat': '.3f'},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [min_val, max_val], 'tickwidth': 0.5, 'tickcolor': '#1f2d47',
                     'tickfont': {'color': '#2d3a55', 'size': 7}, 'nticks': 5},
            'bar': {'color': color, 'thickness': 0.2}, 'bgcolor': '#080b14', 'borderwidth': 0,
            'threshold': {'line': {'color': '#f59e0b', 'width': 2}, 'thickness': 0.75,
                          'value': threshold if threshold else score},
        }
    ))
    fig.update_layout(
        height=180, margin=dict(t=35, b=5, l=15, r=15),
        paper_bgcolor='#0d1120', plot_bgcolor='#0d1120',
        font=dict(color='#6b7280', family='Space Grotesk'),
        annotations=[{'text': threshold_label, 'x': 0.5, 'y': -0.05,
                       'xref': 'paper', 'yref': 'paper', 'showarrow': False,
                       'font': {'size': 8, 'color': '#f59e0b', 'family': 'JetBrains Mono'}}
                     ] if threshold_label else []
    )
    return fig


def _component_waterfall(components, title, color):
    labels = list(components.keys())
    values = [v["value"] * v["weight"] for v in components.values()]
    colors = [color if components[k].get("flag") else "#1f2d47" for k in labels]
    fig = go.Figure(go.Bar(x=labels, y=values, marker=dict(color=colors, line=dict(width=0)),
                            hovertemplate="<b>%{x}</b><br>Weighted: %{y:.3f}<extra></extra>"))
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=10, color='#9ca3af', family='Space Grotesk'), x=0.5),
        height=180, margin=dict(t=30, b=10, l=5, r=5),
        paper_bgcolor='#0d1120', plot_bgcolor='#0d1120',
        font=dict(color='#6b7280', family='Space Grotesk'),
        xaxis=dict(tickfont=dict(color='#4b5563', size=8, family='JetBrains Mono'), showgrid=False),
        yaxis=dict(gridcolor='rgba(26,37,64,0.4)', showticklabels=False),
        bargap=0.3, showlegend=False,
    )
    return fig


def _verdict_radar(score_components):
    labels = [s[0] for s in score_components if s[2] > 0]
    values = [round(s[1] / s[2] * 10, 1) for s in score_components if s[2] > 0]
    if not labels: return None
    fig = go.Figure(go.Scatterpolar(
        r=values + [values[0]], theta=labels + [labels[0]],
        fill='toself', fillcolor='rgba(139,92,246,0.08)',
        line=dict(color='#7c3aed', width=1.5), marker=dict(size=4, color='#a78bfa'),
        hovertemplate="<b>%{theta}</b><br>Score: %{r}/10<extra></extra>",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='#090e1a',
            radialaxis=dict(visible=True, range=[0,10], gridcolor='rgba(26,37,64,0.6)',
                            tickfont=dict(color='#2d3a55', size=7), tickvals=[2,4,6,8,10],
                            linecolor='rgba(26,37,64,0.4)'),
            angularaxis=dict(gridcolor='rgba(26,37,64,0.4)',
                             tickfont=dict(color='#4b5563', size=8, family='JetBrains Mono'),
                             linecolor='rgba(26,37,64,0.4)'),
        ),
        height=300, margin=dict(t=20, b=20, l=40, r=40),
        paper_bgcolor='#0d1120', plot_bgcolor='#0d1120', showlegend=False,
    )
    return fig


def _check_api_keys():
    groq_ok   = bool(_get_groq_key())
    gemini_ok = bool(_get_gemini_key())
    return groq_ok, gemini_ok, groq_ok or gemini_ok


def render_deep_research_tab(result):
    """Main renderer for the Deep Research tab."""
    st.markdown(DEEP_RESEARCH_CSS, unsafe_allow_html=True)

    ticker   = result["ticker"]
    name     = result["name"]
    sector   = result["sector"]
    mcap     = result.get("mcap_cr")
    de       = result.get("de_ratio")
    promo    = result.get("promoter_holding_pct")
    risk_sc  = result.get("risk_score", 0)
    manip_sc = result.get("manip_score", 0)
    rf       = result.get("risk_flags", [])
    mf       = result.get("manip_flags", [])
    nse_sym  = ticker.replace(".NS", "").replace(".BO", "")

    # API key check
    groq_ok, gemini_ok, any_ok = _check_api_keys()
    if not any_ok:
        st.error(
            "🔑 **No AI API key found.**\n\n"
            "Add at least one to `.streamlit/secrets.toml`:\n"
            "```toml\n"
            "GROQ_API_KEY   = 'gsk_...'\n"
            "GEMINI_API_KEY = 'AIza...'\n"
            "```\n"
            "**Free keys:**\n"
            "- Groq → console.groq.com (14,400 req/day free)\n"
            "- Gemini → aistudio.google.com (1,500 req/day free)"
        )
        return

    # Show active AI stack
    active = (["⚡ Groq"] if groq_ok else []) + (["✦ Gemini"] if gemini_ok else [])
    st.markdown(
        f'<div class="ai-stack-badge">🤖 {" + ".join(active)} &nbsp;·&nbsp; 🔍 DuckDuckGo Search (free)</div>',
        unsafe_allow_html=True
    )

    # Snapshot header
    risk_color  = "#ef4444" if risk_sc >= 6 else "#f59e0b" if risk_sc >= 3 else "#22c55e"
    manip_color = "#a78bfa" if manip_sc >= 6 else "#c4b5fd" if manip_sc >= 3 else "#6ee7b7"
    st.markdown(f"""
    <div class="dr-snapshot">
      <div class="dr-badge">🔬 Deep Research Analysis</div>
      <div class="dr-company-name">{name}</div>
      <div class="dr-company-meta">
        NSE: {nse_sym} &nbsp;·&nbsp; {sector} &nbsp;·&nbsp; MCap: {fmt_cr(mcap)}
        &nbsp;·&nbsp; D/E: {f'{de:.2f}x' if de else '—'}
        &nbsp;·&nbsp; Promoter: {f'{promo:.1f}%' if promo else '—'}
      </div>
      <div class="dr-score-row">
        <div class="dr-score-pill"><span class="label">Financial Risk</span><span class="val" style="color:{risk_color};">{risk_sc}/10</span></div>
        <div class="dr-score-pill"><span class="label">Manip Signal</span><span class="val" style="color:{manip_color};">{manip_sc}/10</span></div>
        <div class="dr-score-pill"><span class="label">Total Flags</span><span class="val" style="color:#9ca3af;">{len(rf)+len(mf)}</span></div>
        <div class="dr-score-pill"><span class="label">Date</span><span class="val" style="color:#4b5563;font-size:0.7rem;">{datetime.now().strftime('%d %b %Y')}</span></div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── FORENSIC MODELS ───────────────────────────────────────
    with st.spinner("⚙️ Computing Beneish M-Score and Altman Z-Score…"):
        m_result = compute_beneish_mscore(result)
        z_result = compute_altman_zscore(result, sector)

    st.markdown("""
    <div class="dr-section">
      <div class="dr-section-title" style="color:#a78bfa;">
        <span style="width:7px;height:7px;border-radius:50%;background:#a78bfa;display:inline-block;box-shadow:0 0 8px rgba(167,139,250,0.5);"></span>
        Forensic Risk Models
      </div>""", unsafe_allow_html=True)

    col_m, col_z = st.columns(2)

    with col_m:
        mc = m_result["verdict_color"]
        st.markdown(f"""
        <div class="forensic-card" style="border:1px solid rgba(167,139,250,0.15);">
          <div class="forensic-label">🟣 Beneish M-Score</div>
          <div class="forensic-score" style="color:{mc};">{m_result['score']}</div>
          <div class="forensic-verdict" style="color:{mc};background:rgba(167,139,250,0.08);border:1px solid rgba(167,139,250,0.2);">
            {m_result['verdict_icon']} {m_result['interpretation']}
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:#374151;margin-top:8px;">Threshold: &gt; -1.78 = likely manipulator</div>
        </div>""", unsafe_allow_html=True)
        st.plotly_chart(_gauge_chart(m_result["score"], mc, "M-Score", -4, 0, -1.78, "⚠ -1.78 threshold"),
                        use_container_width=True, config={"displayModeBar": False}, key="gauge_mscore")
        st.plotly_chart(_component_waterfall(m_result["components"], "Weighted contributions", mc),
                        use_container_width=True, config={"displayModeBar": False}, key="bar_mscore")
        if m_result["red_flags"]:
            st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:0.6rem;color:#ef4444;margin:8px 0 4px;'>🚩 {len(m_result['red_flags'])} component(s) above threshold</div>", unsafe_allow_html=True)
        rows = "".join(
            f"<tr><td class='comp-mono'>{k}</td><td class='comp-mono'>{v['value']}</td>"
            f"<td style='font-size:0.65rem;color:#374151;'>×{v['weight']}</td>"
            f"<td class='{'comp-flag' if v.get('flag') else 'comp-ok'}'>{'⚑' if v.get('flag') else '✓'}</td>"
            f"<td style='font-size:0.65rem;color:#374151;max-width:160px;'>{v['note'][:60]}…</td></tr>"
            for k, v in m_result["components"].items()
        )
        st.markdown(f"<table class='comp-table'><thead><tr><th>Factor</th><th>Value</th><th>Weight</th><th>Flag</th><th>Note</th></tr></thead><tbody>{rows}</tbody></table>", unsafe_allow_html=True)
        if m_result["missing"]: st.caption(f"⚠️ Defaulted to neutral: {', '.join(m_result['missing'])}")

    with col_z:
        zc = z_result["verdict_color"]
        st.markdown(f"""
        <div class="forensic-card" style="border:1px solid rgba(239,68,68,0.15);">
          <div class="forensic-label">🔴 Altman Z-Score</div>
          <div class="forensic-score" style="color:{zc};">{z_result['score']}</div>
          <div class="forensic-verdict" style="color:{zc};background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.15);">
            {z_result['verdict_icon']} {z_result['interpretation']}
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:#374151;margin-top:8px;">&lt;1.81 distress · 1.81–2.99 grey · &gt;2.99 safe</div>
        </div>""", unsafe_allow_html=True)
        st.plotly_chart(_gauge_chart(z_result["score"], zc, "Z-Score", 0, 5, 1.81, "⚠ 1.81 distress zone"),
                        use_container_width=True, config={"displayModeBar": False}, key="gauge_zscore")
        st.plotly_chart(_component_waterfall(z_result["components"], "Weighted contributions", zc),
                        use_container_width=True, config={"displayModeBar": False}, key="bar_zscore")
        rows = "".join(
            f"<tr><td class='comp-mono'>{k}</td>"
            f"<td class='comp-mono' style='color:{'#34d399' if v['value']>0 else '#f87171'};'>{v['value']:.4f}</td>"
            f"<td style='font-size:0.65rem;color:#374151;'>×{v['weight']}</td>"
            f"<td style='font-size:0.65rem;color:#374151;'>{v['label']}</td></tr>"
            for k, v in z_result["components"].items()
        )
        st.markdown(f"<table class='comp-table'><thead><tr><th>Factor</th><th>Value</th><th>Weight</th><th>What it measures</th></tr></thead><tbody>{rows}</tbody></table>", unsafe_allow_html=True)
        if z_result["is_financial"]: st.info("ℹ️ Z-Score is less reliable for banks/NBFCs.", icon="ℹ️")
        if z_result["missing"]: st.caption(f"⚠️ Defaulted to 0: {', '.join(z_result['missing'])}")

    st.markdown("</div>", unsafe_allow_html=True)

    # ── GOVERNANCE SCAN ───────────────────────────────────────
    st.markdown("""
    <div class="dr-section">
      <div class="dr-section-title" style="color:#ef4444;">
        <span style="width:7px;height:7px;border-radius:50%;background:#ef4444;display:inline-block;box-shadow:0 0 8px rgba(239,68,68,0.5);"></span>
        Governance &amp; News Intelligence
        <span style="margin-left:auto;font-size:0.55rem;color:#374151;text-transform:none;letter-spacing:0;">DuckDuckGo + Groq/Gemini · Flag-driven</span>
      </div>""", unsafe_allow_html=True)

    gov_key = f"gov_{ticker}"
    if gov_key not in st.session_state:
        st.session_state[gov_key] = governance_scan(name, ticker, sector, rf, mf)

    gov     = st.session_state[gov_key]
    gc      = "#ef4444" if gov.get("overall_risk") == "HIGH" else "#f59e0b" if gov.get("overall_risk") == "MEDIUM" else "#22c55e" if gov.get("overall_risk") == "LOW" else "#6b7280"
    g_score = gov.get("governance_score", 5)
    g_risk  = gov.get("overall_risk", "UNKNOWN")

    col_g1, col_g2 = st.columns([1, 2])
    with col_g1:
        st.markdown(f"""
        <div class="forensic-card" style="border:1px solid rgba(239,68,68,0.15);">
          <div class="forensic-label">Governance Risk Score</div>
          <div class="forensic-score" style="color:{gc};">{g_score}<span style="font-size:1rem;color:#374151;">/10</span></div>
          <div class="forensic-verdict" style="color:{gc};background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.15);">{g_risk}</div>
          <div style="font-size:0.68rem;color:#6b7280;margin-top:12px;line-height:1.5;">{gov.get('summary','')[:180]}</div>
        </div>""", unsafe_allow_html=True)

    with col_g2:
        any_found = False
        for cat_label, cat_key in [
            ("🚨 Auditor Issues", "auditor_issues"), ("⚖️ SEBI Actions", "sebi_actions"),
            ("🏛️ Regulatory Actions", "regulatory_actions"), ("👤 Board Changes", "board_changes"),
            ("📉 Credit Events", "credit_events"), ("🔍 Other Flags", "other_flags"),
        ]:
            items = gov.get(cat_key, [])
            if items:
                any_found = True
                st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:0.6rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin:10px 0 5px;'>{cat_label}</div>", unsafe_allow_html=True)
                for item in items:
                    sev = item.get("severity", "MEDIUM")
                    st.markdown(f"""
                    <div class="gov-item {sev}">
                      <span class="gov-sev {sev}">{sev}</span>
                      <div class="gov-date">{item.get('date','Unknown date')}</div>
                      <div class="gov-detail">{item.get('detail','')}</div>
                    </div>""", unsafe_allow_html=True)
        if not any_found:
            st.success("✅ No major governance red flags found.")
        positives = gov.get("positive_signals", [])
        if positives:
            st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:0.6rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin:12px 0 6px;'>✅ Positive Signals</div>", unsafe_allow_html=True)
            st.markdown("".join(f'<span class="positive-chip">✓ {p}</span>' for p in positives[:6]), unsafe_allow_html=True)
        if gov.get("sources_checked"):
            st.caption(f"Sources: {', '.join(gov['sources_checked'][:5])}")

    if st.button("🔄 Re-run Governance Scan", key="gov_refresh"):
        del st.session_state[gov_key]; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── CONCALL INTELLIGENCE ──────────────────────────────────
    st.markdown("""
    <div class="dr-section">
      <div class="dr-section-title" style="color:#60a5fa;">
        <span style="width:7px;height:7px;border-radius:50%;background:#60a5fa;display:inline-block;box-shadow:0 0 8px rgba(96,165,250,0.5);"></span>
        Concall Intelligence — Management Credibility Tracker
        <span style="margin-left:auto;font-size:0.55rem;color:#374151;text-transform:none;letter-spacing:0;">DuckDuckGo + Groq/Gemini · Last 4 quarters</span>
      </div>""", unsafe_allow_html=True)

    cc_key = f"cc_{ticker}"
    if cc_key not in st.session_state:
        st.session_state[cc_key] = concall_intelligence(name, ticker, rf, mf)

    cc       = st.session_state[cc_key]
    qf       = cc.get("quarters_found", 0)
    cc_score = cc.get("credibility_score", 5)
    cc_cred  = cc.get("overall_credibility", "UNKNOWN")
    cc_color = "#22c55e" if cc_cred == "HIGH" else "#f59e0b" if cc_cred == "MEDIUM" else "#ef4444" if cc_cred == "LOW" else "#6b7280"

    col_c1, col_c2 = st.columns([1, 2])

    with col_c1:
        st.markdown(f"""
        <div class="forensic-card" style="border:1px solid rgba(96,165,250,0.15);">
          <div class="forensic-label">Management Credibility</div>
          <div class="forensic-score" style="color:{cc_color};">{cc_score}<span style="font-size:1rem;color:#374151;">/10</span></div>
          <div class="forensic-verdict" style="color:{cc_color};background:rgba(96,165,250,0.05);border:1px solid rgba(96,165,250,0.15);">{cc_cred}</div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.58rem;color:#374151;margin-top:8px;">{qf}/4 quarters found</div>
          <div style="font-size:0.68rem;color:#6b7280;margin-top:10px;line-height:1.5;">{cc.get('summary','')[:200]}</div>
        </div>""", unsafe_allow_html=True)
        for label, key, color in [("🔴 Key Concerns","key_concerns","#9ca3af"),("✅ Positives","positive_signals","#4ade80")]:
            items = cc.get(key, [])
            if items:
                st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin:10px 0 4px;'>{label}</div>", unsafe_allow_html=True)
                for item in items[:4]:
                    st.markdown(f"<div style='font-size:0.72rem;color:{color};padding:3px 0;'>→ {item}</div>", unsafe_allow_html=True)

    with col_c2:
        quarters = cc.get("quarters_data", [])
        if quarters:
            st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:0.6rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;'>Quarterly Commentary</div>", unsafe_allow_html=True)
            for q in quarters:
                tone   = q.get("management_tone","Neutral")
                themes = " · ".join(q.get("key_themes",[])[:3]) or "No themes extracted"
                cred   = q.get("credibility_score",5)
                cred_c = "#22c55e" if cred>=7 else "#f59e0b" if cred>=4 else "#ef4444"
                source = q.get("source","")
                rfc_html = "".join(f"<div style='font-size:0.65rem;color:#f87171;padding:2px 0;'>⚠ {r}</div>" for r in q.get("red_flags_in_call",[])[:2])
                st.markdown(f"""
                <div class="quarter-card">
                  <div class="quarter-header">
                    <span class="quarter-label">{q.get('quarter','?')} · {q.get('date','')}</span>
                    <div style="display:flex;align-items:center;gap:8px;">
                      <span style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:{cred_c};">Credibility: {cred}/10</span>
                      <span class="quarter-tone tone-{tone.replace(' ','')}">{tone}</span>
                    </div>
                  </div>
                  <div class="quarter-theme">{themes}</div>
                  {rfc_html}
                  {f'<div class="quarter-source">Source: {source}</div>' if source else ''}
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="dr-empty">📞 No concall coverage found via web search.<br>Try <a href="https://www.screener.in" target="_blank" style="color:#60a5fa;">screener.in</a> manually.</div>', unsafe_allow_html=True)

    flag_tracks = cc.get("flag_tracking", [])
    if flag_tracks:
        st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:0.6rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin:1rem 0 0.7rem;border-top:1px solid #111827;padding-top:1rem;'>Red Flag → Management Explanation Tracker</div>", unsafe_allow_html=True)
        for ft in flag_tracks:
            trend    = ft.get("trend","Not Addressed")
            q_by_q   = ft.get("q_by_q",{})
            credible = ft.get("management_credible", True)
            q_cells  = "".join(
                f"<div class='flag-q-cell'><div class='flag-q-label'>{qn}</div><div class='flag-q-text'>{str(q_by_q.get(qn,'—'))[:80]}</div></div>"
                for qn in ["Q1","Q2","Q3","Q4"]
            )
            st.markdown(f"""
            <div class="flag-track">
              <div class="flag-track-header">
                <div class="flag-track-name">{ft.get('flag','Unknown')}</div>
                <div style="display:flex;align-items:center;gap:8px;">
                  <span style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:{'#34d399' if credible else '#f59e0b'};">{'✓ Credible' if credible else '⚠ Questionable'}</span>
                  <span class="flag-track-status status-{trend.replace(' ','-')}">{trend}</span>
                </div>
              </div>
              <div class="flag-q-grid">{q_cells}</div>
              <div class="flag-insight">💡 {ft.get('insight','')}</div>
            </div>""", unsafe_allow_html=True)

    if st.button("🔄 Re-run Concall Analysis", key="cc_refresh"):
        del st.session_state[cc_key]; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── FINAL VERDICT ─────────────────────────────────────────
    verdict = compute_final_verdict(
        risk_sc, manip_sc, m_result, z_result,
        st.session_state.get(gov_key, {}),
        st.session_state.get(cc_key, {})
    )
    vc = verdict["verdict_color"]
    st.markdown(f"""
    <div class="verdict-card" style="background:{verdict['verdict_bg']};border:1px solid {verdict['verdict_border']};">
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:#374151;text-transform:uppercase;letter-spacing:2.5px;margin-bottom:0.4rem;">Final Verdict</div>
      <div class="verdict-word" style="color:{vc};">{verdict['verdict_icon']} {verdict['verdict']}</div>
      <div class="verdict-desc">{verdict['verdict_desc']}</div>
      <div class="verdict-composite">Composite risk score: {verdict['composite_score']}/10</div>
    </div>""", unsafe_allow_html=True)

    col_v1, col_v2 = st.columns(2)
    with col_v1:
        radar = _verdict_radar(verdict["score_components"])
        if radar: st.plotly_chart(radar, use_container_width=True, config={"displayModeBar": False}, key="radar_verdict")

    with col_v2:
        st.markdown("<div style='padding-top:1.5rem;'>", unsafe_allow_html=True)
        for label, val, mx, color in verdict["score_components"]:
            if mx == 0: continue
            pct = min(100, round(val / mx * 100))
            st.markdown(f"""
            <div class="score-bar-row">
              <div class="score-bar-label">{label}</div>
              <div class="score-bar-track"><div class="score-bar-fill" style="width:{pct}%;background:{color};"></div></div>
              <div class="score-bar-val" style="color:{color};">{val}/{mx}</div>
            </div>""", unsafe_allow_html=True)
        if verdict["reasons"]:
            st.markdown(f"<div style='margin-top:1rem;'><div style='font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px;'>Risk Drivers</div><ul class='reason-list'>{''.join(f'<li class=\"neg\">{r}</li>' for r in verdict['reasons'])}</ul></div>", unsafe_allow_html=True)
        if verdict["positives"]:
            st.markdown(f"<div style='margin-top:0.6rem;'><div style='font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px;'>Positive Signals</div><ul class='reason-list'>{''.join(f'<li class=\"pos\">{p}</li>' for p in verdict['positives'])}</ul></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("""
    <div style="margin-top:1rem;padding:0.8rem 1rem;background:rgba(255,255,255,0.02);border:1px solid #111827;border-radius:10px;font-size:0.65rem;color:#374151;line-height:1.6;">
      ⚠️ <strong style="color:#4b5563;">Not investment advice.</strong>
      Beneish M-Score and Altman Z-Score are probabilistic indicators, not proof of manipulation or distress.
      DuckDuckGo search results may be incomplete. Always verify with official BSE/NSE filings.
      Consult a SEBI-registered advisor before investing.
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  INTEGRATION HELPER
# ══════════════════════════════════════════════════════════════

def render_deep_research_selector(all_results):
    """Call inside `with tab_deep_research:` in app.py"""
    if not all_results:
        st.markdown("""
        <div style="text-align:center;padding:3rem 1rem;color:#374151;">
          <div style="font-size:2rem;margin-bottom:1rem;">🔬</div>
          <div style="font-size:0.9rem;color:#4b5563;margin-bottom:0.4rem;">No companies analysed yet</div>
          <div style="font-size:0.75rem;color:#2d3a55;">Go to <strong style="color:#4b5563;">Search &amp; Analyse</strong>, analyse companies, then return here.</div>
        </div>""", unsafe_allow_html=True)
        return

    company_options = {
        f"{r['name']} ({r['ticker'].replace('.NS','')}) — Risk: {r['risk_score']}/10": r
        for r in all_results
    }
    selected_label  = st.selectbox("Select company for deep research", options=list(company_options.keys()))
    selected_result = company_options[selected_label]

    col_btn, col_note = st.columns([1, 3])
    with col_btn:
        run_btn = st.button("🔬 Run Deep Research →", type="primary", key="dr_run_btn")
    with col_note:
        st.caption("Beneish M-Score · Altman Z-Score · Governance scan · Concall analysis · ~30–60 sec")

    dr_key = f"dr_done_{selected_result['ticker']}"
    if run_btn or dr_key in st.session_state:
        st.session_state[dr_key] = True
        render_deep_research_tab(selected_result)
