---
name: listicle-aeo-audit
description: Audit a list of listicle-style blog posts (Best X, Top N, etc.) against the 7-point Citable Listicle Architecture framework - buyer query, quick answer, methodology, comparison table, vendor sections, decision framework, proof+FAQ+schema - and produce an Excel workbook (per-URL sub-checks, sitewide summary, point-by-point detail) plus a markdown report. Use when asked to audit listicles for AI/agent citability, check if listicle posts are "citable" or "AI-friendly", score listicles against a ranking-page framework, or run a "citable listicle" / "listicle architecture" audit. Input is a list of listicle URLs (sitemap XML, plain text with one URL per line, or a JSON array) - NOT a full mixed blog sitemap; pre-filter to listicle-shaped posts first if starting from a full site list.
---

# /listicle-aeo-audit

## What this does

Fetches each URL's raw HTML, scores it against 7 points (see `references/framework.md` for exact definitions and known heuristic limitations), and writes a 3-tab Excel workbook plus a markdown report shaped like:

```
| # | Point | Result | Job |
|---|---|---|---|
| 1 | Buyer Query | 42/155 (27%) fully match "Best X for Y" | Match the question AI is answering |
...
```

## Workflow

1. **Confirm the input is a listicle list, not a full site sitemap.** If the user gives a full blog sitemap, ask whether they've already filtered to listicle posts, or filter yourself first (titles with Best/Top keywords are a reasonable first pass) before running the audit - this skill's checks assume the input is already listicle-shaped.

2. **Determine execution tier.** Check whether Bash + a persistent working directory are available (Claude Code, Claude Cowork) - if yes, use Tier 1 below. If only a sandboxed code-execution tool is available (Claude Web), read `references/execution-tiers.md` and follow its Tier 2/3 guidance instead - do not silently assume raw-HTML checks (schema, table structure) worked if they didn't.

3. **Tier 1 - run the bundled scripts:**
   ```bash
   python -m venv venv
   venv/Scripts/pip install -r requirements.txt   # Windows
   # venv/bin/pip install -r requirements.txt     # macOS/Linux
   venv/Scripts/python scripts/audit_listicles.py <input_file> extract.json
   venv/Scripts/python scripts/build_outputs.py extract.json <output_prefix>
   ```
   Before running the full list, spot-check `audit_listicles.py` against 2-3 URLs and manually verify a couple of results (e.g. does the page really have a comparison table where the script says it does?) - this catches bad heuristic matches early instead of after fetching 100+ pages. `references/framework.md` documents the specific bugs found and fixed during this skill's own development (Table-of-Contents tables miscounted as comparison tables, a CSS-class author heuristic that matched WordPress's comment form on every page) - don't reintroduce either.

4. **Report results.** Lead with the overall average score and tier distribution, then the 7-point table, then priority-ordered recommendations (cheapest sitewide/template fixes first, then structural content gaps, then inconsistency cleanup). Flag explicitly if pick detection failed on a large share of posts (see script output warnings) - that usually means the site's listicle format wasn't recognized, not that the posts scored genuinely low.

## Resources

- `scripts/audit_listicles.py` - fetches and scores each URL. Self-contained (no dependency on any other dataset). Checkpoints progress so an interrupted run can resume.
- `scripts/build_outputs.py` - builds the Excel workbook and markdown report from the extraction JSON.
- `references/framework.md` - exact definition of all 7 points and their sub-checks, plus every known heuristic limitation and false-positive pattern found during development. Read this before interpreting results or explaining a finding to the user.
- `references/execution-tiers.md` - what to do when Bash/venv isn't available (Claude Web). Read this if Tier 1 isn't possible.
