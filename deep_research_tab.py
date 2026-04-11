# ============================================================
#  DEEP RESEARCH TAB  —  deep_research_tab.py
#
#  Integrates with the India Red Flag Dashboard (app.py)
#
#  SECTION A — FORENSIC MODELS  (Beneish M-Score, Altman Z-Score)
#  SECTION B — GOVERNANCE SCAN  (Claude API + Web Search)
#  SECTION C — CONCALL INTELLIGENCE  (Claude API + Web Search)
#  SECTION D — FINAL VERDICT ENGINE
#  SECTION E — UI RENDERER
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import json
import time
from datetime import datetime

# ──────────────────────────────────────────────────────────────
#  HELPERS (reused from app.py style)
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
    """Safe division returning None if b is zero or None."""
    if a is None or b is None or b == 0:
        return None
    return a / b


# ══════════════════════════════════════════════════════════════
#  SECTION A — FORENSIC MODELS
# ══════════════════════════════════════════════════════════════

def compute_beneish_mscore(data):
    """
    Beneish M-Score (8-factor model).
    Returns (score, components_dict, interpretation, verdict_color)
    
    Components:
      DSRI  = Days Sales Receivable Index
      GMI   = Gross Margin Index
      AQI   = Asset Quality Index
      SGI   = Sales Growth Index
      DEPI  = Depreciation Index
      SGAI  = SG&A Index (proxied)
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
    eq   = bs.get("equity")
    cfo  = cf.get("cfo")

    components = {}
    missing = []

    # ── DSRI ──────────────────────────────────────────────────
    # (Receivables_t / Revenue_t) / (Receivables_t-1 / Revenue_t-1)
    rec_t  = _last(rec);  rec_p = _prev(rec)
    rev_t  = _last(rev);  rev_p = _prev(rev)
    if all(v not in (None, 0) for v in [rec_t, rec_p, rev_t, rev_p]):
        dsri = (rec_t / rev_t) / (rec_p / rev_p)
    else:
        dsri = 1.0
        missing.append("DSRI")
    components["DSRI"] = {"value": round(dsri, 3), "weight": 0.920,
                           "label": "Days Sales Receivable Index",
                           "flag": dsri > 1.465,
                           "note": "Receivables growing faster than revenue → potential channel stuffing"}

    # ── GMI ───────────────────────────────────────────────────
    # Gross Margin Index = GM_t-1 / GM_t
    gp_t = _last(gp);  gp_p = _prev(gp)
    if all(v not in (None, 0) for v in [gp_t, gp_p, rev_t, rev_p]):
        gm_t = gp_t / rev_t
        gm_p = gp_p / rev_p
        gmi  = _safe_div(gm_p, gm_t) or 1.0
    else:
        gmi = 1.0
        missing.append("GMI")
    components["GMI"] = {"value": round(gmi, 3), "weight": 0.528,
                          "label": "Gross Margin Index",
                          "flag": gmi > 1.193,
                          "note": "Margins deteriorating — incentive to manipulate earnings"}

    # ── AQI ───────────────────────────────────────────────────
    # AQI = [1 - (CA_t + NCA_t) / TA_t] / [1 - (CA_p + NCA_p) / TA_p]
    ca_t  = _last(bs.get("current_assets"));  ca_p  = _prev(bs.get("current_assets"))
    nca_t = _last(nca);                        nca_p = _prev(nca)
    ta_t  = _last(ta);                         ta_p  = _prev(ta)
    if all(v not in (None, 0) for v in [ca_t, nca_t, ta_t, ca_p, nca_p, ta_p]):
        aqi_t = 1 - (ca_t + nca_t) / ta_t
        aqi_p = 1 - (ca_p + nca_p) / ta_p
        aqi   = _safe_div(aqi_t, aqi_p) or 1.0
    else:
        aqi = 1.0
        missing.append("AQI")
    components["AQI"] = {"value": round(aqi, 3), "weight": 0.404,
                          "label": "Asset Quality Index",
                          "flag": aqi > 1.254,
                          "note": "Non-current / intangible assets increasing → possible capitalisation"}

    # ── SGI ───────────────────────────────────────────────────
    # Sales Growth Index = Revenue_t / Revenue_t-1
    sgi = _safe_div(rev_t, rev_p) or 1.0
    if rev_t is None or rev_p is None:
        missing.append("SGI")
    components["SGI"] = {"value": round(sgi, 3), "weight": 0.892,
                          "label": "Sales Growth Index",
                          "flag": sgi > 1.607,
                          "note": "High growth companies face pressure to sustain it through manipulation"}

    # ── DEPI ──────────────────────────────────────────────────
    # DEPI = (Dep_t-1 / (Dep_t-1 + PPE_t-1)) / (Dep_t / (Dep_t + PPE_t))
    dep_t = _last(dep); dep_p = _prev(dep)
    ppe_t = _last(nca);  ppe_p = _prev(nca)
    if all(v not in (None, 0) for v in [dep_t, dep_p, ppe_t, ppe_p]):
        d_p = dep_p / (dep_p + ppe_p)
        d_t = dep_t / (dep_t + ppe_t)
        depi = _safe_div(d_p, d_t) or 1.0
    else:
        depi = 1.0
        missing.append("DEPI")
    components["DEPI"] = {"value": round(depi, 3), "weight": 0.115,
                           "label": "Depreciation Index",
                           "flag": depi > 1.077,
                           "note": "Slowing depreciation rate → assets being sweated or life extended"}

    # ── SGAI ──────────────────────────────────────────────────
    # Proxy: Interest expense / Revenue (SG&A not directly available from yfinance)
    int_t = abs(_last(pnl.get("interest_exp")) or 0)
    int_p = abs(_prev(pnl.get("interest_exp")) or 0)
    if all(v not in (None, 0) for v in [int_t, int_p, rev_t, rev_p]):
        sgai_t = int_t / rev_t
        sgai_p = int_p / rev_p
        sgai   = _safe_div(sgai_t, sgai_p) or 1.0
    else:
        sgai = 1.0
        missing.append("SGAI")
    components["SGAI"] = {"value": round(sgai, 3), "weight": 0.415,
                           "label": "Expense Index (Interest / Revenue proxy)",
                           "flag": sgai > 1.041,
                           "note": "Disproportionate expense growth vs revenue"}

    # ── LVGI ──────────────────────────────────────────────────
    # LVGI = (LTD_t + CL_t) / TA_t  /  (LTD_p + CL_p) / TA_p
    cl_t  = _last(bs.get("current_liab")); cl_p = _prev(bs.get("current_liab"))
    dbt_t = _last(debt);                   dbt_p = _prev(debt)
    if all(v not in (None, 0) for v in [cl_t, cl_p, dbt_t, dbt_p, ta_t, ta_p]):
        lv_t = (dbt_t + cl_t) / ta_t
        lv_p = (dbt_p + cl_p) / ta_p
        lvgi  = _safe_div(lv_t, lv_p) or 1.0
    else:
        lvgi = 1.0
        missing.append("LVGI")
    components["LVGI"] = {"value": round(lvgi, 3), "weight": 0.172,
                           "label": "Leverage Index",
                           "flag": lvgi > 1.111,
                           "note": "Increasing leverage → debt covenant pressure to inflate profits"}

    # ── TATA ──────────────────────────────────────────────────
    # Total Accruals to Total Assets = (Net Income - CFO) / Total Assets
    pat_t = _last(pat)
    cfo_t = _last(cfo)
    if all(v is not None for v in [pat_t, cfo_t, ta_t]) and ta_t != 0:
        tata = (pat_t - cfo_t) / ta_t
    else:
        tata = 0.0
        missing.append("TATA")
    components["TATA"] = {"value": round(tata, 4), "weight": 4.679,
                           "label": "Total Accruals to Total Assets",
                           "flag": tata > 0.031,
                           "note": "High accruals = earnings not backed by cash → manipulation signal"}

    # ── M-SCORE FORMULA ───────────────────────────────────────
    m_score = (
        -4.840
        + 0.920  * dsri
        + 0.528  * gmi
        + 0.404  * aqi
        + 0.892  * sgi
        + 0.115  * depi
        + 0.415  * sgai
        + 0.172  * lvgi
        + 4.679  * tata
    )
    m_score = round(m_score, 3)

    # ── INTERPRETATION ────────────────────────────────────────
    if m_score > -1.78:
        interpretation = "Likely manipulator"
        verdict_color  = "#ef4444"
        verdict_icon   = "🔴"
        risk_level     = "HIGH"
    elif m_score > -2.22:
        interpretation = "Grey zone — monitor closely"
        verdict_color  = "#f59e0b"
        verdict_icon   = "🟡"
        risk_level     = "MEDIUM"
    else:
        interpretation = "Unlikely manipulator"
        verdict_color  = "#22c55e"
        verdict_icon   = "🟢"
        risk_level     = "LOW"

    red_flags = [k for k, v in components.items() if v["flag"]]

    return {
        "score":          m_score,
        "interpretation": interpretation,
        "verdict_color":  verdict_color,
        "verdict_icon":   verdict_icon,
        "risk_level":     risk_level,
        "components":     components,
        "red_flags":      red_flags,
        "missing":        missing,
        "threshold":      -1.78,
    }


def compute_altman_zscore(data, sector=""):
    """
    Altman Z-Score (public company model).
    Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
    
    X1 = Working Capital / Total Assets
    X2 = Retained Earnings / Total Assets  (proxy: Equity - Paid-up, use net profit cumulative)
    X3 = EBIT / Total Assets
    X4 = Market Cap / Total Liabilities
    X5 = Revenue / Total Assets
    """
    pnl  = data.get("pnl", {})
    bs   = data.get("bs",  {})
    mcap = data.get("mcap_cr")

    ca   = _last(bs.get("current_assets"))
    cl   = _last(bs.get("current_liab"))
    ta   = _last(bs.get("total_assets"))
    eq   = _last(bs.get("equity"))
    debt = _last(bs.get("total_debt"))
    ebit = _last(pnl.get("operating_profit"))
    rev  = _last(pnl.get("revenue"))
    pat  = _last(pnl.get("net_profit"))

    components = {}
    missing    = []

    # X1 — Working Capital / TA
    if ca is not None and cl is not None and ta not in (None, 0):
        x1 = (ca - cl) / ta
    else:
        x1 = 0.0
        missing.append("X1")
    components["X1"] = {"value": round(x1, 4), "weight": 1.2,
                         "label": "Working Capital / Total Assets",
                         "note": "Liquidity measure — negative means current debts exceed current assets"}

    # X2 — Retained Earnings proxy / TA
    # Use cumulative net profit as retained earnings proxy (yfinance doesn't expose RE directly)
    pat_series = pnl.get("net_profit")
    if pat_series is not None and ta not in (None, 0):
        re_proxy = float(pat_series.dropna().sum())
        x2 = re_proxy / ta
    else:
        x2 = 0.0
        missing.append("X2 (RE proxy)")
    components["X2"] = {"value": round(x2, 4), "weight": 1.4,
                         "label": "Retained Earnings (proxy) / Total Assets",
                         "note": "Cumulative profitability — young companies naturally score lower"}

    # X3 — EBIT / TA
    if ebit is not None and ta not in (None, 0):
        x3 = ebit / ta
    else:
        x3 = 0.0
        missing.append("X3")
    components["X3"] = {"value": round(x3, 4), "weight": 3.3,
                         "label": "EBIT / Total Assets",
                         "note": "Core earnings power relative to asset base"}

    # X4 — Market Cap / Total Liabilities
    if mcap is not None and debt is not None and cl is not None:
        total_liab = (debt or 0) + (cl or 0)
        x4 = _safe_div(mcap, total_liab) or 0.0
    else:
        x4 = 1.0
        missing.append("X4")
    components["X4"] = {"value": round(x4, 4), "weight": 0.6,
                         "label": "Market Cap / Total Liabilities",
                         "note": "Market's confidence vs debt burden — low means market distrust"}

    # X5 — Revenue / TA (asset turnover)
    if rev is not None and ta not in (None, 0):
        x5 = rev / ta
    else:
        x5 = 0.0
        missing.append("X5")
    components["X5"] = {"value": round(x5, 4), "weight": 1.0,
                         "label": "Revenue / Total Assets",
                         "note": "Asset efficiency — how hard assets are working"}

    # ── Z-SCORE ───────────────────────────────────────────────
    z_score = (
        1.2 * x1 +
        1.4 * x2 +
        3.3 * x3 +
        0.6 * x4 +
        1.0 * x5
    )
    z_score = round(z_score, 3)

    # ── INTERPRETATION ────────────────────────────────────────
    # Note: For financial/banking sectors Z-score is less applicable
    is_financial = any(k in sector.lower() for k in ["bank", "financial", "nbfc", "insurance"])

    if is_financial:
        interpretation = "Z-Score less reliable for financial sector companies"
        verdict_color  = "#6b7280"
        verdict_icon   = "⚪"
        risk_level     = "N/A"
    elif z_score < 1.81:
        interpretation = "Distress zone — high bankruptcy risk"
        verdict_color  = "#ef4444"
        verdict_icon   = "🔴"
        risk_level     = "HIGH"
    elif z_score < 2.99:
        interpretation = "Grey zone — financial stress possible"
        verdict_color  = "#f59e0b"
        verdict_icon   = "🟡"
        risk_level     = "MEDIUM"
    else:
        interpretation = "Safe zone — financially healthy"
        verdict_color  = "#22c55e"
        verdict_icon   = "🟢"
        risk_level     = "LOW"

    return {
        "score":          z_score,
        "interpretation": interpretation,
        "verdict_color":  verdict_color,
        "verdict_icon":   verdict_icon,
        "risk_level":     risk_level,
        "components":     components,
        "missing":        missing,
        "is_financial":   is_financial,
        "zones":          {"distress": 1.81, "grey": 2.99},
    }


# ══════════════════════════════════════════════════════════════
#  SECTION B — CLAUDE API CALLER
# ══════════════════════════════════════════════════════════════

def call_claude_api(prompt, system_prompt, max_tokens=2500):
    """
    Calls Anthropic API with web_search tool enabled.
    Returns the full text response.
    """
    try:
        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "tools": [
                {
                    "type": "web_search_20250305",
                    "name": "web_search"
                }
            ],
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract all text blocks (web search may produce multiple blocks)
        text_parts = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block["text"])
        return "\n".join(text_parts).strip()

    except requests.exceptions.Timeout:
        return "⚠️ Request timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return f"⚠️ API error: {str(e)[:200]}"
    except Exception as e:
        return f"⚠️ Unexpected error: {str(e)[:200]}"


def governance_scan(company_name, ticker, sector):
    """
    Uses Claude API + web search to scan governance risks.
    Returns structured dict with findings.
    """
    nse_sym = ticker.replace(".NS", "").replace(".BO", "")

    system = """You are a forensic equity research analyst specializing in Indian listed companies.
Your job is to scan for governance risks. Be factual, cite sources, be concise.
You MUST respond ONLY in valid JSON. No markdown, no explanation outside the JSON.
Return this exact structure:
{
  "governance_score": <integer 1-10, where 10 = highest risk>,
  "overall_risk": "<LOW|MEDIUM|HIGH>",
  "auditor_issues": [{"date": "...", "detail": "...", "severity": "<LOW|MEDIUM|HIGH>"}],
  "sebi_actions": [{"date": "...", "detail": "...", "severity": "<LOW|MEDIUM|HIGH>"}],
  "board_changes": [{"date": "...", "detail": "...", "severity": "<LOW|MEDIUM|HIGH>"}],
  "credit_events": [{"date": "...", "detail": "...", "severity": "<LOW|MEDIUM|HIGH>"}],
  "other_flags": [{"date": "...", "detail": "...", "severity": "<LOW|MEDIUM|HIGH>"}],
  "positive_signals": ["..."],
  "summary": "<2-3 sentence governance summary>",
  "sources_checked": ["..."]
}
If nothing found for a category return empty array [].
"""

    prompt = f"""Search for governance risk signals for {company_name} (NSE: {nse_sym}) in the last 18 months.

Check for:
1. Auditor resignation or audit qualification
2. SEBI investigation, show-cause notice, or penalty
3. Independent director or CFO resignation
4. Credit rating downgrade or default
5. Promoter pledge increase above 50%
6. Related party transaction concerns
7. Any fraud, scam, or whistleblower allegations
8. Regulatory or court orders against the company

Search queries to use:
- "{company_name} auditor resignation 2024 2025"
- "{company_name} SEBI notice investigation"  
- "{company_name} director resignation 2024 2025"
- "{nse_sym} NSE BSE corporate governance"
- "{company_name} credit rating downgrade default"

Return ONLY valid JSON."""

    raw = call_claude_api(prompt, system, max_tokens=1500)

    # Parse JSON safely
    try:
        # Strip any accidental markdown fences
        clean = raw.replace("```json", "").replace("```", "").strip()
        # Find JSON object
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(clean[start:end])
    except Exception:
        pass

    # Fallback structure
    return {
        "governance_score": 5,
        "overall_risk":     "UNKNOWN",
        "auditor_issues":   [],
        "sebi_actions":     [],
        "board_changes":    [],
        "credit_events":    [],
        "other_flags":      [],
        "positive_signals": [],
        "summary":          raw[:500] if raw and not raw.startswith("⚠️") else "Could not retrieve governance data.",
        "sources_checked":  [],
    }


def concall_intelligence(company_name, ticker, risk_flags, manip_flags):
    """
    Uses Claude API + web search to find concall commentary.
    Tracks management explanations for detected red flags.
    Returns structured dict with 4-quarter trend analysis.
    """
    nse_sym = ticker.replace(".NS", "").replace(".BO", "")

    # Build flag summary for context
    all_flags = []
    for f in risk_flags:
        all_flags.append(f"RISK [{f[1]}]: {f[2]}")
    for f in manip_flags:
        all_flags.append(f"MANIPULATION [{f[1]}]: {f[2]}")

    flag_text = "\n".join(all_flags[:8]) if all_flags else "No specific flags — do general management credibility review"

    system = """You are a forensic equity analyst reviewing management credibility via earnings call transcripts.
Search for the last 4 quarters of concall/earnings call commentary for an Indian listed company.
Respond ONLY in valid JSON. No markdown. No preamble.
Return this exact structure:
{
  "quarters_found": <integer 0-4>,
  "quarters_data": [
    {
      "quarter": "Q1 FY25",
      "date": "July 2024",
      "key_themes": ["..."],
      "commentary_on_flags": {"<flag_name>": "<what management said>"},
      "management_tone": "<Confident|Cautious|Evasive|Optimistic|Defensive>",
      "credibility_score": <1-10>,
      "notable_quotes": ["<under 15 words>"]
    }
  ],
  "flag_tracking": [
    {
      "flag": "<flag title>",
      "trend": "<Resolved|Improving|Persistent|Worsening|Not Addressed>",
      "trend_color": "<green|yellow|orange|red>",
      "q_by_q": {"Q1": "...", "Q2": "...", "Q3": "...", "Q4": "..."},
      "management_credible": <true|false>,
      "insight": "<2 sentence analyst insight>"
    }
  ],
  "overall_credibility": "<LOW|MEDIUM|HIGH>",
  "credibility_score": <1-10>,
  "key_concerns": ["..."],
  "positive_signals": ["..."],
  "summary": "<3-4 sentence overall concall intelligence summary>"
}
"""

    prompt = f"""Analyze earnings call / concall transcripts for {company_name} (NSE: {nse_sym}).

RED FLAGS DETECTED IN FINANCIAL DATA:
{flag_text}

Search for:
1. Last 4 quarters earnings call transcripts or summaries
2. Management commentary on the specific red flags above
3. Guidance consistency vs actual results
4. Any admissions of issues or forward-looking warnings

Search queries:
- "{company_name} earnings call transcript Q4 Q3 Q2 Q1 FY25 FY24"
- "{company_name} concall management commentary 2024 2025"
- "{company_name} investor call working capital receivables" (if relevant)
- "site:screener.in {nse_sym} concall"

For each flag found, track what management said across quarters. 
Note if management kept changing their explanation (credibility concern).
Return ONLY valid JSON."""

    raw = call_claude_api(prompt, system, max_tokens=2500)

    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(clean[start:end])
    except Exception:
        pass

    return {
        "quarters_found":      0,
        "quarters_data":       [],
        "flag_tracking":       [],
        "overall_credibility": "UNKNOWN",
        "credibility_score":   5,
        "key_concerns":        [],
        "positive_signals":    [],
        "summary":             raw[:500] if raw and not raw.startswith("⚠️") else "Could not retrieve concall data.",
    }


# ══════════════════════════════════════════════════════════════
#  SECTION D — FINAL VERDICT ENGINE
# ══════════════════════════════════════════════════════════════

def compute_final_verdict(risk_score, manip_score, m_score_result, z_score_result,
                           governance_result, concall_result):
    """
    Synthesizes all signals into a final INVEST / WATCH / AVOID verdict.
    """
    reasons = []
    positives = []
    score_components = []

    # ── Risk score contribution ────────────────────────────────
    if risk_score >= 6:
        reasons.append(f"High financial risk score ({risk_score}/10)")
        score_components.append(("Financial Risk", risk_score, 10, "#ef4444"))
    elif risk_score >= 3:
        reasons.append(f"Moderate financial risk ({risk_score}/10) — monitor")
        score_components.append(("Financial Risk", risk_score, 10, "#f59e0b"))
    else:
        positives.append(f"Clean financial risk profile ({risk_score}/10)")
        score_components.append(("Financial Risk", risk_score, 10, "#22c55e"))

    # ── Manipulation score ─────────────────────────────────────
    if manip_score >= 6:
        reasons.append(f"High manipulation signal score ({manip_score}/10)")
        score_components.append(("Manipulation Signal", manip_score, 10, "#a78bfa"))
    elif manip_score >= 3:
        reasons.append(f"Some manipulation signals detected ({manip_score}/10)")
        score_components.append(("Manipulation Signal", manip_score, 10, "#c4b5fd"))
    else:
        positives.append(f"No significant manipulation signals ({manip_score}/10)")
        score_components.append(("Manipulation Signal", manip_score, 10, "#6ee7b7"))

    # ── Beneish M-Score ────────────────────────────────────────
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
        positives.append(f"Beneish M-Score ({m_val}) suggests no manipulation")
        score_components.append(("Beneish M-Score", 2, 10, "#22c55e"))

    # ── Altman Z-Score ─────────────────────────────────────────
    z_risk = z_score_result.get("risk_level", "LOW")
    z_val  = z_score_result.get("score", 3.0)
    if z_risk == "HIGH":
        reasons.append(f"Altman Z-Score ({z_val}) in distress zone — bankruptcy risk elevated")
        score_components.append(("Altman Z-Score", 8, 10, "#ef4444"))
    elif z_risk == "MEDIUM":
        reasons.append(f"Altman Z-Score ({z_val}) in grey zone — watch financial health")
        score_components.append(("Altman Z-Score", 5, 10, "#f59e0b"))
    elif z_risk == "N/A":
        score_components.append(("Altman Z-Score", 0, 10, "#6b7280"))
    else:
        positives.append(f"Altman Z-Score ({z_val}) in safe zone")
        score_components.append(("Altman Z-Score", 2, 10, "#22c55e"))

    # ── Governance ─────────────────────────────────────────────
    gov_risk = governance_result.get("overall_risk", "UNKNOWN")
    gov_score = governance_result.get("governance_score", 5)
    if gov_risk == "HIGH":
        reasons.append(f"High governance risk (score: {gov_score}/10)")
        score_components.append(("Governance", gov_score, 10, "#ef4444"))
    elif gov_risk == "MEDIUM":
        reasons.append(f"Moderate governance concerns (score: {gov_score}/10)")
        score_components.append(("Governance", gov_score, 10, "#f59e0b"))
    elif gov_risk == "LOW":
        positives.append("Clean governance profile")
        score_components.append(("Governance", gov_score, 10, "#22c55e"))
    else:
        score_components.append(("Governance", 5, 10, "#6b7280"))

    # ── Concall credibility ────────────────────────────────────
    cc_cred = concall_result.get("overall_credibility", "UNKNOWN")
    cc_score = concall_result.get("credibility_score", 5)
    if cc_cred == "LOW":
        reasons.append(f"Low management credibility in earnings calls (score: {cc_score}/10)")
        score_components.append(("Mgmt Credibility", 10 - cc_score, 10, "#ef4444"))
    elif cc_cred == "MEDIUM":
        score_components.append(("Mgmt Credibility", 10 - cc_score, 10, "#f59e0b"))
    elif cc_cred == "HIGH":
        positives.append("High management credibility in earnings calls")
        score_components.append(("Mgmt Credibility", 10 - cc_score, 10, "#22c55e"))
    else:
        score_components.append(("Mgmt Credibility", 5, 10, "#6b7280"))

    # ── Compute weighted composite ─────────────────────────────
    weights = {
        "Financial Risk":     0.25,
        "Manipulation Signal":0.20,
        "Beneish M-Score":    0.20,
        "Altman Z-Score":     0.15,
        "Governance":         0.10,
        "Mgmt Credibility":   0.10,
    }
    composite = 0.0
    for label, val, mx, _ in score_components:
        w = weights.get(label, 0.10)
        composite += (val / mx) * w * 10

    composite = round(composite, 1)

    # ── Verdict ────────────────────────────────────────────────
    red_count = sum(1 for r in reasons if "High" in r or "distress" in r or "manipulation zone" in r)

    if composite >= 6.5 or red_count >= 3:
        verdict      = "AVOID"
        verdict_color = "#ef4444"
        verdict_bg    = "rgba(220,38,38,0.08)"
        verdict_border= "rgba(220,38,38,0.3)"
        verdict_icon  = "🔴"
        verdict_desc  = "Multiple high-severity signals across financial, forensic, and governance dimensions."
    elif composite >= 4.0 or red_count >= 1:
        verdict      = "WATCH"
        verdict_color = "#f59e0b"
        verdict_bg    = "rgba(245,158,11,0.08)"
        verdict_border= "rgba(245,158,11,0.3)"
        verdict_icon  = "🟡"
        verdict_desc  = "Some concerns detected. Not safe to invest without deeper due diligence."
    else:
        verdict      = "INVEST"
        verdict_color = "#22c55e"
        verdict_bg    = "rgba(34,197,94,0.08)"
        verdict_border= "rgba(34,197,94,0.3)"
        verdict_icon  = "🟢"
        verdict_desc  = "No major red flags. Financials appear trustworthy. Proceed with normal valuation analysis."

    return {
        "verdict":         verdict,
        "verdict_color":   verdict_color,
        "verdict_bg":      verdict_bg,
        "verdict_border":  verdict_border,
        "verdict_icon":    verdict_icon,
        "verdict_desc":    verdict_desc,
        "composite_score": composite,
        "reasons":         reasons,
        "positives":       positives,
        "score_components": score_components,
    }


# ══════════════════════════════════════════════════════════════
#  SECTION E — UI RENDERER
# ══════════════════════════════════════════════════════════════

# ── CSS for Deep Research Tab ─────────────────────────────────
DEEP_RESEARCH_CSS = """
<style>
/* ── SNAPSHOT HEADER ── */
.dr-snapshot {
    background: linear-gradient(135deg, #060a14 0%, #090c18 100%);
    border: 1px solid #1a2540;
    border-radius: 18px;
    padding: 2rem 2.4rem;
    margin-bottom: 1.4rem;
    position: relative;
    overflow: hidden;
}
.dr-snapshot::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 220px; height: 220px;
    background: radial-gradient(circle, rgba(139,92,246,0.1) 0%, transparent 65%);
    border-radius: 50%;
    pointer-events: none;
}
.dr-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(139,92,246,0.1);
    border: 1px solid rgba(139,92,246,0.25);
    color: #a78bfa;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 4px 12px;
    border-radius: 20px;
    margin-bottom: 0.7rem;
}
.dr-company-name {
    font-size: 1.6rem;
    font-weight: 700;
    color: #f0f2f8;
    letter-spacing: -0.5px;
    margin-bottom: 0.2rem;
}
.dr-company-meta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #4b5563;
    margin-bottom: 1.2rem;
}
.dr-score-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
}
.dr-score-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 8px 14px;
    font-family: 'JetBrains Mono', monospace;
}
.dr-score-pill .label {
    font-size: 0.6rem;
    color: #4b5563;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}
.dr-score-pill .val {
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: -0.5px;
}

/* ── SECTION CARDS ── */
.dr-section {
    background: #0d1120;
    border: 1px solid #1a2540;
    border-radius: 16px;
    padding: 1.5rem 1.8rem;
    margin-bottom: 1.2rem;
}
.dr-section-title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.63rem;
    text-transform: uppercase;
    letter-spacing: 2.5px;
    margin-bottom: 1.2rem;
    padding-bottom: 0.7rem;
    border-bottom: 1px solid #111827;
}

/* ── FORENSIC SCORE CARDS ── */
.forensic-grid { display: flex; gap: 14px; margin-bottom: 0; }
.forensic-card {
    flex: 1;
    background: #090e1a;
    border-radius: 14px;
    padding: 1.2rem;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.forensic-score {
    font-size: 2.6rem;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -1.5px;
    margin: 0.4rem 0;
}
.forensic-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #4b5563;
    margin-bottom: 0.3rem;
}
.forensic-verdict {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    font-weight: 600;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    padding: 3px 12px;
    border-radius: 20px;
    display: inline-block;
    margin-top: 0.4rem;
}

/* ── COMPONENT TABLE ── */
.comp-table { width: 100%; border-collapse: collapse; margin-top: 0.8rem; }
.comp-table th {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.56rem;
    color: #2d3a55;
    text-transform: uppercase;
    letter-spacing: 2px;
    padding: 6px 8px;
    border-bottom: 1px solid #0d1726;
    text-align: left;
}
.comp-table td {
    font-size: 0.72rem;
    padding: 7px 8px;
    border-bottom: 1px solid #0a1020;
    color: #6b7280;
    vertical-align: middle;
}
.comp-table tr:last-child td { border-bottom: none; }
.comp-table tr:hover td { background: rgba(255,255,255,0.015); }
.comp-flag { color: #ef4444; font-weight: 700; }
.comp-ok   { color: #34d399; }
.comp-mono {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: #e5e7eb;
}

/* ── GOVERNANCE SIGNALS ── */
.gov-item {
    background: #090e1a;
    border-radius: 10px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.5rem;
    border-left: 3px solid transparent;
}
.gov-item.HIGH   { border-left-color: #ef4444; background: rgba(220,38,38,0.05); }
.gov-item.MEDIUM { border-left-color: #f59e0b; background: rgba(245,158,11,0.05); }
.gov-item.LOW    { border-left-color: #3b82f6; background: rgba(59,130,246,0.05); }
.gov-date {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem;
    color: #374151;
    margin-bottom: 3px;
}
.gov-detail { font-size: 0.78rem; color: #9ca3af; line-height: 1.5; }
.gov-sev {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.55rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    float: right;
    padding: 2px 8px;
    border-radius: 4px;
}
.gov-sev.HIGH   { color: #ef4444; background: rgba(220,38,38,0.1); }
.gov-sev.MEDIUM { color: #f59e0b; background: rgba(245,158,11,0.1); }
.gov-sev.LOW    { color: #60a5fa; background: rgba(59,130,246,0.1); }

/* ── CONCALL QUARTERS ── */
.quarter-card {
    background: #090e1a;
    border: 1px solid #151e33;
    border-radius: 12px;
    padding: 1rem 1.1rem;
    margin-bottom: 0.7rem;
}
.quarter-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.7rem;
}
.quarter-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #6b7280;
    font-weight: 600;
}
.quarter-tone {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.55rem;
    padding: 3px 10px;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.tone-Confident  { color: #34d399; background: rgba(52,211,153,0.1); }
.tone-Cautious   { color: #f59e0b; background: rgba(245,158,11,0.1); }
.tone-Evasive    { color: #ef4444; background: rgba(220,38,38,0.1); }
.tone-Defensive  { color: #f87171; background: rgba(248,113,113,0.1); }
.tone-Optimistic { color: #60a5fa; background: rgba(96,165,250,0.1); }
.quarter-theme { font-size: 0.72rem; color: #6b7280; line-height: 1.6; }

/* ── FLAG TRACKING ── */
.flag-track {
    background: #090e1a;
    border-radius: 12px;
    padding: 1rem 1.1rem;
    margin-bottom: 0.6rem;
    border: 1px solid #151e33;
}
.flag-track-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 0.6rem;
}
.flag-track-name { font-size: 0.82rem; font-weight: 600; color: #e5e7eb; }
.flag-track-status {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.55rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    padding: 3px 10px;
    border-radius: 6px;
    white-space: nowrap;
}
.status-Resolved   { color: #34d399; background: rgba(52,211,153,0.1); }
.status-Improving  { color: #60a5fa; background: rgba(96,165,250,0.1); }
.status-Persistent { color: #f59e0b; background: rgba(245,158,11,0.1); }
.status-Worsening  { color: #ef4444; background: rgba(220,38,38,0.1); }
.status-Not-Addressed { color: #9ca3af; background: rgba(156,163,175,0.1); }
.flag-q-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
    margin: 0.6rem 0;
}
.flag-q-cell {
    background: rgba(255,255,255,0.03);
    border-radius: 6px;
    padding: 6px 8px;
}
.flag-q-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.55rem;
    color: #374151;
    margin-bottom: 2px;
}
.flag-q-text { font-size: 0.66rem; color: #9ca3af; line-height: 1.4; }
.flag-insight { font-size: 0.72rem; color: #6b7280; font-style: italic; margin-top: 0.5rem; line-height: 1.5; }

/* ── FINAL VERDICT ── */
.verdict-card {
    border-radius: 18px;
    padding: 2rem 2.4rem;
    margin-bottom: 1.4rem;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.verdict-word {
    font-size: 3.5rem;
    font-weight: 700;
    letter-spacing: -2px;
    line-height: 1;
    margin: 0.5rem 0;
}
.verdict-desc { font-size: 0.85rem; color: #6b7280; max-width: 480px; margin: 0.5rem auto; }
.verdict-composite {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: #374151;
    margin-top: 0.7rem;
}
.reason-list { list-style: none; padding: 0; margin: 0.8rem 0; }
.reason-list li {
    font-size: 0.78rem;
    color: #9ca3af;
    padding: 5px 0 5px 1.2rem;
    position: relative;
    line-height: 1.5;
}
.reason-list li::before { content: '→'; position: absolute; left: 0; color: inherit; }
.reason-list li.neg::before { color: #ef4444; }
.reason-list li.pos::before { color: #34d399; }

/* ── PROGRESS BARS ── */
.score-bar-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 0.55rem;
}
.score-bar-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: #4b5563;
    width: 140px;
    flex-shrink: 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.score-bar-track {
    flex: 1;
    background: rgba(255,255,255,0.04);
    border-radius: 4px;
    height: 6px;
    overflow: hidden;
}
.score-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.6s ease;
}
.score-bar-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: #374151;
    width: 36px;
    text-align: right;
}

/* ── POSITIVE SIGNALS ── */
.positive-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(34,197,94,0.07);
    border: 1px solid rgba(34,197,94,0.2);
    color: #4ade80;
    font-size: 0.7rem;
    padding: 4px 12px;
    border-radius: 20px;
    margin: 3px 4px 3px 0;
}

/* ── EMPTY STATE ── */
.dr-empty {
    text-align: center;
    padding: 2rem;
    color: #374151;
    font-size: 0.78rem;
}

/* ── LOADING PULSE ── */
.dr-loading {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #4b5563;
    padding: 0.5rem 0;
}
.pulse-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    animation: pulse-dr 1.5s infinite;
}
@keyframes pulse-dr {
    0%,100% { opacity: 1; transform: scale(1); }
    50%      { opacity: 0.3; transform: scale(0.8); }
}
</style>
"""


def _gauge_chart(score, color, title, min_val, max_val, threshold=None, threshold_label=""):
    """Compact gauge for forensic scores."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={'text': title, 'font': {'size': 10, 'color': '#6b7280', 'family': 'Space Grotesk'}},
        number={'font': {'size': 28, 'color': color, 'family': 'JetBrains Mono'},
                'valueformat': '.3f'},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {
                'range': [min_val, max_val],
                'tickwidth': 0.5,
                'tickcolor': '#1f2d47',
                'tickfont': {'color': '#2d3a55', 'size': 7},
                'nticks': 5,
            },
            'bar': {'color': color, 'thickness': 0.2},
            'bgcolor': '#080b14',
            'borderwidth': 0,
            'threshold': {
                'line': {'color': '#f59e0b', 'width': 2},
                'thickness': 0.75,
                'value': threshold if threshold else score,
            }
        }
    ))
    fig.update_layout(
        height=180,
        margin=dict(t=35, b=5, l=15, r=15),
        paper_bgcolor='#0d1120',
        plot_bgcolor='#0d1120',
        font=dict(color='#6b7280', family='Space Grotesk'),
        annotations=[{
            'text': threshold_label,
            'x': 0.5, 'y': -0.05,
            'xref': 'paper', 'yref': 'paper',
            'showarrow': False,
            'font': {'size': 8, 'color': '#f59e0b', 'family': 'JetBrains Mono'},
        }] if threshold_label else []
    )
    return fig


def _component_waterfall(components, title, color):
    """Waterfall-style bar chart for M-Score or Z-Score components."""
    labels = list(components.keys())
    values = [v["value"] * v["weight"] for v in components.values()]
    colors = [color if components[k]["flag"] else "#1f2d47"
              for k in labels] if "flag" in list(components.values())[0] else [color] * len(labels)

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker=dict(color=colors, line=dict(width=0)),
        hovertemplate="<b>%{x}</b><br>Weighted: %{y:.3f}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>",
                   font=dict(size=10, color='#9ca3af', family='Space Grotesk'), x=0.5),
        height=180,
        margin=dict(t=30, b=10, l=5, r=5),
        paper_bgcolor='#0d1120',
        plot_bgcolor='#0d1120',
        font=dict(color='#6b7280', family='Space Grotesk'),
        xaxis=dict(tickfont=dict(color='#4b5563', size=8, family='JetBrains Mono'), showgrid=False),
        yaxis=dict(gridcolor='rgba(26,37,64,0.4)', showticklabels=False),
        bargap=0.3,
        showlegend=False,
    )
    return fig


def _verdict_radar(score_components):
    """Radar chart of all dimension scores."""
    labels = [s[0] for s in score_components if s[2] > 0]
    values = [round(s[1] / s[2] * 10, 1) for s in score_components if s[2] > 0]
    if not labels:
        return None
    values_closed = values + [values[0]]
    labels_closed  = labels + [labels[0]]

    fig = go.Figure(go.Scatterpolar(
        r=values_closed,
        theta=labels_closed,
        fill='toself',
        fillcolor='rgba(139,92,246,0.08)',
        line=dict(color='#7c3aed', width=1.5),
        marker=dict(size=4, color='#a78bfa'),
        hovertemplate="<b>%{theta}</b><br>Score: %{r}/10<extra></extra>",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='#090e1a',
            radialaxis=dict(
                visible=True, range=[0, 10],
                gridcolor='rgba(26,37,64,0.6)',
                tickfont=dict(color='#2d3a55', size=7),
                tickvals=[2, 4, 6, 8, 10],
                linecolor='rgba(26,37,64,0.4)',
            ),
            angularaxis=dict(
                gridcolor='rgba(26,37,64,0.4)',
                tickfont=dict(color='#4b5563', size=8, family='JetBrains Mono'),
                linecolor='rgba(26,37,64,0.4)',
            ),
        ),
        height=300,
        margin=dict(t=20, b=20, l=40, r=40),
        paper_bgcolor='#0d1120',
        plot_bgcolor='#0d1120',
        showlegend=False,
    )
    return fig


def render_deep_research_tab(result):
    """
    Main renderer for the Deep Research tab.
    result = output from analyse_ticker() in app.py
    """
    st.markdown(DEEP_RESEARCH_CSS, unsafe_allow_html=True)

    ticker  = result["ticker"]
    name    = result["name"]
    sector  = result["sector"]
    mcap    = result.get("mcap_cr")
    de      = result.get("de_ratio")
    promo   = result.get("promoter_holding_pct")
    risk_sc = result.get("risk_score", 0)
    manip_sc= result.get("manip_score", 0)
    rf      = result.get("risk_flags", [])
    mf      = result.get("manip_flags", [])

    nse_sym = ticker.replace(".NS", "").replace(".BO", "")

    # ── SNAPSHOT HEADER ──────────────────────────────────────
    risk_color  = "#ef4444" if risk_sc  >= 6 else "#f59e0b" if risk_sc  >= 3 else "#22c55e"
    manip_color = "#a78bfa" if manip_sc >= 6 else "#c4b5fd" if manip_sc >= 3 else "#6ee7b7"

    st.markdown(f"""
    <div class="dr-snapshot">
      <div class="dr-badge">🔬 Deep Research Analysis</div>
      <div class="dr-company-name">{name}</div>
      <div class="dr-company-meta">
        NSE: {nse_sym} &nbsp;·&nbsp; {sector} &nbsp;·&nbsp;
        MCap: {fmt_cr(mcap)} &nbsp;·&nbsp;
        D/E: {f'{de:.2f}x' if de else '—'} &nbsp;·&nbsp;
        Promoter: {f'{promo:.1f}%' if promo else '—'}
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
          <span class="label">Flags</span>
          <span class="val" style="color:#9ca3af;">{len(rf)+len(mf)}</span>
        </div>
        <div class="dr-score-pill">
          <span class="label">Analysis Date</span>
          <span class="val" style="color:#4b5563;font-size:0.7rem;">
            {datetime.now().strftime('%d %b %Y')}
          </span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── COMPUTE FORENSIC MODELS ───────────────────────────────
    with st.spinner("⚙️ Computing Beneish M-Score and Altman Z-Score…"):
        m_result = compute_beneish_mscore(result)
        z_result = compute_altman_zscore(result, sector)

    # ════════════════════════════════════════════════════════
    #  SECTION 1 — FORENSIC MODELS
    # ════════════════════════════════════════════════════════
    st.markdown("""
    <div class="dr-section">
      <div class="dr-section-title" style="color:#a78bfa;">
        <span style="width:7px;height:7px;border-radius:50%;background:#a78bfa;display:inline-block;box-shadow:0 0 8px rgba(167,139,250,0.5);"></span>
        Forensic Risk Models
      </div>
    """, unsafe_allow_html=True)

    col_m, col_z = st.columns(2)

    # ── Beneish M-Score ───────────────────────────────────────
    with col_m:
        mc = m_result["verdict_color"]
        st.markdown(f"""
        <div class="forensic-card" style="border:1px solid rgba(167,139,250,0.15);">
          <div class="forensic-label">🟣 Beneish M-Score</div>
          <div class="forensic-score" style="color:{mc};">{m_result['score']}</div>
          <div class="forensic-verdict" style="color:{mc};background:rgba(167,139,250,0.08);border:1px solid rgba(167,139,250,0.2);">
            {m_result['verdict_icon']} {m_result['interpretation']}
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:#374151;margin-top:8px;">
            Threshold: &gt; -1.78 = likely manipulator
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.plotly_chart(
            _gauge_chart(m_result["score"], mc, "M-Score", -4, 0,
                         threshold=-1.78, threshold_label="⚠ -1.78 threshold"),
            use_container_width=True,
            config={"displayModeBar": False},
            key="gauge_mscore"
        )

        st.plotly_chart(
            _component_waterfall(m_result["components"], "Weighted component contributions", mc),
            use_container_width=True,
            config={"displayModeBar": False},
            key="bar_mscore"
        )

        # Component table
        if m_result["red_flags"]:
            st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:0.6rem;color:#ef4444;margin:8px 0 4px;text-transform:uppercase;letter-spacing:1.5px;'>🚩 {len(m_result['red_flags'])} component(s) above threshold</div>", unsafe_allow_html=True)

        rows = ""
        for k, v in m_result["components"].items():
            flag_cls = "comp-flag" if v.get("flag") else "comp-ok"
            flag_sym = "⚑" if v.get("flag") else "✓"
            rows += f"""
            <tr>
              <td class="comp-mono">{k}</td>
              <td class="comp-mono">{v['value']}</td>
              <td style="font-size:0.65rem;color:#374151;">×{v['weight']}</td>
              <td class="{flag_cls}">{flag_sym}</td>
              <td style="font-size:0.65rem;color:#374151;max-width:160px;">{v['note'][:60]}…</td>
            </tr>"""

        st.markdown(f"""
        <table class="comp-table">
          <thead><tr>
            <th>Factor</th><th>Value</th><th>Weight</th><th>Flag</th><th>Interpretation</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
        """, unsafe_allow_html=True)

        if m_result["missing"]:
            st.caption(f"⚠️ Could not compute: {', '.join(m_result['missing'])} — defaulted to neutral (1.0)")

    # ── Altman Z-Score ────────────────────────────────────────
    with col_z:
        zc = z_result["verdict_color"]
        st.markdown(f"""
        <div class="forensic-card" style="border:1px solid rgba(239,68,68,0.15);">
          <div class="forensic-label">🔴 Altman Z-Score</div>
          <div class="forensic-score" style="color:{zc};">{z_result['score']}</div>
          <div class="forensic-verdict" style="color:{zc};background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.15);">
            {z_result['verdict_icon']} {z_result['interpretation']}
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:#374151;margin-top:8px;">
            &lt;1.81 distress · 1.81–2.99 grey · &gt;2.99 safe
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.plotly_chart(
            _gauge_chart(z_result["score"], zc, "Z-Score", 0, 5,
                         threshold=1.81, threshold_label="⚠ 1.81 distress zone"),
            use_container_width=True,
            config={"displayModeBar": False},
            key="gauge_zscore"
        )

        st.plotly_chart(
            _component_waterfall(z_result["components"], "Weighted component contributions", zc),
            use_container_width=True,
            config={"displayModeBar": False},
            key="bar_zscore"
        )

        rows = ""
        for k, v in z_result["components"].items():
            val_color = "#34d399" if v["value"] > 0 else "#f87171"
            rows += f"""
            <tr>
              <td class="comp-mono">{k}</td>
              <td class="comp-mono" style="color:{val_color};">{v['value']:.4f}</td>
              <td style="font-size:0.65rem;color:#374151;">×{v['weight']}</td>
              <td style="font-size:0.65rem;color:#374151;max-width:160px;">{v['label']}</td>
            </tr>"""

        st.markdown(f"""
        <table class="comp-table">
          <thead><tr>
            <th>Factor</th><th>Value</th><th>Weight</th><th>What it measures</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
        """, unsafe_allow_html=True)

        if z_result["is_financial"]:
            st.info("ℹ️ Altman Z-Score was designed for manufacturing companies. Use with caution for banks/NBFCs — the leverage ratios work differently.", icon="ℹ️")

        if z_result["missing"]:
            st.caption(f"⚠️ Could not compute: {', '.join(z_result['missing'])} — defaulted to 0")

    st.markdown("</div>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    #  SECTION 2 — GOVERNANCE SCAN (AI-Powered)
    # ════════════════════════════════════════════════════════
    st.markdown("""
    <div class="dr-section">
      <div class="dr-section-title" style="color:#ef4444;">
        <span style="width:7px;height:7px;border-radius:50%;background:#ef4444;display:inline-block;box-shadow:0 0 8px rgba(239,68,68,0.5);"></span>
        Governance & News Intelligence
        <span style="margin-left:auto;font-size:0.55rem;color:#374151;text-transform:none;letter-spacing:0;">
          Powered by Claude + Web Search
        </span>
      </div>
    """, unsafe_allow_html=True)

    gov_key = f"gov_{ticker}"
    if gov_key not in st.session_state:
        with st.spinner("🔍 Scanning governance signals, SEBI notices, auditor changes…"):
            st.session_state[gov_key] = governance_scan(name, ticker, sector)

    gov = st.session_state[gov_key]

    # Governance score pill
    gc = "#ef4444" if gov.get("overall_risk") == "HIGH" else \
         "#f59e0b" if gov.get("overall_risk") == "MEDIUM" else \
         "#22c55e" if gov.get("overall_risk") == "LOW" else "#6b7280"

    g_score = gov.get("governance_score", 5)
    g_risk  = gov.get("overall_risk", "UNKNOWN")

    col_g1, col_g2 = st.columns([1, 2])
    with col_g1:
        st.markdown(f"""
        <div class="forensic-card" style="border:1px solid rgba(239,68,68,0.15);">
          <div class="forensic-label">Governance Risk Score</div>
          <div class="forensic-score" style="color:{gc};">{g_score}<span style="font-size:1rem;color:#374151;">/10</span></div>
          <div class="forensic-verdict" style="color:{gc};background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.15);">
            {g_risk}
          </div>
          <div style="font-size:0.68rem;color:#6b7280;margin-top:12px;line-height:1.5;">
            {gov.get('summary','')[:180]}
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_g2:
        # Render each governance category
        categories = [
            ("🚨 Auditor Issues",    "auditor_issues",  "Auditor resignation or qualification is a severe red flag"),
            ("⚖️ SEBI Actions",      "sebi_actions",    "Regulatory investigations or penalties"),
            ("👤 Board Changes",     "board_changes",   "Key executive or independent director exits"),
            ("📉 Credit Events",     "credit_events",   "Rating downgrades, defaults, covenant breaches"),
            ("🔍 Other Flags",       "other_flags",     "Fraud allegations, litigation, pledge concerns"),
        ]

        any_found = False
        for cat_label, cat_key, cat_desc in categories:
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
                    </div>
                    """, unsafe_allow_html=True)

        if not any_found:
            st.success("✅ No major governance red flags detected in the last 18 months.")

        # Positive signals
        positives = gov.get("positive_signals", [])
        if positives:
            st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:0.6rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin:12px 0 6px;'>✅ Positive Signals</div>", unsafe_allow_html=True)
            chips = "".join(f'<span class="positive-chip">✓ {p}</span>' for p in positives[:6])
            st.markdown(f"<div>{chips}</div>", unsafe_allow_html=True)

        if gov.get("sources_checked"):
            st.caption(f"Sources checked: {', '.join(gov['sources_checked'][:4])}")

    st.markdown("</div>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    #  SECTION 3 — CONCALL INTELLIGENCE
    # ════════════════════════════════════════════════════════
    st.markdown("""
    <div class="dr-section">
      <div class="dr-section-title" style="color:#60a5fa;">
        <span style="width:7px;height:7px;border-radius:50%;background:#60a5fa;display:inline-block;box-shadow:0 0 8px rgba(96,165,250,0.5);"></span>
        Concall Intelligence — Management Credibility Tracker
        <span style="margin-left:auto;font-size:0.55rem;color:#374151;text-transform:none;letter-spacing:0;">
          Last 4 quarters · Powered by Claude + Web Search
        </span>
      </div>
    """, unsafe_allow_html=True)

    cc_key = f"cc_{ticker}"
    if cc_key not in st.session_state:
        with st.spinner("📞 Analyzing last 4 earnings calls and tracking flag explanations…"):
            st.session_state[cc_key] = concall_intelligence(name, ticker, rf, mf)

    cc = st.session_state[cc_key]

    qf = cc.get("quarters_found", 0)
    cc_score = cc.get("credibility_score", 5)
    cc_cred  = cc.get("overall_credibility", "UNKNOWN")
    cc_color = "#22c55e" if cc_cred == "HIGH" else "#f59e0b" if cc_cred == "MEDIUM" else \
               "#ef4444" if cc_cred == "LOW" else "#6b7280"

    col_c1, col_c2 = st.columns([1, 2])

    with col_c1:
        st.markdown(f"""
        <div class="forensic-card" style="border:1px solid rgba(96,165,250,0.15);">
          <div class="forensic-label">Management Credibility</div>
          <div class="forensic-score" style="color:{cc_color};">{cc_score}<span style="font-size:1rem;color:#374151;">/10</span></div>
          <div class="forensic-verdict" style="color:{cc_color};background:rgba(96,165,250,0.05);border:1px solid rgba(96,165,250,0.15);">
            {cc_cred}
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.58rem;color:#374151;margin-top:8px;">
            {qf}/4 quarters found
          </div>
          <div style="font-size:0.68rem;color:#6b7280;margin-top:10px;line-height:1.5;">
            {cc.get('summary','')[:200]}
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Concerns + positives
        concerns = cc.get("key_concerns", [])
        if concerns:
            st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin:10px 0 4px;'>🔴 Key Concerns</div>", unsafe_allow_html=True)
            for c in concerns[:4]:
                st.markdown(f"<div style='font-size:0.72rem;color:#9ca3af;padding:3px 0;'>→ {c}</div>", unsafe_allow_html=True)

        cc_pos = cc.get("positive_signals", [])
        if cc_pos:
            st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin:10px 0 4px;'>✅ Positives</div>", unsafe_allow_html=True)
            for p in cc_pos[:3]:
                st.markdown(f"<div style='font-size:0.72rem;color:#4ade80;padding:3px 0;'>✓ {p}</div>", unsafe_allow_html=True)

    with col_c2:
        # Quarter cards
        quarters = cc.get("quarters_data", [])
        if quarters:
            st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:0.6rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;'>Quarterly Commentary</div>", unsafe_allow_html=True)
            for q in quarters:
                tone = q.get("management_tone", "Neutral")
                tone_cls = f"tone-{tone.replace(' ','')}"
                themes = q.get("key_themes", [])
                themes_str = " · ".join(themes[:3]) if themes else "No themes extracted"
                cred = q.get("credibility_score", 5)
                cred_c = "#22c55e" if cred >= 7 else "#f59e0b" if cred >= 4 else "#ef4444"

                st.markdown(f"""
                <div class="quarter-card">
                  <div class="quarter-header">
                    <span class="quarter-label">{q.get('quarter','?')} · {q.get('date','')}</span>
                    <div style="display:flex;align-items:center;gap:8px;">
                      <span style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:{cred_c};">
                        Credibility: {cred}/10
                      </span>
                      <span class="quarter-tone {tone_cls}">{tone}</span>
                    </div>
                  </div>
                  <div class="quarter-theme">{themes_str}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="dr-empty">📞 No quarterly concall data found. Try searching on screener.in or company IR page.</div>', unsafe_allow_html=True)

    # ── Flag tracking grid ────────────────────────────────────
    flag_tracks = cc.get("flag_tracking", [])
    if flag_tracks:
        st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:0.6rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin:1rem 0 0.7rem;border-top:1px solid #111827;padding-top:1rem;'>Red Flag → Management Explanation Tracker</div>", unsafe_allow_html=True)
        for ft in flag_tracks:
            trend = ft.get("trend", "Not Addressed")
            trend_cls = f"status-{trend.replace(' ','-')}"
            q_by_q = ft.get("q_by_q", {})
            credible = ft.get("management_credible", True)
            cred_indicator = "✓ Credible" if credible else "⚠ Questionable"
            cred_color     = "#34d399" if credible else "#f59e0b"

            q_cells = ""
            for qname in ["Q1", "Q2", "Q3", "Q4"]:
                text = q_by_q.get(qname, "—")
                q_cells += f"""
                <div class="flag-q-cell">
                  <div class="flag-q-label">{qname}</div>
                  <div class="flag-q-text">{str(text)[:80]}</div>
                </div>"""

            st.markdown(f"""
            <div class="flag-track">
              <div class="flag-track-header">
                <div class="flag-track-name">{ft.get('flag','Unknown flag')}</div>
                <div style="display:flex;align-items:center;gap:8px;">
                  <span style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:{cred_color};">{cred_indicator}</span>
                  <span class="flag-track-status {trend_cls}">{trend}</span>
                </div>
              </div>
              <div class="flag-q-grid">{q_cells}</div>
              <div class="flag-insight">💡 {ft.get('insight','')}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    #  SECTION 4 — FINAL VERDICT ENGINE
    # ════════════════════════════════════════════════════════
    gov_data = st.session_state.get(gov_key, {})
    cc_data  = st.session_state.get(cc_key, {})

    verdict = compute_final_verdict(
        risk_sc, manip_sc, m_result, z_result, gov_data, cc_data
    )

    vd_col = verdict["verdict_color"]
    vd_bg  = verdict["verdict_bg"]
    vd_bd  = verdict["verdict_border"]

    st.markdown(f"""
    <div class="verdict-card" style="background:{vd_bg};border:1px solid {vd_bd};">
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:#374151;text-transform:uppercase;letter-spacing:2.5px;margin-bottom:0.4rem;">
        Final Verdict
      </div>
      <div class="verdict-word" style="color:{vd_col};">
        {verdict['verdict_icon']} {verdict['verdict']}
      </div>
      <div class="verdict-desc">{verdict['verdict_desc']}</div>
      <div class="verdict-composite">
        Composite risk score: {verdict['composite_score']}/10
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_v1, col_v2 = st.columns([1, 1])

    with col_v1:
        # Radar chart
        radar = _verdict_radar(verdict["score_components"])
        if radar:
            st.plotly_chart(radar, use_container_width=True,
                            config={"displayModeBar": False}, key="radar_verdict")

    with col_v2:
        # Score bars
        st.markdown("<div style='padding-top:1.5rem;'>", unsafe_allow_html=True)
        for label, val, mx, color in verdict["score_components"]:
            if mx == 0:
                continue
            pct = min(100, round(val / mx * 100))
            st.markdown(f"""
            <div class="score-bar-row">
              <div class="score-bar-label">{label}</div>
              <div class="score-bar-track">
                <div class="score-bar-fill" style="width:{pct}%;background:{color};"></div>
              </div>
              <div class="score-bar-val" style="color:{color};">{val}/{mx}</div>
            </div>
            """, unsafe_allow_html=True)

        # Reasons
        if verdict["reasons"]:
            st.markdown("<div style='margin-top:1rem;'>", unsafe_allow_html=True)
            st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px;'>Risk Drivers</div>", unsafe_allow_html=True)
            items = "".join(f'<li class="neg">{r}</li>' for r in verdict["reasons"])
            st.markdown(f'<ul class="reason-list">{items}</ul>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if verdict["positives"]:
            st.markdown("<div style='margin-top:0.6rem;'>", unsafe_allow_html=True)
            st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px;'>Positive Signals</div>", unsafe_allow_html=True)
            items = "".join(f'<li class="pos">{p}</li>' for p in verdict["positives"])
            st.markdown(f'<ul class="reason-list">{items}</ul>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # ── Disclaimer ────────────────────────────────────────────
    st.markdown("""
    <div style="margin-top:1rem;padding:0.8rem 1rem;background:rgba(255,255,255,0.02);
         border:1px solid #111827;border-radius:10px;font-size:0.65rem;color:#374151;line-height:1.6;">
      ⚠️ <strong style="color:#4b5563;">Not investment advice.</strong>
      Deep Research analysis uses financial models and AI-powered web search. 
      Beneish M-Score and Altman Z-Score are <em>probabilistic</em> indicators, not definitive proof of manipulation or distress.
      Always cross-check with official BSE/NSE filings. Consult a SEBI-registered advisor before making investment decisions.
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  INTEGRATION HELPER
# ══════════════════════════════════════════════════════════════

def render_deep_research_selector(all_results):
    """
    Renders a company selector + the deep research panel.
    Call this inside `with tab_deep_research:` in app.py
    
    all_results: list of analyse_ticker() outputs from tab_search or tab_sector
    """
    if not all_results:
        st.markdown("""
        <div style="text-align:center;padding:3rem 1rem;color:#374151;">
          <div style="font-size:2rem;margin-bottom:1rem;">🔬</div>
          <div style="font-size:0.9rem;color:#4b5563;margin-bottom:0.4rem;">No companies analysed yet</div>
          <div style="font-size:0.75rem;color:#2d3a55;">
            Go to the <strong style="color:#4b5563;">Search & Analyse</strong> tab,
            analyse one or more companies, then return here for Deep Research.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Company selector
    company_options = {
        f"{r['name']} ({r['ticker'].replace('.NS','')}) — Risk: {r['risk_score']}/10": r
        for r in all_results
    }

    st.markdown('<div class="search-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">Select company for deep research</div>', unsafe_allow_html=True)
    selected_label = st.selectbox(
        "Company",
        options=list(company_options.keys()),
        label_visibility="collapsed"
    )
    st.markdown('</div>', unsafe_allow_html=True)

    selected_result = company_options[selected_label]

    # Refresh button
    col_btn, col_note = st.columns([1, 3])
    with col_btn:
        run_btn = st.button("🔬 Run Deep Research →", type="primary",
                            key="dr_run_btn")
    with col_note:
        st.caption("This runs Beneish M-Score, Altman Z-Score, AI governance scan, and concall intelligence. Takes ~30–60 seconds.")

    # Auto-run or button-triggered
    dr_key = f"dr_done_{selected_result['ticker']}"
    if run_btn or dr_key in st.session_state:
        st.session_state[dr_key] = True
        render_deep_research_tab(selected_result)
