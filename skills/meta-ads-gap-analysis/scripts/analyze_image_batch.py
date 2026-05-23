"""
Batch image analysis using Gemini.

Usage:
    python analyze_image_batch.py <analysis_name> <brand>

Processes all images in outputs/<analysis_name>/assets/<brand>/images/
Writes to: outputs/<analysis_name>/video_analysis/<brand>/<id>.md
Requires GEMINI_API_KEY in environment.
"""

import os
import sys
from pathlib import Path

BASE = Path.cwd()

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: google-genai not installed. Run: pip install google-genai")
    sys.exit(1)

PROMPT = """Analyze this Meta ad image for a consumer brand. Structure your output EXACTLY as shown below using these exact bold headings.

**Hook/Attention:** What is the main visual element that grabs attention first?
**Emotional Angle:** ONE of: fear-of-harm / aspiration / social-proof / humor / identity / educational / other — briefly explain
**Creative Type:** ONE of: product-flat-lay / lifestyle-photo / UGC-screenshot / graphic-design / infographic / other
**Key Claim/USP:** The main benefit or claim stated
**On-Screen Text:** List all text shown (verbatim where possible)
**Offers/Pricing:** Any pricing, discounts, or offers mentioned (exact text, or "none")
**Overall Summary:** 2-3 sentences on what this ad communicates and how it persuades"""

MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
    ".gif": "image/gif",
}


def analyze_image(client, image_path: Path) -> str:
    data = image_path.read_bytes()
    mime = MIME_MAP.get(image_path.suffix.lower(), "image/jpeg")
    img_part = types.Part(inline_data=types.Blob(data=data, mime_type=mime))
    text_part = types.Part(text=PROMPT)
    print(f"  [info] Sending to Gemini ({image_path.stat().st_size / 1024:.0f} KB)...", flush=True)
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=types.Content(parts=[img_part, text_part]),
    )
    return response.text or "(no response)"


def main():
    if len(sys.argv) < 3:
        print("Usage: python analyze_image_batch.py <analysis_name> <brand>")
        sys.exit(1)

    analysis_name = sys.argv[1]
    brand = sys.argv[2]
    img_dir = BASE / "outputs" / analysis_name / "assets" / brand / "images"
    out_dir = BASE / "outputs" / analysis_name / "video_analysis" / brand
    out_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    images = [f for f in img_dir.glob("*") if f.suffix.lower() in MIME_MAP]
    print(f"Found {len(images)} images for {brand}")

    ok = fail = skip = 0
    for img_path in sorted(images):
        ad_id = img_path.stem
        out_path = out_dir / f"{ad_id}.md"

        if out_path.exists() and out_path.stat().st_size > 50:
            print(f"[SKIP] {ad_id}", flush=True)
            skip += 1
            continue

        print(f"[RUN ] {ad_id}...", flush=True)
        try:
            result = analyze_image(client, img_path)
            header = f"# Image Analysis: {ad_id} ({brand})\n\n"
            out_path.write_text(header + result + "\n", encoding="utf-8")
            print(f"[DONE] {ad_id}: {len(result)} chars", flush=True)
            ok += 1
        except Exception as e:
            print(f"[FAIL] {ad_id}: {e}", flush=True)
            out_path.write_text(f"# Analysis Failed\n\nError: {e}\n")
            fail += 1

    print(f"\n=== {brand} images: ok={ok} skip={skip} fail={fail} ===")


if __name__ == "__main__":
    main()
