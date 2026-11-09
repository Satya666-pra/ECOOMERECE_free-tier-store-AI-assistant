"""
Shared MongoDB query-fragment helpers.
"""
import re


def case_insensitive_exact(value: str) -> dict:
    """Query fragment for an exact, case-insensitive string match."""
    return {"$regex": f"^{re.escape(value)}$", "$options": "i"}


def case_insensitive_contains(value: str) -> dict:
    """Query fragment for a case-insensitive substring match."""
    return {"$regex": re.escape(value), "$options": "i"}


# The catalog has exactly three categories: men, women, kids. Shoppers (and the
# model) say "male", "ladies", "boys"... — map them, or the exact-match category
# filter finds nothing.
CATEGORY_ALIASES: dict[str, str] = {
    "men": "men", "man": "men", "mens": "men", "men's": "men", "male": "men",
    "gents": "men", "boy": "kids", "boys": "kids",
    "women": "women", "woman": "women", "womens": "women", "women's": "women",
    "female": "women", "ladies": "women", "lady": "women",
    "girl": "kids", "girls": "kids",
    "kid": "kids", "kids": "kids", "child": "kids", "children": "kids",
}


def normalize_category(value: str) -> str:
    """Map a shopper's word for a category onto the catalog's (men/women/kids).

    Unknown words are returned lowercased and unchanged, so a genuinely
    unknown category still (correctly) finds nothing.
    """
    key = value.strip().lower()
    return CATEGORY_ALIASES.get(key, key)


def singularize_keyword(value: str) -> str:
    """
    Reduce each word of a search keyword to a simple singular form, so a plural
    like "shirts" still matches a product called "Polo Shirt" (the query is a
    substring match, and "shirts" is not a substring of "shirt").

    Deliberately simple and conservative — it only strips common plural endings
    and leaves short words and words ending in "ss" alone:
      shirts -> shirt, dresses -> dress, jackets -> jacket, kurtis -> kurti,
      t-shirts -> t-shirt, polo shirts -> polo shirt, jeans -> jean,
      hoodies -> hoodie, dress -> dress, glass -> glass, tee -> tee

    "-ies" just loses its "s" (hoodies -> hoodie, not "hoody"): the result only
    has to be a substring of the product name, and names use the "-ie" spelling.
    """
    def one(word: str) -> str:
        w = word.lower()
        if len(w) > 4 and w.endswith(("sses", "shes", "ches", "xes")):
            return w[:-2]
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            return w[:-1]
        return w

    return " ".join(one(w) for w in value.split())


# What a shopper means by a general clothing word, in this catalog's own
# vocabulary. The catalog says "Jeans"/"Chinos", never "Pants", and a "Tee" is
# not named "Shirt" — so a plain substring search for the shopper's word misses
# items they would expect. Keys are the singular word the shopper used; values
# are the product-name words that satisfy it. Words not listed here fall back to
# a plain substring match.
KEYWORD_SYNONYMS: dict[str, tuple[str, ...]] = {
    "shirt": ("shirt", "tee", "polo", "blouse"),
    "t-shirt": ("t-shirt", "tshirt", "tee"),
    "tshirt": ("t-shirt", "tshirt", "tee"),
    "tee": ("t-shirt", "tshirt", "tee"),
    "pant": ("pant", "trouser", "jean", "chino"),
    "trouser": ("pant", "trouser", "jean", "chino"),
    "bottom": ("pant", "trouser", "jean", "chino", "short", "skirt"),
    "jacket": ("jacket", "coat", "bomber", "trench"),
    "coat": ("jacket", "coat", "bomber", "trench"),
    "sweater": ("sweater", "cardigan", "hoodie", "pullover"),
}


def product_name_filter(keyword: str) -> dict:
    """
    Query fragment matching a product *name* against a shopper's keyword.

    The keyword is singularized first (see singularize_keyword). If it is a
    general word listed in KEYWORD_SYNONYMS, any of its synonyms matches as a
    whole word (optionally plural), e.g. "pants" matches Jeans, Chinos and
    Trousers but not Suits. Otherwise it is a plain case-insensitive substring
    match on the singularized keyword.
    """
    word = singularize_keyword(keyword)
    synonyms = KEYWORD_SYNONYMS.get(word)
    if not synonyms:
        return case_insensitive_contains(word)
    alternatives = "|".join(re.escape(s) for s in synonyms)
    return {"$regex": rf"\b(?:{alternatives})s?\b", "$options": "i"}


def price_range_filter(min_price: int = None, max_price: int = None) -> dict:
    """Query fragment for a price range; empty dict if neither bound is given."""
    price_query = {}
    if min_price is not None:
        price_query["$gte"] = min_price
    if max_price is not None:
        price_query["$lte"] = max_price
    return price_query
