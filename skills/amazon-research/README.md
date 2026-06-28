# /amazon-research

Full Amazon market research for any product category - no Helium 10 or Jungle Scout required.

Give it a category. It generates search keywords, fetches products via the Smacient MCP connector, uses Gemini AI to filter irrelevant results (with interactive review of borderline cases), extracts brand names and product formats, and produces a complete 8-tab Excel analysis plus a markdown summary.

**Cost:** ~8-16 Smacient credits per run (1 credit per 50 results).

---

## Prerequisites

1. **Claude Code** with the Smacient MCP connector configured
2. **Gemini API key** - free tier works. Add to your project's `.env` as `GEMINI_API_KEY=your_key`
3. **Python venv** with dependencies: `pip install -r requirements.txt`
4. **Backend script** - place `scripts/amazon_research.py` in your workspace's `scripts/` folder

---

## Usage

```
/amazon-research "category" --marketplace DOMAIN --keywords N
```

**Examples:**
```
/amazon-research "melatonin for kids" --marketplace in
/amazon-research "protein powder for women" --marketplace com
/amazon-research "baby shampoo" --marketplace co.uk --keywords 10
```

**Supported marketplaces:** `com` `in` `co.uk` `de` `fr` `es` `it` `co.jp` `com.au`

---

## Output

- **8-tab Excel report:** Market Overview, Brand Analysis, Revenue Estimates, Top Products, Format Breakdown, Pricing Analysis, Competitive Flags, Raw Data
- **Markdown summary** displayed in chat and saved to `outputs/`

---

## Setup

See `SKILL.md` for the full step-by-step skill definition to install in your Claude Code workspace.
