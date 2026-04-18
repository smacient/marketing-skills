"""
Transcribe MP4 files in a directory using Whisper.
Usage: python transcribe.py --audio-dir <dir> --transcript-dir <dir> [--model small] [--metadata <json>]

Metadata JSON format (optional, keyed by filename):
{
  "rank_01.mp4": {
    "rank": 1, "views": 1234567, "comments": 456,
    "likes": 789, "caption_hook": "...", "timestamp": "2026-03-01"
  }
}

Skips files that already have a transcript. Saves each transcript as {stem}.txt.
"""
import os
import sys
import json
import time
import argparse

def main():
    parser = argparse.ArgumentParser(description="Transcribe MP4 audio files with Whisper")
    parser.add_argument("--audio-dir", required=True, help="Directory containing MP4 files")
    parser.add_argument("--transcript-dir", required=True, help="Directory to save transcripts")
    parser.add_argument("--model", default="small", help="Whisper model size (tiny/base/small/medium)")
    parser.add_argument("--metadata", help="Path to metadata JSON file (optional)")
    args = parser.parse_args()

    if not os.path.isdir(args.audio_dir):
        print(f"[ERROR] Audio directory not found: {args.audio_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        import whisper
    except ImportError:
        print("[ERROR] whisper not installed. Run: pip install openai-whisper", file=sys.stderr)
        sys.exit(1)

    metadata = {}
    if args.metadata and os.path.exists(args.metadata):
        with open(args.metadata, encoding="utf-8") as f:
            metadata = json.load(f)

    os.makedirs(args.transcript_dir, exist_ok=True)

    audio_files = sorted([
        f for f in os.listdir(args.audio_dir)
        if f.lower().endswith(".mp4") and not f.startswith("_")
    ])

    if not audio_files:
        print(f"[ERROR] No MP4 files found in {args.audio_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading Whisper model '{args.model}'...")
    model = whisper.load_model(args.model)
    print(f"Transcribing {len(audio_files)} files...\n")

    success = 0
    skipped = 0
    failed = 0

    for filename in audio_files:
        stem = os.path.splitext(filename)[0]
        transcript_path = os.path.join(args.transcript_dir, f"{stem}.txt")

        if os.path.exists(transcript_path):
            print(f"  [SKIP] {filename} - transcript exists")
            skipped += 1
            success += 1
            continue

        filepath = os.path.join(args.audio_dir, filename)
        meta = metadata.get(filename, {})

        print(f"  [TRANSCRIBING] {filename}...")
        t0 = time.time()
        try:
            result = model.transcribe(filepath, language="en", fp16=False)
            text = result["text"].strip()
            elapsed = round(time.time() - t0, 1)
            print(f"  [DONE] {filename} in {elapsed}s ({len(text)} chars)")
        except Exception as e:
            print(f"  [ERROR] {filename}: {e}", file=sys.stderr)
            failed += 1
            continue

        # Build header
        header_lines = []
        if meta.get("rank"):
            header_lines.append(f"RANK: {meta['rank']}")
        header_lines.append(f"FILE: {filename}")
        if meta.get("views") is not None:
            views = int(meta.get("views", 0))
            comments = int(meta.get("comments", 0))
            likes = int(meta.get("likes", 0))
            header_lines.append(f"VIEWS: {views:,} | COMMENTS: {comments:,} | LIKES: {likes:,}")
        if meta.get("timestamp"):
            header_lines.append(f"DATE: {meta['timestamp']}")
        if meta.get("caption_hook"):
            header_lines.append(f"HOOK (caption): {meta['caption_hook']}")
        header_lines.append("=" * 60)
        header_lines.append("")
        header_lines.append("TRANSCRIPT:")

        full_text = "\n".join(header_lines) + "\n" + text

        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        success += 1

    print(f"\nTranscription complete: {success - skipped} new, {skipped} skipped, {failed} failed")
    print(f"Transcripts saved to: {args.transcript_dir}")


if __name__ == "__main__":
    main()
