---
name: amazon-research
description: >
  Full Amazon market research for any product category - no Helium 10 or Jungle Scout
  required. Generates search keywords, fetches products via Smacient, uses Gemini AI
  to filter irrelevant products (with interactive user review of borderline cases),
  extracts brand names and product formats, and produces a complete 8-tab Excel
  analysis plus markdown summary. Covers: brand landscape, revenue estimates, top
  products by revenue/units/rating, format breakdown, price tier analysis, and
  competitive quadrants. Use when: researching a new Amazon category, doing
  competitive intelligence before a product launch, auditing a market, or any
  one-time market sizing exercise. Works on all Amazon marketplaces (India, US, UK,
  Germany, France, Spain, Italy, Japan, Australia). Keywords: amazon research,
  market research, competitive analysis, helium 10 alternative, jungle scout
  alternative, amazon category analysis, brand landscape, market sizing.
---

# /amazon-research

Full Amazon market research for any category - no Helium 10 or Jungle Scout required.

Uses Smacient to search Amazon, Gemini AI to filter irrelevant products and extract brand names,
then produces a full competitive analysis Excel + summary.

**Cost:** ~8-16 Smacient credits per run (1 credit per 50 results).

---

## Usage

```
/amazon-research "category" --marketplace DOMAIN --keywords N
```

- `category` - required, e.g. `"melatonin for kids"`, `"protein powder for women"`
- `--marketplace` - optional: `com` `in` `co.uk` `de` `fr` `es` `it` `co.jp` `com.au`
- `--keywords N` - optional: number of search keywords (default 8, max 10)

**Examples:**
```
/amazon-research "melatonin for kids" --marketplace in
/amazon-research "protein powder for women" --marketplace com
/amazon-research "baby shampoo" --marketplace co.uk --keywords 10
```

---

## Prerequisites

1. **Claude Code** - this skill runs as a slash command in Claude Code
2. **Smacient MCP connector** - for Amazon search. Get access at smacient.com
3. **Gemini API key** - free tier is sufficient. Store in your project's `.env` file as `GEMINI_API_KEY=your_key`
4. **Python venv** - install dependencies: `pip install -r requirements.txt` (pandas, openpyxl, google-genai)
5. **Backend script** - `scripts/amazon_research.py` must be present in the workspace

---

## What You Get

The skill produces two outputs:

**8-tab Excel report** (`outputs/Amazon - [Category] - Market Analysis.xlsx`):
- Market Overview - key metrics dashboard
- Brand Analysis - every brand ranked by estimated revenue
- Revenue Estimates - per-product revenue calculations
- Top Products - top 20 by revenue, units, rating, and discount
- Format Breakdown - product format distribution (gummies vs syrup vs tablets, etc.)
- Pricing Analysis - price tier breakdown and revenue by tier
- Competitive Flags - quadrant analysis (Established Winner / Volume Player / High Quality+Low Visibility / Emerging)
- Raw Data - full product dataset

**Markdown summary** (`outputs/Amazon - [Category] - Summary.md`) - also displayed in chat.

---

## Steps — Follow These Exactly in Order

### STEP 1: Parse Arguments

From `$ARGUMENTS`, extract:
- `CATEGORY` — the product category (quoted string or everything before any `--` flag)
- `MARKETPLACE` — value after `--marketplace` (empty if not provided)
- `KEYWORD_COUNT` — value after `--keywords` (default: 8, max: 10)

### STEP 2: Confirm Marketplace

If `MARKETPLACE` was not provided in the arguments, ask the user:

> "Which Amazon marketplace should I search?
> Options: **com** (US) / **in** (India) / **co.uk** (UK) / **de** (Germany) / **fr** (France) / **es** (Spain) / **it** (Italy) / **co.jp** (Japan) / **com.au** (Australia)"

Wait for their response before continuing.

### STEP 3: Create Working Directory

Set `WORKDIR` to:
```
[project-root]\outputs\[category-slug]-[YYYYMMDD]
```

Where:
- `category-slug` = CATEGORY lowercased, spaces replaced with hyphens, special chars removed
- `YYYYMMDD` = today's date
- `project-root` = the root directory of this workspace

Create the directory:
```powershell
New-Item -ItemType Directory -Force -Path "WORKDIR"
```

Tell the user: "Working directory: `WORKDIR`"

### STEP 4: Check Credits

Call `mcp__claude_ai_Smacient__get_credits_balance`.

If balance < 20, warn the user: "You have X credits remaining. This run will use approximately Y credits (8 keywords x 1 credit each). Proceed?"

If balance >= 20, continue without asking.

### STEP 5: Generate Search Keywords

Generate exactly KEYWORD_COUNT (default: 8) Amazon search keywords for CATEGORY.

Think like a shopper who doesn't know the brand - generate varied phrasings covering:
- Direct product name searches
- Use-case or benefit searches
- Target audience variations
- Alternative product names or common synonyms

Present the keywords as a numbered list and say:
> "These are the search terms I'll use. Reply to continue, or tell me what to change."

Wait for confirmation before proceeding. Update the list if the user requests changes.

Store the confirmed list as `KEYWORDS`.

### STEP 6: Run Amazon Searches

Split KEYWORDS into batches of maximum 5 keywords each.

For each batch, call `mcp__claude_ai_Smacient__amazon_search` with:
- `search_terms`: the batch
- `domain`: MARKETPLACE
- `max_results`: "50"

After each call, save the results to a JSON file:
- Extract the product list from the response (it may be a direct array, or nested under a key like `results`, `data`, or `products`, or structured as `{"search_results": {"term": [...]}}`)
- Add a `"query"` field to each product noting which search term it came from
- Write to: `WORKDIR\raw_search_[batch-number].json` as a JSON array

**Handling large results (common):** The Smacient tool often returns more data than fits in context. If the result is saved to a temp file, use Python to extract it:

```powershell
& "python.exe" -c "
import json

def fix_and_extract(src, dst):
    with open(src, encoding='utf-8') as f:
        content = f.read()
    for marker in ['\n\n... [RESPONSE TRUNCATED', '\n... [RESPONSE TRUNCATED']:
        if marker in content:
            content = content[:content.index(marker)]
            break
    content = content.rstrip() + '\n    ]\n  }\n}'
    data = json.loads(content)
    products = []
    for term, plist in data.get('search_results', {}).items():
        for p in (plist or []):
            if isinstance(p, dict):
                p['query'] = term
                products.append(p)
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    print(f'{len(products)} products from {len(data[\"search_results\"])} terms')

fix_and_extract(r'[TOOL_RESULT_PATH]', r'[WORKDIR]\raw_search_[N].json')
"
```

Announce progress after each batch: "Batch 1/2 complete - X products fetched"

### STEP 7: Merge and Deduplicate

Install dependencies if not present:
```powershell
& "python.exe" -m pip install -q pandas openpyxl
```

Run the merge:
```powershell
& "python.exe" "scripts/amazon_research.py" --mode merge --workdir "WORKDIR"
```

Report the output to the user: total records found, unique ASINs after dedup.

### STEP 8: Filter for Relevance (Gemini AI)

Install Gemini SDK if not present:
```powershell
& "python.exe" -m pip install -q google-generativeai
```

Run the filter:
```powershell
& "python.exe" "scripts/amazon_research.py" --mode filter --category "CATEGORY" --workdir "WORKDIR"
```

Tell the user: "Gemini reviewed all X products. RELEVANT: N, BORDERLINE: N, IRRELEVANT: N (dropped)"

Show 3-5 examples of what was dropped (from the IRRELEVANT_SAMPLES in the output).

### STEP 9: Handle Borderline Products

Read `WORKDIR\borderline.json`.

**If the file is empty or has 0 products:**
Copy relevant.csv directly to approved.csv:
```powershell
Copy-Item "WORKDIR\relevant.csv" "WORKDIR\approved.csv"
```
Skip to Step 10.

**If borderline products exist:**

Present them to the user like this:

---
**Gemini flagged N products as uncertain - it wasn't sure if these belong in the [CATEGORY] analysis:**

1. [title] - *[reason]*
2. [title] - *[reason]*
...

**Reply with the numbers you want to KEEP (comma-separated), `all` to keep all, or `none` to reject all.**

---

Wait for the user's reply.

Parse their response:
- `all` -> approve all borderline products
- `none` -> reject all borderline products
- `1, 3, 5` -> approve only those numbered products, reject the rest

Build a `user_decisions.json` file listing each borderline product's ASIN and whether it was approved:
```json
[
  {"asin": "B0...", "approved": true},
  {"asin": "B1...", "approved": false}
]
```

Write this file to `WORKDIR\user_decisions.json` using the Write tool.

Then run:
```powershell
& "python.exe" "scripts/amazon_research.py" --mode apply-decisions --workdir "WORKDIR"
```

Tell the user: "Final dataset confirmed: X products going into analysis."

### STEP 10: Enrich - Brand Names and Product Formats (Gemini AI)

```powershell
& "python.exe" "scripts/amazon_research.py" --mode enrich --category "CATEGORY" --workdir "WORKDIR"
```

Tell the user: "Brands and formats extracted. Detected X unique brands."
Also tell them what product formats Gemini identified for this category (from the output line "Detected formats for...").

### STEP 11: Run Full Market Analysis

```powershell
& "python.exe" "scripts/amazon_research.py" --mode analyze --category "CATEGORY" --marketplace "MARKETPLACE" --workdir "WORKDIR"
```

Note the `EXCEL_PATH` and `SUMMARY_MD_PATH` printed in the output.

### STEP 12: Display Results

Read the markdown summary from `SUMMARY_MD_PATH` and output its full contents in chat.

Then add:
> "Full 8-tab Excel report saved to: `EXCEL_PATH`"
>
> **Tabs included:** Market Overview | Brand Analysis | Revenue Estimates | Top Products | Format Breakdown | Pricing Analysis | Competitive Flags | Raw Data

---

## Notes

- Always quote paths in PowerShell when they contain spaces
- The script reads `.env` automatically for GEMINI_API_KEY - no manual setup needed per run
- If a script step fails, show the error output clearly and stop - do not attempt workarounds
- Pass `--category` exactly as the user gave it (preserve original casing)
- Large Smacient tool results are common and expected - use the Python extraction pattern in Step 6

---

## Backend Script

The analysis is powered by `scripts/amazon_research.py` which must be present in the workspace root. It handles four modes:

| Mode | What it does |
|------|-------------|
| `merge` | Reads all raw_search_*.json files, merges, deduplicates by ASIN |
| `filter` | Calls Gemini to classify products as RELEVANT/BORDERLINE/IRRELEVANT |
| `apply-decisions` | Applies user approve/reject decisions for borderline products |
| `enrich` | Calls Gemini to extract brand names and auto-detect product formats |
| `analyze` | Runs full market analysis and writes Excel + markdown output |

The script is available in the [smacient/marketing-skills](https://github.com/smacient/marketing-skills) repository alongside this skill.
