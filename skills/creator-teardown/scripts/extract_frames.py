"""
Extract PNG frames from a video file at a fixed interval using ffmpeg.
Usage: python extract_frames.py --video <path> --output-dir <dir> [--interval 4]

Outputs frame_001.png, frame_002.png, ... in output-dir.
Skips extraction if frames already exist in the output directory.
"""
import os
import sys
import subprocess
import argparse

def find_ffmpeg():
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        if result.returncode == 0:
            return "ffmpeg"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    raise RuntimeError(
        "ffmpeg not found in PATH.\n"
        "  macOS:   brew install ffmpeg\n"
        "  Ubuntu:  sudo apt install ffmpeg\n"
        "  Windows: winget install Gyan.FFmpeg  (then add bin/ to PATH)\n"
        "  or download from https://ffmpeg.org/download.html"
    )


def extract_frames(video_path, output_dir, interval=4):
    os.makedirs(output_dir, exist_ok=True)

    existing = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".png")]
    if existing:
        print(f"  [SKIP] {len(existing)} frames already exist in {output_dir}")
        return sorted([os.path.join(output_dir, f) for f in existing])

    ffmpeg = find_ffmpeg()
    pattern = os.path.join(output_dir, "frame_%03d.png")

    cmd = [
        ffmpeg,
        "-i", video_path,
        "-vf", f"fps=1/{interval},scale=720:-1",
        "-q:v", "2",
        pattern,
        "-y",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERROR] ffmpeg failed:\n{result.stderr[-800:]}", file=sys.stderr)
        return []

    frames = sorted([
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.startswith("frame_") and f.endswith(".png")
    ])
    print(f"  [OK] Extracted {len(frames)} frames (1 per {interval}s) to {output_dir}")
    return frames


def main():
    parser = argparse.ArgumentParser(description="Extract frames from a video file")
    parser.add_argument("--video", required=True, help="Path to input video file")
    parser.add_argument("--output-dir", required=True, help="Directory to save PNG frames")
    parser.add_argument("--interval", type=int, default=4, help="Seconds between frames (default: 4)")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"[ERROR] Video not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    frames = extract_frames(args.video, args.output_dir, args.interval)

    if not frames:
        print("[ERROR] No frames were extracted", file=sys.stderr)
        sys.exit(1)

    print(f"\nExtracted {len(frames)} frames:")
    for f in frames:
        print(f"  {f}")


if __name__ == "__main__":
    main()
