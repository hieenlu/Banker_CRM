#!/usr/bin/env bash
# Deploy Banker CRM API + web to Google Cloud Run (iPad-reachable HTTPS).
# Prerequisites:
#   gcloud auth login
#   gcloud config set project YOUR_PROJECT_ID
# Optional:
#   export CRM_DB_URL='postgresql://...'   # Neon / Supabase / Cloud SQL
#   export CRM_API_PASSWORD='strong-password'
#   export CRM_JWT_SECRET='long-random-secret'
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${GCP_REGION:-asia-southeast1}"
REPO="${GCP_ARTIFACT_REPO:-banker-crm}"
API_SERVICE="${GCP_API_SERVICE:-banker-crm-api}"
WEB_SERVICE="${GCP_WEB_SERVICE:-banker-crm-web}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Set GCP_PROJECT_ID or run: gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi

API_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:latest"
WEB_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/web:latest"

echo "==> Project: ${PROJECT_ID}  Region: ${REGION}"

echo "==> Enabling required Google APIs"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project "${PROJECT_ID}"

echo "==> Ensure Artifact Registry repo"
if ! gcloud artifacts repositories describe "${REPO}" \
  --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Banker CRM images" \
    --project="${PROJECT_ID}"
fi

CRM_API_USER="${CRM_API_USER:-banker}"
CRM_API_PASSWORD="${CRM_API_PASSWORD:-changeme}"
CRM_JWT_SECRET="${CRM_JWT_SECRET:-$(openssl rand -hex 24)}"

# Placeholder CORS until web URL is known (JWT uses Authorization header).
PLACEHOLDER_CORS="http://localhost:3000"

build_api_env_file() {
  local cors="$1"
  local file="$2"
  {
    echo "CRM_API_USER: \"${CRM_API_USER}\""
    echo "CRM_API_PASSWORD: \"${CRM_API_PASSWORD}\""
    echo "CRM_JWT_SECRET: \"${CRM_JWT_SECRET}\""
    echo "CRM_STORAGE_BACKEND: \"${CRM_STORAGE_BACKEND:-local}\""
    echo "CRM_LOCAL_STORAGE_PATH: \"/tmp/crm-files\""
    echo "CRM_API_CORS_ORIGINS: \"${cors}\""
    if [[ -n "${CRM_DB_URL:-}" ]]; then
      echo "CRM_DB_URL: \"${CRM_DB_URL}\""
    fi
    for key in CRM_S3_ENDPOINT_URL CRM_S3_REGION CRM_S3_BUCKET \
               CRM_S3_ACCESS_KEY_ID CRM_S3_SECRET_ACCESS_KEY CRM_S3_PREFIX; do
      if [[ -n "${!key:-}" ]]; then
        echo "${key}: \"${!key}\""
      fi
    done
  } >"${file}"
}

ENV_FILE="$(mktemp)"
trap 'rm -f "${ENV_FILE}"' EXIT

echo "==> Build & push API image"
gcloud builds submit "${ROOT}" \
  --project="${PROJECT_ID}" \
  --config="${ROOT}/cloudbuild.api.yaml" \
  --substitutions="_IMAGE=${API_IMAGE}"

build_api_env_file "${PLACEHOLDER_CORS}" "${ENV_FILE}"

echo "==> Deploy API"
gcloud run deploy "${API_SERVICE}" \
  --project="${PROJECT_ID}" \
  --image="${API_IMAGE}" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --env-vars-file="${ENV_FILE}"

API_URL="$(gcloud run services describe "${API_SERVICE}" \
  --project="${PROJECT_ID}" --region="${REGION}" \
  --format='value(status.url)')"
echo "API_URL=${API_URL}"

echo "==> Build & push Web image"
gcloud builds submit "${ROOT}/web" \
  --project="${PROJECT_ID}" \
  --config="${ROOT}/web/cloudbuild.yaml" \
  --substitutions="_IMAGE=${WEB_IMAGE},_API_URL=${API_URL}"

echo "==> Deploy Web"
gcloud run deploy "${WEB_SERVICE}" \
  --project="${PROJECT_ID}" \
  --image="${WEB_IMAGE}" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3

WEB_URL="$(gcloud run services describe "${WEB_SERVICE}" \
  --project="${PROJECT_ID}" --region="${REGION}" \
  --format='value(status.url)')"
echo "WEB_URL=${WEB_URL}"

echo "==> Point API CORS at web origin"
build_api_env_file "${WEB_URL}" "${ENV_FILE}"
gcloud run services update "${API_SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --env-vars-file="${ENV_FILE}"

cat <<EOF

============================================================
Banker CRM is live on Google Cloud Run

  iPad Safari → open:   ${WEB_URL}
  API OpenAPI docs:     ${API_URL}/docs

  Login user:     ${CRM_API_USER}
  Login password: (CRM_API_PASSWORD you exported, default changeme)

Persistence tips:
  export CRM_DB_URL='postgresql://...' before re-running this script
  For durable PDFs/attachments set CRM_STORAGE_BACKEND=s3 and CRM_S3_* vars
============================================================
EOF
