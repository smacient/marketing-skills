"""
Diagnosis engine: turns the stage indices into a named problem or success mode.

Runs a fixed resolution order. Operational blockers and structural mismatch
mimic every funnel failure, so they must be tested before the funnel stages.
Stopping at the first hit gives the PRIMARY diagnosis; the rest are recorded
as secondary labels.

Every diagnosis carries an evidence class:
  SQP           provable from this report alone
  SQP+SCP       needs the Search Catalog Performance report
  SQP+EXTERNAL  needs ad, inventory, buy box, or review data the report lacks
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Interpretation bands for the stage indices, used consistently everywhere.
SEVERE, DEFICIT, PARITY_LO, PARITY_HI, ADVANTAGE = 0.60, 0.85, 0.85, 1.15, 1.50


def band(x: float) -> str:
    if pd.isna(x):
        return "n/a"
    if x < SEVERE:
        return "severe deficit"
    if x < DEFICIT:
        return "deficit"
    if x <= PARITY_HI:
        return "parity"
    if x <= ADVANTAGE:
        return "advantage"
    return "strong advantage"


CATALOGUE = {
    # code: (family, label, evidence class, headline action lever)
    "OUT_OF_SCOPE":       ("relevance", "Out of relevance range", "SQP", "none - exclude"),
    "MISMATCH":           ("relevance", "Keyword-product mismatch", "SQP", "PPC negative"),
    "INSUFFICIENT":       ("data", "Insufficient volume to diagnose", "SQP", "cluster or monitor"),
    "VISIBILITY_GAP":     ("visibility", "Visibility gap", "SQP", "PPC + listing"),
    "SATURATION":         ("visibility", "Impression share saturation", "SQP", "reduce spend"),
    "AD_INFLATED":        ("visibility", "Ad-inflated impression share", "SQP+EXTERNAL", "audit spend"),
    "PRICE_BARRIER":      ("serp", "Price barrier at SERP", "SQP", "price / promo"),
    "CTR_PROBLEM":        ("serp", "Creative CTR problem", "SQP", "hero image / title"),
    "PDP_PROBLEM":        ("pdp", "PDP persuasion failure", "SQP", "A+ / bullets / images"),
    "PRICE_SHOCK":        ("pdp", "Price shock between SERP and cart", "SQP", "catalog / coupon"),
    "CHECKOUT_FRICTION":  ("purchase", "Checkout friction", "SQP", "offer / fulfilment"),
    "DELIVERY_SPEED":     ("purchase", "Delivery speed loss", "SQP+SCP", "fulfilment"),
    "HIDDEN_GEM":         ("success", "Hidden gem", "SQP", "scale visibility"),
    "CONVERSION_WINNER":  ("success", "Conversion winner", "SQP", "scale visibility"),
    "CATEGORY_CAPTAIN":   ("success", "Category captain", "SQP", "defend"),
    "PROFITABLE_PREMIUM": ("success", "Profitable premium", "SQP", "scale, do not cut price"),
    "EFFICIENT_DEFENDER": ("success", "Efficient brand defender", "SQP", "cap brand spend"),
    "STEADY":             ("neutral", "At market, no clear lever", "SQP", "monitor"),
}


def diagnose_row(r, price_barrier: float = 1.15) -> tuple[str, list[str], float]:
    """
    Returns (primary_code, secondary_codes, confidence 0-1).

    Confidence = sample adequacy x diagnostic clarity. Clarity is high when one
    stage index is clearly broken and the others sit at parity, low when two
    stages are ambiguous or the diagnosis needs data we do not have.
    """
    sec: list[str] = []
    R1, R2, R3, FE = r.get("R1"), r.get("R2"), r.get("R3"), r.get("FE")
    IS, PS = r.get("IS"), r.get("PS")
    PIc, PIa, PIp = r.get("PIc"), r.get("PIa"), r.get("PIp")

    # --- 1. Relevance. Structural, tested before anything else. ------------
    if not r.get("in_scope", True):
        return "OUT_OF_SCOPE", sec, 0.95

    # Mismatch: fails at BOTH the tile and the page. A pure CTR problem has a
    # healthy R2 (people who do click, do buy). That contrast is the test.
    if (pd.notna(R1) and pd.notna(R2) and R1 < 0.85 and R2 < 0.90
            and pd.notna(FE) and FE < 0.9):
        return "MISMATCH", sec, 0.80

    # --- 2. Reliability. -----------------------------------------------------
    if not r.get("diagnosable", False):
        return "INSUFFICIENT", sec, 0.20

    # --- 3. Success modes worth catching before failure modes. ---------------
    if (r.get("query_type") == "BRANDED" and pd.notna(IS) and IS > 80
            and pd.notna(R1) and R1 > 1.3):
        return "EFFICIENT_DEFENDER", sec, 0.85

    if pd.notna(PS) and PS >= 25 and pd.notna(FE) and FE >= 1.2:
        if pd.notna(IS) and IS >= 6:
            sec.append("SATURATION")
        return "CATEGORY_CAPTAIN", sec, 0.85

    # --- 4. Visibility. ------------------------------------------------------
    if pd.notna(IS) and IS >= 6 and pd.notna(R1) and R1 >= 1.0:
        return "SATURATION", sec, 0.75

    if pd.notna(IS) and IS >= 4 and pd.notna(R1) and R1 <= 0.75:
        sec.append("AD_INFLATED")

    # --- 5. Stage indices, in funnel order. ----------------------------------
    if pd.notna(R1) and R1 < 0.85 and r.get("ok_R1", False):
        if pd.notna(PIc) and PIc > price_barrier:
            return "PRICE_BARRIER", sec, 0.80
        return "CTR_PROBLEM", sec, 0.75

    if pd.notna(R2) and R2 < 0.85 and r.get("ok_R2", False):
        # Price worsening between click and cart points at the offer on the
        # page rather than the content on it.
        if pd.notna(PIa) and pd.notna(PIc) and PIa > PIc * 1.05:
            return "PRICE_SHOCK", sec, 0.70
        return "PDP_PROBLEM", sec, 0.80

    if pd.notna(R3) and R3 < 0.85 and r.get("ok_R3", False):
        if pd.notna(r.get("FSM_market")) and r["FSM_market"] > 0.40:
            sec.append("DELIVERY_SPEED")
        if pd.notna(PIp) and pd.notna(PIa) and PIp > PIa * 1.05:
            sec.append("PRICE_BARRIER")
        return "CHECKOUT_FRICTION", sec, 0.70

    # --- 6. Success modes needing healthy indices. ---------------------------
    if (pd.notna(IS) and IS < 3 and pd.notna(FE) and FE > 1.5
            and pd.notna(R1) and R1 >= 1.1 and pd.notna(R2) and R2 >= 0.95):
        return "HIDDEN_GEM", sec, 0.85

    # Nothing is broken; there simply is not enough visibility. Distinct from a
    # hidden gem, which additionally converts far above its visibility.
    if pd.notna(IS) and IS < 3 and pd.notna(R1) and R1 >= 0.95:
        return "VISIBILITY_GAP", sec, 0.75

    if pd.notna(PIp) and PIp > 1.15 and pd.notna(R2) and R2 >= 1.1 and pd.notna(R3) and R3 >= 0.95:
        return "PROFITABLE_PREMIUM", sec, 0.80

    if pd.notna(R2) and R2 >= 1.2 and pd.notna(R3) and R3 >= 1.0:
        return "CONVERSION_WINNER", sec, 0.80

    return "STEADY", sec, 0.55


def diagnose(df: pd.DataFrame, price_barrier: float = 1.15) -> pd.DataFrame:
    """Apply the engine to a single-period frame."""
    out = df.copy()
    res = out.apply(lambda r: diagnose_row(r, price_barrier), axis=1)
    out["dx"] = [x[0] for x in res]
    out["dx_secondary"] = [",".join(x[1]) for x in res]
    out["dx_confidence"] = [x[2] for x in res]
    out["dx_family"] = out["dx"].map(lambda c: CATALOGUE[c][0])
    out["dx_label"] = out["dx"].map(lambda c: CATALOGUE[c][1])
    out["dx_evidence"] = out["dx"].map(lambda c: CATALOGUE[c][2])
    out["dx_lever"] = out["dx"].map(lambda c: CATALOGUE[c][3])
    return out


# ---------------------------------------------------------------------------
# Opportunity sizing
# ---------------------------------------------------------------------------

def stage_repair_target(df: pd.DataFrame, index_col: str, group_col: str | None = None,
                        pct: float = 75) -> pd.Series:
    """
    The ceiling is the brand's OWN demonstrated capability, not the market
    leader's share. If your PDP converts at 1.1x market on your best quarter of
    queries, that is what you can plausibly reach elsewhere. This single rule
    removes most of the fantasy from sizing.
    """
    vals = df[index_col].replace([np.inf, -np.inf], np.nan)
    if group_col and group_col in df.columns:
        tgt = df.groupby(group_col)[index_col].transform(
            lambda s: np.nanpercentile(s.dropna(), pct) if s.notna().sum() >= 8 else np.nan)
        tgt = tgt.fillna(np.nanpercentile(vals.dropna(), pct))
    else:
        tgt = pd.Series(np.nanpercentile(vals.dropna(), pct), index=df.index)
    return tgt.clip(upper=1.0) if index_col in ("R1", "R2", "R3") else tgt


def size_opportunity(df: pd.DataFrame, decay: float = 0.80,
                     is_lift_cap: float = 2.0, is_ceiling: float = 6.0) -> pd.DataFrame:
    """
    Stage repair, not gap closure.

        PS_current   = IS * R1 * R2 * R3
        PS_projected = IS' * R1' * R2' * R3'

    Only the diagnosed stage moves; everything else is held where it actually
    is. Output is **additional purchases per month**, with a floor-to-ceiling
    range rather than a point estimate.

    Deliberately not expressed in money. Contribution margin varies widely by
    brand and is rarely known at ASIN level, so converting to profit would bury
    an unverifiable assumption inside a number that looks precise. Purchases
    are directly observed, marketplace-agnostic, and every reader can apply
    their own economics to them.

    Note these are purchase ACTIONS, not units: one order of three bottles
    counts once. Anyone who knows their units per order can convert.
    """
    d = df.copy()

    tgt_R1 = stage_repair_target(d, "R1", "segment")
    tgt_R2 = stage_repair_target(d, "R2", "segment")
    tgt_R3 = stage_repair_target(d, "R3", "segment")

    R1n, R2n, R3n, ISn = d["R1"].copy(), d["R2"].copy(), d["R3"].copy(), d["IS"].copy()

    fix_serp = d["dx"].isin(["CTR_PROBLEM", "PRICE_BARRIER"])
    fix_pdp = d["dx"].isin(["PDP_PROBLEM", "PRICE_SHOCK"])
    fix_close = d["dx"].isin(["CHECKOUT_FRICTION"])
    fix_vis = d["dx"].isin(["VISIBILITY_GAP", "HIDDEN_GEM", "CONVERSION_WINNER", "PROFITABLE_PREMIUM"])

    R1n = R1n.where(~fix_serp, np.maximum(R1n, tgt_R1))
    R2n = R2n.where(~fix_pdp, np.maximum(R2n, tgt_R2))
    R3n = R3n.where(~fix_close, np.maximum(R3n, tgt_R3))
    # Visibility lift is capped both by a realistic per-period move and by the
    # structural per-ASIN impression share ceiling.
    ISn = ISn.where(~fix_vis, np.minimum(ISn + is_lift_cap, is_ceiling))

    d["PS_projected"] = ISn * R1n * R2n * R3n
    d["dPS_pp"] = (d["PS_projected"] - d["PS"]).clip(lower=0)
    d["dPS_net_pp"] = d["dPS_pp"] * decay

    d["d_purchases"] = d["Purchases: Total Count"] * d["dPS_net_pp"] / 100.0
    d["expected_purchases"] = d["d_purchases"] * d["dx_confidence"]

    # Floor uses a harsher decay, ceiling a softer one.
    d["purch_floor"] = d["d_purchases"] * 0.70 / decay
    d["purch_ceiling"] = d["d_purchases"] * 0.90 / decay
    return d


# Realisation probability and effort by lever, stated openly rather than
# buried in a spreadsheet.
REALISATION = {
    "PPC bid / budget": (0.85, 1.5, 1),
    "PPC negative": (0.90, 1.0, 1),
    "Price / coupon": (0.75, 1.5, 2),
    "Backend keywords": (0.70, 3.0, 2),
    "Title rewrite": (0.55, 4.5, 3),
    "Hero image": (0.50, 3.0, 3),
    "A+ / bullets": (0.45, 4.5, 3),
    "Fulfilment / stock": (0.80, 3.0, 5),
    "Variation restructure": (0.60, 6.0, 5),
    "New variant": (0.35, 10.0, 8),
    "Reviews": (0.30, 12.0, 8),
    "NPD": (0.20, 19.0, 13),
}

DX_TO_LEVER = {
    "VISIBILITY_GAP": "PPC bid / budget",
    "HIDDEN_GEM": "PPC bid / budget",
    "CONVERSION_WINNER": "PPC bid / budget",
    "PROFITABLE_PREMIUM": "PPC bid / budget",
    "CTR_PROBLEM": "Hero image",
    "PRICE_BARRIER": "Price / coupon",
    "PDP_PROBLEM": "A+ / bullets",
    "PRICE_SHOCK": "Price / coupon",
    "CHECKOUT_FRICTION": "Fulfilment / stock",
    "DELIVERY_SPEED": "Fulfilment / stock",
    "MISMATCH": "PPC negative",
    "SATURATION": "PPC bid / budget",
    "CATEGORY_CAPTAIN": "PPC bid / budget",
    "EFFICIENT_DEFENDER": "PPC bid / budget",
}


def priority_score(expected_purchases: float, confidence: float, lever: str) -> float:
    """
    Expected additional monthly purchases per unit of effort, discounted by how
    long the fix takes to land. Square root on weeks so speed matters without
    dominating.
    """
    prob, weeks, effort = REALISATION.get(lever, (0.5, 4.0, 3))
    if pd.isna(expected_purchases) or expected_purchases <= 0:
        return 0.0
    return (expected_purchases * prob * confidence) / (effort * np.sqrt(weeks))
