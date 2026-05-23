"""
Batch video analysis runner.

Usage:
    python analyze_batch.py <analysis_name> <brand> <id1> <id2> ...

Calls analyze_video.py (Gemini) for each video and writes output to:
  outputs/<analysis_name>/video_analysis/<brand>/<id>.md

Skips if output file already exists (idempotent).
Requires GEMINI_API_KEY in environment.
"""

import os
import sys
import subprocess
from pathlib import Path

BASE = Path.cwd()
SCRIPT = Path.home() / ".claude" / "skills" / "claude-vision" / "scripts" / "analyze_video.py"
PYTHON = sys.executable

PROMPT = """Analyze this Meta ad video for a consumer brand. Structure your output EXACTLY as shown below using these exact bold headings. Be specific and factual.

**Hook (0-3s):** What visual, action, or text appears in the first 3 seconds? Be specific.
**Emotional Angle:** ONE of: fear-of-harm / aspiration / social-proof / humor / identity / educational / other — briefly explain which and why
**Narrator Type:** ONE of: founder / mom-influencer / child / voice-over / on-screen-text-only / none
**Key Claim/USP:** The single main benefit or claim stated in this ad
**CTA Delivery:** How and when does the call-to-action appear? (timing and method)
**Production Quality:** ONE of: UGC-lo-fi / polished-brand / mixed
**On-Screen Text:** List all text overlays/supers shown (verbatim where possible)
**Offers/Pricing:** Any pricing, discounts, or offers mentioned (use exact numbers/text if visible, or "none")
**Overall Summary:** 2-3 sentences on what this ad does, what emotion it targets, and how it persuades the viewer"""


def analyze_one(analysis_name: str, brand: str, ad_id: str) -> bool:
    video_path = BASE / "outputs" / analysis_name / "assets" / brand / "videos" / f"{ad_id}.mp4"
    out_path = BASE / "outputs" / analysis_name / "video_analysis" / brand / f"{ad_id}.md"

    if not video_path.exists():
        print(f"[SKIP] {ad_id}: video file not found at {video_path}", flush=True)
        return False

    if out_path.exists() and out_path.stat().st_size > 100:
        print(f"[SKIP] {ad_id}: analysis already exists", flush=True)
        return True

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[RUN ] {ad_id}: analyzing...", flush=True)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [PYTHON, str(SCRIPT), str(video_path), "--prompt", PROMPT],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=300
    )

    if result.returncode != 0:
        err_safe = result.stderr.strip()[-200:].encode("ascii", errors="replace").decode("ascii")
        print(f"[FAIL] {ad_id}: {err_safe}", flush=True)
        out_path.write_text(f"# Analysis Failed\n\nError: {result.stderr.strip()}\n", encoding="utf-8")
        return False

    output = result.stdout.strip()
    header = f"# Ad Analysis: {ad_id} ({brand})\n\n"
    out_path.write_text(header + output + "\n", encoding="utf-8")
    print(f"[DONE] {ad_id}: saved ({len(output)} chars)", flush=True)
    return True


def main():
    if len(sys.argv) < 4:
        print("Usage: python analyze_batch.py <analysis_name> <brand> <id1> <id2> ...")
        sys.exit(1)

    analysis_name = sys.argv[1]
    brand = sys.argv[2]
    ids = sys.argv[3:]

    ok = fail = skip = 0
    for ad_id in ids:
        try:
            result = analyze_one(analysis_name, brand, ad_id.strip())
            if result:
                ok += 1
            else:
                fail += 1
        except subprocess.TimeoutExpired:
            print(f"[FAIL] {ad_id}: timed out after 300s", flush=True)
            fail += 1
        except Exception as e:
            print(f"[FAIL] {ad_id}: {e}", flush=True)
            fail += 1

    print(f"\n=== BATCH DONE ({brand}) ===")
    print(f"  OK: {ok}  FAIL/SKIP: {fail + skip}")


if __name__ == "__main__":
    main()
