"""
Focused audio hook extraction - re-analyzes all videos for first 5-second hook lines.

Usage:
    python analyze_audio_hooks_batch.py <analysis_name> <brand> <id1> <id2> ...

Outputs to: outputs/<analysis_name>/audio_hooks/<brand>/<id>.md
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

PROMPT = """Watch ONLY the first 5 seconds of this video carefully. Then answer these four fields exactly as shown below.

**First Spoken Line:** The exact verbatim words spoken aloud by any person, narrator, or voiceover in the first 5 seconds. Include punctuation. If no speech in the first 5 seconds, write: none
**First On-Screen Text:** The exact verbatim text that appears as an overlay, caption, or super on screen in the first 5 seconds. If multiple lines appear, list each on a new line with a dash. If no text, write: none
**Hook Type:** Choose exactly ONE: spoken-question / spoken-problem / spoken-claim / spoken-story / text-only / visual-only / mixed
**Hook Summary:** One sentence describing what the opening hook does and what emotion or curiosity it triggers in the viewer."""


def analyze_one(analysis_name: str, brand: str, ad_id: str) -> bool:
    video_path = BASE / "outputs" / analysis_name / "assets" / brand / "videos" / f"{ad_id}.mp4"
    out_path = BASE / "outputs" / analysis_name / "audio_hooks" / brand / f"{ad_id}.md"

    if not video_path.exists():
        print(f"[SKIP] {ad_id}: video file not found", flush=True)
        return False

    if out_path.exists() and out_path.stat().st_size > 80:
        print(f"[SKIP] {ad_id}: already done", flush=True)
        return True

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[RUN ] {ad_id}...", flush=True)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [PYTHON, str(SCRIPT), str(video_path), "--prompt", PROMPT],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=300
    )

    if result.returncode != 0:
        err = result.stderr.strip()[-200:].encode("ascii", errors="replace").decode("ascii")
        print(f"[FAIL] {ad_id}: {err}", flush=True)
        out_path.write_text(f"# Hook Analysis Failed\n\nError: {result.stderr.strip()}\n", encoding="utf-8")
        return False

    output = result.stdout.strip()
    header = f"# Audio Hook: {ad_id} ({brand})\n\n"
    out_path.write_text(header + output + "\n", encoding="utf-8")
    print(f"[DONE] {ad_id}: {len(output)} chars", flush=True)
    return True


def main():
    if len(sys.argv) < 4:
        print("Usage: python analyze_audio_hooks_batch.py <analysis_name> <brand> <id1> <id2> ...")
        sys.exit(1)

    analysis_name = sys.argv[1]
    brand = sys.argv[2]
    ids = sys.argv[3:]
    ok = fail = 0

    for ad_id in ids:
        try:
            if analyze_one(analysis_name, brand, ad_id.strip()):
                ok += 1
            else:
                fail += 1
        except subprocess.TimeoutExpired:
            print(f"[FAIL] {ad_id}: timeout", flush=True)
            fail += 1
        except Exception as e:
            print(f"[FAIL] {ad_id}: {e}", flush=True)
            fail += 1

    print(f"\n=== DONE ({brand}) ok={ok} fail/skip={fail} ===")


if __name__ == "__main__":
    main()
