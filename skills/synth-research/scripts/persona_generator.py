import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


AWARENESS_TEXT = {
    "cold": "You have never heard of this brand before. This is the first time you are seeing it.",
    "warm": "You have seen this brand mentioned a couple of times online but do not know much about it.",
    "hot": "You are actively looking for a product like this and have been comparing options.",
}

DEFAULT_CONCERNS = [
    "the safety and quality of this product",
    "whether this product is genuinely effective",
    "value for money",
    "ease of use and convenience",
    "whether this is a trustworthy brand",
]

AD_MINDSETS = [
    "You are scrolling through your social media feed quickly and barely paying attention.",
    "You are in a buying mindset and were just thinking about this type of product.",
    "You are skeptical of ads in general and tend to scroll past most of them.",
    "You are open to discovering new products if something genuinely catches your attention.",
    "You have bought similar products before and know exactly what to look for.",
]


def _age_points(age_range, n=7):
    if not age_range or len(age_range) < 2:
        return [25, 28, 32, 35, 38, 42, 45]
    start, end = int(age_range[0]), int(age_range[1])
    if (end - start) < n:
        return list(range(start, end + 1))[:n]
    step = (end - start) / (n - 1)
    return [int(start + i * step) for i in range(n)]


def build_product_personas(audience_config, count=35):
    description = audience_config.get("description", "a general consumer")
    age_range = audience_config.get("age_range")
    concerns = audience_config.get("concerns") or DEFAULT_CONCERNS
    awareness = audience_config.get("awareness", "cold")

    while len(concerns) < 5:
        concerns.append("overall satisfaction with the product")
    concerns = concerns[:5]

    ages = _age_points(age_range, n=7)
    awareness_str = AWARENESS_TEXT.get(awareness, AWARENESS_TEXT["cold"])

    personas = []
    for age in ages:
        for concern in concerns:
            if age_range:
                age_clause = f"Your child or the end user is {age} years old."
            else:
                age_clause = f"You are {age} years old."
            prompt = (
                f"You are {description}. "
                f"{age_clause} "
                f"{awareness_str} "
                f"Your primary concern when buying this type of product is {concern}. "
                f"Read the following product information carefully and respond naturally. "
                f"Share what you genuinely think — including any hesitations, what appeals to you, "
                f"and whether you would actually buy this."
            )
            personas.append(prompt)

    return personas[:count]


def build_ad_personas(audience_config, count=20):
    description = audience_config.get("description", "a general consumer")
    concerns = audience_config.get("concerns") or DEFAULT_CONCERNS[:4]
    awareness = audience_config.get("awareness", "cold")

    while len(concerns) < 4:
        concerns.append("overall satisfaction")
    concerns = concerns[:4]

    awareness_str = AWARENESS_TEXT.get(awareness, AWARENESS_TEXT["cold"])

    personas = []
    for concern in concerns:
        for mindset in AD_MINDSETS:
            prompt = (
                f"You are {description}. "
                f"{awareness_str} "
                f"{mindset} "
                f"Your primary concern about products like this is {concern}. "
                f"You just saw the following ad. Respond naturally — share your immediate reaction, "
                f"whether it caught your attention, and whether you would stop to learn more or keep scrolling."
            )
            personas.append(prompt)

    return personas[:count]


def get_personas(mode, audience_config, count=None):
    if mode == "product":
        return build_product_personas(audience_config, count or 35)
    elif mode == "ad":
        return build_ad_personas(audience_config, count or 20)
    else:
        raise ValueError(f"Unknown mode: '{mode}'. V1 supports: product, ad")
