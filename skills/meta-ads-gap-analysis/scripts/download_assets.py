"""
Download video and image assets from Meta Ads Library CSVs.

Usage:
    python download_assets.py <analysis_name>

Reads brand/CSV config from outputs/<analysis_name>/config.json
Downloads to: outputs/<analysis_name>/assets/<brand>/videos|images/<id>.ext
Skips files that already exist (idempotent).
"""

import os
import sys
import csv
import json
import time
import requests
from pathlib import Path

BASE = Path.cwd()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def load_config(analysis_name):
    config_path = BASE / "outputs" / analysis_name / "config.json"
    if not config_path.exists():
        print(f"ERROR: No config.json at {config_path}")
        print("Create it with brand_a and brand_b entries (folder, label, csv).")
        sys.exit(1)
    return json.loads(config_path.read_text(encoding="utf-8"))


def download_file(url, dest_path):
    if dest_path.exists():
        return "skipped"
    try:
        r = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        r.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        return "ok"
    except Exception as e:
        return f"FAIL: {e}"


def run():
    if len(sys.argv) < 2:
        print("Usage: python download_assets.py <analysis_name>")
        sys.exit(1)

    analysis_name = sys.argv[1]
    cfg = load_config(analysis_name)
    analysis_dir = BASE / "outputs" / analysis_name

    brands = [cfg["brand_a"], cfg["brand_b"]]
    results = []

    for brand in brands:
        brand_folder = brand["folder"]
        csv_path = BASE / brand["csv"]
        ok = skip = fail = 0

        print(f"\n=== {brand['label']} ({brand_folder}) ===")
        if not csv_path.exists():
            print(f"  ERROR: CSV not found at {csv_path}")
            continue

        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        for row in rows:
            ad_id = row.get("ad_archive_id", "unknown").strip()
            video_url = row.get("snapshot/videos/0/video_sd_url", "").strip()
            image_url = row.get("snapshot/images/0/original_image_url", "").strip()
            fmt = row.get("snapshot/display_format", "").strip().upper()

            if video_url:
                dest = analysis_dir / "assets" / brand_folder / "videos" / f"{ad_id}.mp4"
                status = download_file(video_url, dest)
                if status == "ok":
                    ok += 1
                elif status == "skipped":
                    skip += 1
                else:
                    fail += 1
                print(f"  VIDEO {ad_id}: {status}")

            if image_url:
                url_path = image_url.split("?")[0]
                img_ext = Path(url_path).suffix or ".jpg"
                dest = analysis_dir / "assets" / brand_folder / "images" / f"{ad_id}{img_ext}"
                status = download_file(image_url, dest)
                if status == "ok":
                    ok += 1
                elif status == "skipped":
                    skip += 1
                else:
                    fail += 1
                print(f"  IMAGE {ad_id}: {status}")

            if not video_url and not image_url:
                print(f"  SKIP  {ad_id}: no media URL (format={fmt})")

        print(f"  -> downloaded={ok} skipped={skip} failed={fail}")
        results.append({"brand": brand_folder, "ok": ok, "skip": skip, "fail": fail})

    print("\n=== SUMMARY ===")
    for r in results:
        print(f"  {r['brand']}: {r['ok']} downloaded, {r['skip']} skipped, {r['fail']} failed")


if __name__ == "__main__":
    run()
