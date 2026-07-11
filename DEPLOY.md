# Deploying the FourCast demo

The demo UI is the **same container** as the submission agent, just started with a
different command. It needs `ffmpeg` and 60–240s request times, so it must run on a
**container host**, not a serverless function platform.

## Why Google Cloud Run (and not Vercel)

| Requirement | Cloud Run | Vercel |
| --- | --- | --- |
| Runs `ffmpeg` (native binary) | ✅ full control of the image | ❌ no system binaries |
| Long requests (video → 4 LLM calls, 60–240s) | ✅ up to 3600s | ❌ 10–300s hard caps |
| Deploy an existing Docker image | ✅ first-class | ❌ functions only |
| Scales to zero (no idle cost) | ✅ | ✅ |

**Cloud Run is the right host.** These steps get you a public HTTPS URL in ~3 minutes.

## Prerequisites (once)

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com
```

## One command (recommended: key in Secret Manager)

```bash
# 1) store your Fireworks key as a secret (do this once)
printf 'fw_your_real_key' | gcloud secrets create fourcast-fw-key --data-file=- \
  || printf 'fw_your_real_key' | gcloud secrets versions add fourcast-fw-key --data-file=-

# 2) deploy from source (uses this repo's Dockerfile, so ffmpeg is included)
gcloud run deploy fourcast-demo \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi --cpu 2 --timeout 300 --concurrency 4 \
  --command uvicorn \
  --args app.main:app,--host,0.0.0.0,--port,8080 \
  --update-secrets FIREWORKS_API_KEY=fourcast-fw-key:latest
```

Cloud Run injects `$PORT=8080`; the command binds to it. The printed
`Service URL` is your public demo — paste it into the lablab "Application URL" field.

## Windows helper

From the repo root:

```powershell
./deploy/deploy-cloudrun.ps1 -ProjectId YOUR_PROJECT_ID -FireworksKey fw_your_real_key
```

## Notes

- **Gemma bonus:** add `--set-env-vars T2_USE_GEMMA=1` to the deploy to run the
  Gemma stylist (keeps Kimi vision + gpt-oss judge; GLM 5.2 stays the fallback).
- **Cost:** scales to zero between requests; a demo run costs cents.
- **The submission image is unaffected** — the harness still runs `python -m agent`
  (the Dockerfile default CMD). This deployment only overrides the command for the UI.
