"""
Fetch and score a list of listicle URLs against the 7-point Citable
Listicle Architecture framework. Self-contained - computes every field
fresh from the live page, no external dataset dependency.

Usage:
    python audit_listicles.py <input_file> [output_json]

<input_file> may be:
  - a sitemap XML file (parses <loc> entries)
  - a .json file containing a JSON array of URL strings
  - a plain text file, one URL per line

Requires: requests, beautifulsoup4, lxml
Install in a project-local venv:
    python -m venv venv
    venv/Scripts/pip install requests beautifulsoup4 lxml   (Windows)
    venv/bin/pip install requests beautifulsoup4 lxml       (macOS/Linux)

IMPORTANT: this script fetches raw HTML directly via requests, not through
a "fetch and summarize" tool - JSON-LD <script> tags and table structure
must be seen as raw markup, or schema/table detection silently returns
false negatives. See references/framework.md for why this matters.
"""

import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 Citable-Listicle-Audit/1.0"
}
REQUEST_DELAY_SECONDS = 0.5
TIMEOUT_SECONDS = 20

YEAR_PATTERN = re.compile(r"\b20(2[4-9]|3[0-9])\b")
BEST_OR_TOP_PATTERN = re.compile(r"\b(best|top\s?\d+|top\s+\w+)\b", re.IGNORECASE)
FOR_CLAUSE_PATTERN = re.compile(r"\bfor\b", re.IGNORECASE)
NUMBERED_HEADING_PATTERN = re.compile(r"^\s*\d+[\.\)]")
BEST_FOR_PATTERN = re.compile(r"\bbest for\b", re.IGNORECASE)
METHOD_HEADING_PATTERN = re.compile(
    r"methodology|how (we|i) (chose|selected|tested|ranked|evaluate)|criteria|"
    r"how this list was (made|created|compiled)",
    re.IGNORECASE,
)
CRITERIA_BODY_PATTERN = re.compile(
    r"\bcriteria\b|\bwe (evaluated|tested|reviewed|compared|ranked)\b|\bmethodology\b",
    re.IGNORECASE,
)
FEATURES_PATTERN = re.compile(r"\bfeatures?\b", re.IGNORECASE)
LIMITS_PATTERN = re.compile(r"\blimit(ation)?s?\b|\bcons?\b|\bdrawbacks?\b|\bdownsides?\b", re.IGNORECASE)
PRICING_PATTERN = re.compile(r"\bpric(e|ing)\b|\bcost\b|\bfree\b|\bplans?\b|\btrial\b", re.IGNORECASE)
CHOOSE_IF_PATTERN = re.compile(r"\bchoose (this |it )?if\b|\bideal for\b|\bgo with\b|\bpick this if\b", re.IGNORECASE)
DECISION_HEADING_PATTERN = re.compile(
    r"how to choose|which (one )?should you|decision|which is right for you|final (thoughts|verdict)",
    re.IGNORECASE,
)
CHOOSE_X_IF_BODY_PATTERN = re.compile(r"\bchoose\b.{0,40}\bif\b", re.IGNORECASE)
AVOID_PATTERN = re.compile(r"\bavoid\b", re.IGNORECASE)
STATS_PATTERN = re.compile(
    r"\d+(\.\d+)?\s?%|\baccording to\b|\bstudy (shows|found)\b|\bstatistics?\b|\bsurvey(ed)?\b",
    re.IGNORECASE,
)
TABLE_COLUMN_KEYWORDS = ["tool", "best for", "strength", "limit", "pricing", "price", "feature", "pros", "cons"]
FAQ_HEADING_PATTERN = re.compile(r"\bfaq|frequently asked questions\b", re.IGNORECASE)
DATE_PATTERN = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
)
# Visible-byline detection is text-pattern only - do NOT add a CSS
# class-based heuristic (e.g. class contains "author"). That matched a
# WordPress comment form's "comment-form-author" field on every page in
# testing and produced a 100% false positive rate.
AUTHOR_HINT_PATTERN = re.compile(r"\bby\s+[A-Z][a-zA-Z.]+(\s+[A-Z][a-zA-Z.]+)?\b")


def load_urls(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    if raw.lstrip().startswith("<?xml") or "<urlset" in raw[:500]:
        root = ET.fromstring(raw)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [el.find("sm:loc", ns).text.strip() for el in root.findall("sm:url", ns)]
        return [u for u in urls if u]

    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(u).strip() for u in data if str(u).strip()]
    except (json.JSONDecodeError, ValueError):
        pass

    return [line.strip() for line in raw.splitlines() if line.strip().startswith("http")]


def find_main_content(soup):
    for selector in ["article", "main", "div.entry-content", "div.post-content", "div[class*='content']"]:
        node = soup.select_one(selector)
        if node and len(node.get_text(strip=True)) > 200:
            return node
    return soup.body if soup.body else soup


def get_headings_in_order(content):
    return [
        {"tag": h.name, "text": h.get_text(strip=True)}
        for h in content.find_all(["h1", "h2", "h3"])
        if h.get_text(strip=True)
    ]


def get_ordered_block_elements(content):
    return content.find_all(["h1", "h2", "h3", "ul", "ol", "table"])


def segment_by_heading(content):
    segments = []
    current_heading = None
    current_texts = []
    for el in content.find_all(["h1", "h2", "h3", "p", "li", "td"]):
        if el.name in ("h1", "h2", "h3"):
            if current_heading is not None:
                segments.append({"heading": current_heading, "text": " ".join(current_texts)})
            current_heading = el.get_text(strip=True)
            current_texts = []
        else:
            txt = el.get_text(" ", strip=True)
            if txt:
                current_texts.append(txt)
    if current_heading is not None:
        segments.append({"heading": current_heading, "text": " ".join(current_texts)})
    return segments


def extract_jsonld_types(soup):
    types_found = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            nodes = graph if isinstance(graph, list) else [item]
            for node in nodes:
                if not isinstance(node, dict) or "@type" not in node:
                    continue
                t = node["@type"]
                types_found.extend(t if isinstance(t, list) else [t])
    return sorted(set(types_found))


def detect_picks(content, headings):
    """Numbered-heading pattern first; if fewer than 3 matches, fall back
    to numbered <ol><li> items. If both fail, pick count is undetected."""
    numbered_headings = [h for h in headings if NUMBERED_HEADING_PATTERN.match(h["text"])]
    if len(numbered_headings) >= 3:
        return len(numbered_headings), "numbered_headings", numbered_headings
    ol_items = content.find_all("li", recursive=True)
    ol_parents = [li for li in ol_items if li.find_parent("ol")]
    if len(ol_parents) >= 3:
        return len(ol_parents), "ordered_list_items", []
    return None, "not_detected", []


def analyze_listicle(url):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    content = find_main_content(soup)
    body_text = content.get_text(separator=" ", strip=True)
    headings = get_headings_in_order(content)
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # 1. BUYER QUERY
    has_best_or_top = bool(BEST_OR_TOP_PATTERN.search(title))
    has_year_in_title = bool(YEAR_PATTERN.search(title))
    has_for_clause = bool(FOR_CLAUSE_PATTERN.search(title))
    buyer_query_match = has_best_or_top and has_for_clause

    # 2. QUICK ANSWER
    pick_count, pick_detection_method, numbered_headings = detect_picks(content, headings)
    pick_count_in_range = 5 <= pick_count <= 8 if pick_count is not None else None
    best_for_count = len(BEST_FOR_PATTERN.findall(body_text))
    has_best_for_labels = best_for_count >= 3

    ordered = get_ordered_block_elements(content)
    before_first_heading = []
    for el in ordered:
        if el.name in ("h1", "h2", "h3"):
            break
        before_first_heading.append(el)
    quick_answer_lists = [
        el for el in before_first_heading if el.name in ("ul", "ol") and len(el.find_all("li", recursive=False)) >= 3
    ]
    quick_answer_tables = [el for el in before_first_heading if el.name == "table"]
    quick_answer_near_top = bool(quick_answer_lists or quick_answer_tables)

    # 3. METHODOLOGY
    methodology_heading_present = any(METHOD_HEADING_PATTERN.search(h["text"]) for h in headings)
    criteria_language_present = bool(CRITERIA_BODY_PATTERN.search(body_text))
    visible_byline_present = bool(AUTHOR_HINT_PATTERN.search(body_text[:1500]))
    visible_date_present = bool(DATE_PATTERN.search(body_text[:3000])) or bool(content.find("time"))

    # 4. COMPARISON TABLE
    all_tables = content.find_all("table")

    def is_toc_table(table):
        return "table of contents" in table.get_text(" ", strip=True).lower()[:60]

    genuine_tables = [t for t in all_tables if not is_toc_table(t)]
    has_comparison_table = any(len(t.find_all("tr")) >= 3 for t in genuine_tables)
    table_column_match_count = 0
    for t in genuine_tables:
        first_row = t.find("tr")
        if not first_row:
            continue
        headers_text = " ".join(c.get_text(" ", strip=True).lower() for c in first_row.find_all(["td", "th"]))
        match = sum(1 for kw in TABLE_COLUMN_KEYWORDS if kw in headers_text)
        table_column_match_count = max(table_column_match_count, match)

    # 5. VENDOR SECTIONS
    segments = segment_by_heading(content)
    if pick_detection_method == "numbered_headings":
        pick_segments = [s for s in segments if NUMBERED_HEADING_PATTERN.match(s["heading"])]
    else:
        pick_segments = []
    n_picks = len(pick_segments)
    if n_picks > 0:
        pct_features = round(100 * sum(1 for s in pick_segments if FEATURES_PATTERN.search(s["text"])) / n_picks, 1)
        pct_limits = round(100 * sum(1 for s in pick_segments if LIMITS_PATTERN.search(s["text"])) / n_picks, 1)
        pct_pricing = round(100 * sum(1 for s in pick_segments if PRICING_PATTERN.search(s["text"])) / n_picks, 1)
        pct_best_for = round(100 * sum(1 for s in pick_segments if BEST_FOR_PATTERN.search(s["text"])) / n_picks, 1)
        pct_choose_if = round(100 * sum(1 for s in pick_segments if CHOOSE_IF_PATTERN.search(s["text"])) / n_picks, 1)
        vendor_sections_present = True
    else:
        pct_features = pct_limits = pct_pricing = pct_best_for = pct_choose_if = None
        vendor_sections_present = False

    # 6. DECISION FRAMEWORK
    decision_heading_present = any(DECISION_HEADING_PATTERN.search(h["text"]) for h in headings)
    choose_if_avoid_body = len(CHOOSE_X_IF_BODY_PATTERN.findall(body_text)) >= 2 and bool(AVOID_PATTERN.search(body_text))
    decision_framework_present = decision_heading_present or choose_if_avoid_body

    # 7. PROOF + FAQ + SCHEMA
    has_stats = bool(STATS_PATTERN.search(body_text))
    domain = urlparse(url).netloc
    external_link_count = sum(
        1 for a in content.find_all("a", href=True)
        if a["href"].startswith("http") and urlparse(a["href"]).netloc not in (domain, "")
    )
    has_faq_section = bool(FAQ_HEADING_PATTERN.search(body_text)) or any(
        FAQ_HEADING_PATTERN.search(h["text"]) for h in headings
    )
    jsonld_types = extract_jsonld_types(soup)
    has_faq_schema = "FAQPage" in jsonld_types
    has_article_schema = any(t in ("Article", "BlogPosting") for t in jsonld_types)
    has_itemlist_schema = "ItemList" in jsonld_types
    proof_score = sum(
        [has_stats, external_link_count > 0, has_faq_section, has_faq_schema, has_article_schema, has_itemlist_schema]
    )

    return {
        "url": url,
        "title": title,
        "fetch_status": "ok",
        "fetch_tier": "tier1_raw_html",

        "p1_has_best_or_top": has_best_or_top,
        "p1_has_year_in_title": has_year_in_title,
        "p1_has_for_clause": has_for_clause,
        "p1_buyer_query_match": buyer_query_match,

        "p2_pick_count": pick_count,
        "p2_pick_detection_method": pick_detection_method,
        "p2_pick_count_in_range_5_8": pick_count_in_range,
        "p2_best_for_mentions": best_for_count,
        "p2_has_best_for_labels": has_best_for_labels,
        "p2_quick_answer_near_top": quick_answer_near_top,

        "p3_methodology_heading_present": methodology_heading_present,
        "p3_criteria_language_present": criteria_language_present,
        "p3_visible_byline_present": visible_byline_present,
        "p3_visible_date_present": visible_date_present,

        "p4_has_comparison_table": has_comparison_table,
        "p4_num_genuine_tables": len(genuine_tables),
        "p4_toc_rendered_as_table": len(all_tables) > len(genuine_tables),
        "p4_table_column_match_count_of_8": table_column_match_count,

        "p5_num_pick_sections": n_picks,
        "p5_vendor_sections_present": vendor_sections_present,
        "p5_pct_sections_with_features": pct_features,
        "p5_pct_sections_with_limits": pct_limits,
        "p5_pct_sections_with_pricing": pct_pricing,
        "p5_pct_sections_with_best_for": pct_best_for,
        "p5_pct_sections_with_choose_if": pct_choose_if,

        "p6_decision_heading_present": decision_heading_present,
        "p6_choose_if_avoid_pattern_in_body": choose_if_avoid_body,
        "p6_decision_framework_present": decision_framework_present,

        "p7_has_stats": has_stats,
        "p7_external_link_count": external_link_count,
        "p7_has_faq_section": has_faq_section,
        "p7_has_faq_schema": has_faq_schema,
        "p7_has_article_schema": has_article_schema,
        "p7_has_itemlist_schema": has_itemlist_schema,
        "p7_proof_score_of_6": proof_score,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python audit_listicles.py <input_file> [output_json]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "listicle_audit_extract.json"
    checkpoint_path = output_path + ".checkpoint"

    urls = load_urls(input_path)
    print(f"[INFO] {len(urls)} URLs loaded from {input_path}")

    try:
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            checkpoint = json.load(f)
    except FileNotFoundError:
        checkpoint = {}
    print(f"[INFO] {len(checkpoint)} already processed in checkpoint")

    for i, url in enumerate(urls, start=1):
        if url in checkpoint:
            continue
        try:
            checkpoint[url] = analyze_listicle(url)
            print(f"[OK] ({i}/{len(urls)}) {url}")
        except Exception as exc:
            checkpoint[url] = {"url": url, "fetch_status": f"error: {exc}"}
            print(f"[ERROR] ({i}/{len(urls)}) {url} - {exc}")

        if i % 10 == 0:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, ensure_ascii=False, indent=2)
            print(f"[CHECKPOINT] saved at {i}/{len(urls)}")

        time.sleep(REQUEST_DELAY_SECONDS)

    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)

    ordered_records = [checkpoint[u] for u in urls if u in checkpoint]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ordered_records, f, ensure_ascii=False, indent=1)

    ok_count = sum(1 for r in ordered_records if r.get("fetch_status") == "ok")
    print(f"[DONE] {ok_count}/{len(ordered_records)} analyzed. Output written to {output_path}")

    low_word_flags = [r["url"] for r in ordered_records if r.get("fetch_status") == "ok" and r.get("p5_num_pick_sections", 0) == 0 and r.get("p2_pick_detection_method") == "not_detected"]
    if len(low_word_flags) > len(ordered_records) * 0.3:
        print(f"[WARNING] {len(low_word_flags)}/{len(ordered_records)} posts had no detectable pick structure. "
              f"This may mean the site needs JS rendering to see real content, or uses a very different "
              f"listicle format than numbered headings/ordered lists. Spot-check 2-3 URLs in a browser "
              f"before trusting these results.")


if __name__ == "__main__":
    main()
