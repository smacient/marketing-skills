---
name: creator-teardown
description: "Full Instagram creator analysis pipeline. Extracts posts via the Smacient MCP, downloads and transcribes audio with Whisper, downloads top videos and extracts frames for visual analysis, and produces four output documents (script learnings, caption learnings, visual analysis, overall creator strategy). Use this skill whenever the user says 'do a creator teardown of @X', 'analyze creator @X', 'research @X content strategy', 'learn from @X videos', 'run a teardown on @X', 'pull learnings from @X', or wants to build structured learnings from any Instagram creator's content - even if they don't use the word teardown."
---

# Creator Teardown

Produces four documents for any Instagram creator:
- `reference/{slug}-script-learnings.md`
- `reference/{slug}-caption-learnings.md`
- `reference/{slug}-visual-analysis.md`
- `reference/{slug}-creator-learnings.md`

Media assets land in `reference/{slug}/`. The `slug` is the handle without `@`, lowercased.

Read `references/output-templates.md` before writing any of the four documents — it has the exact structure for each.

## Parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `creator_handle` | required | e.g. `@somecreator` |
| `days` | 30 | How far back to pull posts |
| `top_audio` | 30 | Posts to transcribe (top by views + comments, deduplicated) |
| `top_videos` | 10 | Videos to download and frame-extract for visual analysis |

Confirm these with the user before starting if anything is unclear.

---

## Phase 1: Extract Posts

Call the Smacient MCP tool:
```
mcp__claude_ai_Smacient__extract_instagram_posts(username="{handle_without_@}")
```

From the response, map each post to: `audioUrl`, `videoUrl`, `caption`, `views`, `comments`, `likes`, `timestamp`, `duration`. Field names may vary slightly — adapt to what the API returns.

Keep the full post list in context — captions are analyzed in Phase 6 without re-fetching.

---

## Phase 2: Select Posts and Build Audio Manifest

Select target posts for transcription:
- Take top `top_audio / 2` by views, top `top_audio / 2` by comments
- Deduplicate, assign `rank` (1 = highest views)

Write two files to `reference/{slug}/`:

**`audio_manifest.json`** — one entry per post to download:
```json
[
  {
    "url": "{audioUrl}",
    "fallback_url": "{videoUrl}",
    "filename": "rank_01_views_1234567.mp4",
    "rank": 1
  }
]
```

**`audio_metadata.json`** — keyed by filename, for transcript headers:
```json
{
  "rank_01_views_1234567.mp4": {
    "rank": 1, "views": 1234567, "comments": 456,
    "likes": 789, "caption_hook": "First caption line...", "timestamp": "2026-03-01"
  }
}
```

Download:
```bash
python .claude/skills/creator-teardown/scripts/download_media.py \
  --manifest reference/{slug}/audio_manifest.json \
  --output-dir reference/{slug}/audio
```

---

## Phase 3: Transcribe

```bash
python .claude/skills/creator-teardown/scripts/transcribe.py \
  --audio-dir reference/{slug}/audio \
  --transcript-dir reference/{slug}/transcripts \
  --metadata reference/{slug}/audio_metadata.json \
  --model small
```

After completion, read all `.txt` files from `reference/{slug}/transcripts/` into context. They are needed for Phase 7.

---

## Phase 4: Download Top Videos and Extract Frames

Select top `top_videos` posts by views. Write `reference/{slug}/video_manifest.json`:
```json
[
  {"url": "{videoUrl}", "filename": "rank_01_views_1234567.mp4"}
]
```

Download:
```bash
python .claude/skills/creator-teardown/scripts/download_media.py \
  --manifest reference/{slug}/video_manifest.json \
  --output-dir reference/{slug}/videos
```

Extract frames for each downloaded video (run sequentially):
```bash
python .claude/skills/creator-teardown/scripts/extract_frames.py \
  --video "reference/{slug}/videos/{filename}" \
  --output-dir "reference/{slug}/frames/v{rank}" \
  --interval 4
```

---

## Phase 5: Visual Analysis

Read all PNG frames using the Read tool (Claude can view images directly). Work through videos in rank order. For each, note what you see frame by frame.

Across all videos, look for:
- **Hook format** — first 2-4 seconds: is it split-screen (image + talking head), full-screen image, or just talking head?
- **Presenter setup** — background, clothing, camera distance, lighting
- **On-screen text** — style, size, placement, frequency; keyword captions vs full subtitles
- **B-roll types** — screen recordings, AI illustrations, real footage, product slides, external clips
- **Editing rhythm** — cut frequency, jump cuts within talking head
- **Branded elements** — title cards, series openers, recurring visual elements

Write `reference/{slug}-visual-analysis.md` using the template in `references/output-templates.md`.

---

## Phase 6: Caption Analysis

Use the captions collected in Phase 1 (already in context). For each caption, note:
- First line structure and word count
- Line length throughout (1-5 words? full sentences?)
- Use of blank lines between thoughts
- Transition phrase wording
- CTA format and keyword used
- Series tag format
- Hashtag count and placement

Write `reference/{slug}-caption-learnings.md` using the template in `references/output-templates.md`.

---

## Phase 7: Transcript Analysis and Synthesis

Using the transcripts loaded after Phase 3:
- Identify spoken hook formulas — the actual first 1-2 sentences before any series opener
- Find the series opener exact wording (if any)
- Map body structure: how context is set, how tension is built
- Extract transition phrases verbatim
- Extract CTA wording verbatim
- Compare top 3 vs bottom 3 posts: what differs in the script?

Write:
- `reference/{slug}-script-learnings.md`
- `reference/{slug}-creator-learnings.md`

Both use templates in `references/output-templates.md`.

---

## Error Handling

- If `audioUrl` download fails, `download_media.py` automatically retries with `fallback_url`
- If a transcript already exists, `transcribe.py` skips it — safe to re-run
- If frames already exist for a video, `extract_frames.py` skips extraction
- If fewer posts are returned than `top_audio`, work with what's available and note it
- Log failures and continue — don't stop the pipeline for individual post failures

---

## Completion Report

When all four documents are written, report:
- Posts extracted and transcribed
- Videos downloaded and frame-extracted
- Paths to all four output documents
- Any failures or gaps to flag
