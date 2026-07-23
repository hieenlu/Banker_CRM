# Deploy to Google Cloud Run (iPad access)

## Goal
Host the Phase 4 web desk + Phase 2/3 API on **Cloud Run** so you can open a
public HTTPS URL from **iPad Safari** (any network, not just home Wi‑Fi).

## What you get
| Service | Cloud Run name | Purpose |
|---|---|---|
| Web | `banker-crm-web` | Next.js UI (open this on iPad) |
| API | `banker-crm-api` | FastAPI + JWT auth |

## One-time setup

1. Create a GCP project and enable billing.
2. Install the Google Cloud SDK: https://cloud.google.com/sdk/docs/install
3. Sign in and select the project:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

If `gcloud builds.submit` returns `PERMISSION_DENIED` even as Owner, set the ADC quota project (command above) and retry after Cloud Build API has been enabled for a minute or two.

4. (Strongly recommended) Point at Postgres so data survives restarts:

```bash
export CRM_DB_URL='postgresql://USER:PASSWORD@HOST/DB?sslmode=require'
# Neon, Supabase, or Cloud SQL all work with Phase 1
```

5. Set a real password + JWT secret:

```bash
export CRM_API_USER=banker
export CRM_API_PASSWORD='pick-a-strong-password'
export CRM_JWT_SECRET="$(openssl rand -hex 32)"
```

## Deploy

From the repo root (this branch):

```bash
# optional region (default asia-southeast1 — change if you prefer)
export GCP_REGION=asia-southeast1

./scripts/deploy_cloudrun.sh
```

The script will:
1. Enable Cloud Run + Artifact Registry + Cloud Build
2. Build/push API and web container images
3. Deploy both services as public HTTPS endpoints
4. Wire CORS so the web origin can call the API

At the end it prints:

```text
iPad Safari → open:   https://banker-crm-web-xxxxx-XX.a.run.app
```

At the end it prints:

```text
iPad Safari → open:   https://banker-crm-web-xxxxx-XX.a.run.app
```

Open that URL on the iPad → sign in with `CRM_API_USER` / `CRM_API_PASSWORD`.

**Important:** every time you pull new UI/API fixes, run `./scripts/deploy_cloudrun.sh` again.
Cloud Run does **not** auto-update from GitHub. On iPad Safari, also hard-refresh
(hold reload → Request Desktop Website off/on, or clear website data) and confirm
the sidebar shows `Build 2026-07-23c-vnd-pnl` (or newer).

## Optional: durable file storage

Cloud Run’s local disk is ephemeral. For attachments / Techcombank PDFs:

```bash
export CRM_STORAGE_BACKEND=s3
export CRM_S3_ENDPOINT_URL='https://<account>.r2.cloudflarestorage.com'  # or omit for AWS
export CRM_S3_REGION=auto
export CRM_S3_BUCKET=banker-crm-files
export CRM_S3_ACCESS_KEY_ID='...'
export CRM_S3_SECRET_ACCESS_KEY='...'
./scripts/deploy_cloudrun.sh
```

## Manual commands (if you prefer)

```bash
# API
gcloud builds submit --config cloudbuild.api.yaml \
  --substitutions=_IMAGE=REGION-docker.pkg.dev/PROJECT/banker-crm/api:latest

gcloud run deploy banker-crm-api --image=... --region=REGION --allow-unauthenticated \
  --set-env-vars="CRM_API_USER=banker,CRM_API_PASSWORD=...,CRM_JWT_SECRET=...,CRM_API_CORS_ORIGINS=https://WEB_URL"

# Web (bake API URL into the client)
gcloud builds submit web --config web/cloudbuild.yaml \
  --substitutions=_IMAGE=REGION-docker.pkg.dev/PROJECT/banker-crm/web:latest,_API_URL=https://API_URL

gcloud run deploy banker-crm-web --image=... --region=REGION --allow-unauthenticated
```

## Local Docker smoke (optional)

```bash
docker build -f Dockerfile.api -t banker-api .
docker run --rm -p 8080:8080 \
  -e CRM_API_USER=banker -e CRM_API_PASSWORD=changeme -e CRM_JWT_SECRET=dev \
  banker-api

# after API is up:
docker build -t banker-web \
  --build-arg NEXT_PUBLIC_API_URL=http://host.docker.internal:8080 \
  web/
docker run --rm -p 3000:8080 banker-web
```

## Cost note
Cloud Run scales to zero when idle. A personal desk usually stays in the free
tier if traffic is light. Postgres (Neon free tier / Cloud SQL) is separate.
