# ============================================================
#  DEEP RESEARCH TAB  —  deep_research_tab.py  (v2)
#
#  Changes from v1:
#  1. Info tab — plain-English explanation of Beneish M-Score
#     and Altman Z-Score with links to full papers
#  2. Bug fix — "search another company" now works without
#     refreshing. Added a "Search Another Company" reset button
#     and ensured session state is scoped per-ticker properly.
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

    rec_t = _last(rec); rec_p = _prev(rec)
    rev_t = _last(rev); rev_p = _prev(rev)
    if all(v not in (None, 0) for v in [rec_t, rec_p, rev_t, rev_p]):
        dsri = (rec_t / rev_t) / (rec_p / rev_p)
    else:
        dsri = 1.0; missing.append("DSRI")
    components["DSRI"] = {"value": round(dsri, 3), "weight": 0.920,
                           "label": "Days Sales Receivable Index", "flag": dsri > 1.465,
                           "note": "Receivables growing faster than revenue → potential channel stuffing"}

    gp_t = _last(gp); gp_p = _prev(gp)
    if all(v not in (None, 0) for v in [gp_t, gp_p, rev_t, rev_p]):
        gmi = _safe_div(gp_p / rev_p, gp_t / rev_t) or 1.0
    else:
        gmi = 1.0; missing.append("GMI")
    components["GMI"] = {"value": round(gmi, 3), "weight": 0.528,
                          "label": "Gross Margin Index", "flag": gmi > 1.193,
                          "note": "Margins deteriorating — incentive to manipulate earnings"}

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

    sgi = _safe_div(rev_t, rev_p) or 1.0
    if rev_t is None or rev_p is None: missing.append("SGI")
    components["SGI"] = {"value": round(sgi, 3), "weight": 0.892,
                          "label": "Sales Growth Index", "flag": sgi > 1.607,
                          "note": "High growth companies face pressure to sustain it through manipulation"}

    dep_t = _last(dep); dep_p = _prev(dep)
    ppe_t = _last(nca);  ppe_p = _prev(nca)
    if all(v not in (None, 0) for v in [dep_t, dep_p, ppe_t, ppe_p]):
        depi = _safe_div(dep_p / (dep_p + ppe_p), dep_t / (dep_t + ppe_t)) or 1.0
    else:
        depi = 1.0; missing.append("DEPI")
    components["DEPI"] = {"value": round(depi, 3), "weight": 0.115,
                           "label": "Depreciation Index", "flag": depi > 1.077,
                           "note": "Slowing depreciation rate → assets being sweated or life extended"}

    int_t = abs(_last(pnl.get("interest_exp")) or 0)
    int_p = abs(_prev(pnl.get("interest_exp")) or 0)
    if all(v not in (None, 0) for v in [int_t, int_p, rev_t, rev_p]):
        sgai = _safe_div(int_t / rev_t, int_p / rev_p) or 1.0
    else:
        sgai = 1.0; missing.append("SGAI")
    components["SGAI"] = {"value": round(sgai, 3), "weight": 0.415,
                           "label": "Expense Index (Interest/Revenue proxy)", "flag": sgai > 1.041,
                           "note": "Disproportionate expense growth vs revenue"}

    cl_t  = _last(bs.get("current_liab")); cl_p = _prev(bs.get("current_liab"))
    dbt_t = _last(debt);                   dbt_p = _prev(debt)
    if all(v not in (None, 0) for v in [cl_t, cl_p, dbt_t, dbt_p, ta_t, ta_p]):
        lvgi = _safe_div((dbt_t + cl_t) / ta_t, (dbt_p + cl_p) / ta_p) or 1.0
    else:
        lvgi = 1.0; missing.append("LVGI")
    components["LVGI"] = {"value": round(lvgi, 3), "weight": 0.172,
                           "label": "Leverage Index", "flag": lvgi > 1.111,
                           "note": "Increasing leverage → debt covenant pressure to inflate profits"}

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
    api_key = _get_gemini_key()
    if not api_key:
        return None, "GEMINI_API_KEY not set"
    try:
        resp = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
    json={
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.1
        },
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
    content, err = call_groq(prompt, system_prompt, max_tokens)
    if content:
        return content
    st.caption(f"ℹ️ Groq unavailable ({err}), switching to Gemini…")
    content, err = call_gemini(prompt, system_prompt, max_tokens)
    if content:
        return content
    return f"⚠️ Both Groq and Gemini failed. Last error: {err}"


def build_search_context(search_queries, max_results_per_query=4):
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
    queries = [
        f"{company_name} SEBI notice investigation penalty 2024 2025",
        f"{company_name} auditor resignation qualification 2024 2025",
        f"{company_name} director CEO CFO resignation exit 2024 2025",
        f"{nse_sym} NSE BSE corporate announcement board 2024 2025",
    ]

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

    seen, unique = set(), []
    for q in queries:
        if q not in seen:
            seen.add(q); unique.append(q)
    return unique[:8]


def governance_scan(company_name, ticker, sector, risk_flags=None, manip_flags=None):
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
Respond ONLY in valid JSON — no markdown, no text outside the JSON."""

    prompt = f"""Company: {company_name} (NSE: {nse_sym})

FINANCIAL RED FLAGS TO TRACK — find what management said about each:
{flag_section}

WEB SEARCH RESULTS (earnings call coverage, analyst notes, news articles):
{search_context}

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
      "insight": "<2 sentence analyst insight>"
    }}
  ],
  "overall_credibility": "<LOW|MEDIUM|HIGH>",
  "credibility_score": <1-10>,
  "key_concerns": ["..."],
  "positive_signals": ["..."],
  "summary": "<3-4 sentence overall assessment>"
}}

Only report what is supported by search results. Return ONLY valid JSON."""

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

    if risk_score >= 6:
        reasons.append(f"High financial risk score ({risk_score}/10)")
        score_components.append(("Financial Risk", risk_score, 10, "#ef4444"))
    elif risk_score >= 3:
        reasons.append(f"Moderate financial risk ({risk_score}/10)")
        score_components.append(("Financial Risk", risk_score, 10, "#f59e0b"))
    else:
        positives.append(f"Clean financial risk profile ({risk_score}/10)")
        score_components.append(("Financial Risk", risk_score, 10, "#22c55e"))

    if manip_score >= 6:
        reasons.append(f"High manipulation signal score ({manip_score}/10)")
        score_components.append(("Manipulation Signal", manip_score, 10, "#a78bfa"))
    elif manip_score >= 3:
        reasons.append(f"Some manipulation signals ({manip_score}/10)")
        score_components.append(("Manipulation Signal", manip_score, 10, "#c4b5fd"))
    else:
        positives.append(f"No significant manipulation signals ({manip_score}/10)")
        score_components.append(("Manipulation Signal", manip_score, 10, "#6ee7b7"))

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
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;1,400&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg-deep:    #070c18;
    --bg-card:    #0b1120;
    --bg-surface: #0e1526;
    --border:     #192138;
    --border-dim: #111827;
    --text-primary:   #eef0f7;
    --text-secondary: #8492b0;
    --text-muted:     #3d4f6e;
    --text-label:     #5a6e8c;
    --accent-purple:  #a78bfa;
    --accent-red:     #f87171;
    --accent-green:   #34d399;
    --accent-amber:   #fbbf24;
    --accent-blue:    #60a5fa;
}

.ai-stack-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(52,211,153,0.07);
    border: 1px solid rgba(52,211,153,0.2);
    color: #34d399;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    letter-spacing: 1px;
    padding: 5px 14px;
    border-radius: 8px;
    margin-bottom: 1.2rem;
}

.dr-snapshot {
    background: linear-gradient(135deg, #070c18 0%, #0b1020 100%);
    border: 1px solid #192138;
    border-radius: 20px;
    padding: 2.4rem 2.8rem;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
    text-align: center;
}
.dr-snapshot::before {
    content: '';
    position: absolute;
    top: -80px; right: -80px;
    width: 280px; height: 280px;
    background: radial-gradient(circle, rgba(139,92,246,0.09) 0%, transparent 65%);
    border-radius: 50%;
    pointer-events: none;
}
.dr-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(139,92,246,0.1);
    border: 1px solid rgba(139,92,246,0.25);
    color: #a78bfa;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    padding: 5px 14px;
    border-radius: 20px;
    margin-bottom: 1rem;
}
.dr-company-name {
    font-family: 'Outfit', sans-serif;
    font-size: 2.4rem;
    font-weight: 800;
    color: #eef0f7;
    letter-spacing: -1px;
    margin-bottom: 0.4rem;
    text-align: center;
}
.dr-company-meta {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.88rem;
    color: #5a6e8c;
    margin-bottom: 1.6rem;
    text-align: center;
    letter-spacing: 0.2px;
}
.dr-score-row {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    justify-content: center;
}
.dr-score-pill {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 12px 20px;
    min-width: 110px;
}
.dr-score-pill .label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #3d4f6e;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}
.dr-score-pill .val {
    font-family: 'Outfit', sans-serif;
    font-size: 1.35rem;
    font-weight: 700;
    letter-spacing: -0.5px;
    line-height: 1;
}

.dr-section {
    background: #0b1120;
    border: 1px solid #192138;
    border-radius: 18px;
    padding: 2rem 2.2rem;
    margin-bottom: 1.8rem;
}
.dr-section-title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'Outfit', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: -0.3px;
    margin-bottom: 1.4rem;
    padding-bottom: 0.9rem;
    border-bottom: 1px solid #111827;
}
.dr-section-subtitle {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.75rem;
    color: #3d4f6e;
    font-weight: 400;
    margin-left: auto;
    letter-spacing: 0;
}

/* ── Info Tab Styles ── */
.info-hero {
    background: linear-gradient(135deg, #070c18, #0d1428);
    border: 1px solid #192138;
    border-radius: 20px;
    padding: 2.2rem 2.5rem;
    margin-bottom: 1.6rem;
    text-align: center;
}
.info-hero-title {
    font-family: 'Outfit', sans-serif;
    font-size: 1.7rem;
    font-weight: 800;
    color: #eef0f7;
    letter-spacing: -0.5px;
    margin-bottom: 0.5rem;
}
.info-hero-sub {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    color: #4b6080;
    line-height: 1.7;
    max-width: 540px;
    margin: 0 auto;
}
.info-model-card {
    background: #070c18;
    border: 1px solid #192138;
    border-radius: 18px;
    padding: 2rem 2.2rem;
    margin-bottom: 1.4rem;
    position: relative;
    overflow: hidden;
}
.info-model-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
}
.info-model-card.purple::before {
    background: linear-gradient(90deg, transparent, rgba(167,139,250,0.7), transparent);
}
.info-model-card.red::before {
    background: linear-gradient(90deg, transparent, rgba(239,68,68,0.7), transparent);
}
.info-model-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 1.2rem;
    flex-wrap: wrap;
    gap: 10px;
}
.info-model-title {
    font-family: 'Outfit', sans-serif;
    font-size: 1.3rem;
    font-weight: 800;
    color: #eef0f7;
    letter-spacing: -0.3px;
}
.info-model-year {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #374151;
    background: #0d1726;
    padding: 4px 12px;
    border-radius: 20px;
    border: 1px solid #1c2640;
    letter-spacing: 1px;
}
.info-model-what {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    color: #8492b0;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 0.5rem;
    font-size: 0.72rem;
}
.info-model-body {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.88rem;
    color: #5a6e8c;
    line-height: 1.85;
    margin-bottom: 1.3rem;
}
.info-threshold-box {
    background: #0d1120;
    border: 1px solid #1a2540;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 1.2rem;
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
}
.info-threshold-item {
    display: flex;
    flex-direction: column;
    gap: 3px;
    flex: 1;
    min-width: 120px;
}
.info-threshold-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}
.info-threshold-value {
    font-family: 'Outfit', sans-serif;
    font-size: 0.9rem;
    font-weight: 700;
}
.info-limitation {
    background: rgba(245,158,11,0.05);
    border: 1px solid rgba(245,158,11,0.15);
    border-radius: 10px;
    padding: 0.75rem 1rem;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.82rem;
    color: #6b7280;
    line-height: 1.65;
    margin-bottom: 1rem;
}
.info-limitation strong { color: #f59e0b; }
.info-link-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 0.5rem;
}
.info-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #0d1726;
    border: 1px solid #1c2640;
    color: #60a5fa;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.78rem;
    font-weight: 500;
    padding: 7px 16px;
    border-radius: 8px;
    text-decoration: none;
    transition: border-color 0.2s;
}
.info-link:hover { border-color: #3b82f6; }
.info-factors-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 1.2rem;
}
.info-factor {
    background: #0d1120;
    border: 1px solid #1a2540;
    border-radius: 10px;
    padding: 0.75rem 0.9rem;
}
.info-factor-code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 600;
    margin-bottom: 3px;
}
.info-factor-name {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.78rem;
    color: #4b6080;
    line-height: 1.4;
}
.info-factor-flag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #374151;
    margin-top: 3px;
}
.info-comparison {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 1.4rem;
}
.info-cmp-cell {
    background: #0d1120;
    border: 1px solid #1a2540;
    border-radius: 12px;
    padding: 1rem;
}
.info-cmp-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #374151;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 0.5rem;
}
.info-cmp-text {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.82rem;
    color: #4b6080;
    line-height: 1.6;
}

.forensic-card {
    flex: 1;
    background: #090e1a;
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.forensic-score {
    font-family: 'Outfit', sans-serif;
    font-size: 3.2rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -2px;
    margin: 0.5rem 0;
}
.forensic-label {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #3d4f6e;
    margin-bottom: 0.3rem;
    font-weight: 500;
}
.forensic-verdict {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    padding: 5px 14px;
    border-radius: 20px;
    display: inline-block;
    margin-top: 0.5rem;
}
.forensic-threshold {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #3d4f6e;
    margin-top: 10px;
}

.comp-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 1rem;
}
.comp-table th {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #2d3a55;
    text-transform: uppercase;
    letter-spacing: 2px;
    padding: 8px 10px;
    border-bottom: 1px solid #0d1726;
    text-align: left;
}
.comp-table td {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.82rem;
    padding: 9px 10px;
    border-bottom: 1px solid #0a1020;
    color: #7a8ca8;
    vertical-align: middle;
    line-height: 1.4;
}
.comp-table tr:last-child td { border-bottom: none; }
.comp-table tr:hover td { background: rgba(255,255,255,0.015); }
.comp-flag { color: #f87171; font-weight: 700; font-size: 0.88rem; }
.comp-ok   { color: #34d399; font-size: 0.88rem; }
.comp-mono {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem;
    color: #c9d2e8;
}

.gov-item {
    background: #090e1a;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
    border-left: 3px solid transparent;
}
.gov-item.HIGH   { border-left-color: #ef4444; background: rgba(220,38,38,0.05); }
.gov-item.MEDIUM { border-left-color: #f59e0b; background: rgba(245,158,11,0.05); }
.gov-item.LOW    { border-left-color: #3b82f6; background: rgba(59,130,246,0.05); }
.gov-date   {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.64rem;
    color: #374151;
    margin-bottom: 4px;
}
.gov-detail {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    color: #8492b0;
    line-height: 1.55;
}
.gov-sev {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    float: right;
    padding: 3px 9px;
    border-radius: 5px;
}
.gov-sev.HIGH   { color: #ef4444; background: rgba(220,38,38,0.1); }
.gov-sev.MEDIUM { color: #f59e0b; background: rgba(245,158,11,0.1); }
.gov-sev.LOW    { color: #60a5fa; background: rgba(59,130,246,0.1); }
.gov-category-label {
    font-family: 'Outfit', sans-serif;
    font-size: 0.78rem;
    font-weight: 600;
    color: #4b5563;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 14px 0 6px;
}

.quarter-card {
    background: #090e1a;
    border: 1px solid #151e33;
    border-radius: 14px;
    padding: 1.2rem 1.3rem;
    margin-bottom: 0.8rem;
}
.quarter-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.8rem;
}
.quarter-label {
    font-family: 'Outfit', sans-serif;
    font-size: 0.82rem;
    color: #7a8ca8;
    font-weight: 600;
}
.quarter-tone {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    padding: 4px 12px;
    border-radius: 7px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.tone-Confident  { color: #34d399; background: rgba(52,211,153,0.1); }
.tone-Cautious   { color: #f59e0b; background: rgba(245,158,11,0.1); }
.tone-Evasive    { color: #ef4444; background: rgba(220,38,38,0.1); }
.tone-Defensive  { color: #f87171; background: rgba(248,113,113,0.1); }
.tone-Optimistic { color: #60a5fa; background: rgba(96,165,250,0.1); }
.quarter-theme {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.83rem;
    color: #5a6e8c;
    line-height: 1.65;
}
.quarter-source {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: #374151;
    margin-top: 6px;
}

.flag-track {
    background: #090e1a;
    border-radius: 14px;
    padding: 1.2rem 1.3rem;
    margin-bottom: 0.7rem;
    border: 1px solid #151e33;
}
.flag-track-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 0.7rem;
}
.flag-track-name {
    font-family: 'Outfit', sans-serif;
    font-size: 0.95rem;
    font-weight: 600;
    color: #e5e7eb;
}
.flag-track-status {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    padding: 4px 11px;
    border-radius: 6px;
    white-space: nowrap;
}
.status-Resolved      { color: #34d399; background: rgba(52,211,153,0.1); }
.status-Improving     { color: #60a5fa; background: rgba(96,165,250,0.1); }
.status-Persistent    { color: #f59e0b; background: rgba(245,158,11,0.1); }
.status-Worsening     { color: #ef4444; background: rgba(220,38,38,0.1); }
.status-Not-Addressed { color: #9ca3af; background: rgba(156,163,175,0.1); }
.flag-q-grid {
    display: grid;
    grid-template-columns: repeat(4,1fr);
    gap: 8px;
    margin: 0.7rem 0;
}
.flag-q-cell {
    background: rgba(255,255,255,0.03);
    border-radius: 8px;
    padding: 8px 10px;
}
.flag-q-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: #374151;
    margin-bottom: 3px;
}
.flag-q-text {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.75rem;
    color: #7a8ca8;
    line-height: 1.45;
}
.flag-insight {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.8rem;
    color: #5a6e8c;
    font-style: italic;
    margin-top: 0.6rem;
    line-height: 1.55;
}

.verdict-card {
    border-radius: 20px;
    padding: 2.4rem 2.8rem;
    margin-bottom: 1.6rem;
    text-align: center;
}
.verdict-word {
    font-family: 'Outfit', sans-serif;
    font-size: 4rem;
    font-weight: 800;
    letter-spacing: -2px;
    line-height: 1;
    margin: 0.5rem 0;
}
.verdict-desc {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.95rem;
    color: #5a6e8c;
    max-width: 500px;
    margin: 0.6rem auto;
    line-height: 1.6;
}
.verdict-composite {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #374151;
    margin-top: 0.8rem;
    letter-spacing: 1px;
}

.reason-list { list-style: none; padding: 0; margin: 0.8rem 0; }
.reason-list li {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    color: #8492b0;
    padding: 6px 0 6px 1.4rem;
    position: relative;
    line-height: 1.5;
}
.reason-list li::before { content: '→'; position: absolute; left: 0; }
.reason-list li.neg::before { color: #ef4444; }
.reason-list li.pos::before { color: #34d399; }

.score-bar-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 0.65rem;
}
.score-bar-label {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.72rem;
    color: #4b5563;
    width: 150px;
    flex-shrink: 0;
    font-weight: 500;
}
.score-bar-track {
    flex: 1;
    background: rgba(255,255,255,0.04);
    border-radius: 5px;
    height: 7px;
    overflow: hidden;
}
.score-bar-fill { height: 100%; border-radius: 5px; }
.score-bar-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #374151;
    width: 38px;
    text-align: right;
}

.positive-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(34,197,94,0.07);
    border: 1px solid rgba(34,197,94,0.2);
    color: #4ade80;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.78rem;
    padding: 5px 13px;
    border-radius: 20px;
    margin: 4px 4px 4px 0;
}

.dr-empty {
    text-align: center;
    padding: 2rem;
    color: #374151;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    line-height: 1.6;
}

.sub-section-label {
    font-family: 'Outfit', sans-serif;
    font-size: 0.85rem;
    font-weight: 600;
    color: #3d4f6e;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin: 1.2rem 0 0.7rem;
    padding-top: 1.2rem;
    border-top: 1px solid #111827;
}

.dr-search-box {
    background: #090e1a;
    border: 1px solid #192138;
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1.6rem;
}
.dr-search-title {
    font-family: 'Outfit', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    color: #8492b0;
    margin-bottom: 0.8rem;
    letter-spacing: 0.2px;
}

/* Reset button */
.reset-search-bar {
    background: rgba(239,68,68,0.06);
    border: 1px solid rgba(239,68,68,0.2);
    border-radius: 12px;
    padding: 0.8rem 1.2rem;
    margin-bottom: 1.4rem;
    display: flex;
    align-items: center;
    gap: 12px;
}
.reset-search-bar-text {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.82rem;
    color: #5a6e8c;
    flex: 1;
}
.reset-search-bar-ticker {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: #ef4444;
    font-weight: 600;
}
</style>
"""


def _gauge_chart(score, color, title, min_val, max_val, threshold=None, threshold_label=""):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        title={'text': title, 'font': {'size': 12, 'color': '#6b7280', 'family': 'DM Sans'}},
        number={'font': {'size': 32, 'color': color, 'family': 'Outfit'}, 'valueformat': '.3f'},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [min_val, max_val], 'tickwidth': 0.5, 'tickcolor': '#1f2d47',
                     'tickfont': {'color': '#2d3a55', 'size': 9}, 'nticks': 5},
            'bar': {'color': color, 'thickness': 0.2}, 'bgcolor': '#080b14', 'borderwidth': 0,
            'threshold': {'line': {'color': '#f59e0b', 'width': 2}, 'thickness': 0.75,
                          'value': threshold if threshold else score},
        }
    ))
    fig.update_layout(
        height=190, margin=dict(t=40, b=8, l=18, r=18),
        paper_bgcolor='#0d1120', plot_bgcolor='#0d1120',
        font=dict(color='#6b7280', family='DM Sans'),
        annotations=[{'text': threshold_label, 'x': 0.5, 'y': -0.05,
                       'xref': 'paper', 'yref': 'paper', 'showarrow': False,
                       'font': {'size': 10, 'color': '#f59e0b', 'family': 'JetBrains Mono'}}
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
        title=dict(text=f"<b>{title}</b>", font=dict(size=11, color='#9ca3af', family='DM Sans'), x=0.5),
        height=190, margin=dict(t=34, b=10, l=5, r=5),
        paper_bgcolor='#0d1120', plot_bgcolor='#0d1120',
        font=dict(color='#6b7280', family='DM Sans'),
        xaxis=dict(tickfont=dict(color='#4b5563', size=10, family='JetBrains Mono'), showgrid=False),
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
        line=dict(color='#7c3aed', width=1.5), marker=dict(size=5, color='#a78bfa'),
        hovertemplate="<b>%{theta}</b><br>Score: %{r}/10<extra></extra>",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='#090e1a',
            radialaxis=dict(visible=True, range=[0,10], gridcolor='rgba(26,37,64,0.6)',
                            tickfont=dict(color='#2d3a55', size=9), tickvals=[2,4,6,8,10],
                            linecolor='rgba(26,37,64,0.4)'),
            angularaxis=dict(gridcolor='rgba(26,37,64,0.4)',
                             tickfont=dict(color='#5a6e8c', size=10, family='DM Sans'),
                             linecolor='rgba(26,37,64,0.4)'),
        ),
        height=320, margin=dict(t=24, b=24, l=48, r=48),
        paper_bgcolor='#0d1120', plot_bgcolor='#0d1120', showlegend=False,
    )
    return fig


def _check_api_keys():
    groq_ok   = bool(_get_groq_key())
    gemini_ok = bool(_get_gemini_key())
    return groq_ok, gemini_ok, groq_ok or gemini_ok


# ══════════════════════════════════════════════════════════════
#  INFO TAB — Plain-English explanation of academic models
# ══════════════════════════════════════════════════════════════

def render_info_tab():
    """Renders the ℹ️ Info tab with plain-English explanations of Beneish M-Score and Altman Z-Score."""
    try:
        st.markdown("""
        <div class="info-hero">
          <div class="info-model-year" style="display:inline-block;margin-bottom:0.8rem;">📖 ACADEMIC MODEL GUIDE</div>
          <div class="info-hero-title">What do these scores actually mean?</div>
          <div class="info-hero-sub">
            Beneish M-Score and Altman Z-Score are academic models used by forensic accountants and
            equity analysts worldwide. Here's what they measure, how to read them, and what their
            limitations are — in plain English.
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── BENEISH M-SCORE ───────────────────────────────────────
        st.markdown("""
        <div class="info-model-card purple">
          <div class="info-model-header">
            <div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#a78bfa;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px;">MODEL 01</div>
              <div class="info-model-title">🟣 Beneish M-Score</div>
            </div>
            <div class="info-model-year">Messod Beneish · 1999</div>
          </div>

          <div class="info-model-what">What it detects</div>
          <div class="info-model-body">
            The Beneish M-Score is a mathematical model designed to detect whether a company has
            <strong style="color:#a78bfa;">manipulated its reported earnings</strong>. It was developed by
            Professor Messod Beneish at Indiana University after studying companies that were later found
            guilty of financial fraud by the SEC. The model looks for patterns in financial data that
            are common in companies that inflate revenue, delay expenses, or otherwise doctor their books.
            <br><br>
            Think of it like a lie-detector test for accounting — it doesn't prove fraud, but a
            high score means the numbers behave in ways that are statistically unusual and deserve scrutiny.
          </div>

          <div class="info-model-what">How the score works</div>
          <div class="info-threshold-box">
            <div class="info-threshold-item">
              <div class="info-threshold-label" style="color:#22c55e;">Below -2.22</div>
              <div class="info-threshold-value" style="color:#22c55e;">🟢 Clean</div>
              <div style="font-family:'DM Sans',sans-serif;font-size:0.75rem;color:#4b6080;margin-top:3px;">Unlikely manipulator</div>
            </div>
            <div class="info-threshold-item">
              <div class="info-threshold-label" style="color:#f59e0b;">-2.22 to -1.78</div>
              <div class="info-threshold-value" style="color:#f59e0b;">🟡 Grey Zone</div>
              <div style="font-family:'DM Sans',sans-serif;font-size:0.75rem;color:#4b6080;margin-top:3px;">Monitor closely</div>
            </div>
            <div class="info-threshold-item">
              <div class="info-threshold-label" style="color:#ef4444;">Above -1.78</div>
              <div class="info-threshold-value" style="color:#ef4444;">🔴 Red Flag</div>
              <div style="font-family:'DM Sans',sans-serif;font-size:0.75rem;color:#4b6080;margin-top:3px;">Likely manipulator</div>
            </div>
          </div>

          <div class="info-model-what">The 8 factors it measures</div>
          <div class="info-factors-grid">
            <div class="info-factor">
              <div class="info-factor-code" style="color:#a78bfa;">DSRI</div>
              <div class="info-factor-name">Days Sales Receivable Index — are customers paying slower (a channel stuffing signal)?</div>
              <div class="info-factor-flag">Flag if &gt; 1.465</div>
            </div>
            <div class="info-factor">
              <div class="info-factor-code" style="color:#a78bfa;">GMI</div>
              <div class="info-factor-name">Gross Margin Index — are margins deteriorating, creating pressure to manipulate?</div>
              <div class="info-factor-flag">Flag if &gt; 1.193</div>
            </div>
            <div class="info-factor">
              <div class="info-factor-code" style="color:#a78bfa;">AQI</div>
              <div class="info-factor-name">Asset Quality Index — are non-cash, hard-to-value assets growing on the balance sheet?</div>
              <div class="info-factor-flag">Flag if &gt; 1.254</div>
            </div>
            <div class="info-factor">
              <div class="info-factor-code" style="color:#a78bfa;">SGI</div>
              <div class="info-factor-name">Sales Growth Index — high growth creates pressure to keep the streak going artificially.</div>
              <div class="info-factor-flag">Flag if &gt; 1.607</div>
            </div>
            <div class="info-factor">
              <div class="info-factor-code" style="color:#a78bfa;">DEPI</div>
              <div class="info-factor-name">Depreciation Index — is the company slowing depreciation to boost reported profit?</div>
              <div class="info-factor-flag">Flag if &gt; 1.077</div>
            </div>
            <div class="info-factor">
              <div class="info-factor-code" style="color:#a78bfa;">SGAI</div>
              <div class="info-factor-name">Sales, General & Admin Index — disproportionate overhead growth vs revenue.</div>
              <div class="info-factor-flag">Flag if &gt; 1.041</div>
            </div>
            <div class="info-factor">
              <div class="info-factor-code" style="color:#a78bfa;">LVGI</div>
              <div class="info-factor-name">Leverage Index — rising debt burden increases pressure to hit profit targets.</div>
              <div class="info-factor-flag">Flag if &gt; 1.111</div>
            </div>
            <div class="info-factor">
              <div class="info-factor-code" style="color:#a78bfa;">TATA</div>
              <div class="info-factor-name">Total Accruals to Total Assets — the most powerful signal. Profit not backed by cash.</div>
              <div class="info-factor-flag">Flag if &gt; 0.031 · Weight: 4.68×</div>
            </div>
          </div>

          <div class="info-limitation">
            <strong>⚠️ Limitations to keep in mind:</strong> The model was trained on US companies from the 1990s.
            It works well for manufacturing and trading companies but is less reliable for banks, NBFCs,
            and other financial services companies (which have structural reasons for high accruals).
            A high M-Score is a signal to investigate further — not proof of fraud.
            Many legitimate high-growth companies may score poorly simply due to rapid business expansion.
          </div>

          <div class="info-link-row">
            <a class="info-link" href="https://onlinelibrary.wiley.com/doi/10.1111/j.1911-3846.1999.tb00586.x" target="_blank">📄 Original Paper (Beneish 1999)</a>
            <a class="info-link" href="https://www.investopedia.com/terms/b/beneish-m-score.asp" target="_blank">📖 Investopedia Explainer</a>
            <a class="info-link" href="https://www.screener.in/explore/" target="_blank">🔍 See it on Screener.in</a>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── ALTMAN Z-SCORE ────────────────────────────────────────
        st.markdown("""
        <div class="info-model-card red">
          <div class="info-model-header">
            <div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#f87171;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px;">MODEL 02</div>
              <div class="info-model-title">🔴 Altman Z-Score</div>
            </div>
            <div class="info-model-year">Edward Altman · 1968</div>
          </div>

          <div class="info-model-what">What it detects</div>
          <div class="info-model-body">
            The Altman Z-Score predicts the probability that a company will go <strong style="color:#f87171;">bankrupt within the next two years</strong>.
            It was created by Professor Edward Altman at NYU Stern School of Business in 1968 — and despite
            being over 50 years old, it remains one of the most widely used tools in credit risk analysis.
            <br><br>
            It combines five financial ratios, each weighted differently, to produce a single number.
            The lower the score, the closer a company is to potential financial distress.
            Auditors, banks, and institutional investors routinely use this as a first-pass filter
            before extending credit or evaluating solvency.
          </div>

          <div class="info-model-what">How the score works</div>
          <div class="info-threshold-box">
            <div class="info-threshold-item">
              <div class="info-threshold-label" style="color:#ef4444;">Below 1.81</div>
              <div class="info-threshold-value" style="color:#ef4444;">🔴 Distress Zone</div>
              <div style="font-family:'DM Sans',sans-serif;font-size:0.75rem;color:#4b6080;margin-top:3px;">High bankruptcy risk</div>
            </div>
            <div class="info-threshold-item">
              <div class="info-threshold-label" style="color:#f59e0b;">1.81 to 2.99</div>
              <div class="info-threshold-value" style="color:#f59e0b;">🟡 Grey Zone</div>
              <div style="font-family:'DM Sans',sans-serif;font-size:0.75rem;color:#4b6080;margin-top:3px;">Financial stress possible</div>
            </div>
            <div class="info-threshold-item">
              <div class="info-threshold-label" style="color:#22c55e;">Above 2.99</div>
              <div class="info-threshold-value" style="color:#22c55e;">🟢 Safe Zone</div>
              <div style="font-family:'DM Sans',sans-serif;font-size:0.75rem;color:#4b6080;margin-top:3px;">Financially healthy</div>
            </div>
          </div>

          <div class="info-model-what">The 5 factors it measures</div>
          <div class="info-factors-grid">
            <div class="info-factor">
              <div class="info-factor-code" style="color:#f87171;">X1 · Weight 1.2×</div>
              <div class="info-factor-name">Working Capital / Total Assets — short-term liquidity. Negative means the company can't easily pay near-term bills.</div>
            </div>
            <div class="info-factor">
              <div class="info-factor-code" style="color:#f87171;">X2 · Weight 1.4×</div>
              <div class="info-factor-name">Retained Earnings / Total Assets — long-run profitability and reinvestment. Young companies naturally score low here.</div>
            </div>
            <div class="info-factor">
              <div class="info-factor-code" style="color:#f87171;">X3 · Weight 3.3×</div>
              <div class="info-factor-name">EBIT / Total Assets — the most heavily weighted factor. Core operating earnings power relative to asset base.</div>
            </div>
            <div class="info-factor">
              <div class="info-factor-code" style="color:#f87171;">X4 · Weight 0.6×</div>
              <div class="info-factor-name">Market Cap / Total Liabilities — market's confidence in the company vs its debt load.</div>
            </div>
            <div class="info-factor">
              <div class="info-factor-code" style="color:#f87171;">X5 · Weight 1.0×</div>
              <div class="info-factor-name">Revenue / Total Assets — asset efficiency, also known as asset turnover. How well assets generate sales.</div>
            </div>
          </div>

          <div class="info-model-what">M-Score vs Z-Score at a glance</div>
          <div class="info-comparison">
            <div class="info-cmp-cell">
              <div class="info-cmp-label">Beneish M-Score</div>
              <div class="info-cmp-text">
                • Detects <strong style="color:#a78bfa;">earnings manipulation</strong><br>
                • Looks at accounting quality<br>
                • 8 factors, all from P&L + BS<br>
                • Score above -1.78 = red flag<br>
                • Best for: non-financial companies
              </div>
            </div>
            <div class="info-cmp-cell">
              <div class="info-cmp-label">Altman Z-Score</div>
              <div class="info-cmp-text">
                • Detects <strong style="color:#f87171;">financial distress / bankruptcy risk</strong><br>
                • Looks at solvency & liquidity<br>
                • 5 factors, uses market cap too<br>
                • Score below 1.81 = distress zone<br>
                • Best for: non-financial companies
              </div>
            </div>
          </div>

          <div class="info-limitation">
            <strong>⚠️ Limitations to keep in mind:</strong> The Z-Score was originally calibrated on US manufacturing
            companies. It is <strong>not reliable for banks, NBFCs, insurance companies, or REITs</strong> because
            these businesses are designed to carry high leverage by nature (that's the business model).
            We display an "N/A" warning when we detect a financial sector company. Additionally,
            very early-stage or pre-revenue companies will almost always score in the distress zone
            even if they are well-funded — use discretion.
          </div>

          <div class="info-link-row">
            <a class="info-link" href="https://www.jstor.org/stable/2978933" target="_blank">📄 Original Paper (Altman 1968)</a>
            <a class="info-link" href="https://www.investopedia.com/terms/a/altman.asp" target="_blank">📖 Investopedia Explainer</a>
            <a class="info-link" href="https://pages.stern.nyu.edu/~ealtman/" target="_blank">🎓 Altman's NYU Page</a>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── QUICK REFERENCE ──────────────────────────────────────
        st.markdown("""
        <div style="background:#070c18;border:1px solid #192138;border-radius:16px;padding:1.6rem 1.8rem;margin-top:0.5rem;">
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#374151;text-transform:uppercase;letter-spacing:2px;margin-bottom:1rem;">HOW THIS TOOL USES THEM</div>
          <div style="font-family:'DM Sans',sans-serif;font-size:0.88rem;color:#4b6080;line-height:1.85;">
            In the <strong style="color:#8492b0;">Deep Research</strong> tab, we run both models automatically using live financial
            data from Yahoo Finance. The Beneish M-Score and Altman Z-Score each contribute
            to the <strong style="color:#8492b0;">Final Verdict</strong> composite score alongside the AI governance scan,
            concall credibility analysis, and our 18 proprietary red-flag checks.
            <br><br>
            Neither model alone should determine an investment decision. Use them as one layer in
            a broader forensic investigation — alongside management commentary, auditor qualifications,
            and sectoral context.
          </div>
          <div style="margin-top:1rem;font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:#1e2a40;border-top:1px solid #111827;padding-top:0.8rem;">
            Data source: Yahoo Finance (yfinance) · Not investment advice · Always verify with official BSE/NSE filings
          </div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Failed to render info tab: {str(e)}")
        st.markdown("Please refresh the page or contact support if the issue persists.")


# ──────────────────────────────────────────────────────────────
#  NSE COMPANY LIST
# ──────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────
#  DATA + RED FLAG ENGINE — now shared with app.py via core/
#  (previously this file kept its own duplicate _dr_-prefixed
#  copies of the NSE list loader, fundamentals fetcher, and all
#  18 red-flag/manipulation checks; removed during Sprint 1
#  de-duplication so Deep Research and Financial Research always
#  score companies identically)
# ──────────────────────────────────────────────────────────────
from core.data import load_nse_company_list as _load_nse_company_list
from core.data import get_company_data as _core_get_company_data
from core.red_flags import run_all_checks as _dr_run_all_checks



def _fetch_company_data_for_deep_research(ticker_symbol: str):
    data = _core_get_company_data(ticker_symbol)
    if data is None:
        return None, f"Could not fetch data for {ticker_symbol}. Ticker may be delisted, wrong, or yfinance is rate-limiting."

    rf, mf, rs, ms = _dr_run_all_checks(data)
    result = {**data, "risk_flags": rf, "manip_flags": mf,
              "risk_score": rs, "manip_score": ms}
    return result, None


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

    groq_ok, gemini_ok, any_ok = _check_api_keys()
    if not any_ok:
        st.error(
            "🔑 **No AI API key found.**\n\n"
            "Add at least one to `.streamlit/secrets.toml`:\n"
            "```toml\nGROQ_API_KEY   = 'gsk_...'\nGEMINI_API_KEY = 'AIza...'\n```\n"
            "**Free keys:**\n"
            "- Groq → console.groq.com (14,400 req/day free)\n"
            "- Gemini → aistudio.google.com (1,500 req/day free)"
        )
        return

    active = (["⚡ Groq"] if groq_ok else []) + (["✦ Gemini"] if gemini_ok else [])
    st.markdown(
        f'<div class="ai-stack-badge">🤖 {" + ".join(active)} &nbsp;·&nbsp; 🔍 DuckDuckGo Search (free)</div>',
        unsafe_allow_html=True
    )

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
        <div class="dr-score-pill">
          <span class="label">Financial Risk</span>
          <span class="val" style="color:{risk_color};">{risk_sc}/10</span>
        </div>
        <div class="dr-score-pill">
          <span class="label">Manip Signal</span>
          <span class="val" style="color:{manip_color};">{manip_sc}/10</span>
        </div>
        <div class="dr-score-pill">
          <span class="label">Total Flags</span>
          <span class="val" style="color:#9ca3af;">{len(rf)+len(mf)}</span>
        </div>
        <div class="dr-score-pill">
          <span class="label">Date</span>
          <span class="val" style="color:#4b5563;font-size:0.85rem;">{datetime.now().strftime('%d %b %Y')}</span>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── SECTION 1: FORENSIC MODELS ────────────────────────────
    with st.spinner("⚙️ Computing Beneish M-Score and Altman Z-Score…"):
        m_result = compute_beneish_mscore(result)
        z_result = compute_altman_zscore(result, sector)

    st.markdown("""
    <div class="dr-section">
      <div class="dr-section-title" style="color:#a78bfa;">
        <span style="width:9px;height:9px;border-radius:50%;background:#a78bfa;display:inline-block;box-shadow:0 0 10px rgba(167,139,250,0.6);flex-shrink:0;"></span>
        01 &nbsp;— Forensic Risk Models
        <span class="dr-section-subtitle">Beneish M-Score · Altman Z-Score &nbsp;·&nbsp; <em style="color:#374151;">See ℹ️ Info tab for explanations</em></span>
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
          <div class="forensic-threshold">Threshold: &gt; -1.78 = likely manipulator</div>
        </div>""", unsafe_allow_html=True)
        st.plotly_chart(_gauge_chart(m_result["score"], mc, "M-Score", -4, 0, -1.78, "⚠ -1.78 threshold"),
                        use_container_width=True, config={"displayModeBar": False}, key=f"gauge_mscore_{ticker}")
        st.plotly_chart(_component_waterfall(m_result["components"], "Weighted contributions", mc),
                        use_container_width=True, config={"displayModeBar": False}, key=f"bar_mscore_{ticker}")
        if m_result["red_flags"]:
            st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:0.68rem;color:#ef4444;margin:10px 0 5px;'>🚩 {len(m_result['red_flags'])} component(s) above threshold</div>", unsafe_allow_html=True)
        rows = "".join(
            f"<tr><td class='comp-mono'>{k}</td><td class='comp-mono'>{v['value']}</td>"
            f"<td style='font-family:JetBrains Mono,monospace;font-size:0.72rem;color:#374151;'>×{v['weight']}</td>"
            f"<td class='{'comp-flag' if v.get('flag') else 'comp-ok'}'>{'⚑' if v.get('flag') else '✓'}</td>"
            f"<td style='font-size:0.78rem;color:#5a6e8c;'>{v['note'][:65]}…</td></tr>"
            for k, v in m_result["components"].items()
        )
        st.markdown(f"<table class='comp-table'><thead><tr><th>Factor</th><th>Value</th><th>Wt</th><th>Flag</th><th>Note</th></tr></thead><tbody>{rows}</tbody></table>", unsafe_allow_html=True)
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
          <div class="forensic-threshold">&lt;1.81 distress · 1.81–2.99 grey · &gt;2.99 safe</div>
        </div>""", unsafe_allow_html=True)
        st.plotly_chart(_gauge_chart(z_result["score"], zc, "Z-Score", 0, 5, 1.81, "⚠ 1.81 distress zone"),
                        use_container_width=True, config={"displayModeBar": False}, key=f"gauge_zscore_{ticker}")
        st.plotly_chart(_component_waterfall(z_result["components"], "Weighted contributions", zc),
                        use_container_width=True, config={"displayModeBar": False}, key=f"bar_zscore_{ticker}")
        rows = "".join(
            f"<tr><td class='comp-mono'>{k}</td>"
            f"<td class='comp-mono' style='color:{'#34d399' if v['value']>0 else '#f87171'};'>{v['value']:.4f}</td>"
            f"<td style='font-family:JetBrains Mono,monospace;font-size:0.72rem;color:#374151;'>×{v['weight']}</td>"
            f"<td style='font-size:0.78rem;color:#5a6e8c;'>{v['label']}</td></tr>"
            for k, v in z_result["components"].items()
        )
        st.markdown(f"<table class='comp-table'><thead><tr><th>Factor</th><th>Value</th><th>Wt</th><th>What it measures</th></tr></thead><tbody>{rows}</tbody></table>", unsafe_allow_html=True)
        if z_result["is_financial"]: st.info("ℹ️ Z-Score is less reliable for banks/NBFCs.", icon="ℹ️")
        if z_result["missing"]: st.caption(f"⚠️ Defaulted to 0: {', '.join(z_result['missing'])}")

    st.markdown("</div>", unsafe_allow_html=True)

    # ── SECTION 2: GOVERNANCE SCAN ────────────────────────────
    st.markdown("""
    <div class="dr-section">
      <div class="dr-section-title" style="color:#f87171;">
        <span style="width:9px;height:9px;border-radius:50%;background:#ef4444;display:inline-block;box-shadow:0 0 10px rgba(239,68,68,0.6);flex-shrink:0;"></span>
        02 &nbsp;— Governance &amp; News Intelligence
        <span class="dr-section-subtitle">DuckDuckGo + Groq/Gemini · Flag-driven queries</span>
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
          <div class="forensic-score" style="color:{gc};">{g_score}<span style="font-family:'DM Sans',sans-serif;font-size:1.2rem;color:#374151;">/10</span></div>
          <div class="forensic-verdict" style="color:{gc};background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.15);">{g_risk}</div>
          <div style="font-family:'DM Sans',sans-serif;font-size:0.82rem;color:#5a6e8c;margin-top:14px;line-height:1.6;">{gov.get('summary','')[:200]}</div>
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
                st.markdown(f"<div class='gov-category-label'>{cat_label}</div>", unsafe_allow_html=True)
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
            st.markdown("<div class='gov-category-label'>✅ Positive Signals</div>", unsafe_allow_html=True)
            st.markdown("".join(f'<span class="positive-chip">✓ {p}</span>' for p in positives[:6]), unsafe_allow_html=True)
        if gov.get("sources_checked"):
            st.caption(f"Sources: {', '.join(gov['sources_checked'][:5])}")

    if st.button("🔄 Re-run Governance Scan", key=f"gov_refresh_{ticker}"):
        del st.session_state[gov_key]; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── SECTION 3: CONCALL INTELLIGENCE ──────────────────────
    st.markdown("""
    <div class="dr-section">
      <div class="dr-section-title" style="color:#60a5fa;">
        <span style="width:9px;height:9px;border-radius:50%;background:#60a5fa;display:inline-block;box-shadow:0 0 10px rgba(96,165,250,0.6);flex-shrink:0;"></span>
        03 &nbsp;— Concall Intelligence
        <span class="dr-section-subtitle">Management Credibility Tracker · Last 4 quarters</span>
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
          <div class="forensic-score" style="color:{cc_color};">{cc_score}<span style="font-family:'DM Sans',sans-serif;font-size:1.2rem;color:#374151;">/10</span></div>
          <div class="forensic-verdict" style="color:{cc_color};background:rgba(96,165,250,0.05);border:1px solid rgba(96,165,250,0.15);">{cc_cred}</div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#374151;margin-top:10px;">{qf}/4 quarters found</div>
          <div style="font-family:'DM Sans',sans-serif;font-size:0.82rem;color:#5a6e8c;margin-top:12px;line-height:1.6;">{cc.get('summary','')[:220]}</div>
        </div>""", unsafe_allow_html=True)
        for label, key, color in [("🔴 Key Concerns","key_concerns","#8492b0"),("✅ Positives","positive_signals","#4ade80")]:
            items = cc.get(key, [])
            if items:
                st.markdown(f"<div class='gov-category-label'>{label}</div>", unsafe_allow_html=True)
                for item in items[:4]:
                    st.markdown(f"<div style='font-family:DM Sans,sans-serif;font-size:0.82rem;color:{color};padding:4px 0;line-height:1.5;'>→ {item}</div>", unsafe_allow_html=True)

    with col_c2:
        quarters = cc.get("quarters_data", [])
        if quarters:
            st.markdown("<div class='gov-category-label'>Quarterly Commentary</div>", unsafe_allow_html=True)
            for q in quarters:
                tone   = q.get("management_tone","Neutral")
                themes = " · ".join(q.get("key_themes",[])[:3]) or "No themes extracted"
                cred   = q.get("credibility_score",5)
                cred_c = "#22c55e" if cred>=7 else "#f59e0b" if cred>=4 else "#ef4444"
                source = q.get("source","")
                rfc_html = "".join(f"<div style='font-family:DM Sans,sans-serif;font-size:0.78rem;color:#f87171;padding:3px 0;'>⚠ {r}</div>" for r in q.get("red_flags_in_call",[])[:2])
                st.markdown(f"""
                <div class="quarter-card">
                  <div class="quarter-header">
                    <span class="quarter-label">{q.get('quarter','?')} · {q.get('date','')}</span>
                    <div style="display:flex;align-items:center;gap:10px;">
                      <span style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:{cred_c};">Credibility: {cred}/10</span>
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
        st.markdown("<div class='sub-section-label'>Red Flag → Management Explanation Tracker</div>", unsafe_allow_html=True)
        for ft in flag_tracks:
            trend    = ft.get("trend","Not Addressed")
            q_by_q   = ft.get("q_by_q",{})
            credible = ft.get("management_credible", True)
            q_cells  = "".join(
                f"<div class='flag-q-cell'><div class='flag-q-label'>{qn}</div><div class='flag-q-text'>{str(q_by_q.get(qn,'—'))[:90]}</div></div>"
                for qn in ["Q1","Q2","Q3","Q4"]
            )
            st.markdown(f"""
            <div class="flag-track">
              <div class="flag-track-header">
                <div class="flag-track-name">{ft.get('flag','Unknown')}</div>
                <div style="display:flex;align-items:center;gap:10px;">
                  <span style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:{'#34d399' if credible else '#f59e0b'};">{'✓ Credible' if credible else '⚠ Questionable'}</span>
                  <span class="flag-track-status status-{trend.replace(' ','-')}">{trend}</span>
                </div>
              </div>
              <div class="flag-q-grid">{q_cells}</div>
              <div class="flag-insight">💡 {ft.get('insight','')}</div>
            </div>""", unsafe_allow_html=True)

    if st.button("🔄 Re-run Concall Analysis", key=f"cc_refresh_{ticker}"):
        del st.session_state[cc_key]; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── SECTION 4: FINAL VERDICT ──────────────────────────────
    st.markdown("""
    <div class="dr-section">
      <div class="dr-section-title" style="color:#fbbf24;">
        <span style="width:9px;height:9px;border-radius:50%;background:#fbbf24;display:inline-block;box-shadow:0 0 10px rgba(251,191,36,0.6);flex-shrink:0;"></span>
        04 &nbsp;— Final Verdict
        <span class="dr-section-subtitle">Composite score across all dimensions</span>
      </div>""", unsafe_allow_html=True)

    verdict = compute_final_verdict(
        risk_sc, manip_sc, m_result, z_result,
        st.session_state.get(gov_key, {}),
        st.session_state.get(cc_key, {})
    )
    vc = verdict["verdict_color"]
    st.markdown(f"""
    <div class="verdict-card" style="background:{verdict['verdict_bg']};border:1px solid {verdict['verdict_border']};">
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#374151;text-transform:uppercase;letter-spacing:2.5px;margin-bottom:0.5rem;">Final Verdict</div>
      <div class="verdict-word" style="color:{vc};">{verdict['verdict_icon']} {verdict['verdict']}</div>
      <div class="verdict-desc">{verdict['verdict_desc']}</div>
      <div class="verdict-composite">Composite risk score: {verdict['composite_score']}/10</div>
    </div>""", unsafe_allow_html=True)

    col_v1, col_v2 = st.columns(2)
    with col_v1:
        radar = _verdict_radar(verdict["score_components"])
        if radar: st.plotly_chart(radar, use_container_width=True, config={"displayModeBar": False}, key=f"radar_verdict_{ticker}")

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
            st.markdown(f"<div style='margin-top:1.2rem;'><div style='font-family:Outfit,sans-serif;font-size:0.78rem;font-weight:600;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;'>Risk Drivers</div><ul class='reason-list'>{''.join(f'<li class=\"neg\">{r}</li>' for r in verdict['reasons'])}</ul></div>", unsafe_allow_html=True)
        if verdict["positives"]:
            st.markdown(f"<div style='margin-top:0.8rem;'><div style='font-family:Outfit,sans-serif;font-size:0.78rem;font-weight:600;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;'>Positive Signals</div><ul class='reason-list'>{''.join(f'<li class=\"pos\">{p}</li>' for p in verdict['positives'])}</ul></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("""
    <div style="margin-top:1rem;padding:1rem 1.3rem;background:rgba(255,255,255,0.02);border:1px solid #111827;border-radius:12px;font-family:'DM Sans',sans-serif;font-size:0.78rem;color:#374151;line-height:1.7;">
      ⚠️ <strong style="color:#4b5563;">Not investment advice.</strong>
      Beneish M-Score and Altman Z-Score are probabilistic indicators, not proof of manipulation or distress.
      DuckDuckGo search results may be incomplete. Always verify with official BSE/NSE filings.
      Consult a SEBI-registered advisor before investing.
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  INTEGRATION HELPER  — render_deep_research_selector
#  BUG FIX: "Search Another Company" button clears result state
#  so users can run deep research on multiple companies without
#  refreshing the page.
# ══════════════════════════════════════════════════════════════

def render_deep_research_selector(all_results=None):
    """
    Call inside `with tab_deep_research:` in app.py.

    THREE tabs:
      1. 🔍 Search Any Company  — full NSE autocomplete
      2. 📋 From Analysed List  — companies already run through red-flag pipeline
      3. ℹ️ Info  — plain-English explanation of Beneish M-Score & Altman Z-Score
    """
    st.markdown(DEEP_RESEARCH_CSS, unsafe_allow_html=True)

    mode_tab1, mode_tab2, mode_tab3 = st.tabs([
        "🔍  Search Any NSE Company",
        "📋  From Analysed List",
        "ℹ️  What are these scores?",
    ], key="dr_tabs_main")

    # ─────────────────────────────────────────────────────────
    #  MODE 1 — Full NSE autocomplete search
    #  BUG FIX: Added "Search Another Company" reset button
    #           that clears per-ticker session state so users
    #           can run back-to-back analyses without refreshing.
    # ─────────────────────────────────────────────────────────
    with mode_tab1:

        st.markdown("""
        <div class="dr-search-box">
          <div class="dr-search-title">
            Search any listed NSE company and run deep research directly —
            no need to analyse it in the main tab first
          </div>
        </div>""", unsafe_allow_html=True)

        with st.spinner("Loading NSE company list…"):
            nse_dict = _load_nse_company_list()

        list_loaded = nse_dict and len(nse_dict) > 60
        source_note = (
            f"✅ {len(nse_dict):,} NSE companies loaded"
            if list_loaded
            else "⚠️ Using fallback list of ~70 companies — EQUITY_L.csv not reachable"
        )
        st.caption(source_note)

        # ── If a result is already shown, offer "Search Another" ──
        active_tk = st.session_state.get("dr_active_ticker")
        if active_tk and st.session_state.get(f"dr_direct_done_{active_tk}"):
            result_shown = st.session_state.get(f"dr_direct_result_{active_tk}")
            shown_name = result_shown.get("name", active_tk) if result_shown else active_tk

            st.markdown(f"""
            <div class="reset-search-bar">
              <div>
                <div class="reset-search-bar-text">Currently showing deep research for:</div>
                <div class="reset-search-bar-ticker">{shown_name} ({active_tk})</div>
              </div>
            </div>""", unsafe_allow_html=True)

            if st.button("🔄 Search Another Company", key="dr_reset_btn", use_container_width=False):
                # Clear all per-ticker state for the previous company
                for key in [
                    f"gov_{active_tk}", f"cc_{active_tk}",
                    f"dr_direct_result_{active_tk}",
                    f"dr_direct_done_{active_tk}",
                ]:
                    st.session_state.pop(key, None)
                st.session_state.pop("dr_active_ticker", None)
                st.rerun()

        else:
            # ── Company selector ──────────────────────────────
            company_labels = ["— select a company —"] + sorted(nse_dict.keys())
            selected_label = st.selectbox(
                "Search by company name or ticker symbol",
                options=company_labels,
                index=0,
                key="dr_nse_company_select",
                help="Start typing a company name or NSE symbol to filter the list",
            )

            selected_ticker = nse_dict.get(selected_label)

            col_exc, col_spacer = st.columns([1, 3])
            with col_exc:
                use_bse = st.checkbox("Use BSE (.BO) instead of NSE", key="dr_use_bse")
            if selected_ticker and use_bse:
                selected_ticker = selected_ticker.replace(".NS", ".BO")

            if selected_ticker:
                st.markdown(
                    f"<div style='font-family:JetBrains Mono,monospace;font-size:0.68rem;"
                    f"color:#5a6e8c;margin:4px 0 12px;'>Ticker: {selected_ticker}</div>",
                    unsafe_allow_html=True,
                )

            col_btn, col_note = st.columns([1, 3])
            with col_btn:
                direct_run = st.button(
                    "🔬 Run Deep Research →",
                    type="primary",
                    key="dr_direct_run_btn",
                    disabled=not bool(selected_ticker),
                )
            with col_note:
                st.caption(
                    "Fetches live data via yfinance · Beneish M-Score · Altman Z-Score "
                    "· Governance scan · Concall intelligence · ~30–60 sec"
                )

            if direct_run and selected_ticker:
                # Clear any lingering state for this ticker
                for key in [f"gov_{selected_ticker}", f"cc_{selected_ticker}",
                            f"dr_direct_result_{selected_ticker}",
                            f"dr_direct_done_{selected_ticker}"]:
                    st.session_state.pop(key, None)

                with st.spinner(f"Fetching company data for {selected_ticker}…"):
                    result, err = _fetch_company_data_for_deep_research(selected_ticker)

                if err:
                    st.error(f"❌ {err}")
                else:
                    st.session_state[f"dr_direct_result_{selected_ticker}"] = result
                    st.session_state[f"dr_direct_done_{selected_ticker}"] = True
                    st.session_state["dr_active_ticker"] = selected_ticker
                    st.rerun()

        # ── Render result if available ────────────────────────
        if active_tk and st.session_state.get(f"dr_direct_done_{active_tk}"):
            result = st.session_state.get(f"dr_direct_result_{active_tk}")
            if result:
                st.divider()
                render_deep_research_tab(result)

    # ─────────────────────────────────────────────────────────
    #  MODE 2 — From already-analysed list
    # ─────────────────────────────────────────────────────────
    with mode_tab2:
        if not all_results:
            st.markdown("""
            <div style="text-align:center;padding:3rem 1rem;">
              <div style="font-size:2.2rem;margin-bottom:1rem;">📋</div>
              <div style="font-family:'Outfit',sans-serif;font-size:1rem;color:#4b5563;margin-bottom:0.5rem;">
                No companies analysed yet
              </div>
              <div style="font-family:'DM Sans',sans-serif;font-size:0.82rem;color:#2d3a55;line-height:1.6;">
                Go to <strong style="color:#4b5563;">Search &amp; Analyse</strong> to run the
                red-flag pipeline first — or use the
                <em>Search Any NSE Company</em> tab above to jump straight in.
              </div>
            </div>""", unsafe_allow_html=True)
            return

        company_options = {
            f"{r['name']} ({r['ticker'].replace('.NS','').replace('.BO','')}) — Risk: {r['risk_score']}/10": r
            for r in all_results
        }
        selected_lbl    = st.selectbox(
            "Select a company from your analysis session",
            options=list(company_options.keys()),
            key="dr_list_select",
        )
        selected_result = company_options[selected_lbl]

        col_btn2, col_note2 = st.columns([1, 3])
        with col_btn2:
            run_btn = st.button("🔬 Run Deep Research →", type="primary", key="dr_list_run_btn")
        with col_note2:
            st.caption(
                "Uses pre-loaded financials · Beneish M-Score · Altman Z-Score "
                "· Governance scan · Concall analysis · ~30–60 sec"
            )

        dr_key = f"dr_done_{selected_result['ticker']}"
        if run_btn or dr_key in st.session_state:
            st.session_state[dr_key] = True
            render_deep_research_tab(selected_result)

    # ─────────────────────────────────────────────────────────
    #  MODE 3 — Info tab (NEW)
    # ─────────────────────────────────────────────────────────
    with mode_tab3:
        render_info_tab()