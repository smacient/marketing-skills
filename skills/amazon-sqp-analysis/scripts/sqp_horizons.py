"""
Horizon analyses: what becomes knowable as the data history grows.

H1  single period   cross-sectional only
H2  three periods   direction of travel, entry/exit, export integrity
H3  twelve periods  seasonality, decomposition, lifecycle, volatility
H4  thirteen plus   year-over-year

Governing principle: shares are the trendable unit, counts are not. Brand share
is a ratio against the same-period market, so any shock hitting all sellers
equally cancels out of numerator and denominator. Absolute counts carry the
full seasonal signal and mean nothing until deseasonalized.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sqp_lib import (BRAND, TOTAL, aggregate, decompose_growth,
                     dilution_vs_displacement, share_change_z)


# ---------------------------------------------------------------------------
# H2: direction of travel
# ---------------------------------------------------------------------------

def monthly_series(df: pd.DataFrame, mask: pd.Series | None = None) -> pd.DataFrame:
    """Aggregate funnel per period. Optionally restricted to a query subset."""
    d = df if mask is None else df[mask]
    return d.groupby("period").apply(aggregate, include_groups=False).sort_index()


def persistence_signals(df: pd.DataFrame, periods: list[str],
                        metric: str = "PS", min_n: int = 400) -> pd.DataFrame:
    """
    The three-period decision rule.

    A signal requires BOTH persistence (two consecutive same-direction moves)
    AND magnitude clearing the noise floor. Two consecutive moves alone is a
    coin flip at p=0.50 and is not evidence of anything.
    """
    if len(periods) < 3:
        return pd.DataFrame()
    p1, p2, p3 = periods[-3:]
    cols = ["q", "Search Query", metric, TOTAL["Purchases"], BRAND["Purchases"], "segment", "query_type"]
    # Normalisation can collapse two raw strings onto one key, so keep the
    # best-ranked row per key rather than letting .loc return a frame.
    f = {p: (df[df["period"] == p]
             .sort_values("Search Query Score")
             .drop_duplicates("q", keep="first")[cols]
             .set_index("q"))
         for p in (p1, p2, p3)}

    common = set(f[p1].index) & set(f[p2].index) & set(f[p3].index)
    rows = []
    for q in common:
        a, b, c = f[p1].loc[q], f[p2].loc[q], f[p3].loc[q]
        s1, s2, s3 = a[metric], b[metric], c[metric]
        n1, n3 = a[TOTAL["Purchases"]], c[TOTAL["Purchases"]]
        if pd.isna(s1) or pd.isna(s3):
            continue
        d1, d2 = s2 - s1, s3 - s2
        if np.sign(d1) != np.sign(d2) or d1 == 0:
            continue
        z = share_change_z(s1, n1, s3, n3)
        rows.append({
            "q": q, "Search Query": c["Search Query"], "segment": c["segment"],
            "query_type": c["query_type"],
            f"{metric}_p1": s1, f"{metric}_p2": s2, f"{metric}_p3": s3,
            "delta_pp": s3 - s1, "direction": "UP" if d1 > 0 else "DOWN",
            "market_purch_now": n3, "z": z,
            "gated": bool(min(n1, n3) >= min_n),
            "significant": bool(pd.notna(z) and abs(z) > 1.96 and min(n1, n3) >= min_n),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["abs_impact"] = out["delta_pp"].abs() * out["market_purch_now"] / 100.0
    return out.sort_values("abs_impact", ascending=False)


def entry_exit(df: pd.DataFrame, periods: list[str], top_n_rank: int = 300) -> dict:
    """
    Query entry and exit between the last two periods.

    Because Search Query Score ranks by BRAND performance rather than market
    volume, a query leaving the report means your performance on it fell, not
    that the market shrank. That makes exit a stronger brand signal than it
    would be on a volume-ranked report, and it is invisible to any comparison
    that only looks at rows present in both months.
    """
    if len(periods) < 2:
        return {}
    prev, cur = periods[-2], periods[-1]
    a = df[df["period"] == prev]
    b = df[df["period"] == cur]
    sa, sb = set(a["q"]), set(b["q"])

    exited = a[a["q"].isin(sa - sb)].copy()
    entered = b[b["q"].isin(sb - sa)].copy()

    # Severity keyed on prior rank, not on volume: rank reflects how much of
    # the brand's funnel the query carried.
    exited["severity"] = np.where(
        exited["Search Query Score"] <= top_n_rank, "HIGH", "LOW")
    exited = exited.sort_values("Search Query Score")
    entered = entered.sort_values("Search Query Score")

    return {
        "prev": prev, "cur": cur,
        "exited": exited, "entered": entered,
        "brand_exit_high": exited[exited["severity"] == "HIGH"],
        "n_exited": len(exited), "n_entered": len(entered),
        "purch_lost": exited[BRAND["Purchases"]].sum(),
        "purch_gained": entered[BRAND["Purchases"]].sum(),
    }


# ---------------------------------------------------------------------------
# H3: seasonality and decomposition
# ---------------------------------------------------------------------------

def seasonal_index(df: pd.DataFrame, core: set, value: str = "Search Query Volume") -> pd.DataFrame:
    """
    Category seasonal index from the CORE panel.

    Geometric mean rather than arithmetic: it is the correct centring for a
    multiplicative index and is robust to a single extreme month such as a
    festive spike.

    With only one full cycle this index is PROVISIONAL. It cannot be validated
    until a second year confirms the profile.
    """
    c = df[df["q"].isin(core)]
    tot = c.groupby("period")[value].sum()
    if len(tot) == 0:
        return pd.DataFrame()
    gm = np.exp(np.log(tot.replace(0, np.nan)).mean())
    out = pd.DataFrame({"period": tot.index, "value": tot.values})
    out["seasonal_index"] = out["value"] / gm
    out["month"] = out["period"].str[-2:].astype(int)
    return out


def lift_vs_gain(df: pd.DataFrame, mask: pd.Series | None = None) -> pd.DataFrame:
    """
    The seasonal-lift versus real-gain view.

    Crosses market size against brand share. The dangerous cell is market up
    with share down: absolute purchases rise so nobody notices, while you are
    being out-competed exactly when demand is highest.
    """
    s = monthly_series(df, mask)
    s = s[["SQV", "TP", "BP", "PS", "IS", "R1", "R2", "R3", "FE"]].copy()
    s["market_index"] = s["TP"] / s["TP"].median()
    s["PS_vs_median"] = s["PS"] - s["PS"].median()
    s["cell"] = np.where(
        s["market_index"] > 1.05,
        np.where(s["PS_vs_median"] < -0.05, "MARKET UP / SHARE DOWN - losing the peak",
                 "MARKET UP / SHARE HELD"),
        np.where(s["market_index"] < 0.95,
                 np.where(s["PS_vs_median"] > 0.05, "MARKET DOWN / SHARE UP - defending well",
                          "MARKET DOWN / SHARE DOWN"),
                 "MARKET FLAT"))
    return s


def yoy_table(df: pd.DataFrame, mask: pd.Series | None = None) -> pd.DataFrame:
    """
    Year-over-year on the same calendar month, which removes seasonality by
    construction and is the cleanest single comparison available.
    """
    s = monthly_series(df, mask)
    rows = []
    for p in s.index:
        y, m = int(p[:4]), int(p[-2:])
        prior = f"{y-1}-{m:02d}"
        if prior not in s.index:
            continue
        c, b = s.loc[p], s.loc[prior]
        dec = decompose_growth(b["TP"], b["BP"], c["TP"], c["BP"])
        dd = dilution_vs_displacement(b["BP"], b["TP"], c["BP"], c["TP"])
        rows.append({"period": p, "prior": prior, **dec, **dd})
    return pd.DataFrame(rows)


def volatility(df: pd.DataFrame, core: set, metric: str = "PS") -> pd.DataFrame:
    """
    Overdispersion score: observed variance against binomial-expected variance.

    This is what separates "bounces because it only has 60 purchases a month"
    from "has plenty of volume and still bounces". It is the mechanism that
    enforces statistical honesty automatically rather than by memory.

        phi < 1.5   stable, safe to build strategy on
        1.5 to 3    real movement, trend it
        phi > 3     erratic, never quote a point estimate
    """
    c = df[df["q"].isin(core)]
    rows = []
    for q, g in c.groupby("q"):
        s = g[metric].dropna() / 100.0
        n = g[TOTAL["Purchases"]]
        if len(s) < 6 or n.sum() == 0:
            continue
        exp = np.mean([si * (1 - si) / ni for si, ni in zip(s, n) if ni > 0])
        if not exp or exp <= 0:
            continue
        phi = s.var(ddof=1) / exp
        rows.append({"q": q, "Search Query": g["Search Query"].iloc[-1],
                     "n_periods": len(s), "mean_pct": 100 * s.mean(),
                     "sd_pp": 100 * s.std(ddof=1), "phi": phi,
                     "stability": "STABLE" if phi < 1.5 else ("TRENDING" if phi <= 3 else "ERRATIC"),
                     "mean_market_purch": n.mean()})
    return pd.DataFrame(rows).sort_values("phi", ascending=False) if rows else pd.DataFrame()


def lifecycle(df: pd.DataFrame, stable: set, seasonal: pd.DataFrame) -> pd.DataFrame:
    """
    Lifecycle is a property of the MARKET, so it is classified on search volume
    rather than on brand counts.

    Seasonal queries are routed out before any growth test runs. A 12-month
    linear trend on a seasonal series is determined mostly by where the window
    starts and ends, and classifying those into growth classes is the most
    common way lifecycle analysis produces confidently wrong answers.
    """
    si = seasonal.set_index("period")["seasonal_index"].to_dict() if len(seasonal) else {}
    periods = sorted(df["period"].unique())
    n = len(periods)
    rows = []
    for q, g in df[df["q"].isin(stable)].groupby("q"):
        g = g.sort_values("period")
        v = g.set_index("period")["Search Query Volume"]
        vd = pd.Series({p: v[p] / si.get(p, 1.0) for p in v.index})
        if len(vd) < max(6, int(0.6 * n)) or vd.sum() <= 0:
            continue
        share = vd / vd.sum()
        H = float((share ** 2).sum())          # seasonal concentration
        t = np.arange(len(vd))
        lg = np.log(vd.replace(0, np.nan)).dropna()
        if len(lg) < 4:
            continue
        tt = np.arange(len(lg))
        slope, intercept = np.polyfit(tt, lg.values, 1)
        pred = slope * tt + intercept
        ss_res = float(((lg.values - pred) ** 2).sum())
        ss_tot = float(((lg.values - lg.values.mean()) ** 2).sum())
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        ann = np.exp(12 * slope) - 1
        present = len(g)

        if H > 0.15:
            cls = "SEASONAL_SPIKE"
        elif present <= max(3, int(0.3 * n)):
            cls = "DEAD"
        elif ann > 0.25 and r2 > 0.30:
            cls = "GROWING"
        elif ann < -0.20 and r2 > 0.30:
            cls = "DECLINING"
        elif abs(ann) <= 0.25 and present >= n - 1:
            cls = "MATURE"
        else:
            cls = "VOLATILE"

        rows.append({"q": q, "Search Query": g["Search Query"].iloc[-1],
                     "segment": g["segment"].iloc[-1], "query_type": g["query_type"].iloc[-1],
                     "months_present": present, "avg_volume": v.mean(),
                     "annual_growth": ann, "fit_r2": r2, "seasonal_conc": H,
                     "lifecycle": cls,
                     "brand_PS_latest": g["PS"].iloc[-1], "brand_IS_latest": g["IS"].iloc[-1]})
    return pd.DataFrame(rows).sort_values("avg_volume", ascending=False) if rows else pd.DataFrame()
