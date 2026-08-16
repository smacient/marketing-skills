"""
Brand configuration: loading, validating and writing the per-brand JSON config.

Everything brand-specific lives in one JSON file so the engine itself stays
generic. Run `profile_brand.py` first to discover what belongs in it.

Schema:

    {
      "name":         "Acme",                     required
      "data_dir":     "/path/to/brand/folder",    required, holds the two report folders
      "marketplace":  "amazon.in",                default amazon.in
      "sqp_folder":   "Search Query Performance",         optional override
      "scp_folder":   "Search Catalogue Performance",     optional override
      "brand_patterns":  ["\\bacme\\b", "\\bakme\\b"],    required, include misspellings
      "competitors":  {"Rival": "\\brival\\b"},           strongly recommended
      "relevance": {
         "type": "category" | "price_tier" | "none",
         "segments":  {"LABEL": "regex"},         category only
         "in_scope":  ["LABEL"],                  category only
         "max_ratio": 3.0                         price_tier only
      },
      "themes": {"Category name": "regex"}        ordered narrow to broad
    }
"""

from __future__ import annotations

import json
import os
import re

from sqp_lib import BrandConfig, PriceTierRule, RelevanceRule

TEMPLATE = {
    "name": "Brand Name",
    "data_dir": "./data/Brand Name",
    "marketplace": "amazon.in",
    "brand_patterns": [],
    "competitors": {},
    "relevance": {"type": "none"},
    "themes": {},
}


def _build_relevance(spec: dict | None):
    if not spec or spec.get("type", "none") == "none":
        return None
    kind = spec["type"]
    if kind == "price_tier":
        return PriceTierRule(max_ratio=float(spec.get("max_ratio", 3.0)))
    if kind == "category":
        segments = spec.get("segments") or {}
        in_scope = spec.get("in_scope") or []
        if not segments or not in_scope:
            raise ValueError(
                "A category relevance rule needs both 'segments' and 'in_scope'. "
                "Without in_scope every search counts as winnable and generic "
                "high-volume terms will dominate the action list.")
        return RelevanceRule(segments=segments, in_scope=in_scope,
                             fallback=spec.get("fallback", "GENERIC"))
    raise ValueError(f"Unknown relevance type '{kind}'. "
                     "Expected 'category', 'price_tier' or 'none'.")


def _check_regexes(label: str, patterns) -> None:
    items = patterns.items() if isinstance(patterns, dict) else enumerate(patterns)
    for key, pat in items:
        try:
            re.compile(pat)
        except re.error as exc:
            raise ValueError(f"{label} entry '{key}' is not a valid regex: {exc}") from exc


def load(path: str) -> BrandConfig:
    """Read and validate a brand config, resolving data_dir relative to it."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    for field in ("name", "data_dir", "brand_patterns"):
        if not raw.get(field):
            raise ValueError(
                f"Config '{path}' is missing required field '{field}'. "
                f"Run profile_brand.py against the data folder to discover it.")

    data_dir = raw["data_dir"]
    if not os.path.isabs(data_dir):
        data_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), data_dir))
    if not os.path.isdir(data_dir):
        raise ValueError(f"data_dir does not exist: {data_dir}")

    _check_regexes("brand_patterns", raw["brand_patterns"])
    _check_regexes("competitors", raw.get("competitors") or {})
    _check_regexes("themes", raw.get("themes") or {})
    rel = raw.get("relevance") or {}
    if rel.get("type") == "category":
        _check_regexes("relevance.segments", rel.get("segments") or {})

    cfg = BrandConfig(
        name=raw["name"],
        data_dir=data_dir,
        marketplace=raw.get("marketplace", "amazon.in"),
        brand_patterns=list(raw["brand_patterns"]),
        competitor_patterns=dict(raw.get("competitors") or {}),
        relevance=_build_relevance(rel),
        product_themes=dict(raw.get("themes") or {}),
    )
    cfg.sqp_folder = raw.get("sqp_folder", "Search Query Performance")
    cfg.scp_folder = raw.get("scp_folder", "Search Catalogue Performance")
    return cfg


def write_template(path: str, name: str = "Brand Name", data_dir: str = "./data") -> str:
    t = dict(TEMPLATE, name=name, data_dir=data_dir)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(t, fh, indent=2)
    return path


def describe(cfg: BrandConfig) -> str:
    rel = cfg.relevance
    kind = ("none" if rel is None
            else "price_tier" if isinstance(rel, PriceTierRule) else "category")
    scope = "" if rel is None else f" ({', '.join(rel.in_scope)})"
    return (f"{cfg.name} | {cfg.marketplace} | {len(cfg.brand_patterns)} brand patterns | "
            f"{len(cfg.competitor_patterns)} competitors | relevance={kind}{scope} | "
            f"{len(cfg.product_themes)} categories")
