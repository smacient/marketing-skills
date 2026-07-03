# Claude Code: synth-research Skill

Run a synthetic consumer research panel against any marketing asset — product page, ad copy, landing page, or brand positioning. Uses SSR (Semantic Similarity Rating) to convert AI persona responses into probability distributions, revealing how your target audience actually feels about your content before you spend.

## Core Function

Runs a panel of synthetic personas against any marketing stimulus and generates a probability distribution report showing:
- Purchase intent split across your target audience
- Product or content sentiment
- Ingredient or safety trust signals (product mode)
- Value perception relative to price
- Ad stopping power and message clarity (ad mode)
- Side-by-side competitor benchmark (optional)

## Workflow

### Step 1: Mode Selection

Ask the user: "What are you testing today?"

Present options:
- **product** — a product page or product description
- **ad** — one or multiple ad copy variants (headline + body)

V1 supports product and ad modes. Confirm before proceeding.

---

### Step 2: Stimulus Input

Ask: "Paste your content below — text, a description, or a URL."

- If text or paste: use directly.
- If ad mode with multiple variants: "How many variants? Paste them one at a time." Collect all variants before continuing.
- If URL: follow the extraction sequence below.

**URL extraction sequence (attempt in order, stop at first success):**

1. **WebFetch the URL directly.** If you get a full product description, price, and feature list — use it.

2. **If the page is truncated or returns only a title** (common on JavaScript-rendered Shopify and other modern storefronts): try appending `.json` to the product URL and WebFetch that instead.
   - Example: `https://example.com/products/product-name` → `https://example.com/products/product-name.json`
   - The JSON response contains the full product title, description, price, and variants in structured form.
   - This works for most Shopify stores.

3. **If neither works** (non-Shopify, behind auth, or heavily JS-rendered): tell the user: "I wasn't able to extract the page content automatically. Please paste the product description, key features, and price directly and I'll use that."

After successful extraction, summarise what you have and confirm before proceeding:
"Got it. I'll be testing: [brief one-line summary — product name, price, 2-3 key claims]."

Apply the same extraction sequence for competitor URLs in Step 3.

---

### Step 3: Competitor Benchmark

Ask: "Do you want to benchmark this against a competitor? (Yes/No)"

If yes: collect their content or URL using the same process as Step 2.
If no: proceed.

---

### Step 4: Audience Definition

Ask: "Describe your target customer in one or two sentences. Who are you trying to reach?"

Then ask targeted follow-up questions based on mode:

**Product mode:**
- "What age range is your end customer?" (skip if not age-relevant)
- "What are their top 2-3 concerns when buying this type of product?" — prompt with examples: price, safety, effectiveness, convenience, brand trust
- "Are these cold prospects (never heard of your brand), warm (some prior exposure), or hot (actively looking)?"

**Ad mode:**
- "What is the campaign objective — awareness, consideration, or conversion?"
- "Is this cold traffic, retargeting, or existing customers?"
- "What platform will this run on? (Meta, Google, TikTok — optional)"

---

### Step 5: Research Dimensions

Present the recommended defaults for the chosen mode and ask if the user wants to add or remove any:

**Product mode defaults:** Purchase Intent, Product Sentiment, Ingredient/Safety Trust, Value for Money

**Ad mode defaults:** Purchase Intent, Content Engagement, Value Proposition Clarity, Brand Sentiment

Ask: "These are the dimensions I will measure. Anything to add or remove?"

Available dimensions to add: brand_sentiment, ingredient_trust, value_for_money, content_engagement, value_proposition_clarity

---

### Step 6: Confirm and Run

Summarise everything collected before executing:

```
Ready to run:
- Mode: [mode]
- Testing: [brief description]
- Competitor: [yes + description | none]
- Audience: [one-line summary]
- Awareness: [cold / warm / hot]
- Dimensions: [list]
- Personas: [35 for product | 20 for ad]
- LLM: Gemini 2.5 Flash
```

Ask: "Shall I start the analysis?"

---

### Step 7: Build Config and Execute

On confirmation, write a JSON config to `outputs/[TIMESTAMP]-config.json`. Use the format below — fill in all values from the conversation:

```json
{
  "mode": "[mode]",
  "stimulus": "[full stimulus text]",
  "competitor_stimulus": "[competitor text or null]",
  "audience": {
    "description": "[audience description]",
    "age_range": [[min, max] or null],
    "concerns": ["concern1", "concern2", "concern3"],
    "awareness": "[cold/warm/hot]",
    "campaign_objective": "[awareness/consideration/conversion or null]"
  },
  "dimensions": ["purchase_intent", "product_sentiment"],
  "persona_count": 35,
  "llm_model": "gemini-2.5-flash",
  "output_dir": "outputs",
  "timestamp": "[YYYYMMDD-HHMMSS]"
}
```

Then run from inside the skill directory:

Windows:
```
.venv\Scripts\python scripts\run_analysis.py --config outputs\[TIMESTAMP]-config.json
```

Mac/Linux:
```
.venv/bin/python scripts/run_analysis.py --config outputs/[TIMESTAMP]-config.json
```

Surface any errors immediately. Do not proceed to Step 8 if the script fails.

---

### Step 8: Present Results

Read `outputs/[TIMESTAMP]-report.md` and present in this order:

1. **Top-line scores** — one plain-English sentence per dimension: "[Dimension]: [score]/5 — [what it means]"
2. **PMF distributions** — show the ASCII bar charts from the report for each dimension
3. **Key insight** — the single most important finding stated as a specific, actionable observation
4. **Competitor comparison** (if run) — who wins on which dimensions and the specific structural reason why
5. **One recommended action** — the highest-leverage single change the data supports

---

### Step 9: Next Steps

Offer:

> "Natural next tests based on what we found:
> 1. Add [specific missing trust signal] to your stimulus and re-run to measure the impact
> 2. Test [alternative message claim] against the same audience
> 3. Run warm-brand personas to see how prior awareness lifts scores
>
> Type 1, 2, or 3 to run that test, or ask me anything about the results."

---

## Critical Constraints

**Persona count:** Product mode runs 35 personas (7 age points x 5 concern types). Ad mode runs 20 (4 concern types x 5 mindsets). Do not reduce — smaller panels produce unstable PMFs.

**Score interpretation:** A score of 2.5-3.5/5 is expected and normal for cold-brand tests — the AI is simulating genuine skepticism. The value is in relative comparison (your score vs competitor) and PMF shape, not the absolute number. Always frame results comparatively.

**Bimodal distributions:** When the PMF shows high mass at both ends (e.g. 35% at rating 1 and 30% at rating 5), this is a segment split — two distinct audience types with opposing reactions. Call it out explicitly. A single message will not convert both segments.

**API key:** The scripts read GEMINI_API_KEY from the environment. Set it in `~/.claude/settings.json` under `"env": {"GEMINI_API_KEY": "your-key-here"}`.

**Windows encoding:** Scripts include stdout UTF-8 reconfiguration. If UnicodeEncodeError appears, the venv is not activated or the system Python is running instead.

**SSR library:** If `pip install semantic-similarity-rating` fails (not yet on PyPI), install from source: `pip install git+https://github.com/pymc-labs/semantic-similarity-rating.git`

---

## Output Files

All saved to `outputs/` inside the skill directory:

| File | Contents |
|---|---|
| `[TIMESTAMP]-report.md` | Full plain-language report, PDF-ready |
| `[TIMESTAMP]-pmf.csv` | PMF distributions and expected scores per stimulus per dimension |
| `[TIMESTAMP]-responses.csv` | All persona responses with per-dimension expected scores |
| `[TIMESTAMP]-config.json` | Input config used — reusable for reproducibility |

---

## Setup (first time only)

```bash
cd ~/.claude/skills/synth-research

python -m venv .venv

# Windows
.venv\Scripts\pip install -r requirements.txt

# Mac/Linux
.venv/bin/pip install -r requirements.txt
```
