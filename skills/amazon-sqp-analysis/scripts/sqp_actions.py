"""
Action detection: turns analysis results into a prioritised, dated plan.

Each detector inspects the results and emits zero or more Action records with
the evidence that triggered it. Nothing is hand-written per brand, so the same
detectors run for any brand in any marketplace.

Actions are ranked by expected additional orders per unit of effort, discounted
by how long the fix takes to land. Impact is always stated in orders, never
money: contribution margin varies too much between products to bake a guess
into the number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from sqp_diagnose import REALISATION
from sqp_lib import BRAND, TOTAL, aggregate

# Which execution window an action belongs in, driven by effort and how fast it
# can realistically land.
NOW, SOON, YEAR = "Next 30 days", "Next 90 days", "Next 12 months"


@dataclass
class Action:
    title: str
    lever: str
    horizon: str
    orders: float                      # additional orders per month
    do: str
    evidence: list[str] = field(default_factory=list)
    caution: str = ""
    confidence: float = 0.8
    unquantified: bool = False
    # Categories this action already accounts for. Later detectors skip them so
    # the same opportunity is never counted in two places.
    claims: set = field(default_factory=set)
    defends: float = 0.0
    # Some findings cannot be sized but are still the headline. Ranking purely
    # on projected orders would bury them under trivial quantified actions.
    critical: bool = False

    @property
    def spec(self):
        return REALISATION.get(self.lever, (0.5, 4.0, 3))

    @property
    def priority(self) -> float:
        if self.critical:
            return float("inf")
        prob, weeks, effort = self.spec
        if self.unquantified:
            return 0.0
        return (self.orders * prob * self.confidence) / (effort * np.sqrt(weeks))


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------

def detect_structural_absence_overall(res: dict) -> list[Action]:
    """
    The brand is effectively invisible in unbranded search.

    Every opportunity figure in this engine scales from current visibility, so
    when there is essentially none the model has nothing to scale and would
    report a trivial number for what is actually the brand's central problem.
    Detect it explicitly and hand back a qualitative finding instead.
    """
    sqp, latest = res["sqp"], res["latest"]
    ins = sqp[res["mask_inscope"] & (sqp.period == latest)]
    if ins.empty:
        return []
    a = aggregate(ins)
    if pd.isna(a["IS"]) or a["IS"] >= 0.5:
        return []
    scp = res.get("scp")
    asins = scp[scp.period == latest]["ASIN"].nunique() if scp is not None and len(scp) else 0
    per = 1.0 / (a["IS"] / 100.0) if a["IS"] else float("inf")
    ev = [f"Impression share across the in-scope market is {a['IS']:.2f}%. A relevant product is "
          f"shown roughly {per:,.0f} times before one of them is ours.",
          f"That yields {a['BP']:,.0f} orders a month out of a {a['TP']:,.0f}-order market."]
    if asins:
        ev.append(f"The catalogue has {asins:,} live ASINs producing those orders, so the problem "
                  f"is not range, it is that the range is never seen.")
    ev.append("Every opportunity figure in this report scales from current visibility. At this "
              "level there is nothing to scale from, so the sizing model is not meaningful and "
              "no number is offered.")
    return [Action(
        title="Establish basic search visibility before anything else",
        lever="PPC bid / budget", horizon=NOW, orders=0.0, unquantified=True, confidence=0.9,
        evidence=ev, claims={"__all__"}, critical=True,
        do="Pick the ten highest-intent terms the catalogue genuinely serves and fund them to a "
           "measurable impression share, then re-measure. Until impression share is materially "
           "above zero, no conversion diagnosis on unbranded terms carries meaning, because the "
           "scores are computed on single-digit counts.",
    )]


def detect_brand_defence(res: dict) -> list[Action]:
    """Purchases lost on searches for our own name."""
    sqp, latest = res["sqp"], res["latest"]
    b = sqp[(sqp.query_type == "BRANDED") & (sqp.period == latest)]
    if b.empty:
        return []
    a = aggregate(b)
    lost = a["TP"] - a["BP"]
    # If the brand is not already winning its own name, the gap is not a bid
    # problem and cannot be closed by defending. Something more basic is wrong,
    # and claiming the whole gap would produce an absurd number.
    if lost < 5 or a["IS"] > 92 or pd.isna(a["PS"]) or a["PS"] < 50:
        return []
    # Nobody captures the entire gap. Half of it is already optimistic, and the
    # uncapped figure can exceed the brand's entire business.
    recoverable = lost * 0.5
    hist = sqp[sqp.query_type == "BRANDED"].groupby("period").apply(
        aggregate, include_groups=False)
    return [Action(
        title="Defend our own brand terms",
        lever="PPC bid / budget", horizon=NOW, orders=float(recoverable), confidence=0.85,
        evidence=[
            f"We win {a['PS']:.1f}% of purchases on searches containing our brand name, "
            f"but hold only {a['IS']:.1f}% of the impressions.",
            f"That gap costs {lost:,.0f} orders a month. Sized at half of it, since no one "
            f"captures every impression on their own name.",
            f"Branded search volume is {'up' if hist.SQV.iloc[-1] > hist.SQV.iloc[0] else 'down'} "
            f"{abs(100*(hist.SQV.iloc[-1]/hist.SQV.iloc[0]-1)):.0f}% over the period, and our "
            f"impression share on brand terms moved from {hist.IS.iloc[0]:.1f}% to {a['IS']:.1f}%.",
        ],
        do="Exact-match campaigns on every brand spelling, including the misspellings shoppers "
           "actually type. Brand-term clicks are typically cheap, so this is usually positive return.",
        claims={"__branded__"},
    )]


def detect_share_restoration(res: dict) -> list[Action]:
    """
    Categories that lost share while their stage scores held or improved.

    This is a visibility loss, not a quality loss, so it is cheap to reverse:
    the target is the share the brand demonstrably held before.
    """
    tmove, tpanel, latest = res["theme_moves"], res["theme_panel"], res["latest"]
    if tmove.empty:
        return []
    out = []
    for _, r in tmove[tmove.significant & (tmove.delta_pp < 0)].iterrows():
        g = tpanel[tpanel.theme == r.theme].sort_values("period")
        cur = g.iloc[-1]
        # Only when the funnel still works. If the scores fell too, it is a
        # quality problem and belongs to a different detector.
        if not (cur.R1 >= 0.95 and cur.R2 >= 0.90):
            continue
        orders = abs(r.delta_pp) * r.market_end / 100.0
        peak_is = g.IS.max()
        out.append(Action(
            title=f"Rebuild {r.theme.lower()} visibility",
            lever="PPC bid / budget", horizon=NOW, orders=float(orders), confidence=0.8,
            evidence=[
                f"Share fell from {r.PS_start:.1f}% to {r.PS_end:.1f}% "
                f"(statistically real, z = {r.z:.2f}) while the market grew "
                f"{r.market_growth_pct:.0f}%.",
                f"Our own sales still grew {r.brand_growth_pct:.0f}%, and every stage score is "
                f"healthy: tile {cur.R1:.2f}, page {cur.R2:.2f}, offer {cur.R3:.2f}.",
                f"Impression share is {cur.IS:.1f}% now against a peak of {peak_is:.1f}%.",
                "We did not get worse. We became harder to find in a market that grew faster "
                "than we did.",
            ],
            do=f"Raise exact-match bids across the {r.theme.lower()} term set, restore coverage on "
               f"terms we dropped out of, and set a top-of-search modifier of +50%. Track "
               f"impression share weekly against a {min(peak_is, 10):.0f}% target.",
            claims={r.theme},
            caution=(f"Impression share peaked at {peak_is:.1f}%, above the roughly 8% a single "
                     f"ASIN can hold, so more than one ASIN was competing then. If bids alone "
                     f"stall near 8%, the constraint is ASIN count and the answer is another "
                     f"variant, not more budget.") if peak_is > 8 else "",
        ))
    return out


def detect_stage_repair(res: dict, claimed: set) -> list[Action]:
    """Categories with a stage score persistently below market."""
    tgap, topp = res["theme_gap"], res["theme_opp"]
    if tgap.empty or topp.empty:
        return []
    tgap = tgap[~tgap.theme.isin(claimed)]
    if tgap.empty:
        return []
    stage_names = {"R1": ("tile", "Hero image"), "R2": ("product page", "A+ / bullets"),
                   "R3": ("offer", "Fulfilment / stock")}
    groups: dict[str, list] = {}
    for _, r in tgap.iterrows():
        for idx, (label, lever) in stage_names.items():
            if r.get(f"{idx}_persistent_deficit"):
                groups.setdefault(idx, []).append(r)
    out = []
    for idx, rows in groups.items():
        label, lever = stage_names[idx]
        themes = [r.theme for r in rows]
        opp = topp[topp.theme.isin(themes)]
        direct = float(opp[f"purch_{'serp' if idx == 'R1' else 'pdp' if idx == 'R2' else 'close'}"].sum())
        withvis = float(opp["purch_total_addressable"].sum())
        no_cap = bool(opp.get(f"{idx}_no_capability", pd.Series([False])).any())
        # A severe, persistent deficit is worth acting on even when the model
        # cannot size it. Only skip when it is both small and not severe.
        severe = any(r[f"{idx}_mean"] < 0.75 for r in rows)
        if direct < 3 and not severe:
            continue
        ev = [f"{r.theme}: score {r[f'{idx}_mean']:.2f}, below market in "
              f"{r[f'{idx}_months_below_1']:.0f} of {r[f'{idx}_months_measured']:.0f} "
              f"measurable months"
              for r in sorted(rows, key=lambda x: -x.market_purch_latest)]
        if no_cap:
            gap = float(opp["TP"].sum()) * (1.0 - min(r[f"{idx}_mean"] for r in rows)) * 0.01
            ev.append(
                "Sizing is unavailable here for a specific reason: we are below market at this "
                "stage in every category we sell, so there is no level we have demonstrated we "
                "can reach, and projecting one would be invention. That absence is itself the "
                "finding. Closing to market parity on the affected categories is the prize, and "
                "it is large relative to current volume.")
        else:
            ev.append(f"Worth {direct:,.0f} orders a month from the fix alone, "
                      f"{withvis:,.0f} if paired with more visibility.")
        do = {
            "R1": "Rebuild the main image: one product, high contrast, benefit legible at "
                  "thumbnail size. Move the strongest differentiator into the first 60 title "
                  "characters. Hold bids constant during the test so the result is readable.",
            "R2": "Rewrite bullets to lead with benefit rather than ingredient. Add a comparison "
                  "module and a module built for a first-time buyer. Add an image answering the "
                  "single most common question in the term set.",
            "R3": "Check delivery speed against the category, confirm the price at checkout "
                  "matches the price on the results page, and verify stock coverage.",
        }[idx]
        out.append(Action(
            title=f"Fix the {label} for {', '.join(t.lower() for t in themes)}",
            lever=lever, horizon=SOON, orders=direct, confidence=0.8,
            evidence=ev, do=do, claims=set(themes),
            unquantified=no_cap, critical=bool(no_cap and severe),
        ))
    return out


def detect_visibility_scale(res: dict, claimed: set) -> list[Action]:
    """Categories that convert far above their visibility. Cheapest growth available."""
    topp, tpanel = res["theme_opp"], res["theme_panel"]
    if topp.empty:
        return []
    cands = topp[(topp.FE > 1.3) & (topp.IS < 8) & (topp.purch_visibility > 3)
                 & (~topp.theme.isin(claimed)) & (topp.theme != "OTHER")]
    rows = []
    for _, r in cands.sort_values("purch_visibility", ascending=False).iterrows():
        g = tpanel[tpanel.theme == r.theme].sort_values("period")
        growth = 100 * (g.SQV.iloc[-3:].mean() / g.SQV.iloc[:3].mean() - 1) if len(g) >= 6 else np.nan
        # A category with shrinking demand is not a scaling opportunity.
        if pd.notna(growth) and growth < 0:
            continue
        rows.append((r, growth))
    if not rows:
        return []
    ev = [f"{r.theme}: we take {r.PS:.1f}% of purchases from {r.IS:.1f}% of impressions "
          f"(efficiency {r.FE:.2f})" + (f", demand {g:+.0f}%" if pd.notna(g) else "")
          for r, g in rows]
    ev.append("We win overwhelmingly whenever we are seen. We are simply not seen enough.")
    total = sum(r.purch_visibility for r, _ in rows)
    names = [r.theme.lower() for r, _ in rows]
    return [Action(
        title=f"Scale visibility in {', '.join(names[:-1]) + ' and ' + names[-1] if len(names) > 1 else names[0]}",
        claims={r.theme for r, _ in rows},
        lever="PPC bid / budget", horizon=NOW, orders=float(total), confidence=0.8,
        evidence=ev,
        do="Dedicated exact-match campaigns on each, bid aggressively for eight weeks while "
           "acquisition is still cheap, and add the query language to titles and backend terms.",
    )]


def detect_competitor_waste(res: dict) -> list[Action]:
    """Spend against rival brand terms that converts far below normal."""
    sqp, latest = res["sqp"], res["latest"]
    c = sqp[(sqp.query_type == "COMPETITOR") & (sqp.period == latest)]
    ins = sqp[res["mask_inscope"] & (sqp.period == latest)]
    if c.empty or ins.empty:
        return []
    cpp = c[BRAND["Clicks"]].sum() / max(1, c[BRAND["Purchases"]].sum())
    npp = ins[BRAND["Clicks"]].sum() / max(1, ins[BRAND["Purchases"]].sum())
    if cpp < npp * 1.3:
        return []
    top = (c.groupby("competitor")[TOTAL["Purchases"]].sum()
            .sort_values(ascending=False).head(3))
    return [Action(
        title="Stop paying for rival brand searches",
        lever="PPC negative", horizon=NOW, orders=0.0, unquantified=True, confidence=0.85,
        evidence=[
            f"We put {c[BRAND['Impressions']].sum():,.0f} impressions a month against competitor "
            f"brand terms and get {c[BRAND['Purchases']].sum():,.0f} orders.",
            f"That is {cpp:.1f} clicks per order against {npp:.1f} on our normal traffic, so this "
            f"traffic is {100*(cpp/npp-1):.0f}% less efficient than everything else we buy.",
            f"We capture {100*c[BRAND['Purchases']].sum()/c[TOTAL['Purchases']].sum():.1f}% of a "
            f"{c[TOTAL['Purchases']].sum():,.0f}-order monthly market searching for someone else "
            f"by name. Largest: {', '.join(top.index)}.",
        ],
        do=f"Cut bids on competitor terms by 50% and hold four weeks, then redeploy the budget. "
           f"Keep a small defensive presence on {top.index[0]} only.",
    )]


def detect_asin_tile(res: dict) -> list[Action]:
    """ASINs whose page converts well but whose search tile underperforms."""
    scp, latest = res["scp"], res["latest"]
    if scp is None or scp.empty:
        return []
    # No headroom means no point improving the tile: the brand already takes
    # essentially everything available.
    ins = res["sqp"][res["mask_inscope"] & (res["sqp"].period == latest)]
    if len(ins):
        overall = aggregate(ins)
        if pd.notna(overall["PS"]) and overall["PS"] > 90:
            return []
    s = scp[scp.period == latest].copy()
    port_ctr = 100 * s["Clicks: Clicks"].sum() / s["Impressions: Impressions"].sum()
    port_cvr = 100 * s["Purchases: Purchases"].sum() / s["Clicks: Clicks"].sum()
    s["gain"] = ((s["Impressions: Impressions"] * port_ctr / 100 - s["Clicks: Clicks"])
                 * s["Purchases: Conversion Rate %"] / 100 * 0.8)
    # Both sides of the contrast must be clear: a genuinely weak tile AND a
    # genuinely strong page. Marginal cases produce inflated, unearned totals.
    cand = s[(s["Clicks: Click Rate (CTR)"] < port_ctr * 0.75)
             & (s["Purchases: Conversion Rate %"] > port_cvr * 1.15)
             & (s["gain"] > 10)].nlargest(3, "gain")
    if cand.empty:
        return []
    ev = [f"{r.ASIN}: click rate {r['Clicks: Click Rate (CTR)']:.2f}% against a "
          f"{port_ctr:.2f}% portfolio average, but page conversion "
          f"{r['Purchases: Conversion Rate %']:.1f}% against {port_cvr:.1f}%. "
          f"Worth {r.gain:.0f} orders a month at portfolio click rate."
          for _, r in cand.iterrows()]
    ev.append("The product and the page are working. The search result tile is not doing them justice.")
    return [Action(
        title=f"Replace the main image on {', '.join(cand.ASIN)}",
        lever="Hero image", horizon=SOON, orders=float(cand.gain.sum()), confidence=0.7,
        evidence=ev,
        do="New main image tested at thumbnail size before upload. Check the first 60 title "
           "characters carry the strongest differentiator.",
    )]


def detect_structural_absence(res: dict) -> list[Action]:
    """
    Large, growing categories where the tile fails outright and price is the
    likely cause. Not fixable with copy: needs a product or price answer.
    """
    topp, tpanel = res["theme_opp"], res["theme_panel"]
    if topp.empty:
        return []
    out = []
    for _, r in topp.iterrows():
        g = tpanel[tpanel.theme == r.theme].sort_values("period")
        if len(g) < 12 or r.TP < 300 or r.PS > 3 or r.R1 > 0.75:
            continue
        below = int((g.R1 < 1.0).sum())
        if below < len(g) * 0.8:
            continue
        avg3, peak = g.TP.iloc[-3:].mean(), g.TP.max()
        growth = 100 * (g.TP.iloc[-3:].mean() / g.TP.iloc[:3].mean() - 1)
        # Ceiling the target twice over. First by what the brand demonstrably
        # achieves in its own strongest categories, not a flat assumption.
        # Second by the size of the existing business: one new product cannot
        # credibly be projected to multiply the whole brand, however large the
        # market is. Without the second cap a huge adjacent market produces a
        # number that dwarfs everything the brand actually does.
        demonstrated = float(np.nanpercentile(topp["PS"].dropna(), 75)) / 100 if len(topp) else 0.05
        target = min(0.05, max(demonstrated, 0.01))
        current_business = float(topp["BP"].sum())
        at5 = min(target * avg3 - r.BP, current_business)
        price_gap = r.get("PIc", np.nan)
        out.append(Action(
            title=f"Build a competitive {r.theme.lower()} offer, or exit the category",
            lever="New variant", horizon=YEAR, orders=float(max(at5, 0)), confidence=0.6,
            claims={r.theme},
            evidence=[
                f"Market grew {growth:.0f}%, now averaging {avg3:,.0f} orders a month and peaking "
                f"at {peak:,.0f} in {g.loc[g.TP.idxmax(),'period']}.",
                f"We hold {r.PS:.2f}% share.",
                f"Our tile score has been {r.R1:.2f} or below in {below} of {len(g)} months, so "
                f"shoppers see us and skip us. No amount of better copy fixes that.",
                f"Sizing assumes we reach {100*target:.1f}% share, which is what we already "
                f"achieve in our strongest categories, and is capped at the size of our current "
                f"in-scope business. Treat it as a business case to test, not a forecast.",
            ],
            do=f"Decide whether to build a {r.theme.lower()} SKU priced within roughly 20% of the "
               f"market median, or exit and stop spending against the category. If building, it "
               f"must be live and reviewed before the demand window opens.",
        ))
    return out


def detect_protect(res: dict) -> list[Action]:
    """Categories winning significantly. Defend rather than optimise."""
    tmove, topp = res["theme_moves"], res["theme_opp"]
    if tmove.empty:
        return []
    out = []
    for _, r in tmove[tmove.significant & (tmove.delta_pp > 0)].nlargest(2, "market_end").iterrows():
        cur = topp[topp.theme == r.theme]
        base = float(cur.BP.iloc[0]) if len(cur) else 0.0
        out.append(Action(
            title=f"Protect {r.theme.lower()}", lever="PPC bid / budget", horizon=YEAR,
            orders=0.0, unquantified=True, confidence=0.85, defends=base, claims={r.theme},
            evidence=[
                f"Share up from {r.PS_start:.1f}% to {r.PS_end:.1f}% (z = {r.z:.2f}) while the "
                f"market grew {r.market_growth_pct:.0f}% and our sales grew "
                f"{r.brand_growth_pct:.0f}%.",
                f"Currently {base:,.0f} orders a month. Nothing needs fixing here.",
            ],
            do="Hold bids, review share monthly, and treat a 3-point drop as a trigger to investigate.",
        ))
    return out


# Order matters: detectors that make a specific, well-evidenced claim on a
# category run before the broad visibility sweep, so the sweep cannot re-sell
# the same headroom.
DETECTORS = [detect_structural_absence_overall, detect_brand_defence, detect_protect, detect_share_restoration,
             detect_structural_absence, detect_stage_repair, detect_visibility_scale,
             detect_competitor_waste, detect_asin_tile]

# Which detectors need to know what has already been claimed.
CLAIM_AWARE = {"detect_visibility_scale", "detect_stage_repair"}


def build_actions(res: dict) -> list[Action]:
    out, claimed = [], set()
    for fn in DETECTORS:
        try:
            got = fn(res, claimed) if fn.__name__ in CLAIM_AWARE else fn(res)
        except Exception as exc:                       # a detector must never kill the run
            print(f"  [warn] {fn.__name__} skipped: {exc}")
            continue
        for a in got:
            # Only a quantified action consumes a category. Claims exist to stop
            # the same orders being counted twice, and an action projecting no
            # orders cannot double-count anything. Letting it claim would
            # silently suppress real findings on the same category: a "protect"
            # note would hide a severe conversion deficit sitting underneath it.
            if not a.unquantified:
                claimed |= a.claims
        out.extend(got)
    return sorted(out, key=lambda a: -a.priority)
