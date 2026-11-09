# FREE TIER edition — LUXE Clothing Store FDE resources

Same structure as `ORIGINA_CLOTHING STORE FDE RESOURCES`, with the GCP deployment
replaced by **Render** so a demo runs at **$0**.

## What changed (only in `FINAL INTEGRATION/FINAL INTEGRATION`)

| File | Change |
|------|--------|
| `main.py` | Port now read from `$PORT` (falls back to 8000) |
| `Dockerfile` | `CMD` expands `${PORT:-8000}` |
| `render.yaml` | **New** — Render Blueprint (free plan, Singapore, `/config` health check) |
| `cloudbuild.yaml` | **Removed** (replaced by Render auto-deploy) |
| `commands-cli.md` | **Removed** (gcloud CLI runbook, no longer applicable) |
| `commands.md` | Rewritten as a Render + Atlas M0 setup guide |
| `.env.example` | Added `GROQ_API_KEY`, `LOGFIRE_TOKEN`, optional Portkey / evals |
| `README.md`, `docs/*` | Hosting / CI-CD / glossary references updated to Render |

## Not copied on purpose

`__pycache__` folders, `POC Development CODE/.env` and
`FINAL INTEGRATION/.logfire/logfire_credentials.json` (they held real keys).
Create your own `.env` from `.env.example`.

## Untouched

`Legacy System Resources`, `POC Development CODE` and `Theory` are copied as-is
(the legacy code is a historical reference and still describes GCP).
