<#
.SYNOPSIS
  Deploy the FourCast demo UI to Google Cloud Run.
.EXAMPLE
  ./deploy/deploy-cloudrun.ps1 -ProjectId my-gcp-project -FireworksKey fw_xxx
.EXAMPLE
  ./deploy/deploy-cloudrun.ps1 -ProjectId my-gcp-project -FireworksKey fw_xxx -UseGemma -Region us-central1
#>
param(
  [Parameter(Mandatory = $true)][string]$ProjectId,
  [Parameter(Mandatory = $true)][string]$FireworksKey,
  [string]$Region = "us-central1",
  [string]$Service = "fourcast-demo",
  [switch]$UseGemma
)

$ErrorActionPreference = "Stop"
Write-Host "==> Project: $ProjectId  Region: $Region  Service: $Service" -ForegroundColor Cyan

gcloud config set project $ProjectId | Out-Null
Write-Host "==> Enabling required APIs (idempotent)..." -ForegroundColor Cyan
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com | Out-Null

Write-Host "==> Storing Fireworks key in Secret Manager..." -ForegroundColor Cyan
$exists = gcloud secrets describe fourcast-fw-key 2>$null
if ($LASTEXITCODE -ne 0) {
  $FireworksKey | gcloud secrets create fourcast-fw-key --data-file=-
} else {
  $FireworksKey | gcloud secrets versions add fourcast-fw-key --data-file=-
}

$envArgs = @()
if ($UseGemma) { $envArgs = @("--set-env-vars", "T2_USE_GEMMA=1") }

Write-Host "==> Deploying to Cloud Run (builds from Dockerfile, includes ffmpeg)..." -ForegroundColor Cyan
gcloud run deploy $Service `
  --source . `
  --region $Region `
  --allow-unauthenticated `
  --memory 2Gi --cpu 2 --timeout 300 --concurrency 4 `
  --command uvicorn `
  --args "app.main:app,--host,0.0.0.0,--port,8080" `
  --update-secrets "FIREWORKS_API_KEY=fourcast-fw-key:latest" `
  @envArgs

Write-Host "`n==> Done. Service URL:" -ForegroundColor Green
gcloud run services describe $Service --region $Region --format "value(status.url)"
