"""
Auto-profiler: inspect a brand's exports and propose a configuration.

Configuration is the real barrier to running this on an unfamiliar brand. Every
brand so far needed four things worked out by hand: brand spellings, the
competitor list, which relevance boundary applies, and a product taxonomy. Get
any of them wrong and the analysis is confident and wrong rather than obviously
broken.

This does that discovery from the data and prints a draft config plus the
evidence behind each choice. It is a starting point for a human to check, not a
substitute for checking: the profiler can see that share collapses above 2x
market price, but only a person knows whether the brand intends to be premium.

Usage:  python profile_brand.py "<path to brand data folder>" "<Brand Name>"
"""

from __future__ import annotations

import os
import re
import sys
from collections import Counter

import numpy as np
import pandas as pd

from sqp_lib import (BRAND, TOTAL, BrandConfig, aggregate, load_scp, load_sqp,
                     normalize_query)

pd.set_option("display.width", 220)

# Words that describe products or attributes rather than who makes them. Used to
# separate candidate brand names from ordinary category language.
STOPWORDS = set("""
for and with the a to of in on by from at is are best top good new latest premium
men man mens women woman womens girls boys kids kid child children baby babies
size small medium large xl xxl xs pack set combo piece pieces ml gm gms kg litre
free natural organic herbal ayurvedic pure original genuine authentic
buy online price cheap under below rs inr discount offer sale deal
half full sleeve sleeves regular slim fit plain solid printed colour color
white black blue red green yellow pink grey brown cream golden silver
soft hard dry oily sensitive normal daily use everyday
""".split())


def _tokens(q: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", q) if len(w) > 2 and w not in STOPWORDS]


def profile(data_dir: str, brand_name: str) -> dict:
    cfg = BrandConfig(name=brand_name, data_dir=data_dir,
                      brand_patterns=[re.escape(brand_name.split()[0].lower())])
    sqp = load_sqp(cfg)
    scp = load_scp(cfg)
    latest = sorted(sqp["period"].unique())[-1]
    cur = sqp[sqp.period == latest].copy()
    out = {"periods": sorted(sqp["period"].unique()), "latest": latest}

    print("=" * 100)
    print(f"BRAND PROFILE: {brand_name}")
    print("=" * 100)
    print(f"  Periods: {len(out['periods'])} ({out['periods'][0]} to {latest})")
    print(f"  Search terms per export: {len(cur):,}")
    print(f"  Market orders in latest period: {cur[TOTAL['Purchases']].sum():,.0f}")
    if len(scp):
        s = scp[scp.period == latest]
        print(f"  Catalogue: {s['ASIN'].nunique():,} ASINs, "
              f"{s['Purchases: Search Traffic Sales'].sum():,.0f} search revenue, "
              f"{s['Purchases: Purchases'].sum():,.0f} orders")
        print(f"  Categories: {s['Category'].value_counts().to_dict()}")

    # ---- 1. Brand spellings -------------------------------------------------
    # Anything whose purchase share is near total is the brand under some
    # spelling, however little it resembles the registered name.
    print("\n" + "-" * 100)
    print("1. BRAND SPELLINGS  (terms where purchase share is near total)")
    print("-" * 100)
    tok_share = {}
    for w in {w for q in cur["q"] for w in _tokens(q)}:
        sub = cur[cur["q"].str.contains(rf"\b{re.escape(w)}\b", regex=True)]
        tp, bp = sub[TOTAL["Purchases"]].sum(), sub[BRAND["Purchases"]].sum()
        if tp >= 5:
            tok_share[w] = (100 * bp / tp, tp, len(sub))
    likely = {w: v for w, v in tok_share.items() if v[0] >= 70}
    for w, (ps, tp, n) in sorted(likely.items(), key=lambda kv: -kv[1][1])[:15]:
        print(f"  {w:22s} share={ps:6.1f}%  market_orders={tp:>7,.0f}  terms={n}")
    out["brand_tokens"] = sorted(likely, key=lambda w: -likely[w][1])
    if not likely:
        print("  none found. Either the brand has no branded search, or the seed")
        print("  pattern is wrong. Check the ASIN titles in the catalogue report.")

    # ---- 2. Competitor candidates ------------------------------------------
    print("\n" + "-" * 100)
    print("2. COMPETITOR CANDIDATES  (real demand, near-zero share for us)")
    print("-" * 100)
    print("  Unlabelled competitors are the most common data-quality failure. They")
    print("  inflate the addressable market and hide who is actually winning.\n")
    cand = [(w, v) for w, v in tok_share.items() if v[0] < 3 and v[1] >= 50]
    for w, (ps, tp, n) in sorted(cand, key=lambda kv: -kv[1][1])[:25]:
        ex = cur[cur["q"].str.contains(rf"\b{re.escape(w)}\b", regex=True)]
        ex = ex.nlargest(1, TOTAL["Purchases"])["Search Query"].iloc[0]
        print(f"  {w:20s} market_orders={tp:>7,.0f}  ourShare={ps:5.2f}%  e.g. \"{ex[:46]}\"")
    out["competitor_candidates"] = [w for w, _ in sorted(cand, key=lambda kv: -kv[1][1])[:25]]
    print("\n  NOTE: this list mixes brand names with ingredient and attribute words")
    print("  (rosemary, kumkumadi, collar). Only the brand names belong in the")
    print("  competitor config. The rest are demand and must stay in the market.")

    # ---- 3. Which relevance boundary applies -------------------------------
    print("\n" + "-" * 100)
    print("3. RELEVANCE BOUNDARY  (which dimension separates winnable from not)")
    print("-" * 100)
    seed = re.compile("|".join(out["brand_tokens"][:6]) if out["brand_tokens"] else r"\bzzz\b", re.I)
    u = cur[~cur["q"].str.contains(seed)].copy()

    verdicts = {}
    if "Clicks: Brand Price (Median)" in u.columns and u["Clicks: Brand Price (Median)"].notna().any():
        u["ratio"] = u["Clicks: Brand Price (Median)"] / u["Clicks: Price (Median)"]
        bands = pd.cut(u["ratio"], [0, 1.25, 2, 3, 5, 1e9],
                       labels=["<=1.25x", "1.25-2x", "2-3x", "3-5x", ">5x"])
        g = u.groupby(bands, observed=True).apply(lambda x: pd.Series({
            "terms": len(x), "market_orders": x[TOTAL["Purchases"]].sum(),
            "our_share_%": 100 * x[BRAND["Purchases"]].sum() / max(1, x[TOTAL["Purchases"]].sum())}),
            include_groups=False)
        print("\n  BY PRICE POSITION:")
        print(g.round(2).to_string())
        if len(g) >= 2 and g["our_share_%"].iloc[0] > 0:
            drop = g["our_share_%"].iloc[0] / max(g["our_share_%"].iloc[-1], 0.001)
            verdicts["price"] = drop
            print(f"  -> share falls {drop:,.0f}x from cheapest band to dearest")

    print("\n  BY MOST COMMON HEAD NOUN:")
    heads = Counter()
    for _, r in u.iterrows():
        for w in _tokens(r["q"]):
            heads[w] += r[TOTAL["Purchases"]]
    rows = []
    for w, _ in heads.most_common(12):
        sub = u[u["q"].str.contains(rf"\b{re.escape(w)}\b", regex=True)]
        tp, bp = sub[TOTAL["Purchases"]].sum(), sub[BRAND["Purchases"]].sum()
        rows.append({"token": w, "market_orders": tp,
                     "our_share_%": 100 * bp / max(1, tp), "terms": len(sub)})
    hd = pd.DataFrame(rows)
    print(hd.round(2).to_string(index=False))
    if len(hd) > 1 and hd["our_share_%"].max() > 0:
        spread = hd["our_share_%"].max() / max(hd["our_share_%"].median(), 0.001)
        verdicts["category"] = spread
        print(f"  -> share varies {spread:,.0f}x between product categories")

    print("\n  SUGGESTED BOUNDARY:")
    if verdicts.get("price", 0) >= max(verdicts.get("category", 0), 5):
        print("    PriceTierRule. Share tracks price position more strongly than category,")
        print("    which means the brand is priced out of most of its market.")
        out["relevance"] = "PriceTierRule"
    elif verdicts.get("category", 0) >= 5:
        print("    RelevanceRule on product category. Share varies far more by what the")
        print("    product is than by what it costs.")
        out["relevance"] = "RelevanceRule(category)"
    else:
        print("    No boundary is obvious from the data. Ask the brand what it does not")
        print("    make. Running with no rule analyses a market the brand cannot win.")
        out["relevance"] = "ASK"

    # ---- 4. Product taxonomy ------------------------------------------------
    print("\n" + "-" * 100)
    print("4. PRODUCT CATEGORY CANDIDATES  (from catalogue titles, most specific first)")
    print("-" * 100)
    if len(scp):
        titles = scp[scp.period == latest]["ASIN Title"].astype(str).str.lower()
        bigrams = Counter()
        for t in titles:
            ws = _tokens(t)
            for a, b in zip(ws, ws[1:]):
                bigrams[f"{a} {b}"] += 1
        for phrase, n in bigrams.most_common(18):
            print(f"  {phrase:34s} in {n:>4} ASIN titles")
        out["theme_candidates"] = [p for p, _ in bigrams.most_common(18)]
    else:
        print("  no catalogue report, so categories must come from the search terms")

    # ---- 5. Data quality ----------------------------------------------------
    print("\n" + "-" * 100)
    print("5. DATA QUALITY")
    print("-" * 100)
    missing = sqp.attrs.get("missing_columns", [])
    print(f"  Missing optional columns: {len(missing)}"
          + (f" -> price and delivery diagnoses disabled" if missing else " (complete export)"))
    if len(scp):
        cov = (sqp[sqp.period == latest][BRAND["Purchases"]].sum()
               / max(1, scp[scp.period == latest]["Purchases: Purchases"].sum()))
        print(f"  Search terms visible cover {100*cov:.0f}% of the brand's search orders")
    a = aggregate(cur)
    print(f"  Overall impression share: {a['IS']:.2f}%"
          + ("  <- effectively invisible; visibility is the whole problem"
             if a["IS"] < 0.5 else ""))
    if len(out["periods"]) < 12:
        print(f"  Only {len(out['periods'])} periods: no seasonality, no year-over-year")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    profile(os.path.abspath(sys.argv[1]), sys.argv[2])
