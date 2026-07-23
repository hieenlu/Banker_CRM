# Deploy to Google Cloud Run (iPad access)

## Goal
Host the Phase 4 web desk + Phase 2/3 API on **Cloud Run** so you can open a
public HTTPS URL from **iPad Safari** (any network, not just home Wi‑Fi).

## What you get
| Service | Cloud Run name | Purpose |
|---|---|---|
| Web | `banker-crm-web` | Next.js UI (open this on iPad) |
| API | `banker-crm-api` | FastAPI + JWT auth |

---

## Update without your Mac (recommended)

After the **one-time** setup below, you never need `./scripts/deploy_cloudrun.sh` on
your laptop again. Updates ship when you:

1. **Merge / push to `main`**, or  
2. On phone/iPad GitHub → **Actions → Deploy Cloud Run → Run workflow**

The iPad sidebar shows a **Build …** stamp (date + git SHA) so you can confirm the new version.

### One-time setup (Mac, ~10 minutes)

```bash
cd ~/Banker_CRM
git checkout cursor/phase4-web-app-a253   # or main after merge
git pull

gcloud auth login
gcloud config set project YOUR_PROJECT_ID

export GCP_PROJECT_ID=YOUR_PROJECT_ID
chmod +x scripts/setup_gcp_github_deploy.sh
./scripts/setup_gcp_github_deploy.sh
```

That creates `gcp-github-sa-key.json`. Then in GitHub → repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `GCP_PROJECT_ID` | your GCP project id |
| `GCP_SA_KEY` | full JSON from `gcp-github-sa-key.json` |
| `CRM_API_USER` | e.g. `banker` |
| `CRM_API_PASSWORD` | strong password |
| `CRM_JWT_SECRET` | `openssl rand -hex 32` |
| `CRM_DB_URL` | optional Postgres URL |
| `CRM_STORAGE_BACKEND` | optional (`local` or `s3`) |
| `CRM_S3_*` | optional if using R2/S3 |

Delete the key file after pasting:

```bash
rm -f gcp-github-sa-key.json
```

### Trigger an update (no Mac)

- **Automatic:** merge the Phase 4 PR (or any later push) into `main`  
- **Manual from phone:** GitHub app → **Actions** → **Deploy Cloud Run** → **Run workflow**

Wait for the green check, open the Cloud Run web URL on iPad, confirm sidebar **Build YYYY-MM-DD-xxxxxxx**.

### Alternative: Cloud Build GitHub trigger (GCP Console)

1. [Cloud Build → Triggers](https://console.cloud.google.com/cloud-build/triggers) → Connect repository  
2. Event: push to `main`  
3. Prefer GitHub Actions above (it builds **both** API and web in one flow)

---

## One-time manual deploy (still useful the first time)

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
```

5. Set a real password + JWT secret:

```bash
export CRM_API_USER=banker
export CRM_API_PASSWORD='pick-a-strong-password'
export CRM_JWT_SECRET="$(openssl rand -hex 32)"
```

## Deploy from Mac (optional after CI is set up)

```bash
export GCP_REGION=asia-southeast1
./scripts/deploy_cloudrun.sh
```

At the end it prints:

```text
iPad Safari → open:   https://banker-crm-web-xxxxx-XX.a.run.app
```

If you use Mac deploys instead of GitHub Actions, re-run the script after each pull.
On iPad Safari, hard-refresh and confirm the sidebar **Build …** stamp changed.

## Optional: durable file storage

```bash
export CRM_STORAGE_BACKEND=s3
export CRM_S3_ENDPOINT_URL='https://<account>.r2.cloudflarestorage.com'
export CRM_S3_REGION=auto
export CRM_S3_BUCKET=banker-crm-files
export CRM_S3_ACCESS_KEY_ID='...'
export CRM_S3_SECRET_ACCESS_KEY='...'
./scripts/deploy_cloudrun.sh
```

(Or set the same values as GitHub Actions secrets.)

## Cost note
Cloud Run scales to zero when idle. GitHub Actions + Cloud Build minutes apply on each auto-deploy.
