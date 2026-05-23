"""
Normalize Smacient Meta Ads API JSON output to pipeline-compatible CSV format.

Usage:
    python normalize_smacient_data.py <analysis_name>

Reads:  data/<brand_folder>_smacient_raw.json  (one per brand)
Writes: data/<brand_folder>_smacient_<date>.csv (one per brand)
Updates config.json csv path to point to the new CSV.

The raw JSON files must be placed in data/ before running this script.
They should be the direct output from the Smacient search_meta_ads tool
(format: {"ads": [...], "metadata": {...}}).

Run after fetching ads in Claude Code via the Smacient MCP tool.
"""

import csv
import json
import sys
import re
from datetime import date
from pathlib import Path

BASE = Path.cwd()


def load_config(analysis_name):
    config_path = BASE / "outputs" / analysis_name / "config.json"
    if not config_path.exists():
        print(f"ERROR: No config.json at {config_path}")
        sys.exit(1)
    return json.loads(config_path.read_text(encoding="utf-8"))


def save_config(analysis_name, cfg):
    config_path = BASE / "outputs" / analysis_name / "config.json"
    config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def normalize_cta(cta_raw):
    cta_map = {
        "shop now": "SHOP_NOW",
        "learn more": "LEARN_MORE",
        "sign up": "SIGN_UP",
        "get offer": "GET_OFFER",
        "contact us": "CONTACT_US",
        "book now": "BOOK_NOW",
        "subscribe": "SUBSCRIBE",
        "download": "DOWNLOAD",
        "watch more": "WATCH_MORE",
        "apply now": "APPLY_NOW",
        "get quote": "GET_QUOTE",
        "order now": "ORDER_NOW",
        "message page": "MESSAGE_PAGE",
        "send message": "SEND_MESSAGE",
        "like page": "LIKE_PAGE",
        "follow page": "FOLLOW_PAGE",
    }
    return cta_map.get(cta_raw.lower().strip(), cta_raw.upper().replace(" ", "_") if cta_raw else "")


def infer_display_format(ad):
    """Infer VIDEO/IMAGE/CAROUSEL/TEXT from available fields."""
    ad_type = ad.get("type", "").lower()
    has_video = bool(ad.get("video_url", "").strip())
    has_image = bool(ad.get("image_url", "").strip())
    card = ad.get("card", "").strip()

    if card and card != "1 of 1":
        return "CAROUSEL"
    if ad_type == "carousel":
        # Some brands mark all ads as carousel type in the API response
        if has_video:
            return "VIDEO"
        if has_image:
            return "IMAGE"
        return "CAROUSEL"
    if has_video:
        return "VIDEO"
    if has_image:
        return "IMAGE"
    # No media - could be text/catalog ad
    return "TEXT"


def is_influencer_ad(ad, brand_main_page_name):
    """Returns the influencer page name if this is a branded content ad, else empty string."""
    page_name = ad.get("page_name", "").strip()
    if not page_name:
        return ""
    if page_name.lower() == brand_main_page_name.lower():
        return ""
    return page_name


def normalize_ads(raw_ads, brand_main_page_name):
    """
    Normalize a list of raw Smacient ad objects to pipeline CSV format.
    Deduplicates carousel cards - keeps only the first card per ad_id.
    """
    seen_ids = set()
    normalized = []

    for ad in raw_ads:
        ad_id = ad.get("ad_id", "").strip()
        if not ad_id:
            continue

        # Skip duplicate carousel cards (keep first occurrence = card "1 of N")
        if ad_id in seen_ids:
            continue
        seen_ids.add(ad_id)

        display_format = infer_display_format(ad)
        influencer_page = is_influencer_ad(ad, brand_main_page_name)

        normalized.append({
            "ad_archive_id": ad_id,
            "start_date_formatted": ad.get("start_date", ""),
            "end_date_formatted": ad.get("end_date", ""),
            "snapshot/display_format": display_format,
            "snapshot/title": ad.get("ad_title", ""),
            "snapshot/body/text": ad.get("ad_text", ""),
            "snapshot/caption": "",
            "snapshot/cta_type": normalize_cta(ad.get("cta", "")),
            "snapshot/link_url": ad.get("link_url", ""),
            "snapshot/videos/0/video_sd_url": ad.get("video_url", ""),
            "snapshot/images/0/original_image_url": ad.get("image_url", ""),
            "snapshot/videos/0/video_preview_image_url": "",
            "collation_count": "",
            "contains_digital_created_media": "",
            "snapshot/branded_content/page_name": influencer_page,
            # Extra Smacient fields (not used by pipeline but useful for reference)
            "_page_name": ad.get("page_name", ""),
            "_page_url": ad.get("page_url", ""),
            "_ig_username": ad.get("ig_username", ""),
            "_ig_followers": str(ad.get("ig_followers", "") or ""),
            "_platforms": ad.get("platforms", ""),
            "_ad_library_url": ad.get("ad_library_url", ""),
            "_raw_type": ad.get("type", ""),
        })

    return normalized


SLIM_COLS = [
    "ad_archive_id", "start_date_formatted", "end_date_formatted",
    "snapshot/display_format", "snapshot/title", "snapshot/body/text",
    "snapshot/caption", "snapshot/cta_type", "snapshot/link_url",
    "snapshot/videos/0/video_sd_url", "snapshot/images/0/original_image_url",
    "snapshot/videos/0/video_preview_image_url", "collation_count",
    "contains_digital_created_media", "snapshot/branded_content/page_name",
    "_page_name", "_page_url", "_ig_username", "_ig_followers",
    "_platforms", "_ad_library_url", "_raw_type",
]


def main():
    if len(sys.argv) < 2:
        print("Usage: python normalize_smacient_data.py <analysis_name>")
        sys.exit(1)

    analysis_name = sys.argv[1]
    cfg = load_config(analysis_name)
    today = date.today().strftime("%Y-%m-%d")

    for brand_key in ["brand_a", "brand_b"]:
        brand = cfg[brand_key]
        folder = brand["folder"]
        label = brand["label"]
        main_page = brand.get("main_page_name", label)

        raw_path = BASE / "data" / f"{folder}_smacient_raw.json"
        if not raw_path.exists():
            print(f"[SKIP] {label}: no raw JSON at {raw_path}")
            print(f"       Fetch first: call Smacient search_meta_ads and save result to {raw_path}")
            continue

        print(f"\nProcessing {label}...")
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        ads = raw.get("ads", [])
        meta = raw.get("metadata", {})

        print(f"  Raw ads in file: {len(ads)}")
        print(f"  API metadata: {meta.get('total_ads', '?')} total_ads, period={meta.get('period', '?')}")

        normalized = normalize_ads(ads, main_page)
        print(f"  Unique ads after dedup: {len(normalized)}")

        # Count formats
        from collections import Counter
        fmt_counts = Counter(r["snapshot/display_format"] for r in normalized)
        inf_count = sum(1 for r in normalized if r["snapshot/branded_content/page_name"])
        print(f"  Format breakdown: {dict(fmt_counts)}")
        print(f"  Influencer/branded content ads: {inf_count}")

        # Save CSV
        csv_filename = f"{folder}_smacient_{today}.csv"
        csv_path = BASE / "data" / csv_filename
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=SLIM_COLS)
            writer.writeheader()
            for row in normalized:
                writer.writerow({col: row.get(col, "") for col in SLIM_COLS})

        print(f"  Saved: {csv_path}")

        # Update config.json csv path
        cfg[brand_key]["csv"] = f"data/{csv_filename}"

    save_config(analysis_name, cfg)
    print(f"\nConfig updated: {BASE / 'outputs' / analysis_name / 'config.json'}")
    print("Next: run metadata_analysis.py to generate analysis JSON")


if __name__ == "__main__":
    main()
