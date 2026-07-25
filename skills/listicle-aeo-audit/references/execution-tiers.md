# Execution tiers across Claude Web, Claude Code, and Claude Cowork

This skill's scripts need: outbound HTTP requests to fetch each URL's raw HTML, and Python packages `requests`, `beautifulsoup4`, `lxml`, `openpyxl`. Not every Claude surface guarantees all of this, so detect capability first and branch.

## Tier 1 - Bash + persistent filesystem available (Claude Code, Claude Cowork)

This is the primary, full-fidelity path. Both surfaces can create a venv, install packages, and run the bundled scripts exactly as written.

```bash
python -m venv venv
# Windows:
venv/Scripts/pip install requests beautifulsoup4 lxml openpyxl
venv/Scripts/python scripts/audit_listicles.py <input_file> extract.json
venv/Scripts/python scripts/build_outputs.py extract.json my-audit
# macOS/Linux:
venv/bin/pip install requests beautifulsoup4 lxml openpyxl
venv/bin/python scripts/audit_listicles.py <input_file> extract.json
venv/bin/python scripts/build_outputs.py extract.json my-audit
```

If a venv already exists in the working directory with these packages installed, reuse it instead of creating a new one.

Both scripts checkpoint progress (`extract.json.checkpoint`) - if a run is interrupted (network blip, rate limit), re-running the same command resumes from where it left off rather than re-fetching everything.

## Tier 2 - Sandboxed code-execution tool only, uncertain network/package access (Claude Web without Bash)

Try the same approach first: run `audit_listicles.py` inside the code-execution tool. If package install or outbound network calls fail:

1. Fetch each URL's raw HTML via whatever fetch tool IS available in that session, if it can return raw source (not a summarized/markdown version - check by looking for `<script type="application/ld+json">` in what comes back; if it's not there, the fetch tool is summarizing and this whole tier degrades further, see below).
2. Feed the raw HTML into the code-execution tool's Python environment (if BeautifulSoup/lxml aren't installable there, fall back to `html.parser`, which is in the Python standard library, or regex-based extraction for the specific patterns needed - schema `<script>` tag contents, `<table>` presence, heading text).
3. Run the same scoring logic from `audit_listicles.py` adapted to operate on already-fetched HTML strings rather than making its own requests.

## Tier 3 - No raw HTML available at all (fetch tool only returns cleaned text/markdown)

This is a materially degraded mode - be explicit about it in the output, don't silently present partial results as if they were the full audit.

Checks that still work on cleaned text (title, headings, body text visible to the fetch tool):
- P1 (Buyer Query) - title pattern
- P2 (Quick Answer) - pick count via headings, best-for mentions, though "near the top" positioning may not survive text cleaning
- P3 (Methodology) - heading/criteria language; visible byline and visible date usually still detectable in cleaned text
- P6 (Decision Framework) - language patterns survive text cleaning fine

Checks that CANNOT be verified without raw HTML - report these as "not verified in this session, re-run in Claude Code/Cowork for accuracy":
- P4 (Comparison Table) - table structure and column headers are lost when converted to prose/markdown (a markdown table may survive in some tools, but don't assume it)
- P7's schema sub-checks (Article/FAQPage/ItemList) - `<script>` tags are stripped before Claude ever sees the content

When running in Tier 3, still produce the workbook and report, but:
- Set P4 and the schema-based P7 sub-checks to null/undetected rather than guessing
- Add a visible note at the top of the report: "Schema and comparison-table checks could not be verified in this session (no raw HTML access) - re-run this skill in Claude Code or Claude Cowork for a complete audit."

## Detecting which tier you're in

- If a Bash tool and persistent working directory are available: Tier 1.
- If only a code-execution/analysis tool is available: attempt Tier 2 first (try installing packages and making a real HTTP request to one test URL from the input list); if that request succeeds and JSON-LD is visible in the raw response, proceed with all URLs at Tier 2. If the request fails or only a summarizing fetch tool is available: Tier 3.
