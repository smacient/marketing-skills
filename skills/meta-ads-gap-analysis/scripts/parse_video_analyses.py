"""
Parse all video/image analysis .md files and extract structured fields into JSON.

Usage:
    python parse_video_analyses.py <analysis_name>

Reads config from outputs/<analysis_name>/config.json
Input:  outputs/<analysis_name>/video_analysis/<brand>/<id>.md
Output: outputs/<analysis_name>/analysis/video_analyses_parsed.json
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path.cwd()

FIELDS = [
    "Hook (0-3s)", "Emotional Angle", "Narrator Type", "Key Claim/USP",
    "CTA Delivery", "Production Quality", "On-Screen Text", "Offers/Pricing",
    "Overall Summary",
    "Hook/Attention", "Creative Type",
]


def load_config(analysis_name):
    config_path = BASE / "outputs" / analysis_name / "config.json"
    if not config_path.exists():
        print(f"ERROR: No config.json at {config_path}")
        sys.exit(1)
    return json.loads(config_path.read_text(encoding="utf-8"))


def extract_fields(content: str) -> dict:
    result = {}
    for field in FIELDS:
        pattern = rf"\*\*{re.escape(field)}[:\*]+\s*(.*?)(?=\n\*\*|\Z)"
        m = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if m:
            result[field] = m.group(1).strip()
    return result


def normalize_emotional_angle(raw: str) -> str:
    raw_lower = raw.lower()
    for tag in ["fear-of-harm", "aspiration", "social-proof", "humor",
                "identity", "educational", "other"]:
        if tag in raw_lower or tag.replace("-", "") in raw_lower:
            return tag
    if "fear" in raw_lower or "guilt" in raw_lower or "concern" in raw_lower:
        return "fear-of-harm"
    if "aspir" in raw_lower or "goal" in raw_lower:
        return "aspiration"
    if "social" in raw_lower or "proof" in raw_lower or "testimonial" in raw_lower:
        return "social-proof"
    if "humor" in raw_lower or "funny" in raw_lower:
        return "humor"
    if "identity" in raw_lower or "mom" in raw_lower or "parent" in raw_lower:
        return "identity"
    if "educat" in raw_lower or "inform" in raw_lower:
        return "educational"
    return "other"


def normalize_narrator(raw: str) -> str:
    raw_lower = raw.lower()
    if "mom" in raw_lower or "influencer" in raw_lower or "creator" in raw_lower:
        return "mom-influencer"
    if "founder" in raw_lower:
        return "founder"
    if "child" in raw_lower or "kid" in raw_lower:
        return "child"
    if "voice" in raw_lower or "vo" in raw_lower or "voice-over" in raw_lower:
        return "voice-over"
    if "text" in raw_lower or "on-screen" in raw_lower or "supers" in raw_lower:
        return "on-screen-text-only"
    if "none" in raw_lower:
        return "none"
    return raw.strip()[:30]


def normalize_quality(raw: str) -> str:
    raw_lower = raw.lower()
    if "ugc" in raw_lower or "lo-fi" in raw_lower or "lofi" in raw_lower:
        return "UGC-lo-fi"
    if "polished" in raw_lower or "brand" in raw_lower:
        return "polished-brand"
    if "mixed" in raw_lower:
        return "mixed"
    return raw.strip()[:20]


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_video_analyses.py <analysis_name>")
        sys.exit(1)

    analysis_name = sys.argv[1]
    cfg = load_config(analysis_name)
    analysis_dir = BASE / "outputs" / analysis_name
    out_dir = analysis_dir / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    brand_a_folder = cfg["brand_a"]["folder"]
    brand_b_folder = cfg["brand_b"]["folder"]
    brands = [brand_a_folder, brand_b_folder]

    all_analyses = {b: [] for b in brands}

    for brand in brands:
        analysis_path = analysis_dir / "video_analysis" / brand
        if not analysis_path.exists():
            print(f"[WARN] No analysis dir for {brand}")
            continue

        md_files = sorted(analysis_path.glob("*.md"))
        print(f"{brand}: found {len(md_files)} analysis files")

        for md_file in md_files:
            ad_id = md_file.stem
            content = md_file.read_text(encoding="utf-8")

            fields = extract_fields(content)
            is_image = "Image Analysis" in content or "Creative Type" in content

            entry = {
                "ad_id": ad_id,
                "brand": brand,
                "type": "image" if is_image else "video",
                "hook": fields.get("Hook (0-3s)") or fields.get("Hook/Attention", ""),
                "emotional_angle_raw": fields.get("Emotional Angle", ""),
                "emotional_angle": normalize_emotional_angle(fields.get("Emotional Angle", "")),
                "narrator_type_raw": fields.get("Narrator Type", ""),
                "narrator_type": normalize_narrator(fields.get("Narrator Type", "")),
                "key_claim": fields.get("Key Claim/USP", ""),
                "cta_delivery": fields.get("CTA Delivery", ""),
                "production_quality_raw": fields.get("Production Quality", ""),
                "production_quality": normalize_quality(fields.get("Production Quality", "")),
                "on_screen_text": fields.get("On-Screen Text", ""),
                "offers_pricing": fields.get("Offers/Pricing", ""),
                "summary": fields.get("Overall Summary", ""),
                "creative_type": fields.get("Creative Type", ""),
                "raw_content": content[:500],
            }
            all_analyses[brand].append(entry)

    stats = {}
    for brand in brands:
        entries = all_analyses[brand]
        angles = Counter(e["emotional_angle"] for e in entries)
        narrators = Counter(e["narrator_type"] for e in entries)
        quality = Counter(e["production_quality"] for e in entries)
        has_offers = sum(
            1 for e in entries
            if e["offers_pricing"] and e["offers_pricing"].lower() not in ("none", "no offers", "")
        )
        stats[brand] = {
            "total": len(entries),
            "emotional_angles": dict(angles),
            "narrator_types": dict(narrators),
            "production_quality": dict(quality),
            "has_offers": has_offers,
        }

    output = {**all_analyses, "stats": stats}
    out_path = out_dir / "video_analyses_parsed.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved parsed analyses to {out_path}")

    for brand in brands:
        s = stats[brand]
        print(f"\n{brand} ({s['total']} analyzed):")
        print(f"  Emotional angles: {s['emotional_angles']}")
        print(f"  Narrator types:   {s['narrator_types']}")
        print(f"  Production:       {s['production_quality']}")
        print(f"  Ads with offers:  {s['has_offers']}")


if __name__ == "__main__":
    main()
