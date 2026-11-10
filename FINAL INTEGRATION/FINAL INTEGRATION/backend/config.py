# ==============================================================================
# FILE: backend/config.py
#
# PROGRAM SUMMARY
#   The single place where every setting of the app is declared and loaded.
#   It reads the `.env` file (local) or the host's environment variables (Render) and
#   exposes them as one typed object, `settings`, that all other modules import.
#
# HOW IT WORKS
#   1. `load_dotenv()` copies the values of `.env` into the process environment.
#   2. `Settings` (pydantic-settings) declares each variable with a type and a default.
#   3. `settings = Settings()` is created once at import time (a singleton).
#   4. Two shared constants live here too: the support phone number and the standard
#      refusal sentence the chatbot/guardrails use when they decline a request.
#
# DEPENDS ON : python-dotenv, pydantic-settings
# USED BY    : database.py, auth/routes (google), chatbot/agent.py, chatbot/guardrails.py, main.py
# ==============================================================================

"""
Centralised configuration.

Every environment variable the app reads is declared here once as a typed field
on :class:`Settings`, and ``.env`` is loaded in exactly one place — this module.
Import the singleton anywhere:

    from backend.config import settings
    MongoClient(settings.mongo_uri)

Modules that hand raw environment values straight to a third-party client (for
example ``groq.AsyncGroq()``, which reads ``GROQ_API_KEY`` itself) keep working:
importing this module also runs ``load_dotenv()``, which populates ``os.environ``.
"""
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Populate os.environ from .env once, for libraries that read it directly.
# Read `.env` into os.environ ONCE, here. Third-party SDKs (e.g. the Groq client) read
# environment variables themselves, so this must run before they are created.
load_dotenv()

# Customer-care number the chatbot and guardrail refusals point users to.
# Phone number shown to shoppers whenever the assistant refuses or fails.
SUPPORT_PHONE = "546464434"

# The single canonical refusal sentence — used by the guardrails, the agent's
# system prompt, and anywhere else the assistant declines a request.
# The ONE canonical refusal sentence. Guardrails, the agent's system prompt and the
# frontend all reuse it so the wording never drifts apart.
REFUSAL_MESSAGE = (
    f"Sorry, I can't help with that. For assistance, contact our customer care at {SUPPORT_PHONE}."
)


# True when a value is empty or still the template text from `.env.example`
# ("REPLACE_WITH..."). Used to decide whether an optional service is really configured.
def is_placeholder(value: str | None) -> bool:
    """True for an unset value or an untouched ``.env.example`` placeholder."""
    return not value or value.strip().upper().startswith("REPLACE_WITH")


# Typed view of the environment. Field names map to upper-case env vars
# (mongo_uri <- MONGO_URI, groq_api_key <- GROQ_API_KEY, ...).
class Settings(BaseSettings):
    """Typed view of the process environment (and ``.env``)."""

    # Pydantic-settings options: read `.env`, ignore case, and ignore unknown variables
    # (extra="ignore") so extra lines in `.env` never crash start-up.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    # REQUIRED. MongoDB Atlas connection string (mongodb+srv://user:password@cluster/...).
    # Special characters in the password must be URL-encoded (@ -> %40).
    mongo_uri: str | None = None

    # --- LLM provider ---
    # REQUIRED for the chatbot. API key from console.groq.com.
    groq_api_key: str | None = None

    # --- Portkey LLM gateway (optional; falls back to calling Groq directly) ---
    # OPTIONAL. If set, LLM calls are routed through the Portkey gateway; if empty the app
    # calls Groq directly (see utils/llm_gateway.py).
    portkey_api_key: str = ""
    portkey_groq_provider: str = "groq"

    # --- Model ids (overridable without a code change) ---
    # gpt-oss-20b is a Groq *production*-tier model (the guard models below are
    # only available as preview, but they are purpose-built and have no
    # production equivalent). Groq's offline eval judge stays on gpt-oss-120b.
    # Which Groq model powers the shopping agent. Change via AGENT_MODEL_NAME - no code edit.
    agent_model_name: str = "openai/gpt-oss-20b"          # the shopping agent's LLM
    # In-code fallback (no third-party gateway): comma-separated Groq models tried IN ORDER
    # when the main agent model fails (rate limit 429, 5xx, timeout). Groq's free-tier limits
    # are per model, so a different model usually still has quota. Set
    # AGENT_FALLBACK_MODEL_NAMES="" to disable.
    agent_fallback_model_names: str = "openai/gpt-oss-120b"
    # Model used for the content-policy guardrail (checks user text and bot replies).
    guard_model_name: str = "openai/gpt-oss-safeguard-20b"
    # Small classifier model that scores prompt-injection / jailbreak attempts (0 to 1).
    prompt_guard_model_name: str = "meta-llama/llama-prompt-guard-2-86m"

    # --- Google Sign-In (public client id, not a secret) ---
    # OPTIONAL. Public OAuth client id for Google Sign-In. Leave blank to disable it.
    google_client_id: str = ""

    # --- Observability ---
    # This project historically stored the Logfire token as LOGFIRE_API_KEY; the
    # SDK itself looks for LOGFIRE_TOKEN. Accept either, preferring the SDK name.
    # OPTIONAL. Pydantic Logfire write token. Without it tracing is simply switched off.
    logfire_token: str | None = None
    logfire_api_key: str | None = None

    # Attach the live pydantic-evals evaluators to the agent (see
    # backend/chatbot/online_evals.py) so every real chat gets scored in the
    # background. Off by default — evals here run offline only, via
    # `python -m backend.evals.chatbot_evals`. Set ONLINE_EVALS_ENABLED=true to
    # turn this back on.
    # Switch for live, background scoring of every chat. OFF by default because it
    # adds extra LLM calls (and uses Groq quota).
    online_evals_enabled: bool = False

    # Convenience accessor: prefer LOGFIRE_TOKEN but still accept the older name LOGFIRE_API_KEY.
    @property
    def logfire_write_token(self) -> str | None:
        return self.logfire_token or self.logfire_api_key


# The singleton every module imports: `from backend.config import settings`.
settings = Settings()
