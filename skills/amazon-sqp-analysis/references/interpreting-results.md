# Interpreting Results

How to read the output, and the misreadings that produce confident wrong
answers.

## Contents

1. The three stage scores
2. Dilution versus displacement
3. Market growth versus share growth
4. What the data horizon permits
5. Common misreadings
6. Sizing rules

---

## 1. The three stage scores

SQP gives brand share at all four funnel stages. The ratios between consecutive
shares are exactly market-relative conversion indices, with no estimation:

```
Tile Score  = Click Share    / Impression Share   the search result tile
Page Score  = Cart Share     / Click Share        the product page
Offer Score = Purchase Share / Cart Share         price, delivery, availability

Funnel Efficiency = Purchase Share / Impression Share = Tile x Page x Offer
```

1.00 is exactly market average. Bands: below 0.60 severe, 0.60-0.85 losing,
0.85-1.15 average, 1.15-1.50 beating, above 1.50 strongly beating.

**The diagnostic rule that makes these useful:** when a problem is upstream, all
downstream shares fall proportionally and the three scores stay flat. When one
score moves, the problem is at that stage. Shares measure how much; the scores
locate where.

A worked read. Tile 1.13, Page 0.89, Offer 1.14: clicked 13 percent more often
than market, 11 percent fewer of those clickers add to cart, then 14 percent
more of the cart-adders complete. Tile and offer are fine; the product page is
the leak. That names the team who owns the fix.

Note these names are this skill's own, chosen because they say what they
measure. They are not Amazon or industry terminology.

---

## 2. Dilution versus displacement

Every share decline has two mechanically distinct causes needing opposite
responses. Run this before recommending anything on a share drop.

| | What happened | Response |
|---|---|---|
| **Displacement** | Absolute counts fell. Ground was lost | Urgent. Something is broken |
| **Dilution** | Counts held or grew, market grew faster | Not broken. A question of whether to invest to keep up |

Real case: a category's share fell from 22 to 16 percent, statistically
significant. Alarming until split: the brand's own sales **grew 28 percent**
while the market grew 76 percent, and every stage score held. Dilution, not
displacement. Nothing was broken; demand simply arrived faster than it was
captured. Without the split the recommendation would have been to rebuild a
product page that was working fine.

---

## 3. Market growth versus share growth

Only the share effect is performance. The market effect would have happened
anyway. Report both, always separately.

Sum the effects across periods rather than averaging the percentages. Signed
percentages from opposite-direction periods cancel and produce a number that
looks precise and means nothing.

Handle three cases distinctly:

- Both positive: report the split as percentages
- Market negative, share positive: all growth was earned, and note the category
  is not helping
- Share negative, market positive: absolute numbers rose while position weakened

And gate on materiality. On a base of a few dozen orders, a share move of a
fraction of a point is a handful of orders and could be chance. Say so rather
than crediting the team.

---

## 4. What the data horizon permits

| Input | Unlocks | Still impossible |
|---|---|---|
| 1 month | Funnel diagnosis, share gaps, price position, segmentation | Any direction of travel, seasonality, stability |
| 3 months | Direction of travel, terms lost, export integrity | Separating trend from season |
| 6 months | Volatility scoring, early category trends | Seasonality |
| 12 months | Seasonality, lifecycle, market-vs-share split, competitive erosion | Validating the seasonal pattern |
| 13+ months | Year-over-year, seasonality removed by construction | |
| 24+ months | Validated seasonality, regime detection | |

The one-month answer is not merely thinner, it can be **actively wrong**. Tested
on a real brand, one month recommended buying more traffic into categories whose
product pages had been below market for 14 straight months, because a single
snapshot cannot see persistence.

---

## 5. Common misreadings

**Reading absolute growth as performance.** If the market grew 65 percent,
absolute growth mostly measures the category.

**Trending counts instead of shares.** Brand share is a ratio against the same
period's market, so shocks hitting all sellers cancel out. Absolute counts carry
the full seasonal signal and mean little alone.

**Averaging shares across searches.** Always sum numerators, sum denominators,
divide. Averaging gives a 50-search term the same weight as a 50,000-search one
and reliably concludes the brand is strong where it is weakest.

**Acting on a single search term's monthly movement.** Across 531 in-scope terms
on a real brand, **zero** monthly share moves cleared the noise floor. All trend
conclusions must be drawn at category level.

**Panicking at a share drop without checking crowding.** If total impressions
per search rose, everyone's impression share fell mechanically. Check absolute
brand impressions before declaring a visibility loss.

**Treating a large market as an opportunity.** The biggest markets in an export
are often generic terms the brand cannot win. Check the Tile Score and the price
ratio before ranking by market size.

**Ranking by search term rather than by action.** A brand manager cannot execute
40 keyword recommendations but can execute "replace the hero image on 3 ASINs".
One image fix may resolve a click problem across 40 searches: its value is the
sum, its effort is one brief.

---

## 6. Sizing rules

**Additional orders per month, never money.** Contribution margin varies too
much between products and is rarely known at ASIN level, so converting to profit
buries an unverifiable assumption inside a precise-looking number. Orders are
directly observed and comparable across marketplaces.

These are purchase **actions**, not units. One order of three bottles counts
once.

**Stage repair, not gap closure.** Move only the diagnosed stage, to a level the
brand already achieves elsewhere in its own range, holding every other stage
where it sits. Never project a competitor's number.

**The demonstrated-capability ceiling has a perverse case.** A brand weak at a
stage in *every* category has a ceiling below market, so the model projects it
to stay weak and the fix sizes to nothing. The engine detects this and reports
it as an unsizeable finding rather than a trivial number. The absence of a
sizeable projection is itself the finding.

**Some findings cannot be sized and are still the headline.** A brand with
near-zero impression share cannot be sized by a model that scales from current
visibility. Those are marked critical and sort to the top.

**Apply a decay factor.** Additional traffic always converts worse than existing
traffic. The engine uses 0.80. Quote a range, roughly 30 percent either side,
never a point estimate.
