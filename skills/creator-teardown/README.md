# Creator Teardown Skill

Automates the full analysis pipeline for any Instagram creator. Given a handle, it extracts their posts, downloads and transcribes audio, downloads top videos and extracts frames for visual analysis, and produces four structured documents you can use to brief your content team or build your own scripts and captions.

## What It Produces

| Output File | Contents |
|-------------|----------|
| `{slug}-script-learnings.md` | Spoken hook formulas, series opener, transition phrases, CTA wording (verbatim), what drives performance |
| `{slug}-caption-learnings.md` | Caption structure, hook line patterns, CTA format, hashtag rules, what to avoid |
| `{slug}-visual-analysis.md` | Hook frame format, presenter setup, on-screen text system, B-roll types, editing rhythm |
| `{slug}-creator-learnings.md` | Performance data, what drives views vs comments, content pillars, what flops |

Media assets (audio, videos, transcripts, frames) land in `reference/{slug}/`.

## Requirements

**Python packages:**

```bash
pip install -r requirements.txt
```

**ffmpeg** must be available in your PATH:

- macOS: `brew install ffmpeg`
- Ubuntu: `sudo apt install ffmpeg`
- Windows: `winget install Gyan.FFmpeg` then add the `bin/` folder to PATH

**[Smacient Claude connector](https://smacient.com/products/marketing-context-claude/)** must be connected in your Claude Code session. The skill uses `mcp__claude_ai_Smacient__extract_instagram_posts` to pull posts.

## Setup

1. Install the skill (globally or at project level):

```bash
# Global
cp -r skills/creator-teardown ~/.claude/skills/creator-teardown

# Project level
cp -r skills/creator-teardown path/to/project/.claude/skills/creator-teardown
```

2. Create a virtual environment in your project and install requirements:

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
pip install -r .claude/skills/creator-teardown/requirements.txt
```

## Usage

In a Claude Code session, trigger the skill with any of the following:

- `Do a creator teardown of @username`
- `Analyze creator @username`
- `Run a teardown on @username`
- `Pull learnings from @username`
- `Research @username content strategy`

Claude will confirm parameters (days to look back, how many posts to transcribe, how many videos to analyze) before starting.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `creator_handle` | required | Instagram handle, e.g. `@somecreator` |
| `days` | 30 | How far back to pull posts |
| `top_audio` | 30 | Number of posts to transcribe (top by views + comments, deduplicated) |
| `top_videos` | 10 | Number of videos to download and frame-extract for visual analysis |

## Pipeline Overview

1. **Extract posts** via Smacient Claude connector
2. **Select and download audio** - top posts by views and comments
3. **Transcribe** using Whisper (`small` model by default)
4. **Download top videos** and extract frames (1 frame per 4 seconds)
5. **Visual analysis** - Claude reads frames directly and documents the production system
6. **Caption analysis** - structure, hooks, CTAs, hashtag patterns
7. **Transcript analysis** - spoken script formulas, exact wording, performance correlation

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/download_media.py` | Parallel downloader from a JSON manifest, with fallback URL support |
| `scripts/transcribe.py` | Whisper transcription of an audio directory, with metadata headers |
| `scripts/extract_frames.py` | ffmpeg frame extraction at a fixed interval (default: 1 per 4 seconds) |

## Output Structure

```
reference/
└── {slug}/
    ├── audio_manifest.json
    ├── audio_metadata.json
    ├── video_manifest.json
    ├── audio/
    │   └── rank_01_views_1234567.mp4
    ├── videos/
    │   └── rank_01_views_1234567.mp4
    ├── transcripts/
    │   └── rank_01_views_1234567.txt
    └── frames/
        └── v1/
            ├── frame_001.png
            └── frame_002.png
{slug}-script-learnings.md
{slug}-caption-learnings.md
{slug}-visual-analysis.md
{slug}-creator-learnings.md
```
