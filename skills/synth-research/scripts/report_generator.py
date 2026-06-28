import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from reference_sentences import DIMENSION_LABELS

SCORE_DESCRIPTIONS = {
    "purchase_intent": [
        (1.0, 2.0, "Most personas would not consider buying."),
        (2.0, 2.8, "Low purchase intent - most are skeptical or undecided."),
        (2.8, 3.5, "Moderate intent - audience is on the fence."),
        (3.5, 4.2, "Good intent - most are likely to consider buying."),
        (4.2, 5.1, "Strong intent - most would actively pursue purchase."),
    ],
    "product_sentiment": [
        (1.0, 2.0, "Predominantly negative reactions to the product."),
        (2.0, 2.8, "More doubt than confidence about the product."),
        (2.8, 3.5, "Mixed feelings - some like it, some do not."),
        (3.5, 4.2, "Generally positive product reception."),
        (4.2, 5.1, "Strong enthusiasm for the product."),
    ],
    "ingredient_trust": [
        (1.0, 2.0, "Serious ingredient trust concerns."),
        (2.0, 2.8, "More worry than confidence about ingredients."),
        (2.8, 3.5, "Neutral on ingredients - neither reassured nor worried."),
        (3.5, 4.2, "Fairly confident in ingredient safety."),
        (4.2, 5.1, "Strong trust in ingredients."),
    ],
    "value_for_money": [
        (1.0, 2.0, "Most feel this is overpriced."),
        (2.0, 2.8, "Value for money is a concern."),
        (2.8, 3.5, "Price seems about right to most."),
        (3.5, 4.2, "Good perceived value."),
        (4.2, 5.1, "Excellent value perception."),
    ],
    "content_engagement": [
        (1.0, 2.0, "Most would scroll past without stopping."),
        (2.0, 2.8, "Low stopping power - most keep scrolling."),
        (2.8, 3.5, "Some would pause but engagement is uncertain."),
        (3.5, 4.2, "Good stopping power - most would pause and read."),
        (4.2, 5.1, "High engagement - most would stop and click through."),
    ],
    "value_proposition_clarity": [
        (1.0, 2.0, "Message is unclear - most do not understand the offer."),
        (2.0, 2.8, "Confusing value proposition."),
        (2.8, 3.5, "Understood but not compelling."),
        (3.5, 4.2, "Clear value proposition."),
        (4.2, 5.1, "Crystal clear and immediately compelling."),
    ],
    "brand_sentiment": [
        (1.0, 2.0, "Brand feels untrustworthy to most."),
        (2.0, 2.8, "Some doubts about the brand."),
        (2.8, 3.5, "Neutral brand perception."),
        (3.5, 4.2, "Positive brand sentiment."),
        (4.2, 5.1, "Strong positive brand perception."),
    ],
}


def _describe(score, dimension):
    for low, high, text in SCORE_DESCRIPTIONS.get(dimension, []):
        if low <= score < high:
            return text
    return f"Score: {score}/5"


def _pmf_bars(pmf, width=20):
    labels = ["1 (lowest)", "2         ", "3         ", "4         ", "5 (highest)"]
    lines = []
    for label, p in zip(labels, pmf):
        bar = "#" * int(round(p * width))
        lines.append(f"  {label}  {bar:<{width}}  {p*100:.1f}%")
    return "\n".join(lines)


def _is_bimodal(pmf, low_threshold=0.22, high_threshold=0.15):
    return pmf[0] >= low_threshold and pmf[4] >= high_threshold


def generate_report(config, all_results, timestamp):
    mode = config["mode"]
    audience = config["audience"]
    has_competitor = "Competitor" in all_results
    primary = all_results["Primary"]
    date_str = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"

    lines = []

    # --- Header ---
    lines += [
        "# Synthetic Consumer Research Report",
        "",
        f"**Date:** {date_str}",
        f"**Mode:** {mode.title()} Analysis",
        f"**Audience:** {audience.get('description', 'General consumer')}",
        f"**Awareness level:** {audience.get('awareness', 'cold').title()}",
        f"**Personas:** {config.get('persona_count', 'Default')}",
        f"**LLM:** {config.get('llm_model', 'gemini-2.5-flash')}",
        "",
        "---",
        "",
    ]

    # --- Executive Summary ---
    lines += ["## Executive Summary", ""]
    for dim_id, data in primary.items():
        label = DIMENSION_LABELS.get(dim_id, dim_id)
        score = data["expected"]
        lines.append(f"- **{label}:** {score}/5 — {_describe(score, dim_id)}")
    lines.append("")

    if has_competitor:
        comp = all_results["Competitor"]
        lines += ["**Competitive snapshot:**", ""]
        for dim_id in primary:
            label = DIMENSION_LABELS.get(dim_id, dim_id)
            p = primary[dim_id]["expected"]
            c = comp[dim_id]["expected"]
            gap = round(p - c, 2)
            sign = "+" if gap >= 0 else ""
            lines.append(f"- {label}: Primary {p} vs Competitor {c} (gap: {sign}{gap})")
        lines.append("")

    lines += ["---", ""]

    # --- Per-stimulus detail ---
    for label, results in all_results.items():
        lines += [f"## {label} - Detailed Results", ""]
        for dim_id, data in results.items():
            dim_label = DIMENSION_LABELS.get(dim_id, dim_id)
            score = data["expected"]
            pmf = data["pmf"]

            lines += [
                f"### {dim_label}",
                "",
                f"**Score:** {score}/5",
                "",
                "**Distribution:**",
                "```",
                _pmf_bars(pmf),
                "```",
                "",
                f"**Interpretation:** {_describe(score, dim_id)}",
            ]

            if _is_bimodal(pmf):
                lines += [
                    "",
                    f"> **Segment split detected:** {pmf[0]*100:.0f}% score very low, "
                    f"{pmf[4]*100:.0f}% score very high. "
                    f"This is two distinct audience groups with opposing reactions - "
                    f"not a messaging problem. A single message will not convert both.",
                ]
            lines.append("")

        lines += ["---", ""]

    # --- Methodology ---
    lines += [
        "## Methodology",
        "",
        "This report uses Semantic Similarity Rating (SSR) - an open-source method that converts "
        "AI persona responses into probability distributions (PMFs) across Likert-scale dimensions. "
        "Each score is the probability-weighted expected rating across the synthetic persona panel, "
        "not a simple average. The distribution shape carries as much information as the score.",
        "",
        "**SSR library:** github.com/pymc-labs/semantic-similarity-rating",
        "**Skill:** github.com/smacient/marketing-skills",
        "",
        "> Synthetic research is a directional signal, not ground truth. "
        "Results are most valuable for relative comparison (A vs B) and identifying "
        "specific gaps - not for predicting absolute conversion rates.",
        "",
    ]

    return "\n".join(lines)
