"""
Phase 2 - CSV Metadata Analysis.
Reads both brand CSVs and generates structured analysis data.

Usage:
    python metadata_analysis.py <analysis_name>

Reads config from outputs/<analysis_name>/config.json
Saves to: outputs/<analysis_name>/analysis/
"""

import csv
import json
import sys
import re
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime, timedelta

BASE = Path.cwd()


def load_config(analysis_name):
    config_path = BASE / "outputs" / analysis_name / "config.json"
    if not config_path.exists():
        print(f"ERROR: No config.json at {config_path}")
        sys.exit(1)
    return json.loads(config_path.read_text(encoding="utf-8"))


SLIM_COLS = [
    "ad_archive_id", "start_date_formatted", "end_date_formatted",
    "snapshot/display_format", "snapshot/title", "snapshot/body/text",
    "snapshot/caption", "snapshot/cta_type", "snapshot/link_url",
    "snapshot/videos/0/video_sd_url", "snapshot/images/0/original_image_url",
    "snapshot/videos/0/video_preview_image_url", "collation_count",
    "contains_digital_created_media", "snapshot/branded_content/page_name",
]

OFFER_KEYWORDS = [
    r"[₹\$][\s]?\d+", r"\d+\s*%\s*off", r"\bcombo\b", r"\bkit\b",
    r"\bfree\b", r"\bbundle\b", r"\bpack\b", r"\bsale\b", r"\bdeal\b",
    r"\bdiscount\b", r"\boffer\b", r"\bget\b.*\bfree\b", r"\bbuy\b.*\bget\b",
    r"sunny side up", r"\b99\b", r"\b199\b", r"\b299\b", r"\b399\b",
]


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def slim_row(row):
    return {col: row.get(col, "").strip() for col in SLIM_COLS}


def get_hook(body_text):
    if not body_text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", body_text.strip())
    return sentences[0] if sentences else ""


def detect_offers(text):
    text_lower = text.lower() if text else ""
    found = []
    for pattern in OFFER_KEYWORDS:
        matches = re.findall(pattern, text_lower)
        if matches:
            found.extend(matches)
    return list(set(found))


def extract_product_slug(url):
    if not url:
        return "other"
    m = re.search(r"/(products|collections)/([^/?#]+)", url)
    if m:
        return f"/{m.group(1)}/{m.group(2)}"
    return url.split("?")[0][-60:]


def parse_date(date_str):
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except Exception:
            pass
    return None


def analyze_brand(rows, brand_folder):
    result = {
        "brand": brand_folder,
        "total_ads": len(rows),
        "slim_rows": [slim_row(r) for r in rows],
    }

    fmt_counter = Counter(r.get("snapshot/display_format", "UNKNOWN").upper() for r in rows)
    result["format_breakdown"] = dict(fmt_counter)

    cta_counter = Counter(r.get("snapshot/cta_type", "") for r in rows)
    result["cta_distribution"] = dict(cta_counter)

    url_counter = Counter(extract_product_slug(r.get("snapshot/link_url", "")) for r in rows)
    result["product_focus"] = dict(url_counter.most_common(20))

    branded = [r for r in rows if r.get("snapshot/branded_content/page_name", "").strip()]
    result["branded_content_count"] = len(branded)
    result["branded_content_pages"] = dict(Counter(r["snapshot/branded_content/page_name"] for r in branded))
    result["branded_content_ads"] = [slim_row(r) for r in branded]

    titles = [r.get("snapshot/title", "").strip() for r in rows if r.get("snapshot/title", "").strip()]
    result["top_titles"] = dict(Counter(titles).most_common(15))

    hooks = []
    for r in rows:
        body = r.get("snapshot/body/text", "").strip()
        hook = get_hook(body)
        if hook:
            hooks.append({
                "ad_id": r.get("ad_archive_id", ""),
                "hook": hook,
                "full_body": body[:300],
                "format": r.get("snapshot/display_format", ""),
                "title": r.get("snapshot/title", ""),
            })
    result["hooks"] = hooks

    offers_found = []
    for r in rows:
        text = " ".join([
            r.get("snapshot/title", ""),
            r.get("snapshot/body/text", ""),
            r.get("snapshot/caption", ""),
        ])
        found = detect_offers(text)
        if found:
            offers_found.append({
                "ad_id": r.get("ad_archive_id", ""),
                "offers": found,
                "title": r.get("snapshot/title", ""),
                "body_snippet": r.get("snapshot/body/text", "")[:200],
            })
    result["ads_with_offers"] = offers_found
    result["offer_count"] = len(offers_found)

    ai_gen = [r for r in rows if str(r.get("contains_digital_created_media", "")).lower() in ("true", "1", "yes")]
    result["ai_generated_count"] = len(ai_gen)

    weekly = defaultdict(int)
    for r in rows:
        d = parse_date(r.get("start_date_formatted", ""))
        if d:
            week_start = (d - timedelta(days=d.weekday())).strftime("%Y-W%W")
            weekly[week_start] += 1
    result["weekly_cadence"] = dict(sorted(weekly.items()))
    # Count only ads launched in the last 28 days — evergreen ads started before this window
    # are excluded so the velocity reflects new creative output, not total active library size.
    cutoff = datetime.today() - timedelta(days=28)
    new_in_period = [r for r in rows if parse_date(r.get("start_date_formatted", "")) and parse_date(r.get("start_date_formatted", "")) >= cutoff]
    result["avg_ads_per_week"] = round(len(new_in_period) / 4.0, 1)

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python metadata_analysis.py <analysis_name>")
        sys.exit(1)

    analysis_name = sys.argv[1]
    cfg = load_config(analysis_name)
    analysis_dir = BASE / "outputs" / analysis_name
    out_dir = analysis_dir / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    brand_a = cfg["brand_a"]
    brand_b = cfg["brand_b"]

    print("Reading CSVs...")
    rows_a = read_csv(BASE / brand_a["csv"])
    rows_b = read_csv(BASE / brand_b["csv"])
    print(f"{brand_a['label']}: {len(rows_a)} ads")
    print(f"{brand_b['label']}: {len(rows_b)} ads")

    data_a = analyze_brand(rows_a, brand_a["folder"])
    data_b = analyze_brand(rows_b, brand_b["folder"])

    (out_dir / f"{brand_a['folder']}_analysis.json").write_text(
        json.dumps(data_a, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / f"{brand_b['folder']}_analysis.json").write_text(
        json.dumps(data_b, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    comparison = {
        "generated_at": datetime.now().isoformat(),
        brand_a["folder"]: {
            "total_ads": data_a["total_ads"],
            "label": brand_a["label"],
            "format_breakdown": data_a["format_breakdown"],
            "cta_distribution": data_a["cta_distribution"],
            "branded_content_count": data_a["branded_content_count"],
            "branded_content_pages": data_a["branded_content_pages"],
            "offer_count": data_a["offer_count"],
            "ai_generated_count": data_a["ai_generated_count"],
            "avg_ads_per_week": data_a["avg_ads_per_week"],
            "top_titles": data_a["top_titles"],
        },
        brand_b["folder"]: {
            "total_ads": data_b["total_ads"],
            "label": brand_b["label"],
            "format_breakdown": data_b["format_breakdown"],
            "cta_distribution": data_b["cta_distribution"],
            "branded_content_count": data_b["branded_content_count"],
            "branded_content_pages": data_b["branded_content_pages"],
            "offer_count": data_b["offer_count"],
            "ai_generated_count": data_b["ai_generated_count"],
            "avg_ads_per_week": data_b["avg_ads_per_week"],
            "top_titles": data_b["top_titles"],
        },
    }
    (out_dir / "comparison_summary.json").write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    for label, data in [(brand_a["label"], data_a), (brand_b["label"], data_b)]:
        print(f"\n{label}: {data['format_breakdown']}")
        print(f"  Influencer ads: {data['branded_content_count']} | Offers: {data['offer_count']} | Avg/week: {data['avg_ads_per_week']}")

    print(f"\nOutputs saved to {out_dir}")


if __name__ == "__main__":
    main()
