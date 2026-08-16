# Metric Definitions
### Plain-language reference for the {{BRAND}} Amazon Brand Analytics reports

Look up anything unfamiliar here. No statistics background assumed.
**Marketplace:** {{MARKETPLACE}}  |  **In scope:** {{SCOPE}}  |  **Months of data:** {{PERIODS}}

---

## Quick lookup: short codes

The workbook uses full English column names. If you meet a short code anywhere (charts, the analysis scripts, an older file), this is what it means.

| Code | Means | Code | Means |
|---|---|---|---|
| **TI** | Market Impressions | **BI** | Our Impressions |
| **TC** | Market Clicks | **BC** | Our Clicks |
| **TA** | Market Cart Adds | **BA** | Our Cart Adds |
| **TP** | Market Purchases (whole market) | **BP** | Our Purchases (ours only) |
| **IS** | Our Impression Share % | **CS** | Our Click Share % |
| **AS** | Our Cart Add Share % | **PS** | Our Purchase Share % |
| **FE** | Funnel Efficiency | **SQV** | Search Volume |
| **SCI** | Results Page Crowding | | |
| **pp** | Percentage points (9% to 11% is +2pp) | **phi** | Volatility Score |

The pattern is simple: **T = Total (the whole market), B = Brand (us).** So TP is the market's purchases and BP is ours.

The three stage scores are named **Tile Score**, **Page Score** and **Offer Score**, after the part of the shopping experience each one measures.

---

## Part 1: The shopper journey

Every Amazon search follows four steps. The reports track all four, for us **and** for the whole market on the same search.

| Step | What happened | Called |
|---|---|---|
| 1 | Our product appeared in the search results | **Impression** |
| 2 | The shopper clicked it | **Click** |
| 3 | They added it to their basket | **Cart add** |
| 4 | They bought it | **Purchase** |

The whole method rests on one thing: Amazon gives us both our number and the market's number at every step. So we can always ask "how did we do compared to everyone else chasing the same shopper at the same moment?"

---

## Part 2: Share

**Impression share, click share, cart share, purchase share** are our slice of the market at each step.

> If 1,000 people bought a product after searching, and 160 bought ours, our **purchase share is 16%**.

**Why share matters more than our own sales numbers.** Sales rise in December because everyone's do. Share cancels that out automatically, because it is measured against the same market in the same month. Share going up means we genuinely beat competitors. Sales going up might just mean the season was good.

This is the single most important idea in the analysis: **share is trustworthy over time, raw sales numbers are not.**

---

## Part 3: The three stage scores

These are the workhorses. Each compares our performance at one step against the market's, on the same searches.

**Read them like a grade where 1.00 is exactly average.**

| Score | What it is | What it measures | Above 1.00 means |
|---|---|---|---|
| **Tile Score** | Click Share / Impression Share | How often people click us when they see us, vs the market | Our search result listing is more appealing than average |
| **Page Score** | Cart Share / Click Share | How often clickers add to cart, vs the market | Our product page persuades better than average |
| **Offer Score** | Purchase Share / Cart Share | How often cart-adders actually buy, vs the market | Our price, delivery and availability close better than average |

**Worked example.** A category scores Tile 1.13, Page 0.89, Offer 1.14.

- Tile Score 1.13: we get clicked **13% more often** than the average seller. Working.
- Page Score 0.89: of those who click, **11% fewer** add to cart than for competitors. Losing us sales.
- Offer Score 1.14: of those who add to cart, **14% more** complete the purchase. Strong.

So the tile is good, the offer is good, and the product page is the leak. That is the entire diagnosis, and it says exactly which team gets the work.

**Bands:**

| Score | Verdict |
|---|---|
| Below 0.60 | Severe problem |
| 0.60 to 0.85 | Losing to the market |
| 0.85 to 1.15 | About average |
| 1.15 to 1.50 | Beating the market |
| Above 1.50 | Strongly beating the market |

**Why three scores instead of one conversion rate.** A single number tells you that you are losing. These tell you *where*, which is the difference between "fix the listing", "fix the photo" and "fix the price".

---

## Part 4: Funnel efficiency

**Funnel efficiency = purchase share divided by impression share.** It is the three scores multiplied together.

Plain English: **how much we punch above our visibility.**

> A category where we get 4% of impressions but 18% of purchases scores **4.35**. Whenever shoppers see us, they overwhelmingly choose us. We are simply not seen enough.

- Above 1.5: we win when seen. More visibility is the cheapest growth available.
- Around 1.0: we convert about in line with how visible we are.
- Below 1.0: we are visible but losing. More visibility would waste money until the funnel is fixed.

---

## Part 5: Reading a diagnosis

One rule makes the three scores diagnostic rather than merely descriptive:

> **When a problem is upstream, everything downstream falls by the same proportion and the three scores stay flat. When one score moves, the problem is at that step.**

If all our shares drop but the three scores hold steady, we have a visibility problem, not a conversion problem. If the page score drops alone, the product page is at fault. Shares tell us *how much*; the scores tell us *where*.

---

## Part 6: Dilution vs displacement

When our share falls there are two very different possible causes, needing opposite responses.

| | What happened | Response |
|---|---|---|
| **Displacement** | Our sales actually fell. We lost ground. | Urgent. Something is broken. |
| **Dilution** | Our sales held or grew, but the market grew faster around us. | Not broken. A question of whether to invest to keep up. |

> A category's share falling from 22% to 16% looks alarming until you split it: our sales **grew 28%** while the market grew 76%. Dilution, not displacement. Nothing was broken.

Without this split, teams get sent to rebuild pages that are working fine.

---

## Part 7: Market growth vs share growth

When sales grow, either the category grew or we took business off competitors. This separates them.

> Our purchases grew 81%. Of that, **65% came from the category expanding** and **35% from share we genuinely won**.

Only the share portion is performance. The rest would have happened anyway. This is the honest answer to "how are we doing", and it is usually less flattering than the topline.

---

## Part 8: Statistical terms

**Noise floor.** Small numbers bounce randomly. If a search gets 30 purchases a month, our share can swing several points on pure chance. A change must be big enough to stand out from that randomness before it means anything.

**Significant / z-score.** A test for whether a change is real or luck. Beyond ±1.96 means under 5% chance the movement is random. Anything without this test is an observation, not a finding.

**Categories (also: themes).** Individual searches grouped into product categories. Grouping multiplies sample size 10 to 100 times, which is what makes trends measurable at all. A category also maps to something a person owns; a single search phrase does not.

> Important: category shares are calculated by adding up all purchases and dividing, **never** by averaging the individual percentages. Averaging would give a 50-search term the same weight as a 50,000-search one and would tell us we are strong exactly where we are weakest.

**CORE panel.** The {{CORE}} searches appearing in every one of the {{PERIODS}} monthly reports. Because each export only contains 1,000 rows, most searches drop in and out month to month, so comparing raw monthly totals is misleading. The CORE panel is a like-for-like set. It covers {{CORE_PURCH}} of our purchases, which is what matters, even though it is only {{CORE_VOL}} of search volume.

**Volatility score.** Below 1.5 the number is stable enough to plan on. Between 1.5 and 3 it is genuinely moving. Above 3 it is too erratic to quote as a point estimate.

**Decay factor (0.80).** When we buy more traffic, the extra traffic converts worse than what we already have, because we win the easiest customers first. All projections are cut by 20% rather than assuming new traffic performs like existing traffic.

---

## Part 9: How opportunity is measured

**Additional orders per month. Never money.**

This is deliberate. Converting an opportunity into currency needs a contribution margin, and margin varies enormously between products. Almost nobody knows it reliably at ASIN level. Bolting a guessed margin onto a real number produces something that *looks* precise but carries a hidden assumption, and readers reasonably stop trusting it.

So we stop at the last thing we actually observe: **how many more orders you could expect per month.** Apply your own economics from there. It also makes the analysis portable: an order is an order whether the marketplace is amazon.in or amazon.com.

**Orders, not units.** Amazon counts purchase *actions*. One order containing three bottles counts once. Multiply by your own units per order to get units.

**Stage repair.** How every opportunity is sized. We move only the one broken score up to a level **we already achieve elsewhere in our own range**, and hold everything else where it is. We never assume we can reach a competitor's number.

**Range, not a point.** Every figure carries roughly 30% either side. Quote the range.

---

## Part 10: Report quirks worth knowing

Properties of Amazon's reports that change how the numbers should be read.

**These are not total sales.** Only purchases that started with an Amazon search, within a short attribution window. Someone who searches Monday and buys Wednesday is not counted. It will never reconcile with Seller Central, by design.

**Purchases means orders, not units.**

**Each export is capped at 1,000 searches, ranked by *our* performance.** The least obvious and most important quirk. The report is not the top 1,000 searches in the category, it is the top 1,000 **where we do best**. Large markets we are absent from are invisible, and a search vanishing from the report means our performance on it dropped, not that shoppers stopped searching it.

**Query churn of 50 to 70% a month is normal** and follows directly from that cap. Not a broken download.

**"Click Rate %" in the raw file is not a click-through rate.** It is clicks divided by search volume, not clicks divided by impressions. Reading it as a click-through rate is wrong by roughly twentyfold. We calculate our own from the underlying counts.

**Shipping speed columns describe the market, not us.**

**Search Catalog Performance is a different report, not a per-product version of this one.** No competitor data, cannot be linked to individual searches, and its rating column is empty. Its value is real revenue figures and per-product conversion.

**What these reports cannot tell us**, and where any claim needs another source: organic ranking, ad spend or ACOS, whether we hold the Buy Box, stock levels, returns, review scores, and *which specific competitor* took share. The reports show that we are losing ground and where; never by whom.
