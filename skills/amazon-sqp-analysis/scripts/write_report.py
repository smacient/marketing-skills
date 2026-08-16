"""
Report generation: analyst markdown and leadership one-pager.

The two have genuinely different jobs. The analyst report carries every number
and its caveat. The leadership page carries the verdict, the one big thing, and
the honest balance, in plain paragraphs with no headers or bullets.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

from sqp_lib import (BRAND, TOTAL, aggregate, dilution_vs_displacement,
                     money, pretty_segment)

OUT = os.environ.get("SQP_OUTPUT_DIR") or os.path.join(os.getcwd(), "outputs")


def brand_out(cfg) -> str:
    """One folder per brand, so runs never contaminate each other."""
    d = os.path.join(OUT, cfg.name)
    os.makedirs(d, exist_ok=True)
    return d


def _fmt(v, dp=0, pct=False, sym=""):
    if pd.isna(v):
        return "n/a"
    s = f"{v:,.{dp}f}"
    return f"{sym}{s}{'%' if pct else ''}"


def analyst_report(res: dict) -> str:
    cfg, mp = res["cfg"], res["cfg"].mp
    sym = mp.report_symbol or mp.symbol
    periods, latest = res["periods"], res["latest"]
    lift, yoy = res["lift"], res["yoy"]
    tmove, topp, tgap = res["theme_moves"], res["theme_opp"], res["theme_gap"]
    tpanel = res["theme_panel"]
    L = []
    A = L.append

    A(f"# {cfg.name} - Search Query Performance Analysis")
    A(f"\n**Marketplace:** {mp.code}  |  **Periods:** {len(periods)} "
      f"({periods[0]} to {latest})  |  **Currency:** {mp.currency}\n")

    # --- scope ---
    A("## How to read this\n")
    A("Search Query Performance measures **behaviour on Amazon search results pages only**. "
      "Direct-to-product-page traffic is excluded, purchases are counted as actions rather than "
      "units, and the attribution window is short, so these totals will never match Seller "
      "Central sales. That is by design, not an error.\n")
    A("Two properties of this report drive everything below:\n")
    A("- **Search Query Score ranks by *this brand's* funnel performance, not by market volume.** "
      "The export is the top 1,000 queries where the brand performs best, not the top 1,000 in "
      "the category. High-volume queries with no brand presence are structurally invisible.")
    A("- **Shares are the trendable unit; counts are not.** Brand share is a ratio against the "
      "same-period market, so any shock hitting all sellers cancels out. Absolute counts carry "
      "the full seasonal signal and mean little on their own.\n")

    A("The three stage scores used throughout. Each compares us against the market on the same "
      "searches, so 1.00 means exactly average:\n")
    A("```\n"
      "Tile Score  = Click Share    / Impression Share   do people click us when they see us\n"
      "Page Score  = Cart Share     / Click Share        do clickers add to cart\n"
      "Offer Score = Purchase Share / Cart Share         do cart-adders actually buy\n"
      "\n"
      "Funnel Efficiency = Purchase Share / Impression Share = Tile x Page x Offer\n```\n")
    A("Above 1.00 means beating the market at that stage. Below 1.00 means losing to it. "
      "When a problem is upstream, all downstream shares fall proportionally and the ratios "
      "stay flat; when a ratio moves, the problem is at that stage.\n")

    # --- headline ---
    A("\n## 1. Headline\n")
    if len(lift):
        f, l = lift.iloc[0], lift.iloc[-1]
        A(f"Across the in-scope market ({', '.join(cfg.relevance.in_scope)}), over "
          f"{len(periods)} months:\n")
        A("| | Start | Latest | Change |")
        A("|---|---|---|---|")
        A(f"| Market purchases | {f.TP:,.0f} | {l.TP:,.0f} | **{100*(l.TP/f.TP-1):+.0f}%** |")
        A(f"| Brand purchases | {f.BP:,.0f} | {l.BP:,.0f} | **{100*(l.BP/f.BP-1):+.0f}%** |")
        A(f"| Purchase share | {f.PS:.2f}% | {l.PS:.2f}% | {l.PS-f.PS:+.2f}pp |")
        A(f"| Tile Score | {f.R1:.2f} | {l.R1:.2f} | {l.R1-f.R1:+.2f} |")
        A(f"| Page Score | {f.R2:.2f} | {l.R2:.2f} | {l.R2-f.R2:+.2f} |")
        A(f"| Offer Score | {f.R3:.2f} | {l.R3:.2f} | {l.R3-f.R3:+.2f} |")
        A(f"| Funnel efficiency | {f.FE:.2f} | {l.FE:.2f} | {l.FE-f.FE:+.2f} |")

    if len(res["coverage"]):
        c = res["coverage"]
        A(f"\nSearch revenue rose from {sym}{c.scp_sales.iloc[0]:,.0f} to "
          f"{sym}{c.scp_sales.iloc[-1]:,.0f} per month "
          f"({100*(c.scp_sales.iloc[-1]/c.scp_sales.iloc[0]-1):+.0f}%), on an average order "
          f"value of {sym}{res['aov']:,.0f}.\n")

    # --- growth decomposition ---
    if len(yoy):
        A("\n## 2. How much of the growth was earned\n")
        A("Same calendar month year over year, so seasonality is removed by construction. "
          "Only the share effect is management performance; the market effect is the category "
          "rising underneath the brand.\n")
        A("| Comparison | Market growth | Brand growth | Share move | Market effect | Share effect | Share effect as % of growth |")
        A("|---|---|---|---|---|---|---|")
        for _, r in yoy.iterrows():
            A(f"| {r.prior} to {r.period} | {100*(r.market_purch_1/r.market_purch_0-1):+.0f}% | "
              f"{100*(r.brand_purch_1/r.brand_purch_0-1):+.0f}% | {r.share_delta_pp:+.2f}pp | "
              f"{r.market_effect:+,.0f} | {r.share_effect:+,.0f} | **{r.share_effect_pct:+.0f}%** |")
        # Sum the effects rather than averaging the percentages. Signed
        # percentages from opposite-direction periods cancel and produce a
        # number that looks precise and means nothing.
        me, se = yoy.market_effect.sum(), yoy.share_effect.sum()
        mkt_pct = 100 * me / (me + se) if (me + se) else float("nan")
        A(f"\nSumming the effects rather than averaging the percentages, "
          f"**{mkt_pct:.0f}% of growth came from the category expanding** and "
          f"{100-mkt_pct:.0f}% from share capture. The brand is growing because its market "
          f"is growing.\n")

    # --- seasonal matrix ---
    if len(lift):
        A("\n## 3. Market size against share\n")
        A("The cell that matters is market up with share down: absolute purchases rise so "
          "nothing looks wrong, while the brand is being out-competed exactly when demand "
          "is highest.\n")
        A("| Period | Market index | Purchase share | Tile | Page | Offer | Read |")
        A("|---|---|---|---|---|---|---|")
        for p, r in lift.iterrows():
            A(f"| {p} | {r.market_index:.2f} | {r.PS:.2f}% | {r.R1:.2f} | {r.R2:.2f} | "
              f"{r.R3:.2f} | {r.cell} |")

    # --- themes ---
    if len(tpanel):
        A("\n## 4. Product themes\n")
        cur = tpanel[tpanel.period == latest].sort_values("TP", ascending=False)
        A("Query-level monthly share moves do not clear the noise floor on this data. "
          "Theme aggregation raises sample size by one to two orders of magnitude, which is "
          "what makes the tests below meaningful. Shares are computed by summing numerators "
          "and denominators, never by averaging query shares.\n")
        A("| Category | Searches | Market purchases | Ours | Impression share | Purchase share | Tile | Page | Offer | Funnel Eff |")
        A("|---|---|---|---|---|---|---|---|---|---|")
        for _, r in cur.iterrows():
            A(f"| {r.theme} | {r.queries:.0f} | {r.TP:,.0f} | {r.BP:,.0f} | {r.IS:.2f}% | "
              f"{r.PS:.2f}% | {r.R1:.2f} | {r.R2:.2f} | {r.R3:.2f} | {r.FE:.2f} |")

    if len(tmove) and tmove.significant.any():
        A("\n### Significant theme movement\n")
        A(f"First period against latest, two-proportion test at 95%.\n")
        A("| Theme | Share start | Share end | Move | Market growth | Brand growth | Purchases at stake | z |")
        A("|---|---|---|---|---|---|---|---|")
        for _, r in tmove[tmove.significant].iterrows():
            A(f"| {r.theme} | {r.PS_start:.2f}% | {r.PS_end:.2f}% | **{r.delta_pp:+.2f}pp** | "
              f"{r.market_growth_pct:+.0f}% | {r.brand_growth_pct:+.0f}% | "
              f"{r.purchases_at_stake:,.0f}/mo | {r.z:+.2f} |")

    if len(tgap):
        pers = tgap[tgap[["R1_persistent_deficit", "R2_persistent_deficit",
                          "R3_persistent_deficit"]].any(axis=1)]
        if len(pers):
            A("\n### Persistent stage deficits\n")
            A("Below market in at least 75% of observed months. Persistence matters more than "
              "depth: an index that has sat below market for a year is a structural property "
              "of the offer, not a bad month.\n")
            A("| Category | Market purchases | Tile Score | months below | Page Score | months below | Offer Score | months below |")
            A("|---|---|---|---|---|---|---|---|")
            for _, r in pers.iterrows():
                A(f"| {r.theme} | {r.market_purch_latest:,.0f} | {r.R1_mean:.3f} | "
                  f"{r.R1_months_below_1:.0f}/{r.periods:.0f} | {r.R2_mean:.3f} | "
                  f"{r.R2_months_below_1:.0f}/{r.periods:.0f} | {r.R3_mean:.3f} | "
                  f"{r.R3_months_below_1:.0f}/{r.periods:.0f} |")

    # --- opportunity ---
    if len(topp):
        A("\n## 5. Opportunity\n")
        A("Stage repair, not gap closure. Each stage index is moved only to the brand's own "
          "75th-percentile performance across its themes, which is a demonstrated capability "
          "rather than a competitor's number. Visibility lift is capped at 1.5x current "
          "impression share and by the structural per-ASIN ceiling. A decay factor of 0.80 is "
          "applied because marginal traffic converts worse than existing traffic.\n")
        A("Stated in **additional purchases per month**, not money. Contribution margin varies "
          "widely by brand and is rarely known at ASIN level, so converting to profit would bury "
          "an unverifiable assumption inside a precise-looking number. Purchases are observed "
          "directly and are comparable across marketplaces, so apply your own economics.\n")
        A("These are purchase **actions**, not units: one order of three bottles counts once. "
          "Multiply by your own units per order to get units.\n")
        A("| Theme | Market purchases | Purch share | Weakest stage | Stage repair | Visibility | Total |")
        A("|---|---|---|---|---|---|---|")
        for _, r in topp.iterrows():
            A(f"| {r.theme} | {r.TP:,.0f} | {r.PS:.1f}% | {r.best_stage} | "
              f"{r.purch_best_stage:,.0f} | {r.purch_visibility:,.0f} | "
              f"**{r.purch_total_addressable:,.0f}** |")
        A(f"\n**Total addressable: {topp.purch_total_addressable.sum():,.0f} additional purchases "
          f"per month**, roughly {100*topp.purch_total_addressable.sum()/topp.BP.sum():.0f}% above "
          f"the current in-scope run rate of {topp.BP.sum():,.0f}.\n")

    # --- data quality ---
    A("\n## 6. Data quality and what was not analysable\n")
    sc, ch = res["scope"], res["churn"]
    A(f"- Every export is capped at **{sc.raw_rows.max():,.0f} rows**, ranked by brand performance. "
      f"Queries below that cut are invisible, so absence from the report is not absence from "
      f"the market.")
    A(f"- Monthly query churn averages **{ch.churn.mean():.0%}**. On a capped export over a long "
      f"tail this is structural, not an export fault.")
    A(f"- The CORE panel (present in all {len(periods)} months) is **{len(res['panels']['CORE'])} "
      f"queries**, covering {res['_cov_pur']:.0%} of brand purchases but only "
      f"{res['_cov_vol']:.0%} of volume. Trend claims are gated on the purchase coverage, "
      f"because purchases are what the analysis is about.")
    if len(res["coverage"]):
        c = res["coverage"]
        A(f"- The visible query set explains **{c.purch_coverage.iloc[-1]:.0%}** of brand search "
          f"purchases, down from {c.purch_coverage.iloc[0]:.0%}. Business is increasingly "
          f"coming from queries outside the top 1,000.")
    if len(res["signals"]):
        A(f"- **No query-level monthly share move cleared the noise floor** "
          f"({len(res['signals'])} persistent movers, 0 significant). This is why every trend "
          f"conclusion above is drawn at theme level.")
    A("- Rating data exists as a column in Search Catalog Performance but is **entirely null**, "
      "so review-driven diagnoses cannot be confirmed from this data.")
    A("- SQP cannot show organic rank, ad spend, buy box, inventory, returns, or which "
      "competitor took share. Any diagnosis touching those is a hypothesis with a named "
      "confirming check, never a finding.")

    return "\n".join(L)


def leadership_note(res: dict) -> str:
    """
    Plain paragraphs. No headers, no bullets, no tables.

    Built from whatever the data actually supports, so it degrades gracefully:
    a brand with three months of history gets a shorter, more careful note
    rather than a confident one full of gaps.
    """
    from sqp_actions import build_actions

    cfg, mp = res["cfg"], res["cfg"].mp
    sym = mp.report_symbol or mp.symbol
    lift, yoy, topp = res["lift"], res["yoy"], res["theme_opp"]
    periods = res["periods"]
    actions = build_actions(res)
    P = []

    scope = (", ".join(pretty_segment(x) for x in cfg.relevance.in_scope).lower()
             if cfg.relevance else "all")
    P.append(
        f"This looks at {len(periods)} months of Amazon Brand Analytics search data for "
        f"{cfg.name} on {mp.code}, covering {periods[0]} to {periods[-1]}. It measures how "
        f"shoppers behave on Amazon search results pages specifically, so it is not the same as "
        f"total sales and will not tie back to Seller Central. What it does uniquely well is "
        f"show how we performed against everyone else competing for the same shopper at the "
        f"same moment, which is the part no internal report can tell us. Throughout, the market "
        f"we measure ourselves against is {scope} demand, because that is what we can "
        f"realistically win.")

    # Scale and direction, only as far as the data supports.
    if len(res["coverage"]):
        c = res["coverage"]
        r0, r1 = c.scp_sales.iloc[0], c.scp_sales.iloc[-1]
        line = (f"Search-driven revenue moved from about {money(r0, mp)} a month to "
                f"{money(r1, mp)}, roughly {100*(r1/r0-1):+.0f} percent.")
        if len(lift):
            f, l = lift.iloc[0], lift.iloc[-1]
            line += (f" Within the market we actually compete in, our orders went from "
                     f"{f.BP:,.0f} to {l.BP:,.0f} a month and our share of it moved from "
                     f"{f.PS:.2f} percent to {l.PS:.2f} percent.")
        P.append(line)

    if len(yoy):
        me, se = yoy.market_effect.sum(), yoy.share_effect.sum()
        dpp = yoy.share_delta_pp.iloc[-1]
        if abs(se) < 25 and abs(me) < 25:
            P.append(
                f"I would not read much into the growth split yet. Share moved {dpp:+.2f} points "
                f"year over year, but on volumes this small that is a handful of orders and could "
                f"as easily be chance. The honest position is that we do not yet have enough "
                f"business flowing through search to say whether we are winning or losing.")
        elif me > 0 and se > 0:
            P.append(
                f"Put plainly, about {100*me/(me+se):.0f} percent of that growth came from the "
                f"category expanding underneath us rather than from taking ground off "
                f"competitors. We are riding a rising market competently without yet pulling "
                f"away from the field. That is a reasonable place to be and a fragile one, "
                f"because a category growing this fast attracts entrants.")
        elif me <= 0 and se > 0:
            P.append(
                f"Worth being clear that all of this was earned rather than given. The category "
                f"itself shrank over the year and we grew anyway, taking {dpp:+.2f} points of "
                f"share off competitors. That is the strongest read available from this data. It "
                f"also means the category is not doing us any favours, so growth from here has to "
                f"keep coming out of someone else's hide.")
        else:
            P.append(
                f"The uncomfortable part is that the category grew and we did not keep up. Our "
                f"share fell {abs(dpp):.2f} points over the year, so absolute numbers can look "
                f"acceptable while our actual position weakens.")

    # The single most important finding, in its own words.
    if actions:
        a = actions[0]
        ev = " ".join(a.evidence[:2]) if a.evidence else ""
        P.append(f"The one thing I would focus on is this. {ev} {a.do}")

    # The second finding, framed as the risk or the follow-up.
    if len(actions) > 1:
        b = actions[1]
        ev = " ".join(b.evidence[:2]) if b.evidence else ""
        P.append(f"Behind that sits a second issue worth naming. {ev}")

    if len(topp) and topp.purch_total_addressable.sum() >= 5:
        tot = topp.purch_total_addressable.sum()
        base = topp.BP.sum()
        ns = [t.theme.lower() for _, t in topp.head(3).iterrows()]
        names = ", ".join(ns[:-1]) + " and " + ns[-1] if len(ns) > 1 else ns[0]
        P.append(
            f"Sizing the fixable part conservatively, the work above is worth roughly "
            f"{tot:,.0f} additional orders a month against our current {base:,.0f}, concentrated "
            f"in {names}. I have deliberately left that in orders rather than rupees, because "
            f"margin varies too much by product for a profit figure to mean anything precise, "
            f"and anyone can apply their own economics to an order count. It assumes we only "
            f"reach conversion levels we already demonstrate elsewhere in our own range, and it "
            f"discounts for the fact that additional traffic always converts worse than existing "
            f"traffic. The honest range runs about thirty percent either side.")

    if len(periods) < 12:
        P.append(
            f"One caveat on confidence. We have {len(periods)} months of history here, which is "
            f"enough to see direction but not enough to separate a genuine trend from a seasonal "
            f"swing. I would treat everything above as a strong steer rather than a settled "
            f"conclusion, and revisit once we have a full year.")

    P.append(
        "What I would like to do next is take the highest-priority item above, execute it "
        "properly, and measure the result against the market rather than against our own prior "
        "numbers, because our own numbers can improve while our position against competitors "
        "does not. I will come back with a before-and-after read in about six weeks. If there is "
        "a decision I need from you, it is how much we are willing to spend ahead of revenue to "
        "hold position while the category is still growing.")

    return "\n\n".join(P)


def write_all(res: dict) -> tuple[str, str]:
    cfg = res["cfg"]
    a = os.path.join(brand_out(cfg), f"{cfg.name}_SQP_Analyst_Report_{res['latest']}.md")
    b = os.path.join(brand_out(cfg), f"{cfg.name}_SQP_Leadership_Note_{res['latest']}.md")
    with open(a, "w", encoding="utf-8") as fh:
        fh.write(analyst_report(res))
    with open(b, "w", encoding="utf-8") as fh:
        fh.write(leadership_note(res))
    return a, b
