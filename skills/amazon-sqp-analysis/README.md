# /amazon-sqp-analysis

Turns Amazon Brand Analytics Search Query Performance exports into a prioritized growth plan. Diagnoses where a brand loses shoppers in the search funnel relative to its category, sizes the fixable part in additional orders per month, and ranks the work by return per unit of effort.

No API or MCP connector required - reads the CSVs Seller Central gives you.

---

## Prerequisites

1. **Python venv** with dependencies: `pip install -r requirements.txt`
2. **Monthly SQP exports** from Seller Central under Brand Analytics, one folder per brand:

```
<brand folder>/
├── Search Query Performance/       one CSV per month (required)
└── Search Catalogue Performance/   one CSV per month (optional, adds revenue and per-ASIN findings)
```

Filenames need not follow any convention. The period is read from the export's own metadata row first, then its Reporting Date column, then the filename.

**Enable all columns before exporting.** Seller Central hides 12 of the 33 by default. Without them, price-position and delivery-speed diagnoses cannot run. The skill detects the omission and says so rather than failing, but the analysis is thinner.

---

## Usage

```
/amazon-sqp-analysis <path to brand folder>
```

The skill profiles the data, proposes a config, confirms the relevance boundary with you, then runs.

Manual invocation:

```bash
python scripts/profile_brand.py "<brand folder>" "<Brand Name>"   # discover config
python scripts/run_analysis.py <config.json> -o <output dir>      # run analysis
```

---

## What it produces

Written to `<output dir>/<Brand Name>/`:

| File | Audience | Answers |
|------|----------|---------|
| `*_Growth_Action_Plan.md` | Brand manager | What to do, in what order, by when |
| `*_SQP_Workbook_*.xlsx` | Analyst | Everything. 23 tabs, definitions at tab 01 |
| `*_SQP_Analyst_Report_*.md` | Analyst | The reasoning, method and caveats |
| `*_SQP_Leadership_Note_*.md` | Founder or CEO | Are we winning, what is needed |
| `*_Metric_Definitions.md` | Anyone | Plain-language glossary |

---

## How it works

SQP gives brand share at all four funnel stages. The ratios between consecutive shares are exactly market-relative conversion indices, with no estimation involved:

```
Tile Score  = Click Share    / Impression Share   the search result tile
Page Score  = Cart Share     / Click Share        the product page
Offer Score = Purchase Share / Cart Share         price, delivery, availability
```

1.00 is market average. When a problem is upstream, all downstream shares fall proportionally and the three scores stay flat. When one score moves, the problem is at that stage. That is what turns "we are losing" into "the product page is the leak", which names the team who owns the fix.

Every analysis is drawn at product-category level rather than per search term. On real data, zero individual search terms produced a monthly share move large enough to clear the statistical noise floor; aggregation is what makes anything trendable.

---

## What it will not claim

Output scales with input. Analyses that need history stay silent without it, and the plan states what was unavailable and what more data unlocks.

| Input | Unlocks |
|-------|---------|
| 1 month | Funnel diagnosis, share gaps, price position. **No direction of travel** |
| 3 months | Direction of travel, terms lost, export integrity checks |
| 12 months | Seasonality, lifecycle, market-versus-share growth split |
| 13+ months | Year-over-year, seasonality removed by construction |

It refuses to size an opportunity when the brand has near-zero visibility, or when it is below market at a stage in every category it sells. In both cases the absence of a number is the finding, and it says so rather than reporting a trivial one.

**Impact is always stated in additional orders per month, never money.** Contribution margin varies too much between products and is rarely known at ASIN level, so a profit figure would bury an unverifiable assumption inside a precise-looking number. Apply your own economics to an order count.

---

## Reference material

- `references/report-mechanics.md` - column inventory and the mechanics that produce wrong answers if misread, including the fact that Search Query Score ranks by *your* performance rather than market volume
- `references/configuring-a-brand.md` - how to choose the relevance boundary, find competitors, build the category list
- `references/interpreting-results.md` - the stage scores, dilution versus displacement, what each data horizon permits, common misreadings

---

## Known gaps

- Only tested against amazon.in. Currency formatting, the event calendar and the price-barrier threshold are untested elsewhere.
- The tokenizer is Latin-script only, so non-Latin queries fall into the unclassified bucket.
- Weekly and quarterly exports are unhandled; the engine assumes monthly.
- The ASIN-level SQP view has not been tested.
