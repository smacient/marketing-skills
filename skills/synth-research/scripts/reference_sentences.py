import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REFERENCE_SENTENCES = {
    "purchase_intent": [
        "I would never buy this product under any circumstances.",
        "I am very unlikely to purchase this product.",
        "I might consider buying this product but I am not sure.",
        "I would likely buy this product in the near future.",
        "I would definitely purchase this product immediately.",
    ],
    "product_sentiment": [
        "I feel very negative about this product and would not recommend it to anyone.",
        "I have more doubts than confidence about this product.",
        "I have mixed feelings about this product.",
        "I feel fairly positive about this product overall.",
        "I absolutely love this product and think it is excellent.",
    ],
    "ingredient_trust": [
        "I have serious concerns about the safety of the ingredients in this product.",
        "I am somewhat worried about what is in this product.",
        "I am neither reassured nor concerned about the ingredients.",
        "I feel fairly confident that the ingredients are safe and appropriate.",
        "I completely trust the ingredients and feel they are ideal for the purpose.",
    ],
    "value_for_money": [
        "This product is severely overpriced for what it offers.",
        "I feel this product costs more than it is worth.",
        "The price seems about right for what you get.",
        "I think this product offers good value for the price.",
        "This product is outstanding value and I would happily pay more for it.",
    ],
    "content_engagement": [
        "I would immediately scroll past this without a second thought.",
        "I would probably keep scrolling as this did not really catch my attention.",
        "I might pause briefly but I am not sure I would engage further.",
        "This caught my attention and I would likely stop to read more.",
        "I would definitely stop, read everything, and probably click through.",
    ],
    "value_proposition_clarity": [
        "I have no idea what this product does or why I should care.",
        "The message is confusing and I am not sure what they are trying to say.",
        "I understand the basic point but it is not very compelling.",
        "The value proposition is clear and makes sense to me.",
        "This communicates exactly what the product does and why it matters.",
    ],
    "brand_sentiment": [
        "This brand feels untrustworthy or off-putting to me.",
        "I have some doubts about this brand.",
        "I feel neutral about this brand.",
        "I feel fairly positive about this brand.",
        "This brand feels trustworthy, credible, and appealing to me.",
    ],
}

MODE_DEFAULTS = {
    "product": ["purchase_intent", "product_sentiment", "ingredient_trust", "value_for_money"],
    "ad": ["purchase_intent", "content_engagement", "value_proposition_clarity", "brand_sentiment"],
}

DIMENSION_LABELS = {
    "purchase_intent": "Purchase Intent",
    "product_sentiment": "Product Sentiment",
    "ingredient_trust": "Ingredient / Safety Trust",
    "value_for_money": "Value for Money",
    "content_engagement": "Content Engagement",
    "value_proposition_clarity": "Value Proposition Clarity",
    "brand_sentiment": "Brand Sentiment",
}


def get_reference_data(dimensions):
    result = {}
    for dim in dimensions:
        if dim not in REFERENCE_SENTENCES:
            raise ValueError(
                f"Unknown dimension: '{dim}'. "
                f"Available: {list(REFERENCE_SENTENCES.keys())}"
            )
        result[dim] = REFERENCE_SENTENCES[dim]
    return result
