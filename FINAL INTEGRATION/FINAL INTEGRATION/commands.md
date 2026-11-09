# Deploying to Render (free tier) — step by step

This guide deploys LUXE to **Render**'s free web service, with **MongoDB Atlas
M0**, **Groq** and **Logfire** on their free tiers. Total cost: **$0**.

Everything is done in the web dashboards — no CLI needed.

---

## Phase 1 — Prepare the repository

1. Make sure the **repo root** is this folder (the one containing `Dockerfile`,
   `main.py`, `render.yaml`). If your GitHub repo is one level higher, set
   **Root Directory** to this folder when creating the Render service.
2. Confirm `.env` is **not** committed (`.gitignore` already excludes it).
3. Rotate any API key that was ever committed or pasted into a shared file.
4. Push to GitHub.

## Phase 2 — MongoDB Atlas (free M0)

1. Sign in at [cloud.mongodb.com](https://cloud.mongodb.com) and create a
   **free M0** cluster. Pick `ap-southeast-1` (Singapore) to sit next to Render's
   Singapore region.
2. **Database Access** → add a user with a strong password.
3. **Network Access** → **Add IP Address** → `0.0.0.0/0` (Allow from anywhere).
   Render's free tier has no fixed outbound IP, so this is required. Keep the
   password strong.
4. **Connect → Drivers** → copy the connection string
   (`mongodb+srv://user:password@cluster.../?appName=...`). This is `MONGO_URI`.

## Phase 3 — Other free keys

| Key | Where to get it |
|-----|-----------------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) → API Keys (free tier) |
| `LOGFIRE_TOKEN` *(optional)* | [logfire.pydantic.dev](https://logfire.pydantic.dev) → project → Settings → Write tokens |
| `GOOGLE_CLIENT_ID` *(optional)* | Google Cloud Console → APIs & Services → Credentials → OAuth client ID (Web). Creating it needs no billing. |

## Phase 4 — Create the Render service

**Option A — Blueprint (recommended).**
1. Sign in at [render.com](https://render.com) and connect your GitHub account.
2. **New → Blueprint** → pick the repo. Render reads
   [`render.yaml`](render.yaml) and proposes a free `luxe-store` web service.
3. Fill in the prompted values: `MONGO_URI`, `GOOGLE_CLIENT_ID`,
   `GROQ_API_KEY`, `LOGFIRE_TOKEN` (leave blank values you don't have).
4. **Apply**.

**Option B — manual.**
1. **New → Web Service** → pick the repo.
2. **Runtime:** Docker. **Instance type:** Free. **Region:** Singapore.
3. **Advanced → Health Check Path:** `/config`.
4. Add the environment variables listed in Phase 3 (plus `MONGO_URI`).
5. **Create Web Service**.

The first build takes a few minutes. When it turns **Live**, the URL at the top
of the service page (`https://luxe-store-xxxx.onrender.com`) is your site.

## Phase 5 — Google Sign-In (only if you use it)

In Google Cloud Console → **Credentials** → your OAuth client → **Authorized
JavaScript origins** → add `https://<your-service>.onrender.com`. Without this,
the Google button fails with an origin error. Changes can take a few minutes to
apply.

## Phase 6 — Verify

1. Open the site → product grid loads.
2. Register / log in, add to cart, place an order.
3. Open the chat widget and ask *"men's shirts under 2000"* → product cards appear.
4. Admin → bulk import with `demo_data/bulk_upload.xlsx` + `demo_data/Imgs.zip`
   (small, fits within the free M0 size).

If something fails, check **Logs** in the Render dashboard first.

## Day-to-day

- **Deploy:** `git push` — Render rebuilds and redeploys automatically.
- **Change a secret:** Render → service → **Environment** → edit → save
  (triggers a redeploy).
- **Cold start:** the free service sleeps after ~15 minutes idle; the next
  visit takes 30–60 s to wake. Open it before a demo, or ping it every 10 minutes
  with a free monitor (e.g. UptimeRobot) hitting `/config`.
- **Rollback:** Render → **Events/Deploys** → pick an earlier deploy → **Rollback**.

## Run locally

```bash
cp .env.example .env          # fill in MONGO_URI and GROQ_API_KEY (minimum)
uv venv clothenv              # or: python -m venv clothenv
source clothenv/Scripts/activate       # Windows; clothenv/bin/activate elsewhere
uv pip install -r requirements.txt
python main.py                # http://localhost:8000
```

## Staying at $0

- Keep the Render instance type on **Free** (not Starter).
- Keep Atlas on **M0**.
- Leave `ONLINE_EVALS_ENABLED=false` and Portkey unset.
- Don't bulk-upload many images (base64 in MongoDB fills 512 MB quickly).
