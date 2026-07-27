def run_all_checks(data):
    risk_flags  = []
    manip_flags = []

    def _last(s):
        if s is None or s.empty: return None
        s2 = s.dropna(); return float(s2.iloc[-1]) if not s2.empty else None
    def _avg(s, n=3):
        if s is None or s.empty: return None
        s2 = s.dropna().iloc[-n:]; return float(s2.mean()) if not s2.empty else None
    def _cagr(s, y=3):
        if s is None: return None
        s2 = s.dropna()
        if len(s2) < 2: return None
        yr = min(y, len(s2)-1); a, b = float(s2.iloc[0]), float(s2.iloc[-1])
        if a <= 0 or b <= 0 or yr == 0: return None
        return (b/a)**(1/yr) - 1

    pnl = data.get("pnl", {})
    bs  = data.get("bs",  {})
    cf  = data.get("cf",  {})

    ebit   = pnl.get("operating_profit")
    intexp = pnl.get("interest_exp")
    if ebit is not None and intexp is not None:
        e = _last(ebit); i = abs(_last(intexp)) if _last(intexp) else None
        if e is not None and i and i != 0:
            icr = e / i
            ev  = [{"panel":"PL","label":"Operating Profit","series":ebit,"highlight":"neutral"},
                   {"panel":"PL","label":"Interest Expense","series":intexp,"highlight":"increase"}]
            if icr < 1.5:
                risk_flags.append(("RISK","HIGH",f"Dangerously low interest coverage ({icr:.1f}x)",
                    f"Operating profit covers interest only {icr:.1f}x. Below 1.5x is danger zone.", ev))
            elif icr < 2.5:
                risk_flags.append(("RISK","MEDIUM",f"Weak interest coverage ({icr:.1f}x)",
                    f"Coverage of {icr:.1f}x is below comfortable 3x+ threshold.", ev))

    de     = data.get("de_ratio")
    sector = data.get("sector", "")
    if de is not None and "financial" not in sector.lower() and "bank" not in sector.lower():
        debt   = bs.get("total_debt"); equity = bs.get("equity")
        ev = [{"panel":"BS","label":"Total Debt","series":debt,"highlight":"increase"},
              {"panel":"BS","label":"Shareholders Equity","series":equity,"highlight":"decrease"}]
        if de > 2.0:
            risk_flags.append(("RISK","HIGH",f"Very high Debt/Equity ({de:.1f}x)",
                f"D/E of {de:.1f}x is well above safe levels (<1x for non-financials).", ev))
        elif de > 1.0:
            risk_flags.append(("RISK","MEDIUM",f"Elevated Debt/Equity ({de:.1f}x)",
                f"D/E of {de:.1f}x above 1x. Combine with interest coverage for full picture.", ev))

    pat = pnl.get("net_profit")
    if pat is not None:
        s = pat.dropna(); loss_years = int((s < 0).sum())
        ev = [{"panel":"PL","label":"Net Profit","series":pat,"highlight":"decrease"}]
        if loss_years >= 3:
            risk_flags.append(("RISK","HIGH",f"Loss-making in {loss_years} of {len(s)} years",
                "Sustained losses ΓÇö check if unit economics are at least improving YoY.", ev))
        elif loss_years >= 1:
            risk_flags.append(("RISK","MEDIUM",f"Net loss in {loss_years} recent year(s)",
                "Check if one-off or structural. Look at EBITDA to separate operating health.", ev))

    rev = pnl.get("revenue")
    if rev is not None:
        rg = _cagr(rev, 3)
        ev = [{"panel":"PL","label":"Revenue","series":rev,"highlight":"decrease"}]
        if rg is not None and rg < -0.05:
            risk_flags.append(("RISK","MEDIUM",f"Revenue declining (3Y CAGR: {rg:.1%})",
                f"Revenue falling at {abs(rg):.1%} per year.", ev))

    debt = bs.get("total_debt"); cfo = cf.get("cfo")
    if debt is not None and cfo is not None:
        d, c = debt.dropna(), cfo.dropna()
        if len(d) >= 3 and len(c) >= 3:
            ev = [{"panel":"BS","label":"Total Debt","series":debt,"highlight":"increase"},
                  {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"decrease"}]
            if float(d.iloc[-1]) > float(d.iloc[0])*1.35 and float(c.iloc[-1]) < float(c.iloc[0])*0.75:
                risk_flags.append(("RISK","HIGH","Debt up 35%+ while CFO dropped 25%+",
                    "Borrowing significantly more while generating less operating cash.", ev))

    ph = data.get("promoter_holding_pct", 0)
    if ph and ph < 25:
        risk_flags.append(("RISK","LOW",f"Low promoter / insider holding ({ph:.1f}%)",
            f"Promoters hold only {ph:.1f}%. Watch for any further quarterly decline.", []))

    inv = bs.get("inventory")
    if inv is not None and rev is not None:
        ig = _cagr(inv, 3); rg2 = _cagr(rev, 3)
        if ig is not None and rg2 is not None and ig - rg2 > 0.15:
            ev = [{"panel":"PL","label":"Revenue","series":rev,"highlight":"neutral"},
                  {"panel":"BS","label":"Inventory","series":inv,"highlight":"increase"}]
            risk_flags.append(("RISK","MEDIUM",f"Inventory growing faster than revenue (gap: {ig-rg2:.0%})",
                f"Inventory 3Y CAGR: {ig:.0%} vs Revenue 3Y CAGR: {rg2:.0%}.", ev))

    if cfo is not None and ebit is not None:
        ac, ae = _avg(cfo, 3), _avg(ebit, 3)
        if ac is not None and ae and ae != 0:
            r = ac / ae
            ev = [{"panel":"PL","label":"Operating Profit","series":ebit,"highlight":"neutral"},
                  {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"decrease"}]
            if r < 0.6:
                manip_flags.append(("MANIP","HIGH","CFO significantly below Operating Income",
                    f"3-yr avg CFO is only {r:.0%} of EBIT.", ev))
            elif r < 0.85:
                manip_flags.append(("MANIP","MEDIUM",f"CFO below Operating Income ({r:.0%} ratio)",
                    f"CFO covers only {r:.0%} of reported operating profit (3yr avg).", ev))

    if cfo is not None and pat is not None:
        ac, ap = _avg(cfo, 3), _avg(pat, 3)
        if ac is not None and ap and ap != 0:
            r = ac / ap
            ev = [{"panel":"PL","label":"Net Profit","series":pat,"highlight":"neutral"},
                  {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"decrease"}]
            if r < 0.7:
                manip_flags.append(("MANIP","HIGH","Low CFO / Net Profit ratio ΓÇö earnings quality concern",
                    f"3-year avg CFO is only {r:.0%} of reported profit.", ev))
            elif r < 0.85:
                manip_flags.append(("MANIP","MEDIUM",f"Below-average CFO / Net Profit ratio ({r:.0%})",
                    f"CFO is {r:.0%} of net profit (3yr avg).", ev))

    if cfo is not None and pat is not None:
        neg_cfo = int((cfo.dropna() < 0).sum()); pos_pat = int((pat.dropna() > 0).sum())
        if neg_cfo >= 2 and pos_pat >= 3:
            ev = [{"panel":"PL","label":"Net Profit","series":pat,"highlight":"neutral"},
                  {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"decrease"}]
            manip_flags.append(("MANIP","HIGH",f"Negative CFO in {neg_cfo} years despite reported profits",
                f"Reported profits in {pos_pat} years but negative CFO in {neg_cfo} years.", ev))

    rec = bs.get("receivables")
    if rev is not None and rec is not None:
        rg3, recg = _cagr(rev, 3), _cagr(rec, 3)
        if rg3 is not None and recg is not None:
            gap = recg - rg3
            ev  = [{"panel":"PL","label":"Revenue","series":rev,"highlight":"neutral"},
                   {"panel":"BS","label":"Receivables","series":rec,"highlight":"increase"}]
            if gap > 0.15:
                manip_flags.append(("MANIP","HIGH","Receivables growing much faster than revenue",
                    f"Revenue 3Y CAGR: {rg3:.0%} | Receivables 3Y CAGR: {recg:.0%} ΓÇö gap of {gap:.0%}.", ev))
            elif gap > 0.08:
                manip_flags.append(("MANIP","MEDIUM","Receivables growing faster than revenue",
                    f"Revenue CAGR: {rg3:.0%} | Receivables CAGR: {recg:.0%} ΓÇö gap of {gap:.0%}.", ev))

    reported_growth = data.get("revenue_growth_pct")
    if rev is not None:
        rg4 = _cagr(rev, 3)
        ev  = [{"panel":"PL","label":"Revenue","series":rev,"highlight":"neutral"}]
        if reported_growth is not None and rg4 is not None:
            if reported_growth > 0.35 and rg4 < 0.10:
                manip_flags.append(("MANIP","MEDIUM","Revenue growth spike vs historical trend",
                    f"Latest YoY growth ({reported_growth:.0%}) far above 3-year CAGR ({rg4:.0%}).", ev))
        elif reported_growth is not None and reported_growth > 0.40:
            manip_flags.append(("MANIP","LOW","Very high revenue growth ΓÇö verify quality",
                f"Revenue growth of {reported_growth:.0%} YoY warrants scrutiny.", ev))

    q4_pct = data.get("q4_revenue_pct")
    if q4_pct is not None:
        if q4_pct > 0.40:
            manip_flags.append(("MANIP","HIGH",f"Q4 revenue concentration very high ({q4_pct:.0%} of annual)",
                f"Final quarter accounts for {q4_pct:.0%} of annual revenue.", []))
        elif q4_pct > 0.32:
            manip_flags.append(("MANIP","MEDIUM",f"Q4 revenue concentration elevated ({q4_pct:.0%} of annual)",
                f"Q4 contributes {q4_pct:.0%} of annual revenue (>32% threshold).", []))

    if rev is not None and ebit is not None:
        rev_s  = rev.dropna().sort_index(); ebit_s = ebit.dropna().sort_index()
        common = rev_s.index.intersection(ebit_s.index)
        if len(common) >= 3:
            margins = (ebit_s[common] / rev_s[common]).dropna()
            if len(margins) >= 3:
                latest_margin = float(margins.iloc[-1]); prior_avg = float(margins.iloc[:-1].mean())
                jump = latest_margin - prior_avg
                ev   = [{"panel":"PL","label":"Operating Profit","series":ebit,"highlight":"neutral"},
                        {"panel":"PL","label":"Revenue","series":rev,"highlight":"neutral"}]
                if jump > 0.08 and prior_avg < 0.15:
                    manip_flags.append(("MANIP","HIGH",
                        f"Unexplained operating margin surge (+{jump:.0%} vs prior avg {prior_avg:.0%})",
                        f"Operating margin jumped {jump:.0%} in latest year to {latest_margin:.0%}.", ev))
                elif jump > 0.05:
                    manip_flags.append(("MANIP","MEDIUM",
                        f"Sharp operating margin improvement (+{jump:.0%})",
                        f"Margin expanded {jump:.0%} in one year (to {latest_margin:.0%}).", ev))

    pay = bs.get("payables"); inv2 = bs.get("inventory")
    if pay is not None and inv2 is not None and cfo is not None:
        pay_s = pay.dropna().sort_index(); inv_s = inv2.dropna().sort_index(); cfo_s = cfo.dropna().sort_index()
        if len(pay_s) >= 2 and len(inv_s) >= 2 and len(cfo_s) >= 2:
            pay_up = float(pay_s.iloc[-1]) > float(pay_s.iloc[-2]) * 1.10
            inv_dn = float(inv_s.iloc[-1]) < float(inv_s.iloc[-2]) * 0.95
            cfo_up = float(cfo_s.iloc[-1]) > float(cfo_s.iloc[-2]) * 1.15
            ev_list = [{"panel":"BS","label":"Payables","series":pay,"highlight":"increase"},
                       {"panel":"BS","label":"Inventory","series":inv2,"highlight":"decrease"},
                       {"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"neutral"}]
            rec_dn = False
            if rec is not None:
                rec_s2 = rec.dropna().sort_index()
                if len(rec_s2) >= 2:
                    rec_dn = float(rec_s2.iloc[-1]) < float(rec_s2.iloc[-2]) * 0.95
                    ev_list.append({"panel":"BS","label":"Receivables","series":rec,"highlight":"decrease"})
            if pay_up and (inv_dn or rec_dn) and cfo_up:
                manip_flags.append(("MANIP","HIGH","Working capital manipulation pattern detected",
                    "Payables rising 10%+ while inventory/receivables shrink with sudden CFO boost.", ev_list))

    ta = bs.get("total_assets")
    gw = bs.get("goodwill")
    if gw is not None and ta is not None:
        gw_l = _last(gw); ta_l = _last(ta)
        if gw_l is not None and ta_l and ta_l != 0:
            ratio = gw_l / ta_l
            ev    = [{"panel":"BS","label":"Goodwill","series":gw,"highlight":"increase"},
                     {"panel":"BS","label":"Total Assets","series":ta,"highlight":"neutral"}]
            if ratio > 0.30:
                manip_flags.append(("MANIP","HIGH",f"Very high goodwill relative to assets ({ratio:.0%})",
                    f"Goodwill represents {ratio:.0%} of total assets.", ev))
            elif ratio > 0.15:
                manip_flags.append(("MANIP","MEDIUM",f"Elevated goodwill-to-assets ratio ({ratio:.0%})",
                    f"Goodwill is {ratio:.0%} of total assets.", ev))

    dt = bs.get("deferred_tax")
    if dt is not None:
        s = dt.dropna().sort_index()
        if len(s) >= 3:
            changes = s.diff().dropna().abs()
            avg_ta  = _last(ta) or 1
            large_swings = int((changes > avg_ta * 0.03).sum())
            ev = [{"panel":"BS","label":"Deferred Tax","series":dt,"highlight":"neutral"}]
            if large_swings >= 2:
                manip_flags.append(("MANIP","MEDIUM","Large recurring deferred tax fluctuations",
                    f"Deferred tax swung by >3% of total assets in {large_swings} years.", ev))

    capex = cf.get("capex")
    if cfo is not None and capex is not None:
        ac2  = _avg(cfo, 3)
        acap = _avg(capex.abs() if hasattr(capex, 'abs') else capex, 3)
        if ac2 is not None and acap is not None and ac2 > 0:
            ratio2 = acap / ac2
            ev     = [{"panel":"CF","label":"Operating CF (CFO)","series":cfo,"highlight":"neutral"},
                      {"panel":"CF","label":"CapEx","series":capex,"highlight":"increase"}]
            if ratio2 > 1.2:
                manip_flags.append(("MANIP","MEDIUM",
                    f"CapEx exceeds CFO ({ratio2:.1f}x) ΓÇö possible expense capitalisation",
                    f"3-yr avg CapEx is {ratio2:.1f}x operating cash flow.", ev))

    sev_pts = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
    risk_score  = min(sum(sev_pts.get(f[1], 0) for f in risk_flags),  10)
    manip_score = min(sum(sev_pts.get(f[1], 0) for f in manip_flags), 10)
    return risk_flags, manip_flags, risk_score, manip_score
