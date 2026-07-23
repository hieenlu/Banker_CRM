#!/usr/bin/env bash
# One-time: create a GCP service account + key for GitHub Actions deploys.
# Usage:
#   export GCP_PROJECT_ID=your-project-id
#   ./scripts/setup_gcp_github_deploy.sh
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
SA_NAME="${GCP_DEPLOY_SA:-github-cloudrun-deploy}"
KEY_OUT="${GCP_SA_KEY_OUT:-./gcp-github-sa-key.json}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Set GCP_PROJECT_ID or: gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==> Project ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

# Owner must enable these once (GitHub SA cannot enable APIs until Service Usage Admin is granted).
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com \
  --quiet

if ! gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="GitHub Actions Cloud Run deploy"
fi

for ROLE in \
  roles/run.admin \
  roles/artifactregistry.admin \
  roles/cloudbuild.builds.editor \
  roles/iam.serviceAccountUser \
  roles/storage.admin \
  roles/serviceusage.serviceUsageAdmin
do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet >/dev/null
done

# Cloud Build default SA also needs to push images / deploy if used by builds.
PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
for ROLE in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${CB_SA}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet >/dev/null || true
done

gcloud iam service-accounts keys create "${KEY_OUT}" --iam-account="${SA_EMAIL}"

cat <<EOF

============================================================
Add these GitHub repo secrets (Settings → Secrets and variables → Actions):

  GCP_PROJECT_ID      = ${PROJECT_ID}
  GCP_SA_KEY          = (paste entire contents of ${KEY_OUT})
  CRM_API_USER        = banker
  CRM_API_PASSWORD    = (your strong password)
  CRM_JWT_SECRET      = (openssl rand -hex 32)
  CRM_DB_URL          = (optional Postgres URL)
  CRM_STORAGE_BACKEND = local   # or s3 + CRM_S3_* secrets

Then either:
  • merge to main  → workflow "Deploy Cloud Run" runs automatically
  • or Actions → Deploy Cloud Run → Run workflow  (works from phone)

Delete ${KEY_OUT} after pasting into GitHub.
============================================================
EOF
