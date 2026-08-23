# Configuring a Brand

Configuration is where this analysis goes wrong. The engine is generic; the
config is where all the judgement lives. A wrong config produces a confident,
plausible analysis of the wrong market.

## Contents

1. The four things to get right
2. Choosing the relevance boundary
3. Finding competitors
4. Brand patterns
5. Product categories
6. Worked examples from four real brands
7. Configuring a single ASIN

---

## 1. The four things to get right

| Field | Failure mode if wrong |
|---|---|
| `brand_patterns` | Brand searches counted as generic demand. Understates brand strength, pollutes the unbranded funnel |
| `competitors` | Rival brand demand counted as winnable market. Inflates opportunity, drags every category metric down, hides who is winning |
| `relevance` | Analysing a market the brand cannot win. Generic high-volume terms dominate every action list |
| `themes` | No statistical power. Search-level monthly moves never clear the noise floor, so without categories there is nothing trendable |

Always run `profile_brand.py` first. It surfaces evidence for all four.

---

## 2. Choosing the relevance boundary

**Determine this empirically. Do not assume.** Three shapes have been observed,
one per brand type, and choosing wrong changes the entire answer.

Run the profiler and read section 3 of its output. It tests two dimensions and
reports how far share varies along each.

The boundary belongs to whatever is being analysed. A brand's boundary is what
the brand can win; a single ASIN's is what that one product can win, which is
usually a subset. See section 7.

### `price_tier`

Use when purchase share tracks price position more strongly than product type.
Typical of a premium brand in a mass-market category.

Signature from a real brand (median price 1,549 in a market whose median is 570):

| How much dearer | Market orders | Their share |
|---|---|---|
| <= 1.25x | 1,123 | **8.6%** |
| 2-3x | 7,897 | 0.65% |
| 4-6x | 74,945 | **0.04%** |

Set `max_ratio` where share collapses. Apparel is more price-sensitive than
personal care: 2.0 suited a menswear brand, 3.0 a premium ayurvedic one.

### `category`

Use when share varies far more by what the product is than what it costs.
Typical of a specialist priced at market.

A traditional-menswear brand priced at parity (ratio ~1.0) held 0.80 percent
share in dhoti and mundu and 0.13 percent in generic apparel. Price told you
nothing; product type told you everything.

Define `segments` as label-to-regex, ordered narrow to broad, then list which
labels the brand can serve in `in_scope`.

Age banding is a category rule. A kids brand serving ages 4 to 16 has **two**
out-of-scope zones, not one: generic adult-ambiguous terms *and* baby terms
below its age range. Missing the second left a 14,571-order market sitting in
the opportunity list looking winnable.

### `none`

Only when the brand genuinely competes across its whole visible market. Rare.
If the profiler cannot find a boundary, ask the brand what it does not make
rather than defaulting to `none`.

---

## 3. Finding competitors

Unlabelled competitors are the most common data-quality failure and they recur
for every brand. Section 2 of the profiler lists tokens with real market demand
and near-zero brand share.

**The list mixes brand names with ingredient and attribute words.** Only brand
names belong in `competitors`. Ingredients (rosemary, kumkumadi, bhringraj) and
attributes (collar, pocket, wrinkle-free) are demand and must stay in the market
or the addressable market shrinks artificially.

Real impact: one brand had eight unlabelled competitors representing 13,079
monthly orders counted as generic demand. Correcting it moved the headline from
"99 percent of growth was the category expanding" to "70 percent", and turned a
share loss into a real gain of 2.07pp. That is the difference between telling a
founder they are treading water and telling them they are winning.

---

## 4. Brand patterns

Must cover more than the registered spelling:

- **Misspellings shoppers actually type.** Two variants of one brand carried over
  92 percent purchase share, which is proof they are brand terms, and both were
  being counted as generic.
- **Run-together spellings.** A pattern like `\bacmelabs\b` fails on
  "acmelabsproducts" because there is no word boundary after it. Use `\w*`.
- **Founder names**, where shoppers use them as a brand handle.
- **Own product line names** searched directly.
- **Own ASIN codes.** Shoppers paste ASINs into search; the engine detects these
  automatically from the catalogue report and marks them branded.

Section 1 of the profiler finds these: any token whose purchase share is near
total is the brand under some spelling, however little it resembles the name.

Guard against over-matching. A short brand name is the dangerous case: a pattern like `\bnova\b` must not match "innovate" or "casanova".

---

## 5. Product categories

Ordered narrow to broad, first match wins. "body wash" must be tested before
"wash", "polo t shirt" before "t shirt", "face cream" before "cream".

Aim for under 15 percent of in-scope market orders landing in the `OTHER`
fallback. The engine reports this as a taxonomy-coverage check. A large `OTHER`
usually means unlabelled competitors rather than a missing category.

`OTHER` is a residual, not a category. It is excluded from trends automatically
because its membership churns freely, so its "share" is composition rather than
performance.

Categories below 30 monthly market orders are suppressed from reporting. Below
that, ratios produce nonsense: a Tile Score of 76 computed on two searches will
otherwise dominate any ranking.

---

## 6. Worked examples

| Brand type | Boundary | Why |
|---|---|---|
| Kids personal care, 4-16 | `category` (age bands) | Baby and generic adult terms unwinnable; price roughly at market |
| Premium ayurvedic adult care | `price_tier`, 3.0 | 2.7x the market median; share collapses with price, not category |
| Premium menswear | `price_tier`, 2.0 | ~2x market; apparel is more price-sensitive so the threshold is tighter |
| Traditional menswear specialist | `category` (product type) | Priced at parity, so price is not the constraint; the constraint is what they make |

---

## 7. Configuring a single ASIN

Seller Central exports SQP for one ASIN at a time as well as for the brand. The
config is the brand's with three changes:

```json
{
  "name": "Acme Kids Shampoo (B0XXXXXXXX)",
  "data_dir": "../data/Acme",
  "sqp_folder": "Search Query Performance/ASIN Level/ASIN ID_ B0XXXXXXXX",
  "relevance": {"type": "category", "in_scope": ["YOUNGER_BAND"]}
}
```

- **`name`** becomes the product plus its ASIN. That name is what the report
  calls itself throughout, so a bare brand name here produces a document that
  reads as if it covers the whole brand.
- **`sqp_folder`** points at the ASIN's export folder. Leave `data_dir` on the
  brand folder: Search Catalog Performance is only ever exported brand-wide and
  the engine filters it to the ASIN itself.
- **`relevance.in_scope`** is re-profiled, never inherited.

The third is the one that matters; the other two are plumbing. Profile the ASIN
with the third argument to `profile_brand.py`:

```bash
python scripts/profile_brand.py "<brand folder>" "<Brand Name>"   "Search Query Performance/ASIN Level/ASIN ID_ B0XXXXXXXX"
```

**Worked example.** A kids personal care brand competes in two age bands, 4-10
and 11-16, and both are in scope in its brand config. One of its shampoos, sold
for the younger band, takes 82% of its purchases from 4-10 terms and 2% from
11-16 terms, so the older band is out of scope for that product. Inheriting the
brand's boundary would have charged a kids shampoo with closing a teen gap it
cannot close, and the resulting action list would have been led by an
opportunity that does not exist.

One reading caveat carries into every ASIN report: a share figure is one
product's slice of the whole market. A weak number can mean the market is hard
to win, or that a sister ASIN is winning it. SQP cannot separate those, so the
brand-level run is what answers it. The mechanics are in
`report-mechanics.md`.
