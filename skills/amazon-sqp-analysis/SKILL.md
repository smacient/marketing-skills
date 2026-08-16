---
name: amazon-sqp-analysis
description: Analyze Amazon Brand Analytics Search Query Performance (SQP) exports to produce a prioritized brand growth plan, an analyst workbook, and a leadership summary. Use when someone supplies Amazon SQP or Search Catalog Performance CSV files, mentions "search query performance", "SQP report", "brand analytics", "search catalog performance", or asks to diagnose Amazon search funnel performance, keyword market share, impression/click/cart/purchase share, why Amazon listings are not converting, where to spend Amazon ad budget, or how a brand is performing against its category on Amazon search. Handles one month through several years of monthly exports and scales what it claims to what the data supports.
---

# Amazon SQP Analysis

Turns Amazon Brand Analytics exports into a ranked action plan. The engine is
generic; all judgement lives in a per-brand config. Getting that config wrong
produces a confident analysis of the wrong market, so the workflow below front-
loads discovery.

## Requirements

Python with `pandas`, `numpy`, `openpyxl`, `xlsxwriter`. Install into a venv if
they are missing.

Expected data layout, one folder per brand:

```
<brand folder>/
├── Search Query Performance/       one CSV per month (required)
└── Search Catalogue Performance/   one CSV per month (optional but valuable)
```

Filenames need not follow any convention. The period is read from the export's
own metadata row first, then its Reporting Date column, then the filename.

## Workflow

### Step 1: Profile before configuring

```bash
python scripts/profile_brand.py "<path to brand folder>" "<Brand Name>"
```

Prints evidence for the four config decisions: brand spellings, competitor
candidates, which relevance boundary applies, and category candidates. Read
`references/configuring-a-brand.md` before interpreting it.

### Step 2: Confirm the relevance boundary with the user

**Do not skip this.** The boundary determines which market the brand is measured
against, and choosing wrong changes the entire answer. The profiler can see that
share collapses above 2x market price; it cannot know whether the brand *intends*
to be premium or is priced wrong.

Show the evidence, state the suggestion, and ask. Three shapes exist:

- `price_tier` - share tracks price position (premium brand in a mass market)
- `category` - share varies by product type (specialist priced at market)
- `none` - genuinely competes across its whole visible market (rare)

### Step 3: Write the config

Create a JSON file. Schema and field-by-field guidance are in
`scripts/brand_config.py` and `references/configuring-a-brand.md`.

```json
{
  "name": "Acme",
  "data_dir": "../data/Acme",
  "marketplace": "amazon.in",
  "brand_patterns": ["\\bacme\\b", "\\bakme\\b"],
  "competitors": {"Rival": "\\brival\\b"},
  "relevance": {"type": "category",
                "segments": {"CORE": "widget|gadget"},
                "in_scope": ["CORE"]},
  "themes": {"Widgets": "widget", "Gadgets": "gadget"}
}
```

Include misspellings in `brand_patterns` and label every competitor found. Both
omissions are common and both materially distort the result.

### Step 4: Run

```bash
python scripts/run_analysis.py <config.json> -o <output dir>
```

Watch the console for warnings that change interpretation:

- `[empty]` - exports containing no rows, excluded and named
- `[columns]` - optional columns absent, price and delivery diagnoses disabled
- `[gate]` - categories too small to report
- `[taxonomy]` - share of orders landing in the `OTHER` fallback; above 15
  percent the category list needs extending, usually because a competitor is
  unlabelled

### Step 5: Review before delivering

Check the generated plan against `references/interpreting-results.md`. In
particular verify that the top actions are not artifacts of a misconfiguration:
a huge unwinnable market at the top of the list almost always means the
relevance boundary or the competitor list is wrong.

## Output

Written to `<output dir>/<Brand Name>/`:

| File | Audience | Answers |
|---|---|---|
| `*_Growth_Action_Plan.md` | Brand manager | What to do, in what order, by when |
| `*_SQP_Workbook_*.xlsx` | Analyst | Everything. 23 tabs, definitions at tab 01 |
| `*_SQP_Analyst_Report_*.md` | Analyst | The reasoning, method and caveats |
| `*_SQP_Leadership_Note_*.md` | Founder or CEO | Are we winning, what is needed |
| `*_Metric_Definitions.md` | Anyone | Plain-language glossary |

All impact is stated in **additional orders per month**, never money. Margin
varies too much between products and is rarely known per ASIN, so a profit
figure would bury an unverifiable assumption inside a precise-looking number.

## What the engine will and will not claim

Output scales with input. Detectors needing history stay silent without it, and
the plan states which analyses were unavailable and what more data unlocks. One
month gives no direction of travel; twelve gives seasonality; thirteen gives
year-over-year.

It refuses to size an opportunity when the brand has near-zero visibility, or
when it is below market at a stage in every category. In both cases the absence
of a number is the finding, and it says so.

## Reference material

- `references/report-mechanics.md` - column inventory and the mechanics that
  produce wrong answers if misread. Read when the data looks odd, columns are
  missing, or a metric behaves unexpectedly.
- `references/configuring-a-brand.md` - how to choose the relevance boundary,
  find competitors, and build the category list. Read during steps 1 to 3.
- `references/interpreting-results.md` - the stage scores, dilution versus
  displacement, what each data horizon permits, and the common misreadings. Read
  during step 5 and whenever explaining a number.

## Maintenance

`scripts/stress_test.py` runs 13 deliberately awkward inputs built by mutating
real exports. Run it after changing any script. It requires real export folders
and is for engine development, not routine analysis.
