# SQP Report Mechanics

Verified directly against real monthly exports from amazon.in. Several of these
contradict what is commonly written about the report. Getting any of them wrong
produces an analysis that looks right and is not.

## Contents

1. Column inventory
2. The five mechanics that trip people up
3. Two column-name traps
4. What Search Catalog Performance actually is
5. What SQP cannot tell you

---

## 1. Column inventory

33 data columns plus `Reporting Date`. Row 1 is an export-metadata line, so the
real header is row 2 (`skiprows=1`). Files carry a UTF-8 BOM.

```
Search Query | Search Query Score | Search Query Volume
Impressions:  Total Count, Brand Count, Brand Share %
Clicks:       Total Count, Click Rate %, Brand Count, Brand Share %,
              Price (Median), Brand Price (Median), Same-Day / 1D / 2D Shipping Speed
Cart Adds:    Total Count, Cart Add Rate %, Brand Count, Brand Share %,
              Price (Median), Brand Price (Median), Same-Day / 1D / 2D Shipping Speed
Purchases:    Total Count, Purchase Rate %, Brand Count, Brand Share %,
              Price (Median), Brand Price (Median), Same-Day / 1D / 2D Shipping Speed
Reporting Date
```

Price and shipping columns exist only from the **click stage onward**. There is
no such thing as the price of an impression.

**Seller Central hides 12 of these by default.** A user who exports without
enabling every column loses all price and shipping data. This is the most
common real-world input problem. The engine fills them as empty, disables the
dependent diagnoses, and states the omission in the report.

---

## 2. The five mechanics that trip people up

### Search Query Score ranks by YOUR performance, not market volume

The single most consequential fact about this report. Spearman correlation of
Score against candidate ranking bases, measured on a real export:

| Basis | Correlation |
|---|---|
| Cart Adds: Brand Count | **0.898** |
| Clicks: Brand Count | 0.856 |
| Purchases: Brand Count | 0.814 |
| Search Query Volume | 0.439 |

The export is the top 1,000 searches **where this brand performs best**, not the
top 1,000 in the category. Consequences:

- High-volume searches where the brand has no presence are structurally invisible
- True category share is not measurable, only share among searches already won
- A search leaving the report means **your** performance on it dropped

### Every export is hard-capped: 1,000 rows brand-level, 100 ASIN-level

Minimum search volume in the export is routinely 1, because the cut is on brand
performance rather than volume. Any censoring rule keyed on volume is invalid.

The ASIN-level view of the same report caps at 100 rows, verified as exactly 100
in all 14 monthly exports for each of six ASINs across four brands. Never state
the cap from memory; the engine reads it from the data.

### Monthly query churn of 50 to 80 percent is structural

A direct consequence of the 1,000-row cap over a long tail. Alarming on generic
thresholds is a false positive. Observed range across four brands: 53 to 79
percent.

### Shipping-speed columns are market level, not brand level

Verified: the sum of Same-Day + 1D + 2D exceeds the brand click count in most
rows but never exceeds the total click count. They describe the whole category's
fulfilment mix. The brand-side equivalent is not in SQP at all; it has to come
from Search Catalog Performance, which is ASIN-level, so the comparison only
works in aggregate.

### The ASIN-level SQP view is the same report with one column family renamed

Seller Central exports SQP at brand level and at single-ASIN level. The two are
structurally identical: same 33 columns, same metadata header row, same funnel.
The only difference is that the brand side of every pair is renamed, so
`Clicks: Brand Count` becomes `Clicks: ASIN Count`, and the same for Share % and
Price (Median). Normalising those names is all it takes to run the whole
analysis at either level.

Three things change in meaning even though nothing changes in the arithmetic:

- **Share means one product's slice of the whole market**, not the brand's. A
  weak ASIN share can mean the market is hard to win, or that a sister ASIN is
  winning it instead. SQP cannot separate those two; only the brand-level run
  can.
- **The row cap is 100, not 1,000**, so coverage of the product's own search
  business is thinner and the visible query set is a smaller slice of the tail.
- **Search Catalog Performance must be filtered to the same ASIN.** SCP is
  always exported brand-wide. Left unfiltered on an ASIN run it puts a
  brand-wide denominator under an ASIN-level numerator: revenue and AOV become
  the brand's, and coverage understates severalfold. Observed on a real run:
  20 percent before the filter, 76 percent after.

The metadata header row is what identifies the level. ASIN-level exports carry
`ASIN or Product=["B0XXXXXXXX"]`; brand-level ones have no such field.

### The relevance boundary is narrower at ASIN level than at brand level

The brand-level boundary is what the brand can win. The ASIN-level boundary is
what that one product can win, which is usually a subset. A brand selling both
kids and teen ranges has both in scope; its kids shampoo does not, and leaving
teen demand in scope charges the product with a gap it structurally cannot
close. Profile the ASIN's own segment mix rather than inheriting the brand's.

### Reported Brand Share percentages are accurate

Match recomputed `brand count / total count` to within 0.005pp. No rounding
correction is needed, though recomputing from counts is still preferable for
consistency.

---

## 3. Two column-name traps

**`Clicks: Click Rate %` is not a click-through rate.** It is
`Total Clicks / Search Query Volume`. Example row: reported 34.77, where total
clicks / search volume = 34.77 but total clicks / total impressions = 1.63.
Reading it as CTR is wrong by roughly twentyfold.

**`Purchases: Purchase Rate %` is likewise `Total Purchases / Search Query
Volume`**, not purchases per click.

Both are market-level. Always compute rates from the underlying counts.

---

## 4. What Search Catalog Performance actually is

**Not the ASIN view of SQP.** A different report with a different scope that
cannot be joined to SQP by search term.

| | Search Query Performance | Search Catalog Performance |
|---|---|---|
| Grain | Search term | ASIN |
| Competitive context | Total + brand + share at every stage | **None.** Own ASINs only |
| Truncation | Top 1,000 by brand performance | All ASINs |
| Revenue | No | **Yes: Search Traffic Sales** |
| Rating | No | Column exists but was **100% null** in every file checked |

Scope differs materially: SCP purchases ran 1.05x to 1.23x SQP brand purchases
across 14 months of one brand. That ratio is a useful coverage metric and it
moves: it fell from 95 percent to 81 percent over the period, meaning business
was increasingly coming from searches outside the visible top 1,000.

What SCP genuinely adds: real revenue (removes price-times-units estimation from
sizing), per-ASIN conversion, own shipping-speed mix, per-ASIN price ladder.

What it does not add: any ability to attribute a search-level funnel leak to a
specific ASIN. That capability does not exist in this data. Do not claim it.

---

## 5. What SQP cannot tell you

Any diagnosis touching these is a hypothesis with a named confirming check,
never a finding:

- Organic rank
- Ad spend, ACOS, or which impressions were paid (sponsored impressions are
  included in the impression counts and cannot be separated)
- Buy Box ownership
- Inventory or stock levels
- Returns
- Review scores or counts
- **Which specific competitor took share.** The report shows that ground was
  lost and where, never to whom.

Also note: SQP covers search-originated activity only, within a short
attribution window, and counts purchase **actions** rather than units. It will
never reconcile with Seller Central. That is by design, not an error.
