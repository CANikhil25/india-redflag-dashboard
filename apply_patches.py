#!/usr/bin/env python3
"""
apply_patches.py
================
Run this script once in your project folder to apply all 5 improvements
to app.py and replace deep_research_tab.py with the updated version.

Usage:
    python apply_patches.py

What it does:
    1. Ticker strip: 35s → 60s animation (slower, readable)
    2. Ticker strip: font 0.65rem → 0.84rem, brighter colour
    3. About section: title colour from invisible (#1e2a40) to visible (#4b6080)
    4. About section: body colour from #2d3a55 to #6b82a0 (much more readable)
    5. Tool tour: injects CSS + render_tool_tour() function + call on landing page
"""

import re
import sys
import shutil
from pathlib import Path

APP_PY   = Path("app.py")
BACKUP   = Path("app.py.bak")

if not APP_PY.exists():
    print("❌ app.py not found. Run this script from your project root directory.")
    sys.exit(1)

# Backup
shutil.copy(APP_PY, BACKUP)
print(f"✅ Backup created: {BACKUP}")

src = APP_PY.read_text(encoding="utf-8")
original_len = len(src)


# ─────────────────────────────────────────────────────────────
# PATCH 1 — Ticker animation speed: 35s → 60s
# ─────────────────────────────────────────────────────────────
if "tickerScroll 35s linear infinite" in src:
    src = src.replace(
        "animation: tickerScroll 35s linear infinite;",
        "animation: tickerScroll 60s linear infinite;"
    )
    print("✅ PATCH 1 applied: Ticker animation slowed to 60s")
else:
    print("⚠️  PATCH 1 skipped: 'tickerScroll 35s' not found (may already be patched)")

# Also fix the .ticker-track inline style override if present
src = src.replace(
    "animation: tickerScroll 35s linear infinite !important",
    "animation: tickerScroll 60s linear infinite !important"
)


# ─────────────────────────────────────────────────────────────
# PATCH 2 — Ticker item font size + colour
# ─────────────────────────────────────────────────────────────
old_ticker_item = """\
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #1e2a40;
    text-transform: uppercase;
    letter-spacing: 2px;
    display: inline-flex;
    align-items: center;
    gap: 8px;"""

new_ticker_item = """\
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.84rem;
    color: #3a5478;
    text-transform: uppercase;
    letter-spacing: 2px;
    display: inline-flex;
    align-items: center;
    gap: 8px;"""

if old_ticker_item in src:
    src = src.replace(old_ticker_item, new_ticker_item)
    print("✅ PATCH 2 applied: Ticker font size → 0.84rem, colour → #3a5478")
else:
    print("⚠️  PATCH 2 skipped: ticker-item CSS block not found verbatim (check manually)")


# ─────────────────────────────────────────────────────────────
# PATCH 3 — About section title: invisible → visible
# ─────────────────────────────────────────────────────────────
old_about_title = """\
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #1e2a40;
    text-transform: uppercase;
    letter-spacing: 2.5px;
    margin-bottom: 0.9rem;
    padding-bottom: 0.7rem;
    border-bottom: 1px solid #0a1020;"""

new_about_title = """\
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #4b6080;
    text-transform: uppercase;
    letter-spacing: 2.5px;
    margin-bottom: 0.9rem;
    padding-bottom: 0.7rem;
    border-bottom: 1px solid #1a2840;"""

if old_about_title in src:
    src = src.replace(old_about_title, new_about_title)
    print("✅ PATCH 3 applied: About title colour → #4b6080 (visible)")
else:
    print("⚠️  PATCH 3 skipped: .about-col-title CSS block not found verbatim")


# ─────────────────────────────────────────────────────────────
# PATCH 4 — About section body: nearly invisible → readable
# ─────────────────────────────────────────────────────────────
old_about_body = """\
.about-col-body {
    font-size: 0.88rem;
    color: #2d3a55;
    line-height: 1.85;
    font-weight: 300;
}"""

new_about_body = """\
.about-col-body {
    font-size: 0.88rem;
    color: #6b82a0;
    line-height: 1.85;
    font-weight: 300;
}"""

if old_about_body in src:
    src = src.replace(old_about_body, new_about_body)
    print("✅ PATCH 4 applied: About body colour → #6b82a0 (readable)")
else:
    print("⚠️  PATCH 4 skipped: .about-col-body CSS block not found verbatim")


# ─────────────────────────────────────────────────────────────
# PATCH 5 — Tool Tour: inject CSS, function, and call site
# ─────────────────────────────────────────────────────────────

TOUR_CSS = """
/* ═══════════════════════════════════════════════════════════
   TOOL TOUR OVERLAY
   ═══════════════════════════════════════════════════════════ */
.tour-overlay {
    position: fixed;
    inset: 0;
    background: rgba(4,6,12,0.93);
    backdrop-filter: blur(10px);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
}
.tour-card {
    background: #070c18;
    border: 1px solid #1c2640;
    border-radius: 24px;
    padding: 2.8rem 3rem;
    max-width: 680px;
    width: 90%;
    box-shadow: 0 40px 100px rgba(0,0,0,0.7), 0 0 0 1px rgba(220,38,38,0.08);
    animation: morphDropIn 0.5s cubic-bezier(0.22,1,0.36,1) both;
}
.tour-logo {
    font-family: 'DM Serif Display', serif;
    font-size: 1.1rem;
    color: #f0f2f8;
}
.tour-logo span { color: #ef4444; font-style: italic; }
.tour-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: #1c2640;
    background: #0d1726;
    padding: 5px 14px;
    border-radius: 20px;
    border: 1px solid #1c2640;
    letter-spacing: 2px;
}
.tour-heading {
    font-family: 'DM Serif Display', serif;
    font-size: 2rem;
    color: #f0f2f8;
    letter-spacing: -0.5px;
    line-height: 1.2;
    margin: 1.2rem 0 0.6rem;
}
.tour-heading .accent { color: #ef4444; font-style: italic; }
.tour-body {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    color: #5a6e8c;
    line-height: 1.8;
    margin-bottom: 1.8rem;
}
.tour-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 2rem;
}
.tour-feat {
    background: #0d1120;
    border: 1px solid #1a2540;
    border-radius: 14px;
    padding: 1rem 1.1rem;
    display: flex;
    gap: 12px;
    align-items: flex-start;
}
.tour-feat-icon {
    width: 34px; height: 34px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem; flex-shrink: 0;
}
.tour-feat-icon.red    { background: rgba(220,38,38,0.12); }
.tour-feat-icon.purple { background: rgba(139,92,246,0.12); }
.tour-feat-icon.blue   { background: rgba(59,130,246,0.12); }
.tour-feat-icon.amber  { background: rgba(245,158,11,0.12); }
.tour-feat-title {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.82rem; font-weight: 600; color: #c0cedf; margin-bottom: 3px;
}
.tour-feat-desc {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.72rem; color: #3d5070; line-height: 1.5;
}
.tour-tip {
    background: rgba(220,38,38,0.05);
    border: 1px solid rgba(220,38,38,0.15);
    border-radius: 10px;
    padding: 0.75rem 1rem;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.78rem; color: #4b6080;
    margin-bottom: 1.6rem; line-height: 1.6;
}
.tour-tip strong { color: #ef4444; }
"""

TOUR_FUNCTION = '''

# ══════════════════════════════════════════════════════════════
#  TOOL TOUR  — First-time user onboarding overlay
# ══════════════════════════════════════════════════════════════

def render_tool_tour():
    """First-time user overlay. Dismissed via \'tour_dismissed\' session key."""
    if st.session_state.get("tour_dismissed"):
        return
    st.markdown("""
    <div class="tour-overlay">
      <div class="tour-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.4rem;">
          <div class="tour-logo">Financial <span>Shenanigans</span></div>
          <div class="tour-pill">QUICK TOUR</div>
        </div>
        <div class="tour-heading">Welcome to your<br><span class="accent">forensic toolkit.</span></div>
        <div class="tour-body">
          Three tools, one mission — spot accounting tricks before they become headlines.
          Here\'s what each module does:
        </div>
        <div class="tour-grid">
          <div class="tour-feat">
            <div class="tour-feat-icon red">🔍</div>
            <div>
              <div class="tour-feat-title">Research &amp; Analysis</div>
              <div class="tour-feat-desc">Search any NSE company. Run 7 risk checks + 11 manipulation signal detectors. Compare side-by-side.</div>
            </div>
          </div>
          <div class="tour-feat">
            <div class="tour-feat-icon purple">📊</div>
            <div>
              <div class="tour-feat-title">Sector Scanner</div>
              <div class="tour-feat-desc">Scan an entire sector at once. Ranked heatmap shows where risk is concentrated across peers.</div>
            </div>
          </div>
          <div class="tour-feat">
            <div class="tour-feat-icon blue">🔬</div>
            <div>
              <div class="tour-feat-title">Deep Research</div>
              <div class="tour-feat-desc">AI-powered dive: Beneish M-Score, Altman Z-Score, governance scan &amp; concall credibility tracking.</div>
            </div>
          </div>
          <div class="tour-feat">
            <div class="tour-feat-icon amber">💡</div>
            <div>
              <div class="tour-feat-title">Not sure what a score means?</div>
              <div class="tour-feat-desc">In Deep Research, tap the ℹ️ "What are these scores?" tab for plain-English explanations of every model.</div>
            </div>
          </div>
        </div>
        <div class="tour-tip">
          <strong>Tip:</strong> Start with <em>Research &amp; Analysis</em> — type any company name or NSE ticker.
          Then use <em>Deep Research</em> for a full AI forensic deep dive.
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    col_dismiss, _ = st.columns([1.5, 3])
    with col_dismiss:
        if st.button("✓  Got it — Start Exploring", type="primary", key="tour_dismiss_btn"):
            st.session_state["tour_dismissed"] = True
            st.rerun()

'''

# Inject CSS into the st.markdown styles block
# Find the end of the styles block (before </style>)
if "TOOL TOUR" not in src:
    css_marker = "hr { border-color: #111827 !important; }"
    if css_marker in src:
        src = src.replace(css_marker, TOUR_CSS + "\n" + css_marker)
        print("✅ PATCH 5a applied: Tool tour CSS injected")
    else:
        print("⚠️  PATCH 5a skipped: CSS injection marker not found")

    # Inject the function before def render_about()
    func_marker = "def render_about():"
    if func_marker in src:
        src = src.replace(func_marker, TOUR_FUNCTION + func_marker)
        print("✅ PATCH 5b applied: render_tool_tour() function injected")
    else:
        print("⚠️  PATCH 5b skipped: render_about() not found as insertion point")

    # Call the tour at the top of the landing page block
    landing_marker = "    st.markdown(\"\"\"\n    <div class=\"hero-eyebrow\">"
    if landing_marker in src:
        src = src.replace(
            landing_marker,
            "    render_tool_tour()  # ← First-time user tour\n\n" + landing_marker
        )
        print("✅ PATCH 5c applied: render_tool_tour() called on landing page")
    else:
        print("⚠️  PATCH 5c skipped: Landing page marker not found (call render_tool_tour() manually)")
else:
    print("⚠️  PATCH 5 skipped: Tool tour already present in app.py")


# ─────────────────────────────────────────────────────────────
# Write patched file
# ─────────────────────────────────────────────────────────────
APP_PY.write_text(src, encoding="utf-8")
new_len = len(src)
print(f"\n✅ app.py patched successfully ({original_len:,} → {new_len:,} chars)")
print(f"   Backup saved to: {BACKUP}")
print("\nNext step: Replace deep_research_tab.py with the provided deep_research_tab.py")
print("           (it includes the ℹ️ info tab and the 'Search Another Company' bug fix)")
