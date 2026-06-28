# synth-research

Synthetic consumer research for any marketing asset. Runs a panel of AI personas against your product page, ad copy, or landing page and returns probability distributions showing how your target audience actually feels — before you spend on traffic.

Uses [SSR (Semantic Similarity Rating)](https://github.com/pymc-labs/semantic-similarity-rating) to convert persona responses into Likert-scale PMFs across research dimensions including purchase intent, product sentiment, trust, and value for money.

## What it produces

- **Purchase intent distribution** — not a single score, but the full split: what % would buy immediately, consider it, or ignore it
- **PMF per dimension** — probability distribution across a 5-point scale for each research dimension
- **Competitor benchmark** (optional) — same audience, same dimensions, side-by-side gap analysis
- **Plain-language report** — Markdown file formatted for PDF conversion and client sharing

Output files saved to `outputs/` inside the skill directory:

| File | Contents |
|------|----------|
| `[TIMESTAMP]-report.md` | Full plain-language report, PDF-ready |
| `[TIMESTAMP]-pmf.csv` | PMF distributions and expected scores per stimulus per dimension |
| `[TIMESTAMP]-responses.csv` | All persona responses with per-dimension expected scores |
| `[TIMESTAMP]-config.json` | Input config used — reusable for exact reproduction |

## Prerequisites

1. **Python 3.10+** with a virtual environment set up inside the skill directory
2. **GEMINI_API_KEY** — set in `~/.claude/settings.json` under the `env` block:
   ```json
   {
     "env": {
       "GEMINI_API_KEY": "your-key-here"
     }
   }
   ```
3. **Python dependencies** — install after setting up the venv (see Setup below)

## Installation

Copy this skill folder to your Claude skills directory:

```bash
# Global install (available across all projects)
cp -r skills/synth-research ~/.claude/skills/synth-research

# Windows
xcopy /E /I skills\synth-research %USERPROFILE%\.claude\skills\synth-research
```

## Setup (first time only)

Run this once after installing:

```bash
cd ~/.claude/skills/synth-research

python -m venv .venv

# Windows
.venv\Scripts\pip install -r requirements.txt

# Mac/Linux
.venv/bin/pip install -r requirements.txt
```

## Usage

Just trigger the skill with a natural prompt or slash command:

```
/synth-research
```

Claude will walk you through setup interactively:
- What you are testing (product page or ad copy)
- Your content (paste text, describe it, or give a URL)
- Optional competitor to benchmark against
- Target audience description
- Research dimensions to measure

No arguments needed upfront. Results in minutes.

## Modes (V1)

| Mode | Personas | Default dimensions | Best for |
|------|----------|--------------------|----------|
| `product` | 35 (7 age points x 5 concern types) | Purchase Intent, Product Sentiment, Ingredient Trust, Value for Money | Product pages, product descriptions |
| `ad` | 20 (4 concern types x 5 mindsets) | Purchase Intent, Content Engagement, Value Proposition Clarity, Brand Sentiment | Ad headlines + body copy, creative variants |

## Platform support

| Platform | Supported | Notes |
|----------|-----------|-------|
| Claude Code CLI (terminal) | Yes | Primary target |
| Claude Code desktop app (Mac/Windows) | Yes | Identical to CLI |
| Claude Code web (claude.ai/code) | Yes | Full support |
| Claude.ai chat (claude.ai) | No | Cannot run shell commands or Python scripts |

## Understanding the scores

A score of 2.5-3.5/5 is normal for cold-brand testing. The AI simulates genuine consumer skepticism toward an unfamiliar brand. The value is in:

- **Relative comparison** — your score vs a competitor under identical conditions
- **PMF shape** — a bimodal distribution (high mass at both ends) signals a segment split, not an average audience
- **Dimension gaps** — which specific dimension is dragging purchase intent tells you what to fix

## Credits / API cost

- Gemini API: billed to your Google account (~35-70 generation calls per run depending on mode and whether a competitor benchmark is included)
- No Smacient credits required — this skill uses your own Gemini API key directly
