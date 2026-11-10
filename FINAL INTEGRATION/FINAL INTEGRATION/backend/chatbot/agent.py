# ==============================================================================
# FILE: backend/chatbot/agent.py
#
# PROGRAM SUMMARY
#   The shopping assistant itself: a Pydantic AI `Agent` backed by a Groq-hosted LLM.
#   It owns (1) the system prompt that defines the assistant's behaviour and rules, and
#   (2) its ONLY tool, `search_products`, which queries the MongoDB product catalog.
#
# HOW IT WORKS
#   1. The model is chosen (Portkey gateway or direct Groq).
#   2. The user's message goes to the model together with SYSTEM_PROMPT.
#   3. For shopping requests the model CALLS `search_products(category, keyword, prices)`.
#   4. The tool runs a read-only MongoDB query (max 8 products), stores the products in
#      `ctx.deps.found_products`, and returns a short text: "Found N products. Filters
#      applied: ...". The model then writes a one-line reply based on that text.
#   5. The pipeline sends the reply plus the stored products to the browser.
#   The model never writes product details itself - the cards come straight from the database.
#
# DEPENDS ON : backend/config.py, database.py, utils (images, mongo, llm_gateway), pydantic-ai
# USED BY    : backend/chatbot/pipeline.py
# ==============================================================================

"""
The Pydantic AI shopping agent: system prompt, dependencies, and its
`search_products` tool for querying the LUXE MongoDB catalog.

Routed through Portkey when configured (see utils/llm_gateway.py), otherwise
talks to Groq directly.
"""
from typing import List, Optional, Dict, Any

from pydantic import BaseModel
# Agent = the LLM wrapper; RunContext = per-run data handed to tools.
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from ..config import REFUSAL_MESSAGE, settings
# READ-ONLY access to the catalog. The agent has no access to users, carts or orders.
from ..database import products_collection
from ..utils.images import resolve_image_field
from ..utils.mongo import (
    case_insensitive_exact,
    normalize_category,
    price_range_filter,
    product_name_filter,
)
from ..utils.llm_gateway import (
    PORTKEY_API_KEY,
    PORTKEY_BASE_URL,
    is_portkey_configured,
    resolve_model_name,
)

# The bare Groq model id, e.g. openai/gpt-oss-20b.
RAW_AGENT_MODEL = settings.agent_model_name

# The assistant's "job description". Prompt-engineering notes:
# - rule 2 forces the tool call and demands a SINGULAR `keyword` (otherwise a search for
#   "men's shirts" returns every men's product);
# - rule 3 stops the model claiming filters it did not use;
# - rule 4 sends off-topic requests to the standard refusal;
# - rule 5 forbids inventing products or prices.
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


# "Dependencies" passed into one agent run. Used here as a side channel: the tool
# leaves the raw product rows in `found_products` so the API can send real cards to
# the browser instead of relying on the model to repeat them.
class StoreDeps(BaseModel):
    """Side-channel for a single agent run: the products `search_products` found."""
    found_products: List[Dict[str, Any]] = []


# Build one model object for a bare Groq model id, reached via Portkey or straight to Groq.
def _build_model(raw_model_name: str):
    if is_portkey_configured():
        return OpenAIChatModel(
            model_name=resolve_model_name(raw_model_name),
            provider=OpenAIProvider(base_url=PORTKEY_BASE_URL, api_key=PORTKEY_API_KEY),
        )
    # Default path: the string 'groq:<model>' lets Pydantic AI use its built-in Groq provider
    # (reads GROQ_API_KEY).
    return f"groq:{raw_model_name}"


# Fallback chain implemented in our own code (no external gateway). If the main model
# fails with an API error (429 rate limit, 5xx, timeout), Pydantic AI's FallbackModel
# transparently retries the same request on the next model in the list.
_fallback_names = [
    name.strip()
    for name in settings.agent_fallback_model_names.split(",")
    if name.strip() and name.strip() != RAW_AGENT_MODEL
]
if _fallback_names:
    agent_model = FallbackModel(
        _build_model(RAW_AGENT_MODEL), *[_build_model(name) for name in _fallback_names]
    )
else:
    agent_model = _build_model(RAW_AGENT_MODEL)

# Live evaluation is optional (see backend/chatbot/online_evals.py). Imported only
# when enabled, so the standalone chatbot POC can ship this file unchanged without
# depending on pydantic-evals.
# Optional extras attached to the agent. Empty unless live evaluation is switched on.
_capabilities = []
# Imported lazily so the app does not require pydantic-evals when the feature is off.
if settings.online_evals_enabled:
    from .online_evals import online_evaluation

    _capabilities = [online_evaluation]

# THE agent object used by the pipeline: model + dependency type + system prompt.
agent = Agent(
    agent_model,
    name="chatbot",
    deps_type=StoreDeps,
    capabilities=_capabilities,
    system_prompt=SYSTEM_PROMPT,
)


# Registers the function below as a tool the LLM may call. Its name, parameter names
# and DOCSTRING are sent to the model as the tool description - so the docstring is
# effectively part of the prompt.
@agent.tool
# The one capability of the assistant: look up products. Every parameter is optional.
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
    # Start with an empty MongoDB filter and add one condition per argument given.
    query: Dict[str, Any] = {}
    # Human-readable list of the filters used; echoed back to the model (rule 3).
    applied: List[str] = []

    # men / women / kids (aliases like "male" are normalised to the real category).
    if category and category.strip():
        # "male" / "ladies" / "boys" -> men / women / kids
        category_name = normalize_category(category)
        query["category"] = case_insensitive_exact(category_name)
        applied.append(f"category={category_name}")

    # Clothing type, matched against the product NAME (plural/synonym aware).
    if keyword and keyword.strip():
        # Plurals and general words ("shirts", "pants") are expanded to the
        # catalog's own names — see product_name_filter.
        query["name"] = product_name_filter(keyword.strip())
        applied.append(f"keyword={keyword.strip().lower()}")

    # Optional budget limits in rupees.
    price_filter = price_range_filter(min_price, max_price)
    if price_filter:
        query["price"] = price_filter
        if min_price is not None:
            applied.append(f"min_price={min_price}")
        if max_price is not None:
            applied.append(f"max_price={max_price}")

    # Readable summary such as "category=men, keyword=shirt, max_price=1000".
    filters_text = ", ".join(applied) if applied else "none (all products)"

    # Run the query. LIMIT 8: keeps the chat cards short and the token cost low.
    raw_results = list(products_collection.find(query).limit(8))

    # Make each MongoDB document JSON-friendly: `_id` -> `id`, image -> URL.
    processed = []
    for r in raw_results:
        r["id"] = str(r["_id"])
        r.pop("_id", None)
        resolve_image_field(r)
        processed.append(r)

    # Store results so the endpoint can send them to the frontend
    # Hand the rows to the API through the side channel (see StoreDeps).
    ctx.deps.found_products = processed

    # Return text for the MODEL to read. It states what was searched so the final reply is honest.
    if not processed:
        return f"No products found. Filters applied: {filters_text}."
    return f"Found {len(processed)} products. Filters applied: {filters_text}."
