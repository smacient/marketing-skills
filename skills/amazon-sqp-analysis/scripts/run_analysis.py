"""
Full SQP analysis run.

Usage:  python run_analysis.py [BrandName]

Produces a multi-tab Excel workbook and a markdown analyst report in outputs/.
Every horizon runs only if the data supports it, and the run states which
analyses were disabled for want of history.
"""

from __future__ import annotations

import os
import sys
import warnings

import numpy as np
import pandas as pd

import brand_config
import sqp_horizons as H
import sqp_themes as T
from sqp_diagnose import (CATALOGUE, DX_TO_LEVER, REALISATION, diagnose,
                          priority_score, size_opportunity)
from sqp_lib import (BRAND, TOTAL, add_reliability, aggregate, build_panels,
                     churn_table, definitions_table, export_scope, humanize,
                     load_scp, load_sqp, panel_coverage)

warnings.filterwarnings("ignore")
pd.set_option("display.width", 250)

# Output root. Overridable so the skill can write wherever the user works.
OUT = os.environ.get("SQP_OUTPUT_DIR") or os.path.join(os.getcwd(), "outputs")


def brand_out(cfg) -> str:
    """One folder per brand, so runs never contaminate each other."""
    d = os.path.join(OUT, cfg.name)
    os.makedirs(d, exist_ok=True)
    return d


def hdr(t):
    print("\n" + "=" * 100)
    print(t)
    print("=" * 100)


def run(cfg) -> dict:
    mp = cfg.mp
    res = {"cfg": cfg}

    # ---- Load ------------------------------------------------------------
    sqp = load_sqp(cfg)
    scp = load_scp(cfg)
    # Search Catalog Performance is always exported for the whole brand. On an
    # ASIN-level run it has to be narrowed to the same product, or revenue, AOV
    # and coverage silently describe the brand while every other number on the
    # page describes one ASIN. Coverage is the worst of the three: a brand-wide
    # denominator under an ASIN-level numerator understates it several-fold.
    asin_scope = sqp.attrs.get("asin_scope")
    own_low = "this ASIN's" if asin_scope else "brand"
    if asin_scope and len(scp) and "ASIN" in scp.columns:
        scp = scp[scp["ASIN"].astype(str).str.upper() == asin_scope]
        if not len(scp):
            print("  [scope] " + asin_scope + " does not appear in Search Catalog "
                  "Performance. Revenue, AOV and coverage cannot be reported for it.")
    sqp = add_reliability(sqp)
    periods = sorted(sqp["period"].unique())
    latest = periods[-1]
    res.update(sqp=sqp, scp=scp, periods=periods, latest=latest)

    hdr(f"{cfg.name}  |  {mp.code}  |  {len(periods)} periods: {periods[0]} to {latest}")

    # ---- Data quality ----------------------------------------------------
    scope = export_scope(sqp)
    churn = churn_table(sqp)
    panels = build_panels(sqp)
    core, stable = panels["CORE"], panels["STABLE"]

    cov_vol = panel_coverage(sqp, core, latest, "Search Query Volume")
    cov_pur = panel_coverage(sqp, core, latest, BRAND["Purchases"])

    # SQP is capped at the top N queries by brand performance, so it covers
    # only part of the brand's search business. SCP is uncapped, so the ratio
    # measures how much of the business the visible query set explains.
    coverage = pd.DataFrame()
    if len(scp):
        s = scp.groupby("period").agg(
            scp_purch=("Purchases: Purchases", "sum"),
            scp_sales=("Purchases: Search Traffic Sales", "sum"),
            scp_impr=("Impressions: Impressions", "sum"),
            asins=("ASIN", "nunique"))
        q = sqp.groupby("period").agg(sqp_purch=(BRAND["Purchases"], "sum"),
                                      sqp_impr=(BRAND["Impressions"], "sum"))
        coverage = q.join(s)
        coverage["purch_coverage"] = coverage.sqp_purch / coverage.scp_purch
        coverage["aov"] = coverage.scp_sales / coverage.scp_purch

    aov = float(coverage["aov"].iloc[-1]) if len(coverage) else 600.0
    res.update(scope=scope, churn=churn, panels=panels, coverage=coverage, aov=aov,
               _cov_vol=cov_vol, _cov_pur=cov_pur)

    print(f"  CORE panel: {len(core)} queries | {cov_vol:.1%} of volume | {cov_pur:.1%} of " + own_low + " purchases")
    if len(churn):
        print(f"  Monthly churn: {churn['churn'].mean():.1%} "
              f"(structural on a {scope.raw_rows.max():.0f}-row cap)")
    else:
        print(f"  Single period: no churn, trend or movement analysis possible")
    if len(coverage):
        print(f"  SQP covers {coverage['purch_coverage'].iloc[-1]:.1%} of " + own_low + " search purchases "
              f"(was {coverage['purch_coverage'].iloc[0]:.1%})")
        print(f"  AOV from Search Traffic Sales: {mp.symbol}{aov:,.0f}")

    # ---- Segmentation ----------------------------------------------------
    hdr("SEGMENTATION")
    seg = (sqp[sqp.period == latest]
           .groupby(["query_type", "segment"]).apply(aggregate, include_groups=False))
    print(seg[["queries", "SQV", "TP", "BP", "IS", "PS", "R1", "R2", "R3", "FE"]].round(2).to_string())
    res["segments"] = seg

    unbr = sqp["query_type"] == "UNBRANDED"
    inscope = unbr & sqp["in_scope"]
    res["mask_unbranded"], res["mask_inscope"] = unbr, inscope

    # ---- H1: current period ---------------------------------------------
    hdr(f"HORIZON 1  |  {latest}")
    cur = sqp[sqp.period == latest].copy()
    cur = diagnose(cur, price_barrier=mp.price_barrier_index)
    cur["lever"] = cur["dx"].map(DX_TO_LEVER).fillna("Monitor")
    cur = size_opportunity(cur)
    cur["priority"] = [priority_score(g, c, l) for g, c, l
                       in zip(cur["expected_purchases"], cur["dx_confidence"], cur["lever"])]

    dxs = (cur.groupby(["dx_family", "dx_label"])
              .agg(queries=("q", "size"), volume=("Search Query Volume", "sum"),
                   market_purch=(TOTAL["Purchases"], "sum"),
                   brand_purch=(BRAND["Purchases"], "sum"),
                   opportunity=("d_purchases", "sum"))
              .sort_values("opportunity", ascending=False))
    print(dxs.round(0).to_string())
    res["current"] = cur
    res["dx_summary"] = dxs

    # ---- H2: three periods ----------------------------------------------
    sig = pd.DataFrame()
    ee = {}
    if len(periods) >= 3:
        hdr("HORIZON 2  |  direction of travel, last 3 periods")
        sig = H.persistence_signals(sqp[inscope | (sqp.query_type == "BRANDED")], periods)
        ee = H.entry_exit(sqp, periods)
        if len(sig):
            n_sig = int(sig["significant"].sum())
            print(f"  Persistent movers: {len(sig)} | clearing the noise floor: {n_sig}")
            print(sig[sig.significant].head(10)[
                ["Search Query", "segment", "PS_p1", "PS_p3", "delta_pp", "direction",
                 "market_purch_now"]].round(2).to_string(index=False))
        print(f"\n  Entered: {ee['n_entered']} | Exited: {ee['n_exited']} "
              f"| high-severity exits: {len(ee['brand_exit_high'])}")
        if len(ee["brand_exit_high"]):
            print(ee["brand_exit_high"].head(10)[
                ["Search Query", "Search Query Score", "Search Query Volume",
                 BRAND["Purchases"], "segment"]].to_string(index=False))
    res["signals"], res["entry_exit"] = sig, ee

    # ---- H3: twelve periods ---------------------------------------------
    seasonal = lift = vol = life = pd.DataFrame()
    if len(periods) >= 12:
        hdr("HORIZON 3  |  seasonality, volatility, lifecycle")
        seasonal = H.seasonal_index(sqp, core)
        lift = H.lift_vs_gain(sqp, inscope)
        print(lift[["SQV", "TP", "BP", "PS", "R1", "R2", "R3", "FE", "market_index", "cell"]]
              .round(3).to_string())
        vol = H.volatility(sqp, core)
        if len(vol):
            print("\n  Volatility of in-scope CORE queries:")
            print(vol["stability"].value_counts().to_string())
        life = H.lifecycle(sqp, stable, seasonal)
        if len(life):
            print("\n  Lifecycle mix:")
            print(life["lifecycle"].value_counts().to_string())
    res.update(seasonal=seasonal, lift=lift, volatility=vol, lifecycle=life)

    # ---- H4: year over year ---------------------------------------------
    yoy = pd.DataFrame()
    if len(periods) >= 13:
        hdr("HORIZON 4  |  year over year (seasonality removed by construction)")
        yoy = H.yoy_table(sqp, inscope)
        if len(yoy):
            print(yoy[["period", "prior", "market_purch_0", "market_purch_1",
                       "brand_purch_0", "brand_purch_1", "share_0_pct", "share_1_pct",
                       "share_delta_pp", "market_effect", "share_effect",
                       "share_effect_pct", "driver"]].round(2).to_string(index=False))
    res["yoy"] = yoy

    # ---- Theme layer ------------------------------------------------------
    # Where the statistical power is. At query level on this data no monthly
    # mover clears the noise floor; at theme level the tests have real power.
    tpanel = tmove = topp = tgap = pd.DataFrame()
    if cfg.product_themes:
        hdr("THEME LAYER  |  in-scope queries aggregated to product themes")
        themed = T.assign_themes(sqp, cfg.product_themes)
        res["themed"] = themed
        tmask = (themed["query_type"] == "UNBRANDED") & themed["in_scope"]
        tpanel_all = T.theme_panel(themed, tmask)
        keep = T.reportable(tpanel_all, latest)
        dropped = sorted(set(tpanel_all.theme) - keep)
        if dropped:
            print(f"  [gate] {len(dropped)} categories below "
                  f"{T.MIN_THEME_PURCHASES} monthly market purchases, suppressed: "
                  f"{', '.join(dropped)}")
        tpanel = tpanel_all[tpanel_all.theme.isin(keep)]
        cur_all = tpanel_all[tpanel_all.period == latest]
        oth = cur_all[cur_all.theme == "OTHER"]["TP"].sum()
        tot = cur_all["TP"].sum()
        if tot:
            print(f"  [taxonomy] {100*oth/tot:.0f}% of in-scope market purchases are "
                  f"unclassified. Above 15% means the category list needs extending.")

        cur_t = tpanel[tpanel.period == latest].sort_values("TP", ascending=False)
        print(cur_t[["theme", "queries", "SQV", "TP", "BP", "IS", "PS",
                     "R1", "R2", "R3", "FE"]].round(2).to_string(index=False))

        tmove = T.theme_trend(tpanel, periods)
        if len(tmove):
            print(f"\n  Theme share movement, {periods[0]} to {latest} "
                  f"({int(tmove.significant.sum())} of {len(tmove)} significant):")
            print(tmove[tmove.significant][
                ["theme", "PS_start", "PS_end", "delta_pp", "market_growth_pct",
                 "brand_growth_pct", "purchases_at_stake", "z"]].round(2).to_string(index=False))

        tgap = T.theme_r2_gap(tpanel, latest)
        pers = tgap[tgap[["R1_persistent_deficit", "R2_persistent_deficit",
                          "R3_persistent_deficit"]].any(axis=1)]
        if len(pers):
            print("\n  Persistent stage deficits (below market in >=75% of months):")
            print(pers[["theme", "market_purch_latest", "R1_mean", "R1_months_below_1",
                        "R2_mean", "R2_months_below_1", "R3_mean", "R3_months_below_1"]]
                  .round(3).to_string(index=False))

        topp = T.theme_opportunity(tpanel, latest)
        if len(topp):
            print("\n  Theme opportunity, additional purchases per month (stage repair + visibility):")
            print(topp[["theme", "TP", "PS", "best_stage", "purch_best_stage",
                        "purch_visibility", "purch_total_addressable"]].round(0).head(12).to_string(index=False))
            print(f"\n  Total addressable: {topp.purch_total_addressable.sum():,.0f} "
                  f"additional purchases per month "
                  f"({100*topp.purch_total_addressable.sum()/topp.BP.sum():.0f}% above the "
                  f"current in-scope run rate of {topp.BP.sum():,.0f})")
    res.update(theme_panel=tpanel, theme_moves=tmove, theme_opp=topp, theme_gap=tgap)

    # ---- Action list -----------------------------------------------------
    hdr("TOP ACTIONS  |  clustered by ASIN-group x diagnosis x lever")
    act = (cur[cur["priority"] > 0]
           .groupby(["dx_label", "lever", "segment"])
           .agg(queries=("q", "size"), volume=("Search Query Volume", "sum"),
                market_purch=(TOTAL["Purchases"], "sum"),
                purch=("d_purchases", "sum"), purch_floor=("purch_floor", "sum"),
                purch_ceiling=("purch_ceiling", "sum"), priority=("priority", "sum"))
           .reset_index().sort_values("priority", ascending=False))
    act["prob"] = act["lever"].map(lambda l: REALISATION.get(l, (0.5, 4, 3))[0])
    act["weeks"] = act["lever"].map(lambda l: REALISATION.get(l, (0.5, 4, 3))[1])
    print(act.head(12).round(0).to_string(index=False))
    res["actions"] = act

    return res


# ---------------------------------------------------------------------------
# Excel output
# ---------------------------------------------------------------------------

def write_excel(res: dict) -> str:
    cfg, mp = res["cfg"], res["cfg"].mp
    cur, sqp = res["current"], res["sqp"]
    span = f"{res['periods'][0]}_to_{res['latest']}"
    path = os.path.join(brand_out(cfg), f"{cfg.name}_SQP_Workbook_{span}.xlsx")

    readme = pd.DataFrame({
        "Item": [
            "Brand", "Marketplace", "Currency", "Periods", "Latest period",
            "Query rows per export", "CORE panel size",
            "CORE coverage of brand purchases", "SQP coverage of brand search purchases",
            "AOV (from Search Traffic Sales)", "Relevance in-scope segments",
            "", "SCOPING CAVEATS", "Attribution",
            "Coverage", "Purchases", "Impressions", "Search Query Score",
            "Row cap", "Shipping speed columns", "Click Rate % column",
            "Search Catalog Performance",
        ],
        "Value": [
            cfg.name, mp.code, mp.currency, len(res["periods"]), res["latest"],
            int(res["scope"].N_rows.max()), len(res["panels"]["CORE"]),
            f"{panel_coverage(sqp, res['panels']['CORE'], res['latest'], BRAND['Purchases']):.1%}",
            f"{res['coverage']['purch_coverage'].iloc[-1]:.1%}" if len(res["coverage"]) else "n/a",
            f"{mp.symbol}{res['aov']:,.0f}",
            ", ".join(cfg.relevance.in_scope) if cfg.relevance else "all",
            "",
            "Read these before interpreting any number below",
            "Short window. SQP purchase totals will never match Seller Central sales. That is by design.",
            "Search-originated traffic only. Direct-to-PDP visits are excluded entirely.",
            "Purchase ACTIONS, not units. Cancellations and returns are included.",
            "Include Sponsored Products, so organic and paid cannot be separated within SQP.",
            "Ranks by BRAND funnel performance, not market volume. The export is the top N queries "
            "where this brand performs best, not the top N queries in the category.",
            "Hard cap per export. High-volume queries where the brand has no presence are invisible.",
            "MARKET level, not brand level. The brand-side fulfilment mix is not in this report.",
            "Is clicks divided by SEARCH VOLUME, not click-through rate on impressions.",
            "A separate report, not the ASIN view of SQP. No competitive data, cannot join by query.",
        ]})

    qcols = ["Search Query", "query_type", "segment", "in_scope", "Search Query Score",
             "Search Query Volume", TOTAL["Impressions"], BRAND["Impressions"],
             TOTAL["Clicks"], BRAND["Clicks"], TOTAL["Cart Adds"], BRAND["Cart Adds"],
             TOTAL["Purchases"], BRAND["Purchases"], "IS", "CS", "AS", "PS",
             "R1", "R2", "R3", "FE", "PIc", "PIa", "PIp", "SCI", "MPR", "FSM_market",
             "dx_label", "dx_secondary", "dx_family", "dx_evidence", "dx_confidence",
             "lever", "d_purchases", "purch_floor", "purch_ceiling", "priority"]
    qcols = [c for c in qcols if c in cur.columns]

    glossary = pd.DataFrame({
        "Metric": ["Impression / Click / Cart / Purchase Share",
                   "Tile Score", "Page Score", "Offer Score", "Funnel Efficiency",
                   "Our Price vs Market", "Results Page Crowding", "Purchases per Search",
                   "Market Fast-Delivery Share", "Volatility Score",
                   "Extra Orders / Month", "Extra Orders low / high", "Priority Score"],
        "Formula": [
            "Brand count / Total count at each funnel stage, recomputed from counts",
            "Click Share / Impression Share", "Cart Share / Click Share",
            "Purchase Share / Cart Share",
            "Purchase Share / Impression Share = Tile x Page x Offer",
            "Brand median price / Market median price, at click / cart / purchase",
            "Total impressions / Search query volume",
            "Total purchases / Search query volume",
            "(Same-day + 1D purchases) / Total purchases, market level",
            "Observed share variance / binomial-expected variance",
            "Market purchases x projected share gain x decay",
            "Range from harsher and softer decay assumptions",
            "Expected purchases x realisation probability x confidence / (effort x sqrt(weeks))"],
        "Reads as": [
            "Your share of the market at that stage",
            "Market-relative click-through. The SERP tile.",
            "Market-relative cart-add. The product page.",
            "Market-relative close rate. The offer.",
            "Purchases won per unit of visibility. Above 1 means punching above your weight.",
            "Above 1 means priced above market at that stage",
            "How crowded the results page is. Rising SCI cuts everyone's impression share mechanically.",
            "Commercial intent of the query",
            "How much the category depends on fast delivery",
            "Below 1.5 stable, 1.5 to 3 real movement, above 3 erratic",
            "Additional purchases per month if the diagnosed stage is repaired. Purchase ACTIONS, not units.",
            "Always quote the range, never the point",
            "What to do first"]})

    tabs = [
        ("00 Read Me", readme),
        ("01 Definitions", definitions_table()),
        ("02 Scorecard", res["lift"].reset_index() if len(res["lift"]) else pd.DataFrame()),
        ("03 Segments", res["segments"].reset_index()),
        ("04 Search Term Detail", cur[qcols].sort_values("priority", ascending=False)),
        ("05 Diagnosis Summary", res["dx_summary"].reset_index()),
        ("06 Actions", res["actions"]),
        ("07 Opportunities", cur[cur.dx.isin(["HIDDEN_GEM", "CONVERSION_WINNER", "VISIBILITY_GAP",
                                              "PROFITABLE_PREMIUM"])][qcols]
                                .sort_values("d_purchases", ascending=False)),
        ("08 Do Not Chase", cur[cur.dx.isin(["MISMATCH", "OUT_OF_SCOPE"])][qcols]
                            .sort_values("Search Query Volume", ascending=False).head(300)),
        ("09 Movers", res["signals"]),
        ("10 Terms Lost", res["entry_exit"].get("exited", pd.DataFrame())[
            [c for c in ["Search Query", "segment", "Search Query Score", "Search Query Volume",
                         BRAND["Purchases"], "severity"] if c in
             res["entry_exit"].get("exited", pd.DataFrame()).columns]]
            if res["entry_exit"] else pd.DataFrame()),
        ("11 Monthly Trend", H.monthly_series(sqp, res["mask_inscope"]).reset_index()),
        ("12 Year over Year", res["yoy"]),
        ("13 Seasonality", res["seasonal"]),
        ("14 Lifecycle", res["lifecycle"]),
        ("15 Volatility", res["volatility"]),
        ("16 Data Quality", res["scope"].merge(res["churn"], on="period", how="left")),
        ("17 Coverage", res["coverage"].reset_index() if len(res["coverage"]) else pd.DataFrame()),
        ("18 Category Detail", res.get("theme_panel", pd.DataFrame())),
        ("19 Category Movement", res.get("theme_moves", pd.DataFrame())),
        ("20 Category Opportunity", res.get("theme_opp", pd.DataFrame())),
        ("21 Category Stage Gaps", res.get("theme_gap", pd.DataFrame())),
        ("22 Method Notes", glossary),
    ]

    with pd.ExcelWriter(path, engine="xlsxwriter") as xl:
        book = xl.book
        hfmt = book.add_format({"bold": True, "bg_color": "#1F3864", "font_color": "white",
                                "border": 1, "text_wrap": True, "valign": "top"})
        for name, frame in tabs:
            f = frame if isinstance(frame, pd.DataFrame) else pd.DataFrame()
            if f.empty:
                f = pd.DataFrame({"note": ["Not available at this data horizon"]})
            f = humanize(f)
            f.to_excel(xl, sheet_name=name[:31], index=False)
            ws = xl.sheets[name[:31]]
            for i, col in enumerate(f.columns):
                width = min(46, max(11, int(f[col].astype(str).str.len().max() if len(f) else 11) + 2,
                                    len(str(col)) + 2))
                ws.set_column(i, i, width)
                ws.write(0, i, str(col), hfmt)
            ws.freeze_panes(1, 0)
    return path


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Run a full SQP analysis for one brand.")
    ap.add_argument("config", help="path to the brand config JSON")
    ap.add_argument("-o", "--output", help="output directory (default ./outputs)")
    a = ap.parse_args()
    if a.output:
        # Set before the writers are imported: each module resolves its output
        # root at import time, so they must all see the same value.
        os.environ["SQP_OUTPUT_DIR"] = os.path.abspath(a.output)
        OUT = os.path.abspath(a.output)
    import write_plan
    import write_report

    cfg = brand_config.load(a.config)
    print(brand_config.describe(cfg))
    r = run(cfg)
    xl = write_excel(r)
    md, ld = write_report.write_all(r)
    plan, defs = write_plan.write_all(r)
    hdr("WROTE")
    for f in (xl, plan, md, ld, defs):
        print("  ", f)
