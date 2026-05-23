# Amazon Review Insights Skill

Fetches Amazon reviews for any brand and surfaces hidden patterns that standard dashboards miss. Given a list of ASINs, it reads every review, cross-references across SKUs and time, and produces a structured report with actionable insights for Marketing, Product, and Operations teams.

## What It Produces

A single markdown report saved to `outputs/<brand-slug>-amazon-review-insights.md` with:

| Section | Contents |
|---|---|
| Silent Complaint Audit | Complaints buried inside 4-5 star reviews — invisible to any rating filter |
| Time-Trend Analysis | Whether issues are new (last 3-6 months) or persistent — flags urgent batch/formulation signals |
| Cross-ASIN Patterns | Same reviewer on multiple SKUs, same complaint across unrelated products, hidden brand differentiators |
| Segment Identification | Gifters, repeat buyers, cross-category users, first-time vs. loyal segments |
| Competitive Intelligence | Every competitor mentioned — classified as Win, Loss, or Comparison |
| Hidden Use Cases | Purchase motivations the brand isn't marketing for: gifting, medical, professional, unexpected combinations |
| Expectation Mismatches | Listing problems disguised as product problems |
| Operational Issues | Short counts, delivery damage, CS failures, near-expiry stock |
| Customer Language Bank | Verbatim phrases from real buyers — ready for listing copy and ad creative |

## Requirements

**[Smacient Claude connector](https://smacient.com/products/marketing-context-claude/)** must be connected in your Claude Code session. The skill uses `mcp__claude_ai_Smacient__amazon_get_reviews` to fetch reviews.

No Python dependencies. No scripts. Pure Claude orchestration.

## Setup

Install the skill globally or at project level:

```bash
# Global
cp -r skills/amazon-review-insights ~/.claude/skills/amazon-review-insights

# Project level
cp -r skills/amazon-review-insights path/to/project/.claude/skills/amazon-review-insights
```

## Usage

In a Claude Code session, trigger the skill with:

- `/amazon-review-insights`
- `Analyze Amazon reviews for [Brand]`
- `Run Amazon review insights for [Brand]`
- `Amazon review analysis for [ASINs]`
- `Find hidden patterns in Amazon reviews for [Brand]`

Claude will ask for the brand name, ASINs, and Amazon marketplace before starting.

## Parameters

| Input | Required | Notes |
|---|---|---|
| Brand name | Yes | Used in report title and filename |
| ASINs | Yes | Any number; fetched in batches of 5 |
| Marketplace | Yes | India, US, UK, Germany, Canada, Australia, UAE |

## Pipeline Overview

1. **Fetch reviews** - All ASINs in parallel batches via Smacient MCP (max 50 reviews/ASIN)
2. **Gather context** - Business objective, stakeholders, known issues, key segments
3. **Deep analysis** - Every review read in full; 8 analysis types run simultaneously
4. **Generate report** - Structured markdown saved to `outputs/`

## Output Location

```
outputs/
└── <brand-slug>-amazon-review-insights.md
```
