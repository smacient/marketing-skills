"""
Theme aggregation.

The single highest-leverage structural step in the whole design, for three
independent reasons:

  1. Statistical power. Sample size rises by one to two orders of magnitude,
     which is what converts monthly share movement from undetectable to
     routine. At query level on this data, zero movers clear the noise floor.
  2. Panel stability. Theme membership survives the query churn that a
     top-N-capped export produces every month.
  3. Ownership. A theme maps to a product line, a campaign, an A+ brief. A
     query maps to nothing anyone owns.

Never average shares across queries. Sum numerators, sum denominators, divide.
Averaging gives a 50-search query the same weight as a 50,000-search one and
reliably concludes you are strong where you are weak.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from sqp_lib import BRAND, TOTAL, aggregate, share_change_z


def assign_themes(df: pd.DataFrame, themes: dict[str, str],
                  fallback: str = "OTHER") -> pd.DataFrame:
    """Rule-based token matching. First match wins, so order narrow to broad."""
    out = df.copy()
    theme = pd.Series(fallback, index=out.index, dtype=object)
    unset = pd.Series(True, index=out.index)
    for label, pattern in themes.items():
        hit = unset & out["q"].str.contains(pattern, case=False, regex=True, na=False)
        theme[hit] = label
        unset &= ~hit
    out["theme"] = theme
    return out


from sqp_lib import AGG_FIELDS


def theme_panel(df: pd.DataFrame, mask: pd.Series | None = None) -> pd.DataFrame:
    """Theme x period funnel. This is the series that is actually trendable."""
    d = df if mask is None else df[mask]
    if len(d) == 0 or "theme" not in d.columns:
        return pd.DataFrame(columns=["theme", "period"] + AGG_FIELDS)
    return (d.groupby(["theme", "period"]).apply(aggregate, include_groups=False)
             .reset_index())


MIN_THEME_PURCHASES = 30   # market purchases per period before a theme is reportable


def reportable(panel: pd.DataFrame, latest: str,
               min_purch: int = MIN_THEME_PURCHASES) -> set:
    """
    Themes large enough to report. Below this, ratios are built on so few
    observations that they produce nonsense (a stage score of 76 on two
    searches) and would dominate any ranking sorted by score.
    """
    if panel is None or panel.empty or "TP" not in panel.columns:
        return set()
    cur = panel[panel["period"] == latest]
    keep = set(cur[cur["TP"].fillna(0) >= min_purch]["theme"])
    # The fallback bucket is a residual whose membership churns freely, so its
    # "share" is composition rather than performance. Report its size as a
    # taxonomy-coverage check, never as a trend.
    return keep - {"OTHER"}


def theme_trend(panel: pd.DataFrame, periods: list[str],
                metric: str = "PS", n_col: str = "TP") -> pd.DataFrame:
    """
    Significance-tested theme movement, first period against last.

    At theme level the market counts are large enough that a two-proportion
    test has real power, which is the whole point of aggregating.
    """
    if len(periods) < 2 or panel is None or panel.empty or n_col not in panel.columns:
        return pd.DataFrame()
    p0, p1 = periods[0], periods[-1]
    rows = []
    for theme, g in panel.groupby("theme"):
        g = g.set_index("period")
        if p0 not in g.index or p1 not in g.index:
            continue
        a, b = g.loc[p0], g.loc[p1]
        z = share_change_z(a[metric], a[n_col], b[metric], b[n_col])
        rows.append({
            "theme": theme,
            f"{metric}_start": a[metric], f"{metric}_end": b[metric],
            "delta_pp": b[metric] - a[metric],
            "market_start": a[n_col], "market_end": b[n_col],
            "market_growth_pct": 100 * (b[n_col] / a[n_col] - 1) if a[n_col] else np.nan,
            "brand_start": a["BP"], "brand_end": b["BP"],
            "brand_growth_pct": 100 * (b["BP"] / a["BP"] - 1) if a["BP"] else np.nan,
            "R1_end": b["R1"], "R2_end": b["R2"], "R3_end": b["R3"], "FE_end": b["FE"],
            "z": z, "significant": bool(pd.notna(z) and abs(z) > 1.96),
            "direction": "UP" if b[metric] > a[metric] else "DOWN",
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    # Purchases at stake if the theme returned to its starting share.
    out["purchases_at_stake"] = (out["delta_pp"].abs() * out["market_end"] / 100.0)
    return out.sort_values("purchases_at_stake", ascending=False)


def theme_opportunity(panel: pd.DataFrame, latest: str, decay: float = 0.80,
                      is_ceiling: float = 8.0) -> pd.DataFrame:
    """
    Stage repair at theme level, expressed in additional monthly purchases.

    Target for each stage index is the brand's OWN demonstrated capability
    across its themes (the 75th percentile), not a competitor's number. If the
    brand never exceeds 1.0 anywhere, projecting 1.2 is fantasy.

    Not converted to money: contribution margin varies by brand and is rarely
    known per ASIN, so a profit figure would hide an unverifiable assumption
    inside a precise-looking number. Purchases are observed directly and every
    reader can apply their own economics.
    """
    if panel is None or panel.empty or "IS" not in panel.columns:
        return pd.DataFrame()
    cur = panel[panel["period"] == latest].copy()
    if cur.empty or cur[["R1", "R2", "R3"]].isna().all().all():
        return pd.DataFrame()

    tgt = {c: min(1.0, np.nanpercentile(cur[c].replace([np.inf, -np.inf], np.nan).dropna(), 75))
           for c in ("R1", "R2", "R3")}

    R1n = np.maximum(cur["R1"], tgt["R1"])
    R2n = np.maximum(cur["R2"], tgt["R2"])
    R3n = np.maximum(cur["R3"], tgt["R3"])

    cur["R1_target"], cur["R2_target"], cur["R3_target"] = tgt["R1"], tgt["R2"], tgt["R3"]
    # Sizing uses the brand's own 75th percentile as the ceiling, which is the
    # right guard against fantasy. But a brand that is weak at a stage in every
    # category has a ceiling below market, so the model projects it to stay
    # weak and the fix sizes to nothing. Flag that case: it is a finding in its
    # own right, not an absence of one.
    for c in ("R1", "R2", "R3"):
        cur[f"{c}_no_capability"] = tgt[c] < 0.85

    # What repairing each stage alone is worth, holding the others where they are.
    for tag, (a, b, c) in {"serp": (R1n, cur["R2"], cur["R3"]),
                           "pdp": (cur["R1"], R2n, cur["R3"]),
                           "close": (cur["R1"], cur["R2"], R3n)}.items():
        ps_new = cur["IS"] * a * b * c
        gain = (ps_new - cur["PS"]).clip(lower=0) * decay
        cur[f"dPS_{tag}_pp"] = gain
        cur[f"purch_{tag}"] = cur["TP"] * gain / 100.0

    # And what closing the visibility gap alone is worth, capped by the
    # structural per-ASIN impression share ceiling.
    is_new = np.minimum(cur["IS"] * 1.5, is_ceiling)
    ps_vis = is_new * cur["R1"] * cur["R2"] * cur["R3"]
    cur["dPS_visibility_pp"] = (ps_vis - cur["PS"]).clip(lower=0) * decay
    cur["purch_visibility"] = cur["TP"] * cur["dPS_visibility_pp"] / 100.0

    stages = ["purch_serp", "purch_pdp", "purch_close"]
    cur["purch_best_stage"] = cur[stages].max(axis=1)
    cur["best_stage"] = cur[stages].idxmax(axis=1).str.replace("purch_", "")
    cur["purch_total_addressable"] = cur["purch_best_stage"] + cur["purch_visibility"]
    return cur.sort_values("purch_total_addressable", ascending=False)


# Brand-side minimums before a stage score means anything. Each stage divides
# by the brand's own count at the previous stage, so a score computed on a
# handful of clicks or cart adds is arithmetic noise, not performance.
STAGE_GATES = {"R1": ("BI", 500), "R2": ("BC", 40), "R3": ("BA", 20)}


def theme_r2_gap(panel: pd.DataFrame, latest: str) -> pd.DataFrame:
    """
    Isolate where the brand under-converts against market at each stage, and
    how persistent that gap has been.

    Persistence matters more than depth: a stage score that has sat below
    market for twelve straight months is a structural property of the offer,
    not a bad month. But only months with enough brand-side volume are counted,
    otherwise a brand with almost no sales appears to have a deficit everywhere
    purely because its ratios are built on single-digit counts.
    """
    if panel is None or panel.empty or "theme" not in panel.columns:
        return pd.DataFrame(columns=["theme", "periods", "market_purch_latest", "brand_purch_latest"] + [f"{i}_{k}" for i in ("R1", "R2", "R3") for k in ("latest", "mean", "months_measured", "months_below_1", "persistent_deficit", "no_capability")])
    rows = []
    for theme, g in panel.groupby("theme"):
        g = g.sort_values("period")
        cur = g[g["period"] == latest]
        if cur.empty:
            continue
        cur = cur.iloc[0]
        rec = {"theme": theme, "periods": len(g), "market_purch_latest": cur["TP"],
               "brand_purch_latest": cur["BP"]}
        for idx, (col, minimum) in STAGE_GATES.items():
            ok = g[g[col] >= minimum]
            vals = ok[idx].dropna()
            rec[f"{idx}_latest"] = cur[idx]
            rec[f"{idx}_mean"] = vals.mean() if len(vals) else np.nan
            rec[f"{idx}_months_measured"] = len(vals)
            rec[f"{idx}_months_below_1"] = int((vals < 1.0).sum()) if len(vals) else 0
            # Needs both a persistent deficit AND enough measurable months.
            rec[f"{idx}_persistent_deficit"] = bool(
                len(vals) >= 6 and (vals < 1.0).mean() >= 0.75)
        rows.append(rec)
    if not rows:
        return pd.DataFrame(columns=["theme", "periods", "market_purch_latest", "brand_purch_latest"] + [f"{i}_{k}" for i in ("R1", "R2", "R3") for k in ("latest", "mean", "months_measured", "months_below_1", "persistent_deficit", "no_capability")])
    return pd.DataFrame(rows).sort_values("market_purch_latest", ascending=False)
