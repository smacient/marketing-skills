"""
Download media files from a JSON manifest.
Usage: python download_media.py --manifest <path> --output-dir <dir> [--workers 8]

Manifest format (JSON array):
[
  {"url": "https://...", "filename": "rank_01.mp4"},
  ...
]

Writes _download_results.json to output-dir with per-file success/failure info.
"""
import os
import sys
import json
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


def download_one(entry, output_dir):
    url = entry["url"]
    filename = entry["filename"]
    filepath = os.path.join(output_dir, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        print(f"  [SKIP] {filename} already exists ({os.path.getsize(filepath) // 1024}KB)")
        return filename, True, os.path.getsize(filepath)

    if not url or not url.startswith("http"):
        print(f"  [SKIP] {filename} - no valid URL")
        return filename, False, 0

    # Try primary URL, then fallback if provided
    urls_to_try = [url]
    if entry.get("fallback_url") and entry["fallback_url"] != url:
        urls_to_try.append(entry["fallback_url"])

    for try_url in urls_to_try:
        try:
            resp = requests.get(try_url, timeout=60, stream=True,
                                headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                size_kb = len(resp.content) // 1024
                print(f"  [OK] {filename} ({size_kb}KB)")
                return filename, True, len(resp.content)
            else:
                print(f"  [FAIL {resp.status_code}] {filename}")
        except Exception as e:
            print(f"  [ERROR] {filename}: {e}")

    return filename, False, 0


def main():
    parser = argparse.ArgumentParser(description="Download media files from a JSON manifest")
    parser.add_argument("--manifest", required=True, help="Path to JSON manifest file")
    parser.add_argument("--output-dir", required=True, help="Directory to save files")
    parser.add_argument("--workers", type=int, default=8, help="Parallel download workers")
    args = parser.parse_args()

    if not os.path.exists(args.manifest):
        print(f"[ERROR] Manifest not found: {args.manifest}", file=sys.stderr)
        sys.exit(1)

    with open(args.manifest, encoding="utf-8") as f:
        entries = json.load(f)

    if not entries:
        print("[ERROR] Manifest is empty", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Downloading {len(entries)} files to {args.output_dir} ({args.workers} workers)...")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download_one, e, args.output_dir): e for e in entries}
        for future in as_completed(futures):
            results.append(future.result())

    success = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]
    total_mb = sum(r[2] for r in success) // (1024 * 1024)

    print(f"\nDownloaded: {len(success)}/{len(entries)} files ({total_mb}MB)")
    if failed:
        print(f"Failed ({len(failed)}): {[r[0] for r in failed]}")

    result_path = os.path.join(args.output_dir, "_download_results.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump([{"filename": r[0], "ok": r[1], "bytes": r[2]} for r in results], f, indent=2)
    print(f"Results written to: {result_path}")


if __name__ == "__main__":
    main()
