#!/usr/bin/env bash
# Deploy the FourCast demo UI to Google Cloud Run.
# Usage: PROJECT_ID=my-proj FIREWORKS_KEY=fw_xxx [USE_GEMMA=1] ./deploy/deploy-cloudrun.sh
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
: "${FIREWORKS_KEY:?set FIREWORKS_KEY}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-fourcast-demo}"

echo "==> Project: $PROJECT_ID  Region: $REGION  Service: $SERVICE"
gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com >/dev/null

echo "==> Storing Fireworks key in Secret Manager..."
if gcloud secrets describe fourcast-fw-key >/dev/null 2>&1; then
  printf '%s' "$FIREWORKS_KEY" | gcloud secrets versions add fourcast-fw-key --data-file=-
else
  printf '%s' "$FIREWORKS_KEY" | gcloud secrets create fourcast-fw-key --data-file=-
fi

ENV_ARGS=()
[ "${USE_GEMMA:-0}" = "1" ] && ENV_ARGS=(--set-env-vars T2_USE_GEMMA=1)

echo "==> Deploying to Cloud Run (builds from Dockerfile, includes ffmpeg)..."
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 2Gi --cpu 2 --timeout 300 --concurrency 4 \
  --command uvicorn \
  --args "app.main:app,--host,0.0.0.0,--port,8080" \
  --update-secrets "FIREWORKS_API_KEY=fourcast-fw-key:latest" \
  "${ENV_ARGS[@]}"

echo "==> Done. Service URL:"
gcloud run services describe "$SERVICE" --region "$REGION" --format "value(status.url)"
