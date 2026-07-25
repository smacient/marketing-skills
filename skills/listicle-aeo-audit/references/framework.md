# Citable Listicle Architecture - 7-point framework

The formula: **Specific + dated + structured + honest + sourced = safest page for AI to cite.**

| # | Point | Structure | Job |
|---|---|---|---|
| 1 | Buyer Query | Title reads "Best [category] for [persona/use case] in [year]" | Match the question AI is answering |
| 2 | Quick Answer | 5-8 picks -> best-for labels -> 1-line why, near the top | Give AI a safe summary to quote |
| 3 | Methodology | Criteria -> sources -> author -> last updated | Make the ranking feel earned |
| 4 | Comparison Table | Tool -> Best for -> Strength -> Limit -> Pricing | Make the market map extractable |
| 5 | Vendor Sections | Best for -> Features -> Limits -> Pricing -> Choose if | Clean entity facts + honest tradeoffs |
| 6 | Decision Framework | Choose X if... -> Choose Y if... -> Avoid Z if... | Answer follow-up buyer questions |
| 7 | Proof + FAQ + Schema | Stats -> sources -> FAQs -> Article/ItemList/FAQ schema | Make the page easy to verify and cite |

## How each point is actually checked (audit_listicles.py)

**P1 - Buyer Query**: regex on the `<title>` tag for a Best/Top keyword AND a "for" clause. Full match requires both. Year is tracked separately but not required for a full match (many good listicles omit the year and are still fine).

**P2 - Quick Answer**: three independent sub-checks, averaged -
- Pick count falls in 5-8 (see "Pick detection" below)
- At least 3 "best for" mentions in the body text
- A list (`<ul>`/`<ol>` with >=3 items) or `<table>` appears before the first heading

**P3 - Methodology**: three sub-checks, averaged -
- A heading matching methodology/criteria/how-we-chose language, OR that language appearing in the body
- A visible byline (text-pattern match on "by [Name]" near the top - see caveat below)
- A visible date (a date-shaped string in the first ~3000 characters, or a `<time>` element)

**P4 - Comparison Table**: a table counts as genuine only if it is NOT a Table-of-Contents block rendered as a `<table>` (checked by looking for "table of contents" in the table's own text) and has at least 3 rows. Column match counts how many of `[tool, best for, strength, limit, pricing, price, feature, pros, cons]` appear in the first row's cell text.

**P5 - Vendor Sections**: the page is split into segments by heading (`h1`/`h2`/`h3`), then segments whose heading matches a numbered-pick pattern are checked for Features/Limits/Pricing/Choose-if language. Reported as a percentage of pick-segments containing each signal.

**P6 - Decision Framework**: a heading matching "how to choose" / "which should you" language, OR at least 2 "choose ... if" phrases plus an "avoid" mention in the body.

**P7 - Proof + FAQ + Schema**: six sub-checks, summed to a score out of 6 - has stats/data points, has any external link, has a visible FAQ section, has FAQPage schema, has Article/BlogPosting schema, has ItemList schema.

## Known heuristic limitations (be upfront about these in any output)

- **Visible byline detection is text-pattern only.** It will produce false positives on phrases like "Notebook LM by Google" (a product-by-vendor mention, not a human byline) and false negatives on unusually formatted bylines. Do not present the byline percentage as ground truth without a manual spot-check on a sample - this exact false-positive pattern was confirmed during development (26 posts flagged, 0 were real bylines on manual review).
- **Do not use a CSS class-based heuristic for author detection** (e.g. "any element with class containing 'author'"). WordPress renders a comment form with `class="comment-form-author"` on nearly every post, which produces a 100% false-positive rate if matched. This was found and removed during development - the shipped script uses text-pattern matching only.
- **JSON-LD schema (Article/FAQPage/ItemList) requires a raw HTML fetch.** A "fetch and summarize" style tool that converts pages to clean text/markdown will strip `<script>` tags before any schema is visible, producing false 0% readings. Always fetch with `requests` (or an equivalent raw-HTTP method) and parse with BeautifulSoup - never rely on a summarization tool for this specific check.
- **Table-of-Contents blocks can be rendered as literal `<table>` elements** by some WordPress themes. An early version of this check counted these as comparison tables, inflating the true rate from ~90% to a false ~96%. Always filter out tables whose own text starts with "table of contents".
- **Pick detection assumes either numbered headings ("1. Nginx") or ordered list items.** Sites that format picks differently (e.g. unordered `<div>` cards with no numbering) will show `pick_detection_method: "not_detected"` - Points 2 and 5 are excluded from that post's score rather than penalized, but this means the total score is less complete for that post. If more than ~30% of posts show "not_detected", the site likely needs a different detection strategy, or may require JS rendering to see its real content (spot-check 2-3 URLs in a browser first).
