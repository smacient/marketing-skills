"""
Stress test: run the engine against deliberately awkward inputs.

Every case is built by mutating real exports, so the failures found are ones a
real user could actually hit. The point is not that each case produces a good
analysis, but that it either produces an honest one or fails loudly. Silent
wrong answers are the only unacceptable outcome.

Usage:  python stress_test.py
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import traceback

import pandas as pd

import run_analysis
import write_plan
import write_report
from sqp_lib import BrandConfig, PriceTierRule, RelevanceRule

# Point at a folder holding real brand export folders. The cases are built by
# mutating real exports, so the failures found are ones a user could hit.
SRC_ROOT = os.environ.get("SQP_STRESS_DATA", "")
SRC_BRAND = os.environ.get("SQP_STRESS_BRAND", "")
WORK = os.path.join(tempfile.gettempdir(), "sqp_stress")

# Columns Seller Central hides by default. A user who exports without enabling
# every column gets a file missing these, which is a very common real case.
DEFAULT_HIDDEN = [
    "Clicks: Price (Median)", "Clicks: Brand Price (Median)",
    "Cart Adds: Price (Median)", "Cart Adds: Brand Price (Median)",
    "Purchases: Price (Median)", "Purchases: Brand Price (Median)",
    "Clicks: Same-Day Shipping Speed", "Clicks: 1D Shipping Speed",
    "Clicks: 2D Shipping Speed", "Cart Adds: Same-Day Shipping Speed",
    "Cart Adds: 1D Shipping Speed", "Cart Adds: 2D Shipping Speed",
]


def _copy(src_brand: str, dst: str, months: list[str] | None = None,
          include_scp: bool = True) -> str:
    """Copy a real brand's exports into a scratch folder."""
    src = os.path.join(SRC_ROOT, src_brand)
    shutil.rmtree(dst, ignore_errors=True)
    for sub in ["Search Query Performance", "Search Catalogue Performance"]:
        if sub.startswith("Search Cat") and not include_scp:
            continue
        s = os.path.join(src, sub)
        if not os.path.isdir(s):
            continue
        d = os.path.join(dst, sub)
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(s):
            if months and f not in months:
                continue
            shutil.copy(os.path.join(s, f), os.path.join(d, f))
    return dst


def _rewrite(path: str, fn) -> None:
    """Apply fn to every SQP csv in a scratch folder, preserving the meta row."""
    d = os.path.join(path, "Search Query Performance")
    for f in os.listdir(d):
        p = os.path.join(d, f)
        with open(p, encoding="utf-8-sig") as fh:
            meta = fh.readline()
        df = pd.read_csv(p, skiprows=1)
        df.columns = [c.strip() for c in df.columns]
        df = fn(df)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(meta)
            df.to_csv(fh, index=False)


def _asinify(path: str, asin: str) -> None:
    """
    Rewrite a copied brand-level export as the ASIN-level view of itself.

    Amazon's ASIN-level SQP is the same 33 columns with the brand side renamed
    and an extra field in the metadata row. Building the case this way exercises
    the real load path rather than a mock of it.
    """
    d = os.path.join(path, "Search Query Performance")
    for f in os.listdir(d):
        fp = os.path.join(d, f)
        with open(fp, encoding="utf-8-sig") as fh:
            meta = fh.readline().rstrip()
        df = pd.read_csv(fp, skiprows=1)
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns={c: c.replace(": Brand ", ": ASIN ")
                                for c in df.columns if ": Brand " in c})
        with open(fp, "w", encoding="utf-8", newline="") as fh:
            fh.write(f'ASIN or Product=["{asin}"],' + meta + chr(10))
            df.to_csv(fh, index=False)


def _an_asin(path: str) -> str:
    """Any ASIN the catalogue report actually contains, so the filter finds rows."""
    d = os.path.join(path, "Search Catalogue Performance")
    f = sorted(os.listdir(d))[-1]
    df = pd.read_csv(os.path.join(d, f), skiprows=1)
    df.columns = [c.strip() for c in df.columns]
    return str(df["ASIN"].dropna().iloc[0]).upper()


BASE_CFG = os.environ.get("SQP_STRESS_CONFIG", "")


def _cfg(name: str, data_dir: str, **over) -> BrandConfig:
    import brand_config
    b = brand_config.load(BASE_CFG)
    kw = dict(name=name, data_dir=data_dir, marketplace=b.marketplace,
              brand_patterns=b.brand_patterns, competitor_patterns=b.competitor_patterns,
              relevance=b.relevance, product_themes=b.product_themes)
    kw.update(over)
    return BrandConfig(**kw)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

ALL = ["JUNE - 2025.csv", "JULY - 2025.csv", "AUG - 2025.csv", "SEP - 2025.csv",
       "OCT - 2025.csv", "NOV - 2025.csv", "DEC - 2025.csv", "JAN - 2026.csv",
       "FEB - 2026.csv", "MARCH - 2026.csv", "APRIL - 2026.csv", "MAY - 2026.csv",
       "JUNE - 2026.csv", "JULY - 2026.csv"]


def build_cases() -> list[tuple[str, BrandConfig, str]]:
    """Returns (label, config, what_we_expect)."""
    os.makedirs(WORK, exist_ok=True)
    cases = []

    d = _copy(SRC_BRAND, os.path.join(WORK, "two_months"), ALL[-2:])
    cases.append(("2 months of history", _cfg("S_TwoMonths", d),
                  "runs; no trend, no seasonality, states what is missing"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "asin_level"), ALL[-4:])
    _asinify(d, _an_asin(d))
    cases.append(("ASIN-level export (ASIN present in catalogue)", _cfg("S_AsinLevel", d),
                  "runs; names the ASIN, states its scope, revenue is the ASIN's not the brand's"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "asin_not_in_scp"), ALL[-4:])
    _asinify(d, "B0ZZZZZZZZ")
    cases.append(("ASIN-level export, ASIN absent from catalogue", _cfg("S_AsinNoSCP", d),
                  "runs; says revenue and coverage are unavailable, never falls back to brand-wide"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "no_scp"), ALL[-3:], include_scp=False)
    cases.append(("No catalog report at all", _cfg("S_NoSCP", d),
                  "runs; no revenue, no per-ASIN findings"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "hidden_cols"), ALL[-4:])
    _rewrite(d, lambda df: df.drop(columns=[c for c in DEFAULT_HIDDEN if c in df.columns]))
    cases.append(("Default Seller Central export (21 of 33 columns)", _cfg("S_HiddenCols", d),
                  "runs or fails loudly; must not silently mis-price"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "no_brand"), ALL[-3:])
    cases.append(("Brand name matches nothing", _cfg("S_NoBrand", d, brand_patterns=[r"\bzzzznotabrand\b"]),
                  "runs; everything unbranded, no brand-defence action"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "all_brand"), ALL[-3:])
    cases.append(("Brand pattern matches everything", _cfg("S_AllBrand", d, brand_patterns=[r"."]),
                  "runs; no unbranded market to analyse, says so"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "zero_purch"), ALL[-3:])
    _rewrite(d, lambda df: df.assign(**{"Purchases: Brand Count": 0}))
    cases.append(("Zero brand purchases anywhere", _cfg("S_ZeroPurch", d),
                  "runs; cannot size anything, must not divide by zero"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "total_dominance"), ALL[-3:])
    _rewrite(d, lambda df: df.assign(**{
        "Impressions: Brand Count": df["Impressions: Total Count"],
        "Clicks: Brand Count": df["Clicks: Total Count"],
        "Cart Adds: Brand Count": df["Cart Adds: Total Count"],
        "Purchases: Brand Count": df["Purchases: Total Count"]}))
    cases.append(("Brand owns 100% of every market", _cfg("S_Dominant", d),
                  "runs; no opportunity, all scores 1.00"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "tiny"), ALL[-3:])
    _rewrite(d, lambda df: df.head(12))
    cases.append(("Only 12 search terms in the export", _cfg("S_Tiny", d),
                  "runs; almost everything gated out"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "no_themes"), ALL[-3:])
    cases.append(("No product theme taxonomy configured", _cfg("S_NoThemes", d, product_themes={}),
                  "runs; theme layer skipped cleanly"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "no_relevance"), ALL[-3:])
    cases.append(("No relevance rule configured", _cfg("S_NoRelevance", d, relevance=None),
                  "runs; everything in scope"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "us_market"), ALL[-3:])
    cases.append(("Unknown marketplace code", _cfg("S_BadMarket", d, marketplace="amazon.zz"),
                  "runs; falls back to a neutral profile"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "zero_market"), ALL[-3:])
    _rewrite(d, lambda df: df.assign(**{"Purchases: Total Count": 0,
                                        "Purchases: Brand Count": 0}))
    cases.append(("Market purchases all zero", _cfg("S_ZeroMarket", d),
                  "runs; no purchase-based analysis possible"))

    d = _copy(SRC_BRAND, os.path.join(WORK, "price_no_data"), ALL[-3:])
    _rewrite(d, lambda df: df.assign(**{"Clicks: Brand Price (Median)": None}))
    cases.append(("Price-tier rule with no brand prices", _cfg(
        "S_PriceNoData", d, relevance=PriceTierRule(max_ratio=3.0)),
        "runs; price rule degrades without crashing"))

    return cases


def run_case(label: str, cfg: BrandConfig, expect: str) -> dict:
    buf = io.StringIO()
    out = {"case": label, "expect": expect}
    try:
        with contextlib.redirect_stdout(buf):
            res = run_analysis.run(cfg)
            xl = run_analysis.write_excel(res)
            write_report.write_all(res)
            write_plan.write_all(res)
        out["status"] = "OK"
        out["periods"] = len(res["periods"])
        out["actions"] = len(__import__("sqp_actions").build_actions(res))
        for f in (xl,):
            if os.path.exists(f):
                os.remove(f)
    except Exception as exc:
        out["status"] = "FAIL"
        out["error"] = f"{type(exc).__name__}: {exc}"
        out["where"] = traceback.format_exc().strip().splitlines()[-3].strip()
    out["log"] = buf.getvalue()
    return out


if __name__ == "__main__":
    if not (SRC_ROOT and SRC_BRAND and BASE_CFG):
        print(__doc__)
        print("Set SQP_STRESS_DATA (folder of brand folders), SQP_STRESS_BRAND "
              "(one brand folder name) and SQP_STRESS_CONFIG (a working config json).")
        sys.exit(1)
    results = []
    for label, cfg, expect in build_cases():
        r = run_case(label, cfg, expect)
        results.append(r)
        mark = "PASS" if r["status"] == "OK" else "FAIL"
        extra = (f"{r.get('periods','?')}p, {r.get('actions','?')} actions"
                 if r["status"] == "OK" else r.get("error", ""))
        print(f"[{mark}] {label:52s} {extra}")
        if r["status"] == "FAIL":
            print(f"        at: {r.get('where','')}")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    print(f"\n{len(results) - n_fail}/{len(results)} passed")
    sys.exit(1 if n_fail else 0)
