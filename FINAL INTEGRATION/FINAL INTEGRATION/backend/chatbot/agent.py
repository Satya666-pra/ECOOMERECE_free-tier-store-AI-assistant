"""
The Pydantic AI shopping agent: system prompt, dependencies, and its
`search_products` tool for querying the LUXE MongoDB catalog.

Routed through Portkey when configured (see utils/llm_gateway.py), otherwise
talks to Groq directly.
"""
from typing import List, Optional, Dict, Any

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from ..config import REFUSAL_MESSAGE, settings
from ..database import products_collection
from ..utils.images import resolve_image_field
from ..utils.mongo import (
    case_insensitive_exact,
    price_range_filter,
    product_name_filter,
)
from ..utils.llm_gateway import (
    PORTKEY_API_KEY,
    PORTKEY_BASE_URL,
    is_portkey_configured,
    resolve_model_name,
)

RAW_AGENT_MODEL = settings.agent_model_name

SYSTEM_PROMPT = (
    "You are a friendly shopping assistant for LUXE — an online clothing store. "
    "The store has 3 categories: men, women, and kids."
    "\n\n"
    "RULES:\n"
    "1. If the user greets you or asks who you are → reply naturally and warmly.\n"
    "2. If the user wants to browse, find, or buy products → ALWAYS call the `search_products` tool with the right filters. Never describe products yourself.\n"
    "   - Whenever the user names a type of clothing (shirt, pants, suit, dress, jacket, jeans, ...), pass it as `keyword` — a single SINGULAR word like 'shirt' or 'pant'. Never leave it out, or the search returns every product in the category.\n"
    "   - Pass men / women / kids as `category`, and any budget as `max_price` / `min_price`.\n"
    "3. After calling `search_products`, tell the user only what you actually searched for, using the filters the tool reports back (e.g. 'Here are men's shirts under ₹2000!'). Never claim a filter you did not use.\n"
    f"4. If the user asks something completely unrelated to shopping or clothes, reply: '{REFUSAL_MESSAGE}'\n"
    "5. DO NOT make up product names, prices, or details ever."
)


class StoreDeps(BaseModel):
    """Side-channel for a single agent run: the products `search_products` found."""
    found_products: List[Dict[str, Any]] = []


if is_portkey_configured():
    agent_model = OpenAIChatModel(
        model_name=resolve_model_name(RAW_AGENT_MODEL),
        provider=OpenAIProvider(base_url=PORTKEY_BASE_URL, api_key=PORTKEY_API_KEY),
    )
else:
    agent_model = f"groq:{RAW_AGENT_MODEL}"

# Live evaluation is optional (see backend/chatbot/online_evals.py). Imported only
# when enabled, so the standalone chatbot POC can ship this file unchanged without
# depending on pydantic-evals.
_capabilities = []
if settings.online_evals_enabled:
    from .online_evals import online_evaluation

    _capabilities = [online_evaluation]

agent = Agent(
    agent_model,
    name="chatbot",
    deps_type=StoreDeps,
    capabilities=_capabilities,
    system_prompt=SYSTEM_PROMPT,
)


@agent.tool
def search_products(
    ctx: RunContext[StoreDeps],
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    max_price: Optional[int] = None,
    min_price: Optional[int] = None,
) -> str:
    """
    Search the LUXE product database.

    Args:
        category: Filter by category — one of 'men', 'women', 'kids'.
        keyword: The TYPE of clothing the user asked for, as one singular word
            (e.g. 'shirt', 'pant', 'suit', 'dress', 'jacket', 'jeans'). ALWAYS
            set this when the user names a type of clothing; leaving it empty
            returns every product in the category.
        max_price: Maximum price in rupees (e.g. 2000 means under ₹2000).
        min_price: Minimum price in rupees.

    Returns:
        A short confirmation string of what was found, including the filters
        that were applied.
    """
    query: Dict[str, Any] = {}
    applied: List[str] = []

    if category and category.strip():
        query["category"] = case_insensitive_exact(category.strip())
        applied.append(f"category={category.strip().lower()}")

    if keyword and keyword.strip():
        # Plurals and general words ("shirts", "pants") are expanded to the
        # catalog's own names — see product_name_filter.
        query["name"] = product_name_filter(keyword.strip())
        applied.append(f"keyword={keyword.strip().lower()}")

    price_filter = price_range_filter(min_price, max_price)
    if price_filter:
        query["price"] = price_filter
        if min_price is not None:
            applied.append(f"min_price={min_price}")
        if max_price is not None:
            applied.append(f"max_price={max_price}")

    filters_text = ", ".join(applied) if applied else "none (all products)"

    raw_results = list(products_collection.find(query).limit(8))

    processed = []
    for r in raw_results:
        r["id"] = str(r["_id"])
        r.pop("_id", None)
        resolve_image_field(r)
        processed.append(r)

    # Store results so the endpoint can send them to the frontend
    ctx.deps.found_products = processed

    if not processed:
        return f"No products found. Filters applied: {filters_text}."
    return f"Found {len(processed)} products. Filters applied: {filters_text}."
