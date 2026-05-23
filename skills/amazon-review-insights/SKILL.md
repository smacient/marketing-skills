---
name: amazon-review-insights
description: >
  Fetches Amazon reviews for any number of ASINs and generates a deep hidden-insights
  report for a brand. Uncovers silent complaints buried in 5-star reviews, cross-SKU
  patterns invisible per-ASIN, time-trend signals, competitive switching patterns,
  untapped positioning angles, and operational issues. Generates a structured
  markdown report saved to outputs/. Use when: analyzing a brand's Amazon review
  data, preparing brand growth strategy, finding product/ops/marketing issues hidden
  in customer voice. Keywords: amazon reviews, amazon insights, ASIN analysis,
  review analysis, brand insights, customer voice, VOC, hidden patterns.
---

# /amazon-review-insights

Surface-level review analysis is worthless. Anyone can see that 85% gave 5 stars.
The value is in finding **hidden patterns** — things buried across hundreds of reviews
that no one discovers without reading every single one and cross-referencing across
ASINs, segments, and time.

This skill fetches reviews from Amazon, reads every one, and delivers findings that
change decisions — not a summary of what customers said, but what they revealed
without realising it.

---

## Inputs Required

Before starting, collect from the user:

1. **Brand name** — used in report title and filename
2. **ASINs** — any number; paste as a list
3. **Amazon marketplace** — ask explicitly: "Which Amazon marketplace? (e.g. India,
   US, UK, Germany, Canada, Australia, UAE)"

Domain mapping for the MCP tool:
| User says | Use domain |
|---|---|
| India / Amazon.in | `in` |
| US / Amazon.com | `com` |
| UK / Amazon UK | `co.uk` |
| Germany | `de` |
| France | `fr` |
| Canada | `ca` |
| Australia | `com.au` |
| UAE | `ae` |

---

## Step 1 — Fetch Reviews

Use `mcp__claude_ai_Smacient__amazon_get_reviews` to fetch reviews.

**Constraints:**
- Max 5 ASINs per call
- Max 50 reviews per ASIN (use `max_reviews: 50` always)
- Batch all ASINs in groups of 5; run batches in parallel where possible

**Call structure:**
```
mcp__claude_ai_Smacient__amazon_get_reviews(
  asins: ["B0XXXXXXX1", "B0XXXXXXX2", ...],  // max 5
  domain: "in",                                // from user input
  max_reviews: 50
)
```

**Large result handling:** When a tool result is very large, it is automatically saved
to a temp file and you receive only a path. If this happens, spawn a subagent to read
the file in chunks and return a structured summary of: ASIN, rating, date, reviewer
name, review text for each review. Do not attempt to read oversized files inline.

After fetching all batches, state:
- Total ASINs attempted
- Total reviews retrieved
- Any ASINs that returned zero results (flag for investigation)
- Date range of retrieved reviews

---

## Step 2 — Gather Context

Before analysis, ask:

> Before I dive into the analysis, quick context to make sure insights are framed
> for the right decisions:
>
> 1. **Key business objective:** What's the main goal? (e.g. improve BSR, understand
>    why repeat rate is low, prep for a relaunch)
> 2. **Stakeholders:** Who will act on these insights? (Founder / Marketing /
>    Product-R&D / Operations — or all)
> 3. **Known issues:** Any problems you already know about that I should investigate
>    more deeply?
> 4. **Customer segments:** Any important customer types to analyse separately?
>    (e.g. gifters vs direct buyers, kids vs teens)
> 5. **Priority metric:** What matters most? (BSR, repeat rate, conversion, NPS)
>
> You can skip any questions — I'll proceed with reasonable assumptions.

Apply the answers to frame every insight in the final report.

---

## Step 3 — Deep Analysis

**Read every review.** No sampling. Every review, every field.

Run all of the following analyses simultaneously:

### A. Silent Complaint Audit

For each ASIN, scan 4- and 5-star reviews for buried complaint keywords:
`but, however, unfortunately, issue, problem, broken, damaged, missing, wrong,
dried, expired, defect, disappointed, expected, thought it would, not as, wish,
leaked, smell, strong fragrance, confused, pump, though, except, only complaint`

Count and categorise:
- How many high-rated reviews contain complaint language
- What type of complaint (product defect / packaging / instructions / scent /
  price / CS)
- Build a per-ASIN table: 5-star reviews | with buried complaint | rate % | type

**This is the most important audit.** These complaints are invisible to every
standard dashboard.

### B. Time-Trend Analysis

For every complaint type, note the earliest and latest review date.

Ask: Is this complaint new (last 3-6 months only) or persistent (spans years)?

- **New signal** — may indicate a recent batch change, formulation update, or
  supplier switch. Flag as urgent.
- **Persistent signal** — structural issue; assess cumulative damage.
- **Resolved signal** — complaints stopped at a point in time; note what changed.

Flag any complaint type that appears only in recent reviews with zero historical
precedent — this is a critical early-warning signal.

### C. Cross-ASIN Pattern Matching

Read all ASINs simultaneously and look for:

1. **Same reviewer on multiple ASINs** — if a reviewer left negative reviews on 2+
   products in the same month, that is a shared ingredient or formulation signal,
   not independent product failures
2. **Same complaint theme across unrelated SKUs** — e.g. pump failures on lotion,
   face wash, and face cream = hardware problem, not per-product defect
3. **Consistent praise theme across SKUs** — the brand's real differentiator as
   customers experience it (often different from what marketing says)
4. **Rating suppression pattern** — complaints that land in 2-4 star reviews, never
   1-star, are systematically missed by 1-star filters
5. **"Format confusion" complaints** — negative reviews that describe working-as-
   designed features (e.g. foam pump producing foam, not gel) = listing problem,
   not product problem

### D. Segment Identification

From review text, identify segments present in the data:
- Trial/starter pack buyers vs direct full-size buyers
- Gift purchasers (look for "bought as a gift", "birthday", "baby shower")
- Multi-product households (look for "also use your X", "my 3rd order", "whole
  family")
- Adult sensitive skin users using a kids product
- First-time buyers vs repeat buyers (signal words: "reordering", "5th bottle",
  "have been buying for X years")

Note which complaints and praises are segment-specific vs universal.

### E. Competitive Intelligence

Identify every competitor brand mentioned by name. Classify each mention as:
- **Win** — "switched from [Brand] to this"
- **Loss** — "switched back to [Brand]"
- **Comparison** — "better/worse than [Brand] because..."

Map: what [Brand] wins on vs what it loses on. The loss reasons are actionable
formulation or marketing gaps.

### F. Hidden Use Cases and Untapped Opportunities

Look for purchase motivations the brand isn't marketing for:
- Gifting occasions mentioned
- Adult users of a kids product
- Age gap filling ("nothing exists for 6-10 year olds")
- Professional use, medical use, therapeutic use
- Unexpected product combinations customers invented

These are acquisition channels with zero competition in PPC.

### G. Expectation Mismatches

Find reviews where the product did exactly what it was designed to do, but the
customer didn't expect it. These are listing problems, not product problems.
Signal phrases: "thought it would", "expected", "not what I thought", "only foam",
"only spray", "not a cream", "doesn't lather".

### H. Operational and CS Issues

Identify complaints about:
- Delivery damage, leakage, wrong items
- Inability to return or get replacements
- Specific customer service failure language ("pathetic", "fraudulent", "zero CS")

These generate the highest-damage public language and are often fixable immediately
via Seller Central settings.

---

## Step 4 — Generate the Report

Save to: `outputs/<brand-slug>-amazon-review-insights.md`

Where `<brand-slug>` is the brand name in lowercase with hyphens (e.g. Momentum →
`momentum`, Rise Co → `rise-co`).

Use this **exact structure**:

---

```markdown
# Customer Insights from Amazon Reviews — [Brand]
**Dataset:** [X] reviews across [Y] ASINs | Amazon [Marketplace] | [date range]
**Analysis Date:** [today's date]
**Business Objective:** [from context questions]
**Stakeholders:** [from context questions]
**Known Issues Going In:** [from context questions]

---

## Stakeholder Navigation

| If you are... | Start with insights... |
|---|---|
| **Founder / CEO** | [insight numbers most relevant] |
| **Marketing** | [insight numbers most relevant] |
| **Product / R&D** | [insight numbers most relevant] |
| **Operations / Supply Chain** | [insight numbers most relevant] |

---

## Dataset Profile

| ASIN | Product | Reviews | Avg Rating | Date Range |
|---|---|---|---|---|
| [ASIN] | [product name] | [count] | [avg] | [range] |

[Note any ASINs with zero reviews]

---

## Silent Complaint Audit — 5-Star Reviews With Buried Complaints

[One paragraph explaining why this matters — these complaints are invisible to
every dashboard filter]

| ASIN | 5-Star Reviews | With Buried Complaint | Silent Complaint Rate | Primary Complaint Type |
|---|---|---|---|---|

**Key finding:** [Summarise what the silent complaint audit revealed across the
portfolio — what the most common buried complaint is and why it won't appear in
any standard reporting tool]

---

## Time-Trend Analysis

| Issue | Earliest Review | Latest Review | Pattern |
|---|---|---|---|

**Critical signals:** [Flag any complaint type concentrated only in recent months
with zero historical precedent — explain what this implies]

---

## Priority Action Matrix

| Priority | Insight | Effort | Owner |
|---|---|---|---|
| **P0** | [insight name] | Low/Med/High | [team] |
| **P1** | ... | ... | ... |
| **P2** | ... | ... | ... |
| **P3** | ... | ... | ... |

Effort = effort to fix, not effort to investigate.
P0 = fix within 7 days. P1 = fix within 30 days. P2 = fix within 60-90 days.
P3 = strategic / longer-term.

---

## Detailed Insights

### INSIGHT #[N] [optional tag: KNOWN ISSUE / URGENT]: [Specific, Descriptive Title]

**Finding:**
[One paragraph. State exactly what you found and what makes it significant. If it's
a known issue, state what the hidden downstream effect is that they don't know about.]

**Evidence:**
- *"[Full customer quote]"* — [Reviewer name], [ASIN or product], [star]-star, [date]
- *"[Full customer quote]"* — [Reviewer name], [ASIN or product], [star]-star, [date]
- *"[Full customer quote]"* — [Reviewer name], [ASIN or product], [star]-star, [date]
- **Quantification:** [X] reviews ([Y]% of total / [Z]% of [ASIN/segment]) exhibit
  this pattern
- **Cross-field pattern:** Found in [list ASINs / segments / time windows where this
  appears]

**Why It's Hidden:**
[Specifically explain why this is invisible in standard tools. Examples:
- "Sits in 5-star reviews, so rating filters miss it entirely"
- "Appears across 4 ASINs independently — per-ASIN analysis shows 1-2 incidents,
  easy to dismiss as outliers; only visible when reading the full portfolio"
- "Lands in 2-4 star reviews, never 1-star — missed by every 1-star filter"
- "Appears as 'product quality' complaint in keyword tools; only qualitative reading
  reveals it's a listing format mismatch, not a formula problem"
- "Single reviewer visible on 3 ASINs simultaneously — cross-ASIN signal completely
  invisible in per-ASIN dashboards"]

**Recommended Actions:**
1. **Immediate (0-7 days):** [Specific, executable action] - owner: **[Team]**
2. **Short-term (30 days):** [Specific action] - owner: **[Team]**
3. **Long-term (60-90 days):** [Specific action] - owner: **[Team]**

---

[Repeat for all insights. Target 8-12 insights minimum.]

---

## Customer Language Bank — Ready for Listing Copy and Ad Creative

[Intro: one line explaining these are verbatim phrases that convert because they
reflect how buyers actually think]

| Use Case | Verbatim Customer Language |
|---|---|
| **[positioning angle]** | *"[exact quote]"* |
| **[positioning angle]** | *"[exact quote]"* |

[Aim for 10-15 rows covering the brand's strongest proof points and positioning angles]

---

## Methodology

**Analysis Approach:**
- Manual reading of all [X] reviews across [Y] ASINs — every review in full, no
  sampling
- Cross-ASIN pattern matching: reviewer identity, complaint themes, competitor
  mentions, purchase occasion language
- Silent complaint audit: high-rated reviews scanned for buried complaint keywords
- Time-trend analysis: complaint types plotted by date to identify new vs persistent
- Segment analysis: [list segments identified]
- Competitive mapping: all competitor mentions categorised as win vs loss

**Data Quality Notes:**
- [Any ASINs with zero or truncated data]
- [Any data limitations affecting confidence]
- Confidence level: High / Medium / Low per insight group

**Assumptions:**
- [Any assumptions made about the brand, marketplace, or business context]
```

---

## Quality Rules

Before including any insight, verify all of these:

- [ ] Would this be visible in a standard analytics dashboard? If yes — it is not
      a hidden insight, don't include it
- [ ] Do I have 3+ full customer quotes as evidence? If not, keep reading
- [ ] Did I explain specifically why standard analysis misses this? Required for
      every insight
- [ ] Is the recommended action specific enough to execute this week? If not, add
      more detail
- [ ] Does the insight cover what's hidden — not just the surface complaint?

### What NOT to include

- "Customers love the product" — visible in any dashboard
- "92% gave 5 stars" — raw rating aggregations belong in a dashboard, not here
- "Shipping was mentioned 47 times" — frequency counts without hidden signal
- Vague recommendations: "improve product quality", "better packaging"
- Quote fragments — always use full sentences in context

### The standard for a good insight

**Poor:** "Customers complain about the pump"

**Good:** "Pump failures are suppressing ratings on 4 SKUs simultaneously — but
every pump complaint sits in a 2-4 star review, not 1-star, making it invisible
to every 1-star filter. One reviewer upgraded from 1-star to 4-star after a
workaround — your data records her as a satisfied customer."

---

## Notes on Tool Output Size

The Amazon reviews tool can return very large payloads for batches of 5 ASINs at
50 reviews each. If a tool result exceeds your context window:

1. The result is automatically saved to a temp file and you receive a path
2. Spawn a subagent: "Read the file at [path] and return a structured list of all
   reviews with: ASIN, rating, date, reviewer name, review text"
3. The subagent returns structured data you can analyse without overloading context
4. Do not attempt to inline-read oversized files

This is normal behaviour, not an error.
