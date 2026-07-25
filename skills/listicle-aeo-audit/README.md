# /listicle-aeo-audit

Audit any list of listicle-style blog posts ("Best X", "Top N") against the 7-point Citable Listicle Architecture framework — the structural pattern that makes a ranking page safe for AI agents to cite: buyer query, quick answer, methodology, comparison table, vendor sections, decision framework, and proof+FAQ+schema.

No external API or MCP connector required — fetches pages directly and parses raw HTML.

---

## Prerequisites

1. **Python venv** with dependencies: `pip install -r requirements.txt`
2. A list of listicle URLs — sitemap XML, plain text (one URL per line), or a JSON array. Pre-filter to listicle-shaped posts first if starting from a full site sitemap; this skill does not classify content type.

---

## Usage

```
/listicle-aeo-audit <path-to-url-list>
```

**Examples:**
```
/listicle-aeo-audit sitemap-listicles.xml
/listicle-aeo-audit listicle-urls.txt
/listicle-aeo-audit listicle-urls.json
```

---

## Output

- **Excel workbook** (3 tabs): Full Data (every sub-check per URL), Summary (sitewide pass rates, 15 lowest/highest scorers), Point Detail (the 7-point framework + sitewide result)
- **Markdown report**: the same `# | Point | Result | Job` table shape, plus a priority-ordered "what this means" section

Each post gets a 0-1 score per point, summed to a Total Score /7, bucketed into Weak (<3) / Moderate (3-5) / Strong (5+).

---

## Known limitations

- Visible-byline and comparison-table detection are heuristic (regex/structural), not full reading comprehension — see `references/framework.md` for documented false-positive patterns found during development (and fixed) that are worth knowing about before trusting the numbers blindly.
- Schema (Article/FAQPage/ItemList) detection requires a raw HTML fetch. In environments without Bash/Python access (e.g. Claude Web without a code-execution tool), some checks degrade — see `references/execution-tiers.md`.

---

## Setup

See `SKILL.md` for the full step-by-step skill definition to install in your Claude Code workspace.
