"""
Amazon Brand Analytics - Search Query Performance (SQP) analysis library.

Marketplace-agnostic core. Brand-specific behaviour is supplied via a BrandConfig,
so the same engine runs any brand in any marketplace.

Verified against real monthly exports from four brands on amazon.in. See
references/report-mechanics.md for the mechanics this encodes, in particular:
  - Search Query Score ranks by BRAND funnel performance, not market volume
  - Exports are hard-capped at 1000 rows
  - Shipping-speed columns are MARKET level, not brand level
  - "Clicks: Click Rate %" is clicks / search volume, NOT click-through rate
  - Reported Brand Share % is accurate, but we recompute from counts anyway
"""

from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Period parsing
# ---------------------------------------------------------------------------

MONTHS = {
    "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6, "JUL": 7, "JULY": 7,
    "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10, "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12,
}


def _period_from_metadata(path: str) -> tuple[int, int] | None:
    """
    Read the period from the export's own metadata row, which looks like
    `Reporting Range=["Monthly"],Select year=["2026"],Select month=["July"]`.

    This is authoritative and beats guessing from the filename, which users
    rename freely and which Amazon's own download names do not follow.
    """
    try:
        with open(path, encoding="utf-8-sig") as fh:
            head = fh.readline()
    except OSError:
        return None
    y = re.search(r'year\s*=\s*\["?(\d{4})"?\]', head, re.I)
    m = re.search(r'month\s*=\s*\["?([A-Za-z]+)"?\]', head, re.I)
    if y and m and m.group(1).upper() in MONTHS:
        return int(y.group(1)), MONTHS[m.group(1).upper()]
    return None


def _period_from_reporting_date(path: str) -> tuple[int, int] | None:
    """Fall back to the Reporting Date column, which every export carries."""
    try:
        df = pd.read_csv(path, skiprows=1, nrows=1)
    except Exception:
        return None
    df.columns = [c.strip() for c in df.columns]
    if "Reporting Date" not in df.columns or df.empty:
        return None
    try:
        d = pd.to_datetime(df["Reporting Date"].iloc[0])
        return int(d.year), int(d.month)
    except Exception:
        return None


def _period_from_name(path: str) -> tuple[int, int] | None:
    """
    Last resort. Handles the common shapes: month names in any position, and
    numeric YYYY-MM or MM-YYYY, separated by spaces, dashes or underscores.
    """
    stem = os.path.basename(path).rsplit(".", 1)[0]
    parts = re.split(r"[\s_\-]+", stem)
    month = next((p for p in parts if p.upper() in MONTHS), None)
    year = next((p for p in parts if p.isdigit() and len(p) == 4
                 and 2000 <= int(p) <= 2100), None)
    if month and year:
        return int(year), MONTHS[month.upper()]
    # Numeric forms, e.g. 2026-07 or 2026_07_31 or 07-2026.
    m = re.search(r"(20\d{2})[\s_\-]?(0[1-9]|1[0-2])(?![\d])", stem)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(?<![\d])(0[1-9]|1[0-2])[\s_\-](20\d{2})", stem)
    if m:
        return int(m.group(2)), int(m.group(1))
    return None


def parse_period(path: str) -> tuple[int, int]:
    """
    Determine which month an export covers.

    Tries the file's own metadata first, then its Reporting Date column, then
    the filename. Users rename these files freely and Amazon's default download
    name follows none of the obvious conventions, so filename parsing alone is
    not dependable.
    """
    for fn in (_period_from_metadata, _period_from_reporting_date, _period_from_name):
        got = fn(path)
        if got:
            return got
    raise ValueError(
        f"Cannot determine which month '{os.path.basename(path)}' covers. "
        "Expected the period in the export's metadata row, a Reporting Date "
        "column, or a filename containing a month and a four-digit year.")


def period_key(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _safe_div(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return np.divide(a, b, out=np.full_like(a, np.nan, dtype=float), where=b > 0)


# ---------------------------------------------------------------------------
# Marketplace profiles
# ---------------------------------------------------------------------------

@dataclass
class MarketplaceProfile:
    """Marketplace-specific interpretation rules."""
    code: str
    currency: str
    symbol: str
    report_symbol: str = ""
    # Price-barrier threshold on the relative price index. India is more price
    # sensitive, so the barrier bites at a smaller premium.
    price_barrier_index: float = 1.15
    # Periods distorted by category-wide sale events, as (year, month).
    # Excluded from trailing medians used for sizing and flagged in outputs.
    event_periods: set = field(default_factory=set)
    # Whether cash-on-delivery is a live factor in close-rate diagnosis.
    cod_market: bool = False
    # Whether to cluster transliterated / vernacular query variants.
    transliteration: bool = False


MARKETPLACES = {
    "amazon.in": MarketplaceProfile(
        code="amazon.in", currency="INR", symbol="Rs.", report_symbol="₹",
        price_barrier_index=1.10,
        event_periods={(2025, 9), (2025, 10), (2025, 11), (2026, 9), (2026, 10), (2026, 11)},
        cod_market=True, transliteration=True,
    ),
    "amazon.com": MarketplaceProfile(
        code="amazon.com", currency="USD", symbol="$", report_symbol="$",
        price_barrier_index=1.15,
        event_periods={(2025, 7), (2025, 11), (2026, 7), (2026, 11)},
        cod_market=False, transliteration=False,
    ),
    "default": MarketplaceProfile(code="default", currency="", symbol=""),
}


# ---------------------------------------------------------------------------
# Brand configuration
# ---------------------------------------------------------------------------

@dataclass
class RelevanceRule:
    """
    Defines which queries the brand can plausibly win.

    Queries outside the brand's relevance boundary are structurally unwinnable
    and must be routed out of opportunity ranking. Without this, generic
    high-volume terms dominate every action list.

    `segments` maps a segment label to a regex. Order matters: the first match
    wins, so put narrower patterns first. `in_scope` lists the labels the brand
    can actually serve.
    """
    segments: dict[str, str]
    in_scope: list[str]
    fallback: str = "GENERIC"

    def classify(self, q: str) -> str:
        for label, pattern in self.segments.items():
            if re.search(pattern, q, re.I):
                return label
        return self.fallback

    def is_in_scope(self, label: str) -> bool:
        return label in self.in_scope

    def assign(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        seg = df["q"].map(self.classify)
        return seg, seg.map(self.is_in_scope)


@dataclass
class PriceTierRule:
    """
    Relevance by price position rather than by wording.

    For a premium brand in a mass-market category, the boundary is not what the
    shopper searched for but what they are willing to pay. A brand priced at
    several times the market median cannot win those searches at any level of
    ad spend, and including them makes the addressable market look enormous
    while dragging every category metric down.

    `max_ratio` is how many times the market median price the brand can be and
    still plausibly compete. Derive it from the data rather than guessing: look
    at purchase share bucketed by price ratio and find where it collapses.
    """
    max_ratio: float = 3.0
    labels: tuple[str, ...] = ("AT MARKET", "PREMIUM", "SUPER PREMIUM")

    def assign(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        ratio = _safe_div(df["Clicks: Brand Price (Median)"], df["Clicks: Price (Median)"])
        ratio = pd.Series(ratio, index=df.index)
        # Where the brand had no clicks there is no brand price, so fall back to
        # the brand's typical price across the whole export.
        typical = df["Clicks: Brand Price (Median)"].median()
        fallback = _safe_div(np.full(len(df), typical), df["Clicks: Price (Median)"])
        ratio = ratio.fillna(pd.Series(fallback, index=df.index))

        seg = pd.Series(self.labels[2], index=df.index, dtype=object)
        seg[ratio <= self.max_ratio] = self.labels[1]
        seg[ratio <= 1.25] = self.labels[0]
        seg[ratio.isna()] = "UNKNOWN"
        return seg, seg.isin(self.labels[:2])

    @property
    def in_scope(self) -> list[str]:
        return list(self.labels[:2])


@dataclass
class BrandConfig:
    name: str
    data_dir: str
    marketplace: str = "amazon.in"
    brand_patterns: list[str] = field(default_factory=list)
    competitor_patterns: dict[str, str] = field(default_factory=dict)
    relevance: object | None = None
    # Product themes for aggregation. Ordered narrow to broad; first match wins.
    product_themes: dict[str, str] = field(default_factory=dict)
    # Report folder names, overridable because Amazon's own download names and
    # user folder conventions vary ("Catalogue" vs "Catalog", for instance).
    sqp_folder: str = "Search Query Performance"
    scp_folder: str = "Search Catalogue Performance"

    @property
    def mp(self) -> MarketplaceProfile:
        return MARKETPLACES.get(self.marketplace, MARKETPLACES["default"])

    @property
    def brand_regex(self) -> re.Pattern:
        return re.compile("|".join(self.brand_patterns), re.I)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

STAGES = ["Impressions", "Clicks", "Cart Adds", "Purchases"]

# Canonical short names for the funnel counts.
TOTAL = {s: f"{s}: Total Count" for s in STAGES}
BRAND = {s: f"{s}: Brand Count" for s in STAGES}


# Columns the analysis cannot run without.
REQUIRED_COLS = ["Search Query", "Search Query Volume", "Search Query Score"] +     [f"{st}: {kind} Count" for st in STAGES for kind in ("Total", "Brand")]

# Columns Seller Central hides by default. Without them the funnel still works,
# but price and delivery diagnoses are impossible. Missing them is the single
# most likely real-world input problem, so it is handled rather than fatal.
# Price and shipping exist only from the click stage onward: there is no such
# thing as the price of an impression.
PRICED_STAGES = ["Clicks", "Cart Adds", "Purchases"]
OPTIONAL_COLS = [f"{st}: {p}" for st in PRICED_STAGES for p in
                 ("Price (Median)", "Brand Price (Median)")] +     [f"{st}: {sp} Shipping Speed" for st in PRICED_STAGES
     for sp in ("Same-Day", "1D", "2D")]


def check_columns(df: pd.DataFrame) -> list[str]:
    """
    Verify the export contract. Missing REQUIRED columns is fatal and says so.
    Missing OPTIONAL columns is added back as empty and reported, so downstream
    code has a stable shape and the report can state what could not be analysed.
    """
    missing_req = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing_req:
        raise ValueError(
            "Export is missing columns the analysis cannot run without: "
            + ", ".join(missing_req)
            + ". Re-download from Brand Analytics with all columns enabled.")
    return [c for c in OPTIONAL_COLS if c not in df.columns]


NUMERIC_HINTS = ("Count", "Volume", "Score", "Shipping Speed", "Median",
                 "Rate %", "Impressions", "Clicks", "Cart Adds", "Purchases", "Sales")


def _read_report(path: str) -> pd.DataFrame:
    """
    Row 1 is an export-metadata line, so the real header is row 2.

    Counts are coerced to numeric. An empty export leaves every column as
    object dtype, and a partly-formatted one can carry thousands separators;
    either silently breaks arithmetic much further downstream, where the cause
    is no longer visible.
    """
    df = pd.read_csv(path, skiprows=1)
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        if any(h in c for h in NUMERIC_HINTS) and df[c].dtype == object:
            df[c] = pd.to_numeric(
                df[c].astype(str).str.replace(",", "", regex=False).str.strip(),
                errors="coerce")
    return df


ASIN_RE = re.compile(r"(b0[a-z0-9]{8})", re.I)


def brand_asins(cfg: BrandConfig) -> set:
    """ASINs the brand owns, read from Search Catalog Performance if present."""
    try:
        scp = load_scp(cfg)
        return set(scp["ASIN"].astype(str).str.lower()) if len(scp) else set()
    except Exception:
        return set()


def load_sqp(cfg: BrandConfig, folder: str | None = None) -> pd.DataFrame:
    folder = folder or getattr(cfg, "sqp_folder", "Search Query Performance")
    paths = sorted(glob.glob(os.path.join(cfg.data_dir, folder, "*.csv")), key=parse_period)
    if not paths:
        raise FileNotFoundError(f"No SQP CSVs under {os.path.join(cfg.data_dir, folder)}")
    frames, empty = [], []
    for p in paths:
        y, m = parse_period(p)
        df = _read_report(p)
        if len(df) == 0:
            empty.append(os.path.basename(p))
            continue
        df["year"], df["month"], df["period"] = y, m, period_key(y, m)
        df["source_file"] = os.path.basename(p)
        # Raw row count before duplicate merging, so the reported export cap is
        # the actual cap rather than the post-merge total.
        df["raw_rows_in_export"] = len(df)
        frames.append(df)
    if empty:
        # Dropping these silently would let a user believe they supplied more
        # history than was actually analysed.
        print(f"  [empty] {len(empty)} export(s) contained no rows and were excluded: "
              f"{', '.join(empty)}")
    if not frames:
        raise ValueError(
            f"Every export under {os.path.join(cfg.data_dir, folder)} is empty. "
            "Re-download from Brand Analytics.")
    out = pd.concat(frames, ignore_index=True)
    missing = check_columns(out)
    if missing:
        print(f"  [columns] {len(missing)} optional columns absent from the export "
              f"(Seller Central hides these by default). Price and delivery "
              f"diagnoses are disabled: {', '.join(sorted(set(c.split(':')[1].strip() for c in missing)))}")
        for c in missing:
            out[c] = np.nan
    # attrs do not survive the concat and copy inside enrichment, so they are
    # attached to the finished frame rather than the raw one.
    enriched = _enrich_sqp(out, cfg)
    enriched.attrs["missing_columns"] = missing
    enriched.attrs["empty_exports"] = empty
    return enriched


def load_scp(cfg: BrandConfig, folder: str | None = None) -> pd.DataFrame:
    """
    Search Catalog Performance. NOT the ASIN view of SQP: different scope, no
    competitive data, cannot be joined to SQP by query.
    """
    folder = folder or getattr(cfg, "scp_folder", "Search Catalogue Performance")
    paths = sorted(glob.glob(os.path.join(cfg.data_dir, folder, "*.csv")), key=parse_period)
    if not paths:
        return pd.DataFrame()
    frames = []
    for p in paths:
        y, m = parse_period(p)
        df = _read_report(p)
        if len(df) == 0:
            continue
        df["year"], df["month"], df["period"] = y, m, period_key(y, m)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def normalize_query(s: pd.Series) -> pd.Series:
    """Stable query identity across periods."""
    return (s.astype(str).str.lower().str.strip()
             .str.replace(r"[^\w\s]", " ", regex=True)
             .str.replace(r"\s+", " ", regex=True))


def _merge_duplicate_queries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Amazon reports punctuation variants as separate rows ("kids' face wash" and
    "kids face wash"). Normalisation collapses them onto one key, so the counts
    must be summed rather than one row discarded: they are the same demand
    split across two rows, and keeping only one understates it.

    Counts sum. Rank takes the better (lower) value. Median prices cannot be
    summed, so they come from the larger row.
    """
    dup_keys = df.groupby(["period", "q"]).size()
    dup_keys = set(dup_keys[dup_keys > 1].index)
    if not dup_keys:
        return df

    is_dup = pd.Series(list(zip(df["period"], df["q"])), index=df.index).isin(dup_keys)
    clean, dirty = df[~is_dup], df[is_dup]

    sum_cols = [c for c in df.columns
                if ("Count" in c or "Shipping Speed" in c or c == "Search Query Volume")]
    merged = []
    for (_, _), g in dirty.groupby(["period", "q"]):
        base = g.sort_values("Search Query Volume", ascending=False).iloc[0].copy()
        for c in sum_cols:
            base[c] = g[c].sum()
        base["Search Query Score"] = g["Search Query Score"].min()
        merged.append(base)
    return pd.concat([clean, pd.DataFrame(merged)], ignore_index=True)


def _enrich_sqp(df: pd.DataFrame, cfg: BrandConfig) -> pd.DataFrame:
    df = df.copy()
    df["q"] = normalize_query(df["Search Query"])
    df = _merge_duplicate_queries(df)

    # Query type. Brand match takes precedence over competitor match.
    df["is_branded"] = df["q"].str.contains(cfg.brand_regex)
    # Shoppers paste ASINs into search. If it is one of ours, that is brand
    # traffic, not generic demand, and it converts near 100%.
    owned = brand_asins(cfg)
    if owned:
        found = df["q"].str.extract(ASIN_RE, expand=False).str.lower()
        df.loc[found.isin(owned), "is_branded"] = True
    df["competitor"] = ""
    for comp, pat in cfg.competitor_patterns.items():
        hit = df["q"].str.contains(pat, case=False, regex=True) & ~df["is_branded"]
        df.loc[hit & (df["competitor"] == ""), "competitor"] = comp
    df["query_type"] = np.where(
        df["is_branded"], "BRANDED",
        np.where(df["competitor"] != "", "COMPETITOR", "UNBRANDED"))

    # Relevance segment. Each rule type decides for itself how to classify,
    # so a regex-based rule and a price-based rule are interchangeable here.
    if cfg.relevance is not None:
        df["segment"], df["in_scope"] = cfg.relevance.assign(df)
        # Branded searches are always in scope: the brand can always win its own name.
        df.loc[df["is_branded"], "in_scope"] = True
    else:
        df["segment"], df["in_scope"] = "ALL", True

    df["is_event"] = [(y, m) in cfg.mp.event_periods
                      for y, m in zip(df["year"], df["month"])]
    return add_metrics(df)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Shares recomputed from counts (never read from the reported % columns),
    and the three stage indices.

    R1/R2/R3 are internal identifiers only. Everywhere a reader sees them they
    are labelled Tile Score, Page Score and Offer Score, after the part of the
    shopping experience each measures.

        R1 "Tile Score"  = ClickShare / ImpressionShare   market-relative CTR
        R2 "Page Score"  = CartShare  / ClickShare        market-relative cart add
        R3 "Offer Score" = PurchShare / CartShare         market-relative close
        FE "Funnel Efficiency" = PurchShare / ImpressionShare = R1 * R2 * R3
    """
    df = df.copy()
    for s, short in zip(STAGES, ["IS", "CS", "AS", "PS"]):
        df[short] = 100.0 * _safe_div(df[BRAND[s]], df[TOTAL[s]])

    df["R1"] = _safe_div(df["CS"], df["IS"])
    df["R2"] = _safe_div(df["AS"], df["CS"])
    df["R3"] = _safe_div(df["PS"], df["AS"])
    df["FE"] = _safe_div(df["PS"], df["IS"])

    # Relative price index per stage. Scale-free, so comparable across queries
    # and across time. Never use the raw currency gap for either.
    for stage, tag in [("Clicks", "PIc"), ("Cart Adds", "PIa"), ("Purchases", "PIp")]:
        df[tag] = _safe_div(df[f"{stage}: Brand Price (Median)"],
                            df[f"{stage}: Price (Median)"])

    # Market structure. SCI rising means everyone's impression share falls
    # mechanically, which is the most common false alarm in this dataset.
    df["SCI"] = _safe_div(df[TOTAL["Impressions"]], df["Search Query Volume"])
    df["MPR"] = _safe_div(df[TOTAL["Purchases"]], df["Search Query Volume"])
    df["MCLR"] = _safe_div(df[TOTAL["Purchases"]], df[TOTAL["Clicks"]])
    df["PLS"] = _safe_div(df["Purchases: Price (Median)"], df["Clicks: Price (Median)"])

    # Market fast-ship mix at purchase. Brand-side equivalent is not available
    # in SQP (these columns are market level), so the gap needs SCP.
    fast = (df["Purchases: Same-Day Shipping Speed"] + df["Purchases: 1D Shipping Speed"])
    df["FSM_market"] = _safe_div(fast, df[TOTAL["Purchases"]])
    return df


# ---------------------------------------------------------------------------
# Human-readable output
# ---------------------------------------------------------------------------

# Short codes are fine inside the code. They must never reach a spreadsheet a
# person opens cold. Every frame written to Excel is renamed through this map.
COLUMN_LABELS = {
    "TI": "Market Impressions", "BI": "Our Impressions",
    # Raw Amazon export headers, renamed on the way out too.
    "Impressions: Total Count": "Market Impressions",
    "Impressions: Brand Count": "Our Impressions",
    "Clicks: Total Count": "Market Clicks", "Clicks: Brand Count": "Our Clicks",
    "Cart Adds: Total Count": "Market Cart Adds", "Cart Adds: Brand Count": "Our Cart Adds",
    "Purchases: Total Count": "Market Purchases", "Purchases: Brand Count": "Our Purchases",
    "Clicks: Price (Median)": "Market Price (at click)",
    "Clicks: Brand Price (Median)": "Our Price (at click)",
    "Purchases: Price (Median)": "Market Price (at purchase)",
    "Purchases: Brand Price (Median)": "Our Price (at purchase)",
    "PS_vs_median": "Share vs Own Median (pp)",
    "market_purch_now": "Market Purchases (now)",
    "market_start": "Market Purchases (start)", "market_end": "Market Purchases (end)",
    "brand_start": "Our Purchases (start)", "brand_end": "Our Purchases (end)",
    "FE_end": "Funnel Efficiency", "severity": "Severity",
    "months_present": "Months Present", "avg_volume": "Average Search Volume",
    "fit_r2": "Trend Fit", "seasonal_conc": "Seasonality",
    "brand_PS_latest": "Our Purchase Share % (latest)",
    "brand_IS_latest": "Our Impression Share % (latest)",
    "mean_pct": "Average Share %", "sd_pp": "Variation (pp)",
    "mean_market_purch": "Average Market Purchases",
    "market_purch_0": "Market Purchases (prior year)",
    "market_purch_1": "Market Purchases (this year)",
    "brand_purch_0": "Our Purchases (prior year)",
    "brand_purch_1": "Our Purchases (this year)",
    "share_0_pct": "Our Purchase Share % (prior year)",
    "share_1_pct": "Our Purchase Share % (this year)",
    "total_change": "Total Order Change", "prior": "Compared With",
    "displacement_pp": "Lost Ground (pp)", "dilution_pp": "Market Grew Around Us (pp)",
    "total_pp": "Net Share Change (pp)",
    "market_purch_latest": "Market Purchases (latest)",
    "brand_purch_latest": "Our Purchases (latest)",
    "entered": "Terms Entered", "exited": "Terms Exited",
    "overlap": "Terms In Both Months", "n_prior": "Terms Last Month",
    "n_current": "Terms This Month", "seasonal_index": "Seasonal Index",
    "value": "Search Volume", "month": "Month Number", "is_event": "Sale Event Month",
    "score_max": "Max Rank", "vol_min": "Lowest Search Volume",
    "vol_max": "Highest Search Volume", "total_SQV": "Total Search Volume",
    "N_flag": "Export Size Anomaly", "asins": "ASINs", "scp_impr": "Our Impressions (all terms)",
    "sqp_impr": "Our Impressions (top terms only)",
    "TC": "Market Clicks", "BC": "Our Clicks",
    "TA": "Market Cart Adds", "BA": "Our Cart Adds",
    "TP": "Market Purchases", "BP": "Our Purchases",
    "IS": "Our Impression Share %", "CS": "Our Click Share %",
    "AS": "Our Cart Add Share %", "PS": "Our Purchase Share %",
    "R1": "Tile Score", "R2": "Page Score", "R3": "Offer Score",
    "R1_end": "Tile Score", "R2_end": "Page Score", "R3_end": "Offer Score",
    "R1_mean": "Tile Score (average)", "R2_mean": "Page Score (average)",
    "R3_mean": "Offer Score (average)",
    "R1_latest": "Tile Score (latest)", "R2_latest": "Page Score (latest)",
    "R3_latest": "Offer Score (latest)",
    "R1_months_below_1": "Tile Score: months below market",
    "R2_months_below_1": "Page Score: months below market",
    "R3_months_below_1": "Offer Score: months below market",
    "R1_persistent_deficit": "Tile Score persistently weak",
    "R2_persistent_deficit": "Page Score persistently weak",
    "R3_persistent_deficit": "Offer Score persistently weak",
    "R1_target": "Tile Score target", "R2_target": "Page Score target",
    "R3_target": "Offer Score target",
    "FE": "Funnel Efficiency",
    "SQV": "Search Volume", "Search Query Volume": "Search Volume",
    "Search Query": "Search Term", "Search Query Score": "Amazon Rank (1=best)",
    "q": "Search Term (normalised)",
    "PIc": "Our Price vs Market (at click)",
    "PIa": "Our Price vs Market (at cart)",
    "PIp": "Our Price vs Market (at purchase)",
    "SCI": "Results Page Crowding", "MPR": "Purchases per Search",
    "MCLR": "Market Close Rate", "PLS": "Market Price Ladder",
    "FSM_market": "Market Fast-Delivery Share",
    "phi": "Volatility Score", "queries": "Search Terms",
    "query_type": "Term Type", "segment": "Age Segment", "in_scope": "In Scope",
    "theme": "Category", "period": "Month", "n_periods": "Months Present",
    "dx_label": "Diagnosis", "dx_secondary": "Secondary Flags",
    "dx_family": "Diagnosis Area", "dx_evidence": "Evidence Needed",
    "dx_confidence": "Confidence (0-1)", "lever": "Fix Type",
    "d_purchases": "Extra Orders / Month", "purch_floor": "Extra Orders (low)",
    "purch_ceiling": "Extra Orders (high)", "priority": "Priority Score",
    "purch_best_stage": "Extra Orders from Stage Fix",
    "purch_visibility": "Extra Orders from Visibility",
    "purch_total_addressable": "Extra Orders / Month (total)",
    "best_stage": "Weakest Stage",
    "market_purch": "Market Purchases", "brand_purch": "Our Purchases",
    "opportunity": "Extra Orders / Month", "volume": "Search Volume",
    "market_index": "Market Size Index", "cell": "Read",
    "delta_pp": "Share Change (pp)", "z": "Significance (z)",
    "significant": "Statistically Real", "direction": "Direction",
    "market_growth_pct": "Market Growth %", "brand_growth_pct": "Our Growth %",
    "purchases_at_stake": "Orders at Stake / Month",
    "PS_start": "Our Purchase Share % (start)", "PS_end": "Our Purchase Share % (end)",
    "market_effect": "Orders from Market Growth",
    "share_effect": "Orders from Share Gain",
    "share_effect_pct": "% of Growth Earned", "driver": "Driver",
    "share_delta_pp": "Share Change (pp)",
    "lifecycle": "Lifecycle Stage", "annual_growth": "Annual Growth",
    "stability": "Stability", "churn": "Term Churn", "jaccard": "Term Overlap",
    "N_rows": "Rows Analysed", "raw_rows": "Rows in Export",
    "purch_coverage": "Share of Our Orders Visible", "aov": "Average Order Value",
    "scp_sales": "Search Revenue", "scp_purch": "Our Orders (all terms)",
    "sqp_purch": "Our Orders (top terms only)",
}


def money(v: float, mp) -> str:
    """Format currency the way the marketplace's readers actually write it."""
    sym = mp.report_symbol or mp.symbol
    if mp.code == "amazon.in":
        if v >= 1e7:
            return f"{sym}{v/1e7:.2f} crore"
        if v >= 1e5:
            return f"{sym}{v/1e5:.1f} lakh"
    if v >= 1e6:
        return f"{sym}{v/1e6:.1f}M"
    if v >= 1e3:
        return f"{sym}{v/1e3:.0f}k"
    return f"{sym}{v:,.0f}"


def pretty_segment(code: str) -> str:
    """KIDS_4_10 -> 'Kids 4-10'. Segment codes must never reach a reader."""
    if not code:
        return code
    parts = code.split("_")
    word = parts[0].title()
    nums = [p for p in parts[1:] if p.isdigit()]
    if len(nums) == 2:
        return f"{word} {nums[0]}-{nums[1]}"
    return " ".join([word] + nums) if nums else word


def humanize(df: pd.DataFrame) -> pd.DataFrame:
    """Rename short internal codes to labels a first-time reader can follow."""
    if df is None or df.empty:
        return df
    return df.rename(columns={c: COLUMN_LABELS.get(c, c) for c in df.columns})


def definitions_table() -> pd.DataFrame:
    """The glossary, written for someone who has never seen this report."""
    rows = [
        ("THE FOUR FUNNEL STEPS", "", "", ""),
        ("Market Impressions", "Total, whole market", "Times ANY seller's product appeared for this search", ""),
        ("Our Impressions", "Ours only", "Times OUR product appeared for this search", ""),
        ("Market Clicks / Our Clicks", "Step 2", "Shoppers who clicked through", ""),
        ("Market Cart Adds / Our Cart Adds", "Step 3", "Shoppers who added to basket", ""),
        ("Market Purchases / Our Purchases", "Step 4", "Orders placed. ORDERS, not units: one order of 3 bottles counts once", ""),
        ("", "", "", ""),
        ("SHARE: our slice of the market", "", "", ""),
        ("Our Impression Share %", "Our Impressions / Market Impressions", "How often we show up", "Higher is better"),
        ("Our Click Share %", "Our Clicks / Market Clicks", "Our slice of all clicks", "Higher is better"),
        ("Our Cart Add Share %", "Our Cart Adds / Market Cart Adds", "Our slice of all cart adds", "Higher is better"),
        ("Our Purchase Share %", "Our Purchases / Market Purchases", "Our slice of all sales. The headline number", "Higher is better"),
        ("", "", "", ""),
        ("THE THREE STAGE SCORES: us vs the market. 1.00 = exactly average", "", "", ""),
        ("Tile Score", "Click Share / Impression Share", "Do people click us when they see us? THE SEARCH RESULT TILE (image, title, price)", "Above 1 = our tile beats the market"),
        ("Page Score", "Cart Add Share / Click Share", "Do clickers add to cart? THE PRODUCT PAGE (content, images, reviews)", "Above 1 = our page beats the market"),
        ("Offer Score", "Purchase Share / Cart Add Share", "Do cart-adders buy? THE OFFER (price, delivery, availability)", "Above 1 = our offer beats the market"),
        ("Funnel Efficiency", "Purchase Share / Impression Share", "Sales won per unit of visibility. Tile x Page x Offer", "Above 1.5 = we win when seen, we just aren't seen enough"),
        ("", "", "", ""),
        ("HOW TO READ THE SCORES", "", "", ""),
        ("Below 0.60", "", "Severe problem at that stage", ""),
        ("0.60 to 0.85", "", "Losing to the market", ""),
        ("0.85 to 1.15", "", "About average", ""),
        ("1.15 to 1.50", "", "Beating the market", ""),
        ("Above 1.50", "", "Strongly beating the market", ""),
        ("THE DIAGNOSTIC RULE", "", "If a problem is upstream, ALL later shares fall together and the three scores stay flat. If ONE score moves, the problem is at that stage.", ""),
        ("", "", "", ""),
        ("EVERYTHING ELSE", "", "", ""),
        ("Search Volume", "", "How many times this was searched in the month", ""),
        ("Amazon Rank (1=best)", "", "Amazon's rank of this term BY OUR OWN PERFORMANCE, not by market size", "Only top 1,000 are exported"),
        ("Our Price vs Market", "Our median / market median", "1.00 = same price. 2.00 = we cost twice as much", ""),
        ("Results Page Crowding", "Market Impressions / Search Volume", "How many products compete per search. If this rises, EVERYONE's impression share falls mechanically", "Check before calling a share drop a problem"),
        ("Purchases per Search", "Market Purchases / Search Volume", "How commercial the search is. Low = browsing, not buying", ""),
        ("Market Fast-Delivery Share", "", "How much of the category buys same-day or 1-day. MARKET only, not ours", ""),
        ("Volatility Score", "", "Below 1.5 = stable. 1.5 to 3 = real movement. Above 3 = too erratic to trust", ""),
        ("Significance (z)", "", "Beyond +/-1.96 means under 5% chance the change is random luck", ""),
        ("Extra Orders / Month", "", "Additional ORDERS if the diagnosed problem is fixed. Deliberately not in money: margin varies too much by product", "Apply your own economics"),
        ("Confidence (0-1)", "", "How clear-cut the diagnosis is. Below 0.6 means verify before acting", ""),
        ("Relevance Segment", "", "Which part of the market this search belongs to. Searches outside what the brand can serve are excluded from opportunity ranking", ""),
        ("Term Type", "", "BRANDED = contains our name. COMPETITOR = contains a rival's name. UNBRANDED = generic demand", ""),
        ("Category", "", "Searches grouped into product categories. Individual terms are too small to trend reliably", ""),
    ]
    return pd.DataFrame(rows, columns=["Term", "How it is calculated", "What it means", "Reading it"])


AGG_FIELDS = ["queries", "SQV", "TI", "BI", "TC", "BC", "TA", "BA", "TP", "BP",
              "IS", "CS", "AS", "PS", "R1", "R2", "R3", "FE"]


def empty_agg() -> pd.Series:
    return pd.Series({k: (0 if k in ("queries",) else np.nan) for k in AGG_FIELDS})


def aggregate(g: pd.DataFrame) -> pd.Series:
    if g is None or len(g) == 0:
        return empty_agg()
    """
    Roll a set of queries up to one funnel.

    Sums numerators and denominators, then divides. Never averages shares:
    averaging gives a 50-search query the same weight as a 50,000-search query
    and reliably concludes you are strong where you are weak.
    """
    TI, BI = g[TOTAL["Impressions"]].sum(), g[BRAND["Impressions"]].sum()
    TC, BC = g[TOTAL["Clicks"]].sum(), g[BRAND["Clicks"]].sum()
    TA, BA = g[TOTAL["Cart Adds"]].sum(), g[BRAND["Cart Adds"]].sum()
    TP, BP = g[TOTAL["Purchases"]].sum(), g[BRAND["Purchases"]].sum()

    IS = 100.0 * BI / TI if TI else np.nan
    CS = 100.0 * BC / TC if TC else np.nan
    AS = 100.0 * BA / TA if TA else np.nan
    PS = 100.0 * BP / TP if TP else np.nan

    return pd.Series({
        "queries": len(g), "SQV": g["Search Query Volume"].sum(),
        "TI": TI, "BI": BI, "TC": TC, "BC": BC,
        "TA": TA, "BA": BA, "TP": TP, "BP": BP,
        "IS": IS, "CS": CS, "AS": AS, "PS": PS,
        "R1": CS / IS if IS else np.nan,
        "R2": AS / CS if CS else np.nan,
        "R3": PS / AS if AS else np.nan,
        "FE": PS / IS if IS else np.nan,
    })


# ---------------------------------------------------------------------------
# Reliability gates
# ---------------------------------------------------------------------------

# Market-side minimums for trusting a SHARE (share estimation precision).
SHARE_GATES = {"IS": ("TI", 1000), "CS": ("TC", 400), "AS": ("TA", 200), "PS": ("TP", 50)}
# Market purchases needed before a share CHANGE can be claimed at query level.
PS_CHANGE_GATE = 400
# Brand-side minimums for trusting a stage INDEX (diagnosis confidence).
INDEX_GATES = {"R1": ("BI", 1000), "R2": ("BC", 50), "R3": ("BA", 25)}


def add_reliability(df: pd.DataFrame) -> pd.DataFrame:
    attrs = dict(df.attrs)
    df = df.copy()
    df.attrs.update(attrs)
    df["n_TI"], df["n_TC"] = df[TOTAL["Impressions"]], df[TOTAL["Clicks"]]
    df["n_TA"], df["n_TP"] = df[TOTAL["Cart Adds"]], df[TOTAL["Purchases"]]
    df["ok_R1"] = df[BRAND["Impressions"]] >= INDEX_GATES["R1"][1]
    df["ok_R2"] = df[BRAND["Clicks"]] >= INDEX_GATES["R2"][1]
    df["ok_R3"] = df[BRAND["Cart Adds"]] >= INDEX_GATES["R3"][1]
    df["ok_PS_level"] = df[TOTAL["Purchases"]] >= SHARE_GATES["PS"][1]
    df["ok_PS_change"] = df[TOTAL["Purchases"]] >= PS_CHANGE_GATE
    df["diagnosable"] = df["ok_R1"] | df["ok_R2"] | df["ok_R3"]
    return df


def share_se(share_pct: float, n: float, deff: float = 1.5) -> float:
    """Standard error of a share in percentage points, with overdispersion."""
    if not n or n <= 0 or pd.isna(share_pct):
        return np.nan
    s = share_pct / 100.0
    return 100.0 * np.sqrt(deff * s * (1 - s) / n)


def share_change_z(s0, n0, s1, n1, deff: float = 1.5) -> float:
    """Two-proportion z for a share change, shares in percentage points."""
    if min(n0 or 0, n1 or 0) <= 0 or pd.isna(s0) or pd.isna(s1):
        return np.nan
    p0, p1 = s0 / 100.0, s1 / 100.0
    se = np.sqrt(deff * (p0 * (1 - p0) / n0 + p1 * (1 - p1) / n1))
    return (p1 - p0) / se if se > 0 else np.nan


def bh_fdr(pvals: np.ndarray, q: float = 0.10) -> np.ndarray:
    """Benjamini-Hochberg. Returns a boolean reject mask."""
    p = np.asarray(pvals, dtype=float)
    ok = ~np.isnan(p)
    out = np.zeros(len(p), dtype=bool)
    if ok.sum() == 0:
        return out
    idx = np.where(ok)[0]
    order = idx[np.argsort(p[idx])]
    m = len(order)
    thresh = q * np.arange(1, m + 1) / m
    passed = p[order] <= thresh
    if passed.any():
        out[order[: np.max(np.where(passed)[0]) + 1]] = True
    return out


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------

def build_panels(df: pd.DataFrame) -> dict:
    """
    CORE     present in every period. Licensed for trend, seasonality, volatility.
    STABLE   present in >= 80% of periods. Lifecycle and cohort work.
    FULL     ever seen. Coverage and discovery only, never a trend claim.

    Panel membership must be stamped on every trend output. Mixing panels
    produces "declines" that are entirely composition change.
    """
    periods = sorted(df["period"].unique())
    presence = df.groupby("q")["period"].nunique()
    n = len(periods)
    return {
        "periods": periods,
        "n_periods": n,
        "CORE": set(presence[presence == n].index),
        "STABLE": set(presence[presence >= 0.8 * n].index),
        "FULL": set(presence.index),
        "presence": presence,
    }


def panel_coverage(df: pd.DataFrame, panel: set, period: str, metric: str) -> float:
    """
    Share of `metric` in `period` accounted for by `panel`.

    Gate on the metric being analyzed, not on volume. On a 1000-row capped
    export the CORE panel can be a third of volume but three quarters of
    purchases, and gating on volume would wrongly suppress valid work.
    """
    cur = df[df["period"] == period]
    tot = cur[metric].sum()
    return float(cur[cur["q"].isin(panel)][metric].sum() / tot) if tot else np.nan


def export_scope(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-export scope metadata. A jump in row count or score ceiling means the
    export scope changed, not the market. This check runs before anything else
    and suppresses other alerts when it trips.
    """
    rows = []
    for p, g in df.groupby("period"):
        rows.append({
            "period": p, "N_rows": len(g),
            "raw_rows": int(g["raw_rows_in_export"].iloc[0]),
            "score_max": g["Search Query Score"].max(),
            "vol_min": g["Search Query Volume"].min(),
            "vol_max": g["Search Query Volume"].max(),
            "total_SQV": g["Search Query Volume"].sum(),
            "brand_purch": g[BRAND["Purchases"]].sum(),
            "market_purch": g[TOTAL["Purchases"]].sum(),
            "is_event": bool(g["is_event"].iloc[0]),
        })
    out = pd.DataFrame(rows).sort_values("period").reset_index(drop=True)
    cur = out["N_rows"]
    out["N_flag"] = (cur - cur.median()).abs() / cur.median() > 0.20
    return out


def churn_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Month-to-month query overlap. On a capped export this runs structurally
    high (0.5 to 0.7 monthly is normal), so it is reported for context rather
    than alarmed on at generic thresholds.
    """
    periods = sorted(df["period"].unique())
    sets = {p: set(df[df["period"] == p]["q"]) for p in periods}
    rows = []
    for a, b in zip(periods, periods[1:]):
        inter, union = len(sets[a] & sets[b]), len(sets[a] | sets[b])
        rows.append({"period": b, "overlap": inter, "n_prior": len(sets[a]),
                     "n_current": len(sets[b]),
                     "jaccard": inter / union if union else np.nan,
                     "churn": 1 - inter / union if union else np.nan,
                     "entered": len(sets[b] - sets[a]), "exited": len(sets[a] - sets[b])})
    cols = ["period", "overlap", "n_prior", "n_current", "jaccard", "churn",
            "entered", "exited"]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Growth decomposition
# ---------------------------------------------------------------------------

def decompose_growth(TP0, BP0, TP1, BP1) -> dict:
    """
    Split brand purchase growth into market growth and share gain.

    Shapley-symmetric, so the two effects sum exactly to the change with no
    unallocated interaction term. Only the share effect is management
    performance; the market effect is the category rising underneath you.
    """
    if not TP0 or not TP1:
        return {}
    s0, s1 = BP0 / TP0, BP1 / TP1
    market = (TP1 - TP0) * (s0 + s1) / 2
    share = (s1 - s0) * (TP0 + TP1) / 2
    total = BP1 - BP0
    return {
        "market_purch_0": TP0, "market_purch_1": TP1,
        "brand_purch_0": BP0, "brand_purch_1": BP1,
        "share_0_pct": 100 * s0, "share_1_pct": 100 * s1,
        "share_delta_pp": 100 * (s1 - s0),
        "market_effect": market, "share_effect": share,
        "total_change": total,
        "market_effect_pct": 100 * market / total if total else np.nan,
        "share_effect_pct": 100 * share / total if total else np.nan,
    }


def dilution_vs_displacement(B0, T0, B1, T1) -> dict:
    """
    Every share change has two mechanically distinct causes needing opposite
    responses: the market grew around you (dilution, moderate concern) or you
    lost absolute ground (displacement, diagnose immediately).
    """
    if not T0 or not T1:
        return {}
    disp = (B1 - B0) / T0
    dil = B1 * (1 / T1 - 1 / T0)
    total = B1 / T1 - B0 / T0
    if abs(total) < 1e-12:
        driver = "NO CHANGE"
    elif abs(disp) >= abs(dil):
        driver = "DISPLACEMENT"
    else:
        driver = "DILUTION"
    return {"displacement_pp": 100 * disp, "dilution_pp": 100 * dil,
            "total_pp": 100 * total, "driver": driver}
