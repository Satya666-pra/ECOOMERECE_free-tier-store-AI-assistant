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


def singularize_keyword(value: str) -> str:
    """
    Reduce each word of a search keyword to a simple singular form, so a plural
    like "shirts" still matches a product called "Polo Shirt" (the query is a
    substring match, and "shirts" is not a substring of "shirt").

    Deliberately simple and conservative — it only strips common plural endings
    and leaves short words and words ending in "ss" alone:
      shirts -> shirt, dresses -> dress, jackets -> jacket, kurtis -> kurti,
      t-shirts -> t-shirt, polo shirts -> polo shirt, jeans -> jean,
      dress -> dress, glass -> glass, tee -> tee
    """
    def one(word: str) -> str:
        w = word.lower()
        if len(w) > 4 and w.endswith("ies"):
            return w[:-3] + "y"
        if len(w) > 4 and w.endswith(("sses", "shes", "ches", "xes", "zes")):
            return w[:-2]
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            return w[:-1]
        return w

    return " ".join(one(w) for w in value.split())


def price_range_filter(min_price: int = None, max_price: int = None) -> dict:
    """Query fragment for a price range; empty dict if neither bound is given."""
    price_query = {}
    if min_price is not None:
        price_query["$gte"] = min_price
    if max_price is not None:
        price_query["$lte"] = max_price
    return price_query
