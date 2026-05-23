# Meta Ads Gap Analysis

End-to-end Meta Ads competitive analysis between two brands. Fetches active ads via Smacient, analyzes every video and image via Gemini, and outputs a 9-tab Excel report plus a markdown summary.

## What it produces

A 9-tab Excel report:

| Tab | Contents |
|-----|----------|
| Overview | Side-by-side comparison table |
| Gap Analysis | 7 strategic gaps with priority ratings |
| Recommendations | Actionable steps for your brand based on competitor learnings |
| Product Focus | Top destination URLs / landing pages per brand |
| Hooks Comparison | Per-ad emotional angle, narrator type, hook, key claim |
| Audio Hooks | Verbatim first spoken line and on-screen text from each video |
| Influencer Analysis | All branded content / influencer ads |
| Own Brand Ads | Raw ad data for your brand |
| Competitor Ads | Raw ad data for the competitor |

Plus a markdown summary (`<analysis_name>_summary.md`).

## Prerequisites

1. **Smacient MCP connector** - connected in Claude Code settings
2. **Python 3.x** with a virtual environment (`venv/`) in your project root
3. **GEMINI_API_KEY** - set in `~/.claude/settings.json` env block
4. **claude-vision skill** - installed at `~/.claude/skills/claude-vision/`
5. **Python dependencies** - install from `requirements.txt`:
   ```
   venv\Scripts\pip install -r .claude\skills\meta-ads-gap-analysis\requirements.txt
   ```

## Installation

Copy this skill folder to your Claude skills directory:

```bash
# Global install (available across all projects)
cp -r skills/meta-ads-gap-analysis ~/.claude/skills/meta-ads-gap-analysis

# Or project-level install (available only in this workspace)
cp -r skills/meta-ads-gap-analysis path/to/your/project/.claude/skills/meta-ads-gap-analysis
```

Your project must have a `data/` directory and `outputs/` directory at the root (or they will be created automatically).

## Usage

```
/meta-ads-gap-analysis <ownPageURL> <competitorPageURL> <country>
```

**Example:**
```
/meta-ads-gap-analysis https://www.facebook.com/yourbrand/ https://www.facebook.com/competitorbrand/ IN
```

The skill runs all steps automatically:
- Fetches 50 active ads per brand via Smacient
- Downloads all video/image assets
- Analyzes every video and image via Gemini (parallel)
- Extracts audio hooks (first 5s spoken line + on-screen text)
- Outputs Excel + markdown report

## Platform support

| Platform | Supported | Notes |
|----------|-----------|-------|
| Claude Code CLI (terminal) | Yes | Primary target |
| Claude Code desktop app (Mac/Windows) | Yes | Identical to CLI |
| Claude Code web (claude.ai/code) | Yes | Full support - runs shell + Python + MCP |
| Claude.ai chat (claude.ai) | No | Cannot run shell commands or Python scripts |

**Cloud co-work (claude.ai/code)** is the web-based version of Claude Code and works identically to the CLI, as long as: (1) Smacient MCP is connected, (2) Python venv with dependencies is set up in the project, (3) GEMINI_API_KEY is configured.

## Credits cost

- Smacient: 12 credits per analysis (6 per brand: 1 lookup + 5 for 50 ads)
- Gemini API: billed to your Google account (~100 video + image analyses per run)

## config.json convention

`brand_a` = competitor (benchmark), `brand_b` = own brand (receives recommendations).

The Excel recommendations tab always targets `brand_b` based on `brand_a` learnings. This is set automatically by the skill - do not swap.
