"""
Generates the Growth Action Plan and the Metric Definitions document.

Both were hand-written for the first brand. Generating them means every brand
gets the same rigour without manual work, and the wording stays consistent with
whatever the data actually says.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

from sqp_actions import NOW, SOON, YEAR, build_actions
from sqp_lib import BRAND, TOTAL, aggregate, money, pretty_segment

OUT = os.environ.get("SQP_OUTPUT_DIR") or os.path.join(os.getcwd(), "outputs")


def brand_out(cfg) -> str:
    """One folder per brand, so runs never contaminate each other."""
    d = os.path.join(OUT, cfg.name)
    os.makedirs(d, exist_ok=True)
    return d

HORIZON_ORDER = [NOW, SOON, YEAR]


def _horizon_note(n_periods: int) -> tuple[str, list[str]]:
    """What this many periods of history does and does not support."""
    if n_periods < 3:
        return ("single snapshot", [
            "With one month of data there is **no direction of travel**. A 9% share could be up "
            "from 5% or down from 16% and nothing here can tell you which.",
            "No seasonality context, so a category that looks big may simply be in season.",
            "No stability estimate, so a number that has been steady all year looks identical to "
            "one that swings wildly.",
            "Add two more months to unlock movement, terms lost, and export integrity checks."])
    if n_periods < 12:
        return (f"{n_periods} months", [
            "Enough for direction of travel and for spotting terms that disappeared, but **not "
            "enough to separate a trend from a season**.",
            "Category-level movement is testable. Individual search terms are not.",
            f"Add {12 - n_periods} more month{'s' if 12 - n_periods != 1 else ''} to unlock "
            f"seasonality, lifecycle and the market-versus-share growth split."])
    if n_periods < 13:
        return ("12 months", [
            "A full seasonal cycle, so seasonality can be described but **not yet validated**: "
            "one cycle cannot confirm a pattern repeats.",
            "Year-over-year needs 13 months. One more export unlocks it."])
    return (f"{n_periods} months", [
        "Enough for year-over-year on the same calendar month, which removes seasonality by "
        "construction and is the cleanest comparison available.",
        "The seasonal pattern remains provisional until a second full year confirms it."])


def growth_plan(res: dict) -> str:
    cfg, mp = res["cfg"], res["cfg"].mp
    sym = mp.report_symbol or mp.symbol
    periods, latest = res["periods"], res["latest"]
    lift, yoy, tmove = res["lift"], res["yoy"], res["theme_moves"]
    topp, sqp = res["theme_opp"], res["sqp"]
    actions = build_actions(res)
    L, A = [], None
    A = L.append

    label, caveats = _horizon_note(len(periods))
    scope = (", ".join(pretty_segment(x) for x in cfg.relevance.in_scope)
             if cfg.relevance else "all searches")

    A(f"# {cfg.name} Growth Action Plan")
    A(f"**Source:** {len(periods)} months of Amazon Brand Analytics "
      f"({periods[0]} to {latest}), {mp.code}")
    A(f"**Scope:** {scope} search demand. Out-of-range and generic terms excluded as "
      f"structurally unwinnable.")
    A("**Unfamiliar terms:** see the Definitions document, or tab `01 Definitions` in the workbook.\n")
    A("> **All impact is stated in additional orders per month, not money.** Contribution margin "
      "varies too much between products for a profit figure to mean anything precise, and few "
      "sellers know it at ASIN level. Orders are directly observed and comparable across "
      "marketplaces, so apply your own economics. These are purchase *actions*: one order of "
      "three bottles counts once.\n")
    A("---\n")

    # ---- verdict ----
    A("## The verdict\n")
    verdict = []
    if len(res["coverage"]):
        c = res["coverage"]
        verdict.append(
            f"Search revenue moved from {money(c.scp_sales.iloc[0], mp)} to "
            f"{money(c.scp_sales.iloc[-1], mp)} a month "
            f"({100*(c.scp_sales.iloc[-1]/c.scp_sales.iloc[0]-1):+.0f}%).")
    if len(yoy):
        me, se = yoy.market_effect.sum(), yoy.share_effect.sum()
        dpp = yoy.share_delta_pp.iloc[-1]
        if me > 0 and se > 0:
            mkt = 100 * me / (me + se)
            verdict.append(
                f"**About {mkt:.0f}% of growth was the category expanding and {100-mkt:.0f}% was "
                f"share we actually took**, with a real share move of {dpp:+.2f}pp year over year.")
        elif abs(se) < 25 and abs(me) < 25:
            verdict.append(
                f"**The numbers are too small to attribute.** Share moved {dpp:+.2f}pp year over "
                f"year, but on volumes this low that is a handful of orders and could be chance. "
                f"Treat the growth split as unmeasurable until the base is bigger.")
        elif me <= 0 and se > 0:
            verdict.append(
                f"**All of the growth was earned, not given.** The category actually shrank over "
                f"the year, and we grew anyway by taking {dpp:+.2f}pp of share. That is the "
                f"strongest possible read, though it also means the category is not doing us "
                f"any favours.")
        elif se <= 0 and me > 0:
            verdict.append(
                f"**None of the growth was earned.** The category expanded and we lost "
                f"{abs(dpp):.2f}pp of share into it, so absolute numbers rose while our position "
                f"weakened.")
        else:
            verdict.append(
                f"**Both the category and our share moved against us**, with share down "
                f"{abs(dpp):.2f}pp year over year.")
    elif len(lift):
        f, l = lift.iloc[0], lift.iloc[-1]
        verdict.append(f"Purchase share moved from {f.PS:.2f}% to {l.PS:.2f}% while the market "
                       f"grew {100*(l.TP/f.TP-1):+.0f}%.")
    for a in actions[:3]:
        if a.evidence:
            verdict.append(f"**{a.title}.** {a.evidence[0]}")
    for i, v in enumerate(verdict, 1):
        A(f"{i}. {v}")

    quant = [a for a in actions if not a.unquantified]
    total = sum(a.orders for a in quant)
    base = float(sqp[sqp.period == latest][BRAND["Purchases"]].sum())
    if total and base > 0:
        A(f"\n**Total identified opportunity: {total:,.0f} to {total*1.3:,.0f} additional orders "
          f"per month**, against a current {base:,.0f}. That is a "
          f"{100*total/base:.0f} to {100*total*1.3/base:.0f} percent lift on search-driven orders.\n")
    elif total:
        A(f"\n**Total identified opportunity: {total:,.0f} to {total*1.3:,.0f} additional orders "
          f"per month.** There are no search-driven orders in the current period to compare "
          f"against, so this cannot be stated as a percentage lift.\n")
    else:
        A("\n**No opportunity could be sized from this data.** Either the brand has too little "
          "measurable presence, or the export lacks the columns needed to size one. The findings "
          "below are qualitative and should be read as direction, not as a forecast.\n")

    # ---- priority table ----
    A("---\n")
    A("## Priority list\n")
    A("Ranked by expected additional orders per unit of effort, discounted by how long each takes "
      "to land. Effort runs 1 (a settings change) to 13 (new product development).\n")
    A("| # | Action | Extra orders/month | Effort | Time to land | Window |")
    A("|---|---|---|---|---|---|")
    for i, a in enumerate(actions, 1):
        prob, weeks, effort = a.spec
        if a.critical:
            orders = "**Do this first**"
        elif a.defends:
            orders = f"Defends {a.defends:,.0f}"
        elif a.unquantified and a.lever == "PPC negative":
            orders = "Frees budget"
        elif a.unquantified:
            orders = "Not sizeable"
        else:
            orders = f"**{a.orders:,.0f}**"
        wk = f"{round(weeks):.0f} week" + ("s" if round(weeks) != 1 else "")
        A(f"| {i} | {a.title} | {orders} | {effort} | {wk} | {a.horizon} |")

    # ---- by window ----
    for h in HORIZON_ORDER:
        block = [a for a in actions if a.horizon == h]
        if not block:
            continue
        sub = sum(a.orders for a in block if not a.unquantified)
        A(f"\n---\n\n## {h}\n")
        if sub:
            A(f"{len(block)} action{'s' if len(block) > 1 else ''}, together worth roughly "
              f"**{sub:,.0f} additional orders a month**.\n")
        for a in block:
            head = f"### {a.title}"
            if not a.unquantified:
                head += f"  →  +{a.orders:,.0f} orders/month"
            A(head + "\n")
            A("**What the data says.**\n")
            for e in a.evidence:
                A(f"- {e}")
            A(f"\n**Do this.** {a.do}\n")
            if a.caution:
                A(f"**Worth knowing.** {a.caution}\n")

    # ---- not doing ----
    A("\n---\n\n## What we are deliberately not doing\n")
    A("Each of these looks attractive in a naive ranking and each would waste money.\n")
    A("| Not doing | Why |")
    A("|---|---|")
    cur = sqp[sqp.period == latest]
    oos = cur[~cur["in_scope"] & (cur.query_type == "UNBRANDED")]
    if len(oos):
        A(f"| Chasing out-of-range and generic searches | {len(oos):,} terms and "
          f"{oos['Search Query Volume'].sum():,.0f} monthly searches where the product cannot "
          f"win. Purchase share {100*oos[BRAND['Purchases']].sum()/oos[TOTAL['Purchases']].sum():.2f}%. |")
    if len(res["signals"]) and len(res["periods"]) >= 3:
        A(f"| Acting on any single search term's monthly movement | Across the in-scope set, "
          f"**{int(res['signals'].significant.sum())}** monthly share moves cleared the "
          f"statistical noise floor out of {len(res['signals'])} that moved consistently. Every "
          f"conclusion here is drawn at category level. |")
    if len(lift) and len(res["periods"]) >= 12:
        A(f"| Reading absolute order growth as performance | The market grew "
          f"{100*(lift.TP.iloc[-1]/lift.TP.iloc[0]-1):+.0f}%. Absolute growth mostly measures the "
          f"category, not us. |")

    # ---- method ----
    A("\n---\n\n## How these numbers were built\n")
    A("Every projection moves only the one broken stage to a level **we already achieve elsewhere "
      "in our own range**, never to a competitor's number, and holds every other stage where it "
      "actually sits. A 0.80 decay factor is applied throughout because additional traffic always "
      "converts worse than existing traffic. The honest range is roughly 30% either side.\n")
    A(f"**Data horizon: {label}.**\n")
    gaps = res["sqp"].attrs.get("empty_exports", [])
    if gaps:
        A(f"- **{len(gaps)} of the supplied exports contained no data** and were excluded "
          f"({', '.join(gaps)}). This covers {len(periods)} periods, not the number of files "
          f"provided, so check whether those months are genuinely empty or failed to download.")
    absent = res["sqp"].attrs.get("missing_columns", [])
    if absent:
        A(f"- **The export is missing {len(absent)} optional columns** that Seller Central hides "
          f"by default, so price-position and delivery-speed diagnoses could not run. Re-download "
          f"with all columns enabled to unlock them.")
    for c in caveats:
        A(f"- {c}")
    A("\nFigures cover search-originated orders only. They exclude direct-to-page traffic and "
      "anything outside a short attribution window, so they are a floor rather than a total.\n")

    br = cur[cur.query_type == "BRANDED"]
    cp = cur[cur.query_type == "COMPETITOR"]
    A(f"**Classification:** {len(br):,} branded terms (including misspellings), "
      f"{len(cp):,} competitor-brand terms representing "
      f"{cp[TOTAL['Purchases']].sum():,.0f} monthly orders we can never win, and "
      f"{len(cur)-len(br)-len(cp):,} generic terms. Misclassifying either group materially "
      f"distorts every category metric, so it is worth re-checking whenever new competitors "
      f"appear.\n")
    return "\n".join(L)


def definitions_doc(res: dict) -> str:
    """Static glossary, parameterised only by brand and marketplace."""
    cfg = res["cfg"]
    scope = (", ".join(pretty_segment(x) for x in cfg.relevance.in_scope)
             if cfg.relevance else "all searches")
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "definitions_template.md")
    with open(src, encoding="utf-8") as fh:
        tpl = fh.read()
    return (tpl.replace("{{BRAND}}", cfg.name)
               .replace("{{MARKETPLACE}}", cfg.mp.code)
               .replace("{{SCOPE}}", scope)
               .replace("{{PERIODS}}", str(len(res["periods"])))
               .replace("{{CORE}}", str(len(res["panels"]["CORE"])))
               .replace("{{CORE_PURCH}}", f"{res['_cov_pur']:.0%}")
               .replace("{{CORE_VOL}}", f"{res['_cov_vol']:.0%}"))


def write_all(res: dict) -> tuple[str, str]:
    cfg = res["cfg"]
    a = os.path.join(brand_out(cfg), f"{cfg.name}_Growth_Action_Plan.md")
    b = os.path.join(brand_out(cfg), f"{cfg.name}_Metric_Definitions.md")
    with open(a, "w", encoding="utf-8") as fh:
        fh.write(growth_plan(res))
    with open(b, "w", encoding="utf-8") as fh:
        fh.write(definitions_doc(res))
    return a, b
