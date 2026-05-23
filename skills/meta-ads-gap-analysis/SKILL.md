---
name: meta-ads-gap-analysis
description: >
  Run a complete Meta Ads competitive gap analysis between two brands.
  Use when asked to: compare Meta ads for two brands, do a Meta ads gap analysis,
  analyze Facebook/Instagram ads vs a competitor, run /meta-ads-gap-analysis.
  Requires: Smacient MCP connector, Python 3.x venv, GEMINI_API_KEY.
---

# /meta-ads-gap-analysis

Run a complete Meta Ads competitive gap analysis between a brand and its competitor, end-to-end.

## Usage

```
/meta-ads-gap-analysis <ownPageURL> <competitorPageURL> <country>
```

- `ownPageURL`: Facebook page URL of your brand (e.g. `https://www.facebook.com/yourbrand/`)
- `competitorPageURL`: Facebook page URL of the competitor brand (e.g. `https://www.facebook.com/competitorbrand/`)
- `country`: 2-letter country code (e.g. `IN`, `US`, `GB`)

## What this does

Full pipeline, end to end:
1. Fetches 50 active ads per brand via Smacient
2. Auto-detects brand names and page names from API response
3. Creates analysis folder + config.json
4. Normalizes raw JSON to pipeline CSV
5. Downloads all video and image assets from CDN URLs
6. Runs metadata analysis (format breakdown, CTAs, offers, influencer detection)
7. Analyzes all videos via Gemini (parallel batches of 15)
8. Analyzes all images via Gemini
9. Extracts audio hooks from all videos (parallel batches of 15)
10. Parses all analysis .md files to structured JSON
11. Generates 8-tab Excel report + markdown summary
12. Adds Audio Hooks as 9th tab
13. Reports summary and updates CLAUDE.md Completed Analyses table

---

## Steps to execute

### Step 1 - Derive slugs and analysis name

Extract a slug from each page URL: take the last non-empty path segment, lowercase it, strip trailing slash.

Examples:
- `https://www.facebook.com/yourbrand/` -> `yourbrand`
- `https://www.facebook.com/competitorbrand/` -> `competitorbrand`

Set `analysis_name = <own_slug>_vs_<competitor_slug>`

---

### Step 2 - Fetch own brand ads

Call `mcp__claude_ai_Smacient__search_meta_ads` with:
- `page_url`: ownPageURL
- `max_ads`: 50
- `active_status`: "active"
- `period`: "last30d"
- `country`: the country argument

**Save the result:**
- If returned inline (small response): write the JSON directly to `data/<own_slug>_smacient_raw.json`
- If saved to a temp file (large response): read the temp file, strip any `[RESPONSE TRUNCATED...]` notice from the end, write to `data/<own_slug>_smacient_raw.json`
- If the resulting JSON is still invalid after stripping: find the last complete ad object using `content.rfind('},')`, close the structure as `]\n}}`, and save

**Auto-detect brand metadata from the result:**
- `own_main_page_name`: the most frequently occurring `page_name` value across the returned ads
- `own_label`: same value as `own_main_page_name`

---

### Step 3 - Fetch competitor ads

Same as Step 2 but:
- `page_url`: competitorPageURL
- Save to `data/<competitor_slug>_smacient_raw.json`
- Auto-detect `competitor_main_page_name` and `competitor_label`

---

### Step 4 - Create analysis folder and config.json

Create directory `outputs/<analysis_name>/` if it does not exist.

Write `outputs/<analysis_name>/config.json` using today's date for the csv paths:
```json
{
  "brand_a": {
    "folder": "<competitor_slug>",
    "label": "<competitor_label>",
    "page_url": "<competitorPageURL>",
    "main_page_name": "<competitor_main_page_name>",
    "csv": "data/<competitor_slug>_smacient_<YYYY-MM-DD>.csv"
  },
  "brand_b": {
    "folder": "<own_slug>",
    "label": "<own_label>",
    "page_url": "<ownPageURL>",
    "main_page_name": "<own_main_page_name>",
    "csv": "data/<own_slug>_smacient_<YYYY-MM-DD>.csv"
  }
}
```

**IMPORTANT:** brand_a = competitor (benchmark), brand_b = own brand (the brand receiving recommendations). The Excel generate_excel.py always produces recommendations FOR brand_b BASED ON brand_a. Never swap this — own brand must always be brand_b.

---

### Step 5 - Normalize to CSV

Run:
```
venv\Scripts\python.exe scripts\normalize_smacient_data.py <analysis_name>
```

This writes CSVs to `data/` and updates `config.json` with the actual CSV paths.

---

### Step 6 - Download assets

Run:
```
venv\Scripts\python.exe scripts\download_assets.py <analysis_name>
```

Downloads all videos and images to `outputs/<analysis_name>/assets/<brand>/videos/` and `/images/`. Must run before CDN URLs expire.

---

### Step 7 - Metadata analysis

Run:
```
venv\Scripts\python.exe scripts\metadata_analysis.py <analysis_name>
```

---

### Step 8 - Video analysis (parallel)

For each brand (own + competitor):
1. List all `.mp4` files in `outputs/<analysis_name>/assets/<brand>/videos/`
2. Extract ad IDs from filenames (strip `.mp4` extension)
3. Split IDs into batches of 15
4. Spawn one Agent per batch to run:
   ```
   venv\Scripts\python.exe scripts\analyze_batch.py <analysis_name> <brand> <id1> <id2> ... <id15>
   ```

Spawn ALL batches for BOTH brands in parallel in a single message. Wait for all agents to complete before proceeding.

---

### Step 9 - Image analysis

For each brand, run:
```
venv\Scripts\python.exe scripts\analyze_image_batch.py <analysis_name> <brand>
```

Run both brands sequentially (image counts are typically small).

---

### Step 10 - Audio hooks analysis (parallel)

Same parallel approach as Step 8, but using `analyze_audio_hooks_batch.py`:
```
venv\Scripts\python.exe scripts\analyze_audio_hooks_batch.py <analysis_name> <brand> <id1> <id2> ... <id15>
```

Spawn ALL batches for BOTH brands in parallel in a single message. Wait for all agents to complete.

---

### Step 11 - Parse analyses

Run:
```
venv\Scripts\python.exe scripts\parse_video_analyses.py <analysis_name>
```

---

### Step 12 - Generate Excel

Run:
```
venv\Scripts\python.exe scripts\generate_excel.py <analysis_name>
```

---

### Step 13 - Add audio hooks tab

Run:
```
venv\Scripts\python.exe scripts\add_audio_hooks_tab.py <analysis_name>
```

---

### Step 14 - Final report and housekeeping

Print a summary table:

| Metric | Own Brand | Competitor |
|--------|-----------|-----------|
| Brand name | | |
| Total ads fetched | | |
| Unique ads (after dedup) | | |
| VIDEO / IMAGE / TEXT | | |
| Influencer ads detected | | |
| Videos analyzed | | |
| Audio hooks extracted | | |

Report the Excel output path: `outputs/<analysis_name>/<analysis_name>_analysis.xlsx`

Add a row to the Completed Analyses table in CLAUDE.md:
```
| <analysis_name> | <own_label> vs <competitor_label> | <YYYY-MM-DD> | outputs/<analysis_name>/ |
```

---

## Important notes

**Auto-detected brand names:** `main_page_name` is taken as the most common `page_name` in the Smacient response — this is the brand's own Facebook page name, used to distinguish influencer ads. If the detected name looks wrong (e.g. the first few ads are all influencer posts), check `config.json` after Step 4 and correct `main_page_name` manually before running Step 5.

**JSON truncation:** Smacient may truncate large responses mid-object. The rfind repair typically recovers 35-45 of the 50 requested ads. This is expected for brands with large active libraries.

**CDN URL expiry:** Facebook CDN URLs expire within days. Do not pause the pipeline between Steps 5 and 6.

**Gemini API key:** Must be set in `~/.claude/settings.json` env block as `GEMINI_API_KEY`. Video and image analysis will fail silently if this is missing.

**Parallel video analysis:** Steps 8 and 10 spawn multiple sub-agents. With ~100 total videos across both brands, expect 6-8 parallel agents and 15-25 minutes for each step.

**Idempotent:** All scripts skip files that already exist. If the pipeline fails mid-way, re-run the skill - it will resume from where it left off without re-downloading or re-analyzing completed files.

**Period note:** The skill always fetches `last30d`. For brands with large evergreen libraries that rarely launch new ads, this may return fewer ads than `ALL`. If the ad count seems low after Step 5, run `/fetch-ads <analysis_name> ALL` manually for the relevant brand to top up, then re-run from Step 5.

**Creative velocity methodology:** `avg_ads_per_week` = ads with `start_date` in the last 28 days / 4 weeks. Evergreen ads started before the 28-day window are intentionally excluded - a brand running 50 old ads is not launching 12.5 new ads/week. A result of 0.0 means the brand launched no new creatives in the last month.

## Credits cost

- Smacient: 12 credits total (6 per brand: 1 lookup + 5 for 50 ads)
- Gemini API: billed to your Google account (~100 video analyses + image analyses)
